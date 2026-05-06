"""
Geocode HAST addresses to lat/lon via Nominatim (OpenStreetMap).

This version is stricter than the first prototype:
- it queries Wiesentheid with postal code 97353,
- it normalises German street abbreviations such as "Blütenstr." -> "Blütenstraße",
- it prefers exact house-number hits,
- it marks street-only fallbacks clearly in the note field so they are not mistaken for exact coordinates.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd

from . import load_data as ld

CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "geocode_cache.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "uz-mainfranken-heating-network/0.1 (project seminar JMU Wuerzburg)"

# For this project the HAST addresses are in Wiesentheid.
LOCALITIES = (
    "97353 Wiesentheid, Bayern, Germany",
)
LOCALITY = LOCALITIES[0]


@dataclass
class GeocodeResult:
    address: str
    lat: Optional[float]
    lon: Optional[float]
    display_name: Optional[str]
    osm_type: Optional[str]
    importance: Optional[float]
    note: str = ""


# ---------------------------------------------------------------------------
# Address parsing / validation


def _clean_text(value: object) -> str:
    """Normalize strings for robust comparison."""
    s = str(value or "").strip().lower()
    s = s.replace("ß", "ss")
    s = s.replace("straße", "strasse")
    s = s.replace("str.", "strasse")
    s = s.replace("str ", "strasse ")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _normalise_street_name(street: str) -> str:
    """Convert common German street abbreviations to a geocoder-friendly form."""
    s = str(street or "").strip()
    # Blumenstr. -> Blumenstraße, Prichsenstädter Str. -> Prichsenstädter Straße
    s = re.sub(r"(?i)\bstr\.?$", "Straße", s)
    s = re.sub(r"(?i)str\.?$", "straße", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _split_address(address: str) -> tuple[str, str]:
    """Return (street_name, house_number) from strings like 'Blütenstr. 15'."""
    raw = str(address or "").strip()

    # match final house number including suffix/range: 19 a, 7b, 6 - 8
    m = re.search(r"(\d+\s*(?:[-/]\s*\d+)?\s*[a-zA-Z]?)\s*$", raw)
    if not m:
        return _normalise_street_name(raw), ""

    street = _normalise_street_name(raw[:m.start()].strip())
    house = re.sub(r"\s+", "", m.group(1)).lower()
    return street, house


def _house_candidates(house: str) -> set[str]:
    """Generate comparable variants for house numbers."""
    h = re.sub(r"\s+", "", str(house or "").lower())
    if not h:
        return set()

    candidates = {h}

    # 19a -> 19 a and 19
    m = re.fullmatch(r"(\d+)([a-z])", h)
    if m:
        candidates.add(f"{m.group(1)} {m.group(2)}")
        candidates.add(m.group(1))

    # 6-8 -> 6, 8, 6-8
    m = re.fullmatch(r"(\d+)[-/](\d+)", h)
    if m:
        candidates.add(m.group(1))
        candidates.add(m.group(2))

    return {_clean_text(x) for x in candidates}


def _is_exact_house_hit(hit: dict, requested_address: str) -> bool:
    """True if Nominatim returned the requested house number on the right street."""
    street, house = _split_address(requested_address)
    if not street or not house:
        return False

    details = hit.get("address") or {}
    hit_house = details.get("house_number") or details.get("housenumber") or ""
    hit_road = (
        details.get("road")
        or details.get("residential")
        or details.get("pedestrian")
        or details.get("footway")
        or ""
    )

    if not hit_house:
        # Fallback only for rare cases where addressdetails lacks house_number
        # but display_name starts with the number. This is not as reliable.
        display = str(hit.get("display_name") or "")
        hit_house = display.split(",", 1)[0]

    house_ok = _clean_text(hit_house) in _house_candidates(house)

    requested_street_clean = _clean_text(street)
    hit_road_clean = _clean_text(hit_road)
    display_clean = _clean_text(hit.get("display_name"))

    street_ok = (
        requested_street_clean == hit_road_clean
        or requested_street_clean in display_clean
    )

    return bool(house_ok and street_ok)


# ---------------------------------------------------------------------------
# Nominatim requests


def _open_json(url: str) -> list[dict]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _query_nominatim(address: str, locality: str) -> Optional[dict]:
    """Query the bulk OSM data first, then fall back to Nominatim.

    The bulk data is fetched once via Overpass (see osm_addresses.py)
    and gives us a complete (street, housenumber) -> coords index for
    the whole 97353 postcode area. That's far more reliable than
    Nominatim's per-address search, which often returns only a
    street-level fallback.
    """
    street, house = _split_address(address)

    # 0) Bulk OSM data (single Overpass fetch, cached) - try this first.
    if street and house:
        try:
            from .osm_addresses import lookup as _osm_lookup
            osm_hit = _osm_lookup(street, house)
        except Exception:
            osm_hit = None

        if osm_hit is not None:
            # Adapt to Nominatim's response shape so the rest of the
            # pipeline (cache, validate_results, ...) is unchanged.
            return {
                "lat": str(osm_hit["lat"]),
                "lon": str(osm_hit["lon"]),
                "display_name": (
                    f"{osm_hit['street']} {osm_hit['house_number']}, "
                    f"{osm_hit['postcode']} {osm_hit['city']}"
                ).strip(", "),
                "osm_type": osm_hit["osm_type"],
                "osm_id": osm_hit["osm_id"],
                "importance": 1.0,
                "address": {
                    "road": osm_hit["street"],
                    "house_number": osm_hit["house_number"],
                    "postcode": osm_hit["postcode"],
                    "city": osm_hit["city"],
                },
                "_match_quality": "exact_house_number_osm",
            }

    # 1) Structured search: more reliable for address lists than one free text string.
    if street and house:
        params = {
            "street": f"{house} {street}",
            "city": "Wiesentheid",
            "postalcode": "97353",
            "country": "Germany",
            "countrycodes": "de",
            "format": "json",
            "addressdetails": "1",
            "limit": "5",
            "dedupe": "0",
        }
        url = f"{NOMINATIM_URL}?{urlencode(params)}"
        data = _open_json(url)

        for hit in data:
            if _is_exact_house_hit(hit, address):
                hit["_match_quality"] = "exact_house_number"
                return hit

        # Keep a fallback, but clearly mark that it is not house-number exact.
        if data:
            data[0]["_match_quality"] = "street_or_area_fallback_manual_check_required"
            return data[0]

    # 2) Free-form fallback. Useful when parsing failed.
    q = f"{address}, {locality}"
    url = f"{NOMINATIM_URL}?q={quote(q)}&format=json&addressdetails=1&limit=5&countrycodes=de&dedupe=0"
    data = _open_json(url)

    for hit in data:
        if _is_exact_house_hit(hit, address):
            hit["_match_quality"] = "exact_house_number"
            return hit

    if data:
        data[0]["_match_quality"] = "street_or_area_fallback_manual_check_required"
        return data[0]

    return None


def _query_nominatim_multi(address: str,
                           localities: tuple = LOCALITIES,
                           delay: float = 1.0,
                           ) -> tuple[Optional[dict], str]:
    """Try each locality in turn, return the first hit + which locality won."""
    for i, loc in enumerate(localities):
        if i > 0:
            time.sleep(delay)
        try:
            hit = _query_nominatim(address, loc)
            if hit is not None:
                return hit, loc
        except Exception:
            continue
    return None, ""


# ---------------------------------------------------------------------------
# Cache + public functions


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    with CACHE_PATH.open() as f:
        return json.load(f)


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def geocode_addresses(addresses: list[str],
                      localities: tuple = LOCALITIES,
                      delay: float = 1.0,
                      verbose: bool = True) -> dict[str, GeocodeResult]:
    """Geocode a list of addresses; returns a dict keyed by raw address."""
    cache = _load_cache()
    results: dict[str, GeocodeResult] = {}
    new_queries = 0

    for i, addr in enumerate(addresses, 1):
        cached_hit = None
        for key, entry in cache.items():
            # Only reuse cache entries that are *exact* house-number
            # matches (from OSM bulk data or from a confirmed Nominatim
            # exact match). Street-level fallbacks must be re-queried
            # because the bulk OSM data may now have a better hit.
            if key.startswith(f"{addr} || ") and entry.get("lat") is not None:
                note = str(entry.get("note") or "")
                if "exact_house_number" in note:
                    cached_hit = entry
                    break

        if cached_hit is not None:
            results[addr] = GeocodeResult(**cached_hit)
            continue

        try:
            if new_queries > 0:
                time.sleep(delay)
            hit, used_locality = _query_nominatim_multi(addr, localities, delay)
            new_queries += 1
        except Exception as e:
            r = GeocodeResult(addr, None, None, None, None, None,
                              note=f"error: {e}")
            results[addr] = r
            cache[f"{addr} || {localities[0]}"] = asdict(r)
            if verbose:
                print(f"  [{i}/{len(addresses)}] {addr!r}: ERROR {e}")
            continue

        if hit is None:
            r = GeocodeResult(addr, None, None, None, None, None,
                              note="no match in any locality")
            cache_key = f"{addr} || {localities[0]}"
        else:
            quality = hit.get("_match_quality", "unknown_quality")
            r = GeocodeResult(
                address=addr,
                lat=float(hit["lat"]),
                lon=float(hit["lon"]),
                display_name=hit.get("display_name"),
                osm_type=hit.get("osm_type"),
                importance=hit.get("importance"),
                note=f"{quality}; matched via: {used_locality}",
            )
            cache_key = f"{addr} || {used_locality}"

        results[addr] = r
        cache[cache_key] = asdict(r)

        if verbose:
            if r.lat:
                short = used_locality.split(",")[0]
                quality = r.note.split(";", 1)[0]
                print(f"  [{i}/{len(addresses)}] {addr!r}: OK ({quality}, via {short})")
            else:
                print(f"  [{i}/{len(addresses)}] {addr!r}: MISS")

        if new_queries % 10 == 0:
            _save_cache(cache)

    _save_cache(cache)
    if verbose:
        hits = sum(1 for r in results.values() if r.lat is not None)
        exact = sum(1 for r in results.values() if "exact_house_number" in r.note)
        fallback = sum(1 for r in results.values() if "street_or_area_fallback" in r.note)
        print(f"\n  {hits}/{len(results)} addresses geocoded; "
              f"{exact} exact house-number hits, {fallback} street/area fallbacks; "
              f"{new_queries} fresh queries, {len(results)-new_queries} cached")
    return results


def geocode_nodes(nodes_df: Optional[pd.DataFrame] = None,
                  localities: tuple = LOCALITIES) -> pd.DataFrame:
    """Geocode every address in the Nodes sheet, return a joined frame."""
    if nodes_df is None:
        nodes_df = ld.load_logical_nodes()
    addrs = nodes_df["address"].astype(str).str.strip().unique().tolist()
    results = geocode_addresses(addrs, localities=localities)
    geo = pd.DataFrame([asdict(r) for r in results.values()])
    out = nodes_df.merge(geo, left_on="address", right_on="address", how="left")
    return out


def validate_results(geo_df: pd.DataFrame,
                     expected_bounds: tuple = (49.795, 10.338, 49.804, 10.352),
                     ) -> pd.DataFrame:
    """Flag results that fall outside the expected Wiesentheid service area.

    expected_bounds = (min_lat, min_lon, max_lat, max_lon)
    """
    min_lat, min_lon, max_lat, max_lon = expected_bounds
    out = geo_df.copy()
    out["in_expected_area"] = (
        out["lat"].between(min_lat, max_lat)
        & out["lon"].between(min_lon, max_lon)
    )
    return out


# --- CLI -------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plot", action="store_true",
                   help="render an updated map with HAST markers")
    args = p.parse_args()

    print("→ geocoding HAST addresses via Nominatim")
    geo = geocode_nodes()
    geo = validate_results(geo)

    out_csv = Path("data/processed/hast_geocoded.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    geo.to_csv(out_csv, index=False)
    print(f"\n→ wrote {out_csv}")

    n_hit = geo["lat"].notna().sum()
    n_in_area = geo["in_expected_area"].sum()
    n_exact = geo["note"].astype(str).str.contains("exact_house_number", na=False).sum()
    n_fallback = geo["note"].astype(str).str.contains("street_or_area_fallback", na=False).sum()

    print(f"   {n_hit}/{len(geo)} matched")
    print(f"   {n_in_area}/{n_hit} fall inside the expected Wiesentheid bbox")
    print(f"   {n_exact} exact house-number matches")
    print(f"   {n_fallback} street/area fallbacks that need manual checking")

    if n_fallback:
        print("\n   Street/area fallbacks:")
        cols = ["address", "display_name", "note"]
        print(geo[geo["note"].astype(str).str.contains("street_or_area_fallback", na=False)][cols]
              .drop_duplicates("address")
              .to_string(index=False))

    if args.plot:
        from .visualize import make_folium_map, find_main_cluster
        import folium
        from shapely.geometry import MultiLineString

        pipes = ld.load_pipes()
        points = ld.load_gis_points()
        bounds = find_main_cluster(pipes)
        out_html = Path("outputs/network_map_with_hast.html")
        make_folium_map(pipes, points, out_html, bounds=bounds)

        pipes_in_bounds = pipes.cx[bounds[0]:bounds[2], bounds[1]:bounds[3]]
        pipes_wgs = pipes_in_bounds.to_crs("EPSG:4326")
        bbox = pipes_wgs.total_bounds
        cy, cx = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
        m = folium.Map(location=[cy, cx], zoom_start=16, tiles="OpenStreetMap")

        for _, row in pipes_wgs.iterrows():
            g = row.geometry
            if g is None or g.is_empty:
                continue
            parts = list(g.geoms) if isinstance(g, MultiLineString) else [g]
            for part in parts:
                folium.PolyLine([(y, x) for x, y in part.coords],
                                color="#888", weight=2, opacity=0.6).add_to(m)

        hits = geo[geo["lat"].notna() & geo["in_expected_area"]]
        for _, row in hits.iterrows():
            exact = "exact_house_number" in str(row.get("note", ""))
            color = "#1f77b4" if exact else "#ff7f0e"
            tip = (f"{row['address']}<br/>"
                   f"Anschlusswert: {row.get('Anschlusswert','?')} kW<br/>"
                   f"Zählernr: {row.get('Zählernummer','?')}<br/>"
                   f"{row.get('note','')}")
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=6, color="white", weight=1.5, fill=True,
                fill_color=color, fill_opacity=0.9,
                tooltip=tip,
            ).add_to(m)

        m.save(str(out_html))
        print(f"→ wrote {out_html}  ({len(hits)} HAST marked)")
