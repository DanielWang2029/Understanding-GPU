#!/usr/bin/env python3
"""Geocode Epoch AI data-center addresses into a committed cache.

Epoch's public CSV gives a free-text `Address` but no coordinates, so the map
needs a geocoding pass. Results are cached in
`data/sources/geocode_cache.json` and committed, which keeps the map build
offline-reproducible and stops us hammering Nominatim on every run.

    python3 scripts/geocode_sites.py           # fill in anything missing
    python3 scripts/geocode_sites.py --force   # re-geocode everything

Nominatim usage policy: max 1 request/second, identifying User-Agent.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
EPOCH = ROOT / "data" / "sources" / "epoch_ai" / "data_centers.csv"
CACHE = ROOT / "data" / "sources" / "geocode_cache.json"

UA = "understanding-gpu-compute-map/1.0 (+https://github.com/DanielWang2029/Understanding-GPU)"
ENDPOINT = "https://nominatim.openstreetmap.org/search"

# Addresses Epoch leaves blank, plus the ones where a naive geocode lands in the
# wrong place. Each entry says what to search instead and how precise the answer
# can possibly be. Nothing here invents a coordinate: the fallback is always a
# real administrative place named in Epoch's own record.
FALLBACKS = {
    "OpenAI Stargate New Mexico": ("Santa Teresa, Dona Ana County, New Mexico, USA", "city"),
    "OpenAI Stargate Wisconsin": ("Port Washington, Ozaukee County, Wisconsin, USA", "city"),
    "OpenAI Stargate Milam": ("Milam County, Texas, USA", "county"),
    "OpenAI Stargate Lordstown": ("2300 Hallock Young Rd, Warren, Ohio, USA", "street"),
    "QTS Richmond 2": ("6030 Technology Blvd, Sandston, Virginia, USA", "street"),
    "QTS Richmond 3": ("3525 Portugee Rd, Sandston, Virginia, USA", "street"),
    # Naive "Lenoir NC" resolves to Lenoir County on the coast, 300 km from the
    # Google campus in the city of Lenoir, Caldwell County.
    "Google Lenoir": ("Lenoir, Caldwell County, North Carolina, USA", "city"),
}


def query(text: str) -> dict | None:
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'format': 'json', 'limit': 1, 'q': text})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as exc:  # network failures must not break the build
        print(f"    ! request failed: {exc}")
        return None
    if not payload:
        return None
    hit = payload[0]
    return {
        "lat": float(hit["lat"]),
        "lon": float(hit["lon"]),
        "matched": hit.get("display_name", ""),
        "osm_type": hit.get("osm_type", ""),
        "place_rank": hit.get("place_rank"),
    }


def precision_from_rank(rank: int | None, hinted: str | None) -> str:
    if hinted:
        return hinted
    if rank is None:
        return "unknown"
    if rank >= 30:
        return "building"
    if rank >= 26:
        return "street"
    if rank >= 16:
        return "city"
    return "region"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.15)
    args = ap.parse_args()

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    rows = list(csv.DictReader(EPOCH.open()))
    print(f"{len(rows)} Epoch sites; {len(cache)} already cached")

    resolved = 0
    for row in rows:
        name = row["Name"].strip()
        if not args.force and name in cache and cache[name].get("lat") is not None:
            continue
        address = (row.get("Address") or "").strip()
        hint = None
        if name in FALLBACKS:
            address, hint = FALLBACKS[name]
        if not address:
            country = (row.get("Country") or "").strip()
            if not country:
                cache[name] = {"lat": None, "lon": None, "precision": "none",
                               "query": "", "matched": "", "note": "no address published"}
                continue
            address, hint = country, "country"

        print(f"  geocoding {name!r} -> {address!r}")
        hit = query(address)
        time.sleep(args.sleep)
        if hit is None and "," in address:
            # Retry with a coarser query: drop the street line.
            coarse = address.split(",", 1)[1].strip()
            print(f"    retry coarse -> {coarse!r}")
            hit = query(coarse)
            hint = hint or "city"
            time.sleep(args.sleep)
        if hit is None:
            cache[name] = {"lat": None, "lon": None, "precision": "none",
                           "query": address, "matched": "", "note": "geocoder returned no match"}
            continue
        cache[name] = {
            "lat": hit["lat"],
            "lon": hit["lon"],
            "precision": precision_from_rank(hit["place_rank"], hint),
            "query": address,
            "matched": hit["matched"],
            "source": "OpenStreetMap Nominatim (ODbL)",
        }
        resolved += 1

    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    got = sum(1 for v in cache.values() if v.get("lat") is not None)
    print(f"resolved {resolved} this run; cache now holds {got}/{len(cache)} with coordinates")
    print(f"wrote {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
