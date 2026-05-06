"""
Generate stub geocode coordinates for offline / sandbox testing.

WHEN TO USE THIS: only when Nominatim is unreachable (e.g. running in
a sandbox without internet). Locally on your machine, run
`python -m src.geocode` instead - that uses real Nominatim and produces
genuinely correct coordinates. Once you have a real cache, delete this
script's output and never look at it again.

Strategy: use the main spatial cluster's bounding box and place each
HAST address at a deterministic position derived from a hash of its
street + number. This produces coordinates that:
  * are inside the right village (correct cluster bbox)
  * are stable across runs (same address -> same point)
  * spread out enough to be visually separable on a map

These are NOT real coordinates. They exist purely so you can render a
test map and verify the visualisation pipeline works.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from . import load_data as ld
from .geocode import GeocodeResult, CACHE_PATH, LOCALITY
from .visualize import find_main_cluster

from pyproj import Transformer


def make_stub_cache(seed: str = "stub") -> int:
    """Write stub coordinates into the geocode cache.

    Only fills entries that aren't already in the cache - real geocode
    results are never overwritten.
    """
    nodes = ld.load_logical_nodes()
    pipes = ld.load_pipes()
    bounds = find_main_cluster(pipes)  # in UTM 32N
    minx, miny, maxx, maxy = bounds

    # Project to lat/lon
    t = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
    sw_lon, sw_lat = t.transform(minx, miny)
    ne_lon, ne_lat = t.transform(maxx, maxy)

    cache = {}
    if CACHE_PATH.exists():
        with CACHE_PATH.open() as f:
            cache = json.load(f)

    written = 0
    for addr in nodes["address"].astype(str).str.strip().unique():
        cache_key = f"{addr} || {LOCALITY}"
        if cache_key in cache and cache[cache_key].get("lat"):
            continue  # already have a real result, leave it alone

        # Hash address -> two unit values, scale into bbox
        h = hashlib.sha256(f"{seed}:{addr}".encode()).digest()
        u1 = int.from_bytes(h[:8], "big") / 2**64
        u2 = int.from_bytes(h[8:16], "big") / 2**64
        lon = sw_lon + (ne_lon - sw_lon) * u1
        lat = sw_lat + (ne_lat - sw_lat) * u2

        r = GeocodeResult(
            address=addr,
            lat=round(lat, 6),
            lon=round(lon, 6),
            display_name=f"[STUB] {addr}, {LOCALITY}",
            osm_type="stub",
            importance=0.0,
            note="STUB - replace with real Nominatim run",
        )
        cache[cache_key] = asdict(r)
        written += 1

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    return written


if __name__ == "__main__":
    n = make_stub_cache()
    print(f"wrote {n} stub coordinates to {CACHE_PATH}")
    print("THESE ARE NOT REAL COORDINATES - run 'python -m src.geocode' "
          "locally to replace with real Nominatim results")
