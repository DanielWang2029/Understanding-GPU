"""The document layer: the individual URLs cited by records.

A source is where data comes from; a document is one piece of evidence inside
it. The atlas search tab is a search over documents, and each document carries
the recognition results of every record that cited it, so "why is this entity
attached to this link" always has an answer.
"""

from __future__ import annotations

import re

from .recognize import (DOC_KINDS, GENERIC_HOSTS, PUBLISHERS, Recognizer,  # noqa: F401
                        document_kind, host_of)

TITLE_JUNK = re.compile(r"\.(html?|php|aspx?|pdf|csv|json|xml)$", re.I)
ACRONYMS = {"ai", "gpu", "tpu", "hbm", "cowos", "nvl72", "mw", "gw", "us", "uk", "uae",
            "hpc", "llm", "sec", "eu", "b200", "b300", "h100", "h200", "gb200", "gb300",
            "mi300x", "mi355x", "trn1", "trn2", "iso", "pue", "ercot", "tva", "qts"}


def canonical_url(url: str) -> str:
    u = (url or "").strip().rstrip("/.,)")
    u = re.sub(r"^http://", "https://", u)
    u = re.sub(r"^https://www\.", "https://", u)
    return re.sub(r"[?#].*$", "", u)


def title_from_url(url: str) -> str:
    """A readable headline from the URL itself. Most cited links in these
    datasets are bare, so this is the honest thing to show."""
    path = re.sub(r"^https://[^/]+", "", url).strip("/")
    if not path:
        return ""
    for seg in reversed([p for p in path.split("/") if p]):
        seg = TITLE_JUNK.sub("", seg)
        words = [w for w in re.split(r"[-_+]", seg) if w]
        alpha = [w for w in words if re.search(r"[a-z]{3}", w, re.I)]
        if len(alpha) >= 3 or (len(alpha) >= 2 and len(seg) > 14):
            out = []
            for w in words:
                if w.lower() in ACRONYMS:
                    out.append(w.upper())
                elif re.fullmatch(r"\d{4,}", w):
                    continue
                else:
                    out.append(w.capitalize() if w.islower() else w)
            text = " ".join(out).strip()
            if len(text) > 4:
                return text[:120]
    return ""


def collect(records: list[dict], store, catalog: dict) -> list[dict]:
    """Fold every record's cited URLs into a deduplicated document list."""
    docs: dict[str, dict] = {}
    names = {eid: e["name"] for eid, e in store.entities.items()}

    for record in records:
        for raw in record.get("documents") or []:
            url = canonical_url(raw)
            if not url.startswith("https://"):
                continue
            doc = docs.get(url)
            if not doc:
                host = host_of(url)
                pub_entity = None if host in GENERIC_HOSTS else store.recognizer.match_host(host)
                doc = {
                    "id": "doc-%06d" % (len(docs) + 1),
                    "url": url,
                    "host": host,
                    "publisher": (GENERIC_HOSTS.get(host) or PUBLISHERS.get(host)
                                  or names.get(pub_entity or "", host)),
                    "publisher_entity": pub_entity or "",
                    "kind": document_kind(url, pub_entity or ""),
                    "title": title_from_url(url),
                    "date": record.get("date") or "",
                    "sources": set(),
                    "record_ids": [],
                    "attached_to": [],
                    "contexts": [],
                    "claims": [],
                    "recognition": {},
                }
                docs[url] = doc

            doc["sources"].add(record["source"])
            if len(doc["record_ids"]) < 40:
                doc["record_ids"].append(record["id"])
            if record.get("date") and not doc["date"]:
                doc["date"] = record["date"]
            subject = record.get("subject")
            label = names.get(subject) if subject else (record.get("subject_hint") or "")
            if label and label not in doc["attached_to"]:
                doc["attached_to"].append(label)
            ctx = (record.get("context") or "").strip()
            if ctx and ctx not in doc["contexts"]:
                doc["contexts"].append(ctx[:400])
            if record["claims"] and len(doc["claims"]) < 3:
                keep = {k: v for k, v in record["claims"].items()
                        if v not in (None, "", [], {})}
                if keep and keep not in doc["claims"]:
                    doc["claims"].append(keep)
            for hit in record.get("entities") or []:
                slot = doc["recognition"].setdefault(
                    hit["entity"], {"score": 0.0, "methods": {}})
                for m in hit["methods"]:
                    if m["method"] not in slot["methods"]:
                        slot["methods"][m["method"]] = m["span"]
                slot["score"] = max(slot["score"], hit["score"])

    out = []
    for doc in sorted(docs.values(), key=lambda d: (-len(d["recognition"]), d["url"])):
        recognition = [
            {"entity": eid, "score": round(info["score"], 2),
             "methods": [{"method": m, "span": s} for m, s in info["methods"].items()]}
            for eid, info in sorted(doc["recognition"].items(), key=lambda kv: -kv[1]["score"])
            if eid in store.entities
        ]
        out.append({
            "id": doc["id"], "url": doc["url"], "host": doc["host"],
            "publisher": doc["publisher"], "publisher_entity": doc["publisher_entity"],
            "kind": doc["kind"], "title": doc["title"], "date": doc["date"],
            "sources": sorted(doc["sources"]),
            "attached_to": doc["attached_to"][:4],
            "contexts": doc["contexts"][:3],
            "claims": doc["claims"][:3],
            "records": doc["record_ids"][:6],
            "entities": recognition,
        })
    return out
