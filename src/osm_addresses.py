"""
Bulk-fetch OSM address data for the service area via the Overpass API.

Why this exists in addition to Nominatim:
    Nominatim's structured search frequently fails to find specific
    house numbers in Wiesentheid - it returns only a street-level
    "fallback" match. Pulling the full address list directly via the
    Overpass API bypasses Nominatim's search heuristics and gives us
    every (street, housenumber) -> (lat, lon) pair OSM has.

Run once locally:

    python -m src.osm_addresses               # fetches and caches
    python -m src.osm_addresses --no-fetch    # just read existing cache

The cache (`data/processed/osm_addresses.json`) is safe to commit -
it's public OSM data with no PII, and it lets your colleagues skip
the Overpass query entirely.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "uz-mainfranken-heating-network/0.1 (project seminar JMU Wuerzburg)"

OSM_CACHE = (Path(__file__).resolve().parents[1]
             / "data" / "processed" / "osm_addresses.json")

# Postcode 97353 covers Wiesentheid + adjacent Gemeindeteile, which is
# exactly the residential cluster the heating network serves.
DEFAULT_POSTCODES = ("97353",)


# --- Overpass query ------------------------------------------------------

def _build_overpass_query(postcodes: tuple = DEFAULT_POSTCODES) -> str:
    """Return Overpass QL for all addresses in the given postcodes.

    Strategy: resolve each postcode to its OSM area (a polygon), then
    select every node/way/relation with addr:housenumber + addr:street
    inside that area. The area lookup is more robust than matching
    addr:postcode tags directly, since some OSM elements omit the
    postcode tag (the postcode is implied by their location).
    """
    parts = []
    for i, pc in enumerate(postcodes):
        parts.append(f'area[postal_code="{pc}"]->.pc{i};')
    area_block = "\n  ".join(parts)

    in_blocks = []
    for i in range(len(postcodes)):
        in_blocks.append(
            f'  node["addr:housenumber"]["addr:street"](area.pc{i});\n'
            f'  way["addr:housenumber"]["addr:street"](area.pc{i});\n'
            f'  relation["addr:housenumber"]["addr:street"](area.pc{i});'
        )
    in_block = "\n".join(in_blocks)

    return (
        "[out:json][timeout:60];\n"
        f"  {area_block}\n"
        "(\n"
        f"{in_block}\n"
        ");\n"
        "out center;\n"
    )


def fetch_osm_addresses(postcodes: tuple = DEFAULT_POSTCODES) -> list[dict]:
    """Run one Overpass query and parse the result into a list of dicts.

    Raises RuntimeError if Overpass returns no elements. This is almost
    always a query problem, not a real "no addresses" answer - we don't
    want to silently overwrite a valid cache with an empty file.
    """
    query = _build_overpass_query(postcodes)
    payload = urlencode({"data": query}).encode("utf-8")
    req = Request(OVERPASS_URL, data=payload,
                  headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=120) as r:
        result = json.loads(r.read().decode("utf-8"))

    elements = result.get("elements", [])
    if not elements:
        raise RuntimeError(
            "Overpass returned 0 elements. Likely causes:\n"
            "  - the postal_code area is unknown to Overpass right now\n"
            "    (try again in a few minutes - their area cache rebuilds nightly)\n"
            "  - the wrong postcode was passed (current: "
            + ", ".join(postcodes) + ")\n"
            "  - Overpass is overloaded; try https://overpass.kumi.systems/api/interpreter\n"
            "Run with --debug to see the full query."
        )

    addresses = []
    for el in elements:
        tags = el.get("tags") or {}
        street = (tags.get("addr:street") or "").strip()
        house = (tags.get("addr:housenumber") or "").strip()
        if not street or not house:
            continue

        if el.get("type") == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue

        addresses.append({
            "street": street,
            "house_number": house,
            "postcode": (tags.get("addr:postcode") or "").strip(),
            "city": (tags.get("addr:city") or "").strip(),
            "lat": float(lat),
            "lon": float(lon),
            "osm_type": el.get("type"),
            "osm_id": el.get("id"),
        })
    return addresses


def fetch_and_cache(postcodes: tuple = DEFAULT_POSTCODES,
                    verbose: bool = True) -> list[dict]:
    """Fetch addresses and write them to OSM_CACHE."""
    if verbose:
        print(f"  querying Overpass for postcodes {postcodes} (~30 s)")
    addresses = fetch_osm_addresses(postcodes)
    OSM_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with OSM_CACHE.open("w", encoding="utf-8") as f:
        json.dump(addresses, f, indent=2, ensure_ascii=False)
    if verbose:
        print(f"  cached {len(addresses)} addresses -> {OSM_CACHE}")
    return addresses


def load_addresses(auto_fetch: bool = True) -> list[dict]:
    """Load cached OSM addresses, optionally fetching if cache is missing."""
    if OSM_CACHE.exists():
        with OSM_CACHE.open(encoding="utf-8") as f:
            return json.load(f)
    if not auto_fetch:
        return []
    return fetch_and_cache()


# --- Local lookup --------------------------------------------------------

def _normalise_street(s: str) -> str:
    """All variants of 'Blütenstraße' / 'Blütenstr.' / 'bluetenstrasse' fold here."""
    if not s:
        return ""
    s = s.lower().strip()
    s = s.replace("ß", "ss")
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = re.sub(r"\.", "", s)
    s = re.sub(r"str(asse)?\b", "strasse", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 \-]", "", s)
    return s.strip()


def _normalise_housenumber(h: str) -> str:
    """Lowercase, strip whitespace, keep digits + suffix letter + range."""
    h = str(h or "").lower().strip()
    h = re.sub(r"\s+", "", h)             # "19 a" -> "19a"
    h = re.sub(r"\s*-\s*", "-", h)        # "6 - 8" -> "6-8"
    return h


def build_index(addresses: list[dict]) -> dict[tuple, dict]:
    """Build a (street_norm, housenumber_norm) -> address lookup.

    When multiple OSM elements share the same address (e.g. node + way),
    we keep the way/relation since those carry the building footprint
    and tend to have more accurate centroids.
    """
    index: dict[tuple, dict] = {}
    for a in addresses:
        key = (_normalise_street(a["street"]),
               _normalise_housenumber(a["house_number"]))
        existing = index.get(key)
        if existing is None or (existing["osm_type"] == "node"
                                and a["osm_type"] != "node"):
            index[key] = a
    return index


def _house_variants(house: str) -> list[str]:
    """Generate house-number variants to try in order of preference."""
    h = _normalise_housenumber(house)
    out = [h]

    # "19a" -> also try "19 a", "19"
    m = re.fullmatch(r"(\d+)([a-z])", h)
    if m:
        out.extend([f"{m.group(1)} {m.group(2)}", m.group(1)])

    # "6-8" -> try "6", "8" too (range -> first/last)
    m = re.fullmatch(r"(\d+)-(\d+)", h)
    if m:
        out.extend([m.group(1), m.group(2)])

    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def lookup(street: str, house_number: str,
           addresses: Optional[list[dict]] = None) -> Optional[dict]:
    """Look up a single address in the cached OSM data.

    Returns the matching record or None. Tries several house-number
    variants ('19a' / '19 a' / '19') before giving up.
    """
    if addresses is None:
        addresses = load_addresses(auto_fetch=False)
    if not addresses:
        return None
    index = build_index(addresses)
    street_n = _normalise_street(street)
    for variant in _house_variants(house_number):
        hit = index.get((street_n, variant))
        if hit is not None:
            return hit
    return None


# --- CLI -----------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-fetch", action="store_true",
                   help="don't query Overpass; just read the existing cache")
    p.add_argument("--postcode", action="append", default=None,
                   help="add another postcode to fetch (repeatable)")
    p.add_argument("--debug", action="store_true",
                   help="print the Overpass query before running it")
    args = p.parse_args()

    pcs = tuple(args.postcode) if args.postcode else DEFAULT_POSTCODES

    if args.debug:
        print("Overpass query:")
        print(_build_overpass_query(pcs))
        print()

    if args.no_fetch:
        addrs = load_addresses(auto_fetch=False)
        print(f"loaded {len(addrs)} cached addresses")
    else:
        addrs = fetch_and_cache(pcs)

    if addrs:
        print("\nsample (first 10):")
        for a in addrs[:10]:
            print(f"  {a['street']:<28} {a['house_number']:<6}  "
                  f"({a['lat']:.5f}, {a['lon']:.5f})")
        streets = sorted({_normalise_street(a['street']) for a in addrs})
        print(f"\n{len(streets)} distinct streets in cache")
