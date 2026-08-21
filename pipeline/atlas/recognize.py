"""Stage 3 — recognition: attach entity references to every record.

One pass, four evidence channels, applied to every record from every source in
the same way:

    field   a record claim names an entity (operator, tenant, country, chip)
    domain  an evidencing document's host belongs to an entity
    path    an entity alias appears in a document's URL path
    text    an entity alias appears in the record's context or subject name

Each hit keeps the method, the matched span and a score from
`schema.METHOD_SCORE`; scores add across channels, and anything at or above
`schema.RECOGNITION_MIN_SCORE` is kept. The output is per-record, so the same
machinery serves the UI's "how was this recognised" panel and the fill stage's
provenance.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from . import schema

# Aliases that would fire on almost any page and are never evidence alone.
STOP_ALIASES = {
    "meta", "oci", "gcp", "aws", "amd", "arm", "hbm", "dc", "ai", "gpu", "tpu",
    "x.ai", "q.com", "one", "two", "data", "center", "cloud", "power", "site",
}

# Hosts that carry no entity evidence: a file locker, archive or social post
# says nothing about which company a document concerns.
GENERIC_HOSTS = {
    "drive.google.com": "Google Drive (scan)",
    "docs.google.com": "Google Docs (scan)",
    "storage.googleapis.com": "Google Storage (file)",
    "web.archive.org": "Internet Archive",
    "archive.org": "Internet Archive",
    "x.com": "X / Twitter",
    "twitter.com": "X / Twitter",
    "youtube.com": "YouTube",
    "linkedin.com": "LinkedIn",
    "scribd.com": "Scribd",
    "medium.com": "Medium",
    "substack.com": "Substack",
    "wikipedia.org": "Wikipedia",
    "baike.baidu.com": "Baidu Baike",
}

# Claim keys whose values name another entity, and the type to look for.
FIELD_CHANNELS = {
    "operator": "company",
    "tenant": "company",
    "provider": "company",
    "vendor": "company",
    "owner": "company",
    "user": "company",
    "org": "company",
    "country": "country",
    "chip": "accelerator",
    "chip_type": "accelerator",
    "platform": "accelerator",
    "hardware": "accelerator",
    "accelerator_label": "accelerator",
    "item": "component",
    "system": None,
    "accelerator_families": None,
    "accelerators": None,
}


def norm(text) -> str:
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def host_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return re.sub(r"^www\.", "", m.group(1).lower()) if m else ""


class Recognizer:
    """An alias index over the resolved entities, plus the four channels."""

    def __init__(self):
        self.alias_map: dict[str, str] = {}
        self.domain_map: dict[str, str] = {}
        self.type_of: dict[str, str] = {}
        self.max_ngram = 1
        self._cache: dict[str, list] = {}

    # ---------------------------------------------------------------- indexing
    def add_entity(self, entity_id: str, etype: str, names, domains=()):
        self.type_of[entity_id] = etype
        for name in names:
            a = norm(name)
            if len(a) < 3 or a in STOP_ALIASES:
                continue
            self.max_ngram = max(self.max_ngram, min(6, len(a.split())))
            self.alias_map.setdefault(a, entity_id)
        for d in domains:
            self.domain_map[d.lower()] = entity_id
        self._cache.clear()

    # ---------------------------------------------------------------- matching
    def match_text(self, text: str, want_type: str | None = None) -> list[tuple[str, str]]:
        """Longest-alias-wins n-gram lookup. One hit per entity."""
        t = norm(text)
        if not t:
            return []
        key = (t, want_type or "")
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        tokens = re.findall(r"[a-z0-9.+]+", t)
        out, seen, used = [], set(), set()
        for n in range(min(self.max_ngram, len(tokens)), 0, -1):
            for i in range(len(tokens) - n + 1):
                if any((i + k) in used for k in range(n)):
                    continue
                gram = " ".join(tokens[i:i + n])
                eid = self.alias_map.get(gram)
                if not eid or eid in seen:
                    continue
                if want_type and self.type_of.get(eid) != want_type:
                    continue
                out.append((eid, gram))
                seen.add(eid)
                used.update(range(i, i + n))
        if len(self._cache) < 80000:
            self._cache[key] = out
        return out

    def match_host(self, host: str) -> str | None:
        if not host or host in GENERIC_HOSTS:
            return None
        if host in self.domain_map:
            return self.domain_map[host]
        for d, eid in self.domain_map.items():
            if host == d or host.endswith("." + d):
                return eid
        return None

    # ---------------------------------------------------------------- the pass
    def recognise(self, record: dict) -> list[dict]:
        hits: dict[str, dict] = {}

        def note(eid: str, method: str, span: str):
            if not eid:
                return
            slot = hits.setdefault(eid, {"entity": eid, "score": 0.0, "methods": []})
            if any(m["method"] == method for m in slot["methods"]):
                return
            slot["methods"].append({"method": method, "span": str(span)[:80]})
            slot["score"] = round(slot["score"] + schema.METHOD_SCORE[method], 2)

        # 1. the subject itself
        if record.get("subject"):
            note(record["subject"], "field", record.get("subject_hint") or record["subject"])
        elif record.get("subject_hint"):
            for eid, span in self.match_text(record["subject_hint"],
                                             record.get("subject_type") or None):
                note(eid, "field", span)

        # 2. claim fields that name entities
        for key, value in (record.get("claims") or {}).items():
            want = FIELD_CHANNELS.get(key, "__skip__")
            if want == "__skip__":
                continue
            values = value if isinstance(value, list) else [value]
            for v in values:
                if not isinstance(v, (str, int, float)):
                    continue
                for eid, span in self.match_text(str(v), want):
                    note(eid, "field", span)

        # 3 and 4. evidencing documents, then free text
        for url in record.get("documents") or []:
            note(self.match_host(host_of(url)), "domain", host_of(url))
            path = re.sub(r"^https?://[^/]+", "", url)
            if path:
                for eid, span in self.match_text(re.sub(r"[-_/.]+", " ", path)):
                    note(eid, "path", span)
        for text in (record.get("context"), record.get("subject_hint")):
            for eid, span in self.match_text(text or ""):
                note(eid, "text", span)

        kept = [h for h in hits.values() if h["score"] >= schema.RECOGNITION_MIN_SCORE]
        kept.sort(key=lambda h: -h["score"])
        return kept


def publisher_label(url: str, recognizer: Recognizer, entity_names: dict) -> tuple[str, str]:
    """(display publisher, entity id or '') for a document URL."""
    host = host_of(url)
    if host in GENERIC_HOSTS:
        return GENERIC_HOSTS[host], ""
    eid = recognizer.match_host(host)
    if eid:
        return entity_names.get(eid, host), eid
    return PUBLISHERS.get(host, host), ""


PUBLISHERS = {
    "datacenterdynamics.com": "DataCenterDynamics",
    "datacenterfrontier.com": "Data Center Frontier",
    "datacenterknowledge.com": "Data Center Knowledge",
    "datacenters.com": "DataCenters.com",
    "datacentermap.com": "Data Center Map",
    "baxtel.com": "Baxtel",
    "ocolo.io": "oColo",
    "peeringdb.com": "PeeringDB",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "wsj.com": "Wall Street Journal",
    "ft.com": "Financial Times",
    "nytimes.com": "New York Times",
    "theinformation.com": "The Information",
    "tomshardware.com": "Tom's Hardware",
    "theregister.com": "The Register",
    "arxiv.org": "arXiv",
    "sec.gov": "SEC EDGAR",
    "comptroller.texas.gov": "Texas Comptroller",
    "tdlr.texas.gov": "Texas TDLR",
    "chipsandcheese.com": "Chips and Cheese",
    "servethehome.com": "ServeTheHome",
    "businesswire.com": "Business Wire",
    "prnewswire.com": "PR Newswire",
    "globenewswire.com": "GlobeNewswire",
    "epoch.ai": "Epoch AI",
    "mlcommons.org": "MLCommons",
    "eurohpc-ju.europa.eu": "EuroHPC JU",
}

DOC_KINDS = [
    (("sec.gov", "investors.", "investor."), "filing"),
    (("arxiv.org", "jmlr.org", "dl.acm.org", "doi.org", "proceedings."), "paper"),
    (("peeringdb.com", "datacenters.com", "datacentermap.com", "baxtel.com",
      "ocolo.io", "databank.com"), "registry"),
    ((".gov", "europa.eu", "eurohpc"), "government"),
    (("prices.azure.com", "instances.vantage.sh", "/pricing"), "pricing"),
    (("epoch.ai", "mlcommons.org"), "dataset"),
]


def document_kind(url: str, publisher_entity: str) -> str:
    low = (url or "").lower()
    for hints, kind in DOC_KINDS:
        if any(h in low for h in hints):
            return kind
    return "vendor" if publisher_entity else "news"
