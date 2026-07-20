"""
Snapping: geocodete HAST-Stationen an den naechstgelegenen Knoten des
raeumlichen Graphen (Rohrgeometrie) zuordnen.

Der raeumliche Graph (build_graph.build_spatial_graph, unveraendert)
liegt in ETRS89 / UTM 32N (EPSG:25832); die geocodeten Stationen in
WGS84. Wir transformieren die Stationen nach UTM und suchen den
naechsten Rohrknoten per KD-Tree. Die Distanz in Metern ist das
zentrale EHRLICHKEITS-MASS: fast alle Koordinaten stammen aus
Strassenmittelpunkt-Fallbacks (OSM-Hausnummernluecke), d.h. eine kleine
Snapping-Distanz beweist keine korrekte Zuordnung - aber eine grosse
Distanz beweist, dass die Verortung am Netz NICHT verlaesslich ist.

Output: data/processed/hast_snapped.csv
(Zaehlernummer, Koordinaten, zugeordneter Rohrknoten in UTM und WGS84,
snap_dist_m, snap_verlaesslich)

    python -m src.snap_hast
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# Stationen, deren naechster Rohrknoten weiter entfernt ist, gelten als
# nicht verlaesslich am Netz verortet (Geocoding-Unsicherheit dominiert
# dann die Zuordnung). Startwert; ggf. mit UEZ-Koordinaten obsolet.
SNAP_MAX_DIST_M = 50.0


def snap_stations(geocoded_csv: Path = PROCESSED / "hast_geocoded.csv",
                  ) -> pd.DataFrame:
    """Naechster Rohrknoten je Station mit Koordinaten."""
    if not geocoded_csv.exists():
        raise FileNotFoundError(
            f"{geocoded_csv} fehlt - erzeugen mit: python -m src.main --geocode")
    geo = pd.read_csv(geocoded_csv)
    geo = geo[geo["lat"].notna() & geo["lon"].notna()].copy()
    if geo.empty:
        raise ValueError(f"{geocoded_csv} enthaelt keine Koordinaten")

    from pyproj import Transformer
    from scipy.spatial import cKDTree

    from .build_graph import build_spatial_graph

    g = build_spatial_graph()  # Knoten sind (x, y) in EPSG:25832
    nodes = np.array(list(g.nodes))

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
    sx, sy = to_utm.transform(geo["lon"].values, geo["lat"].values)

    dist, idx = cKDTree(nodes).query(np.column_stack([sx, sy]))
    node_xy = nodes[idx]

    to_wgs = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
    node_lon, node_lat = to_wgs.transform(node_xy[:, 0], node_xy[:, 1])

    out = geo[["Zählernummer", "address", "lat", "lon"]].copy()
    out["node_x"] = node_xy[:, 0].round(2)
    out["node_y"] = node_xy[:, 1].round(2)
    out["node_lat"] = node_lat.round(7)
    out["node_lon"] = node_lon.round(7)
    out["snap_dist_m"] = dist.round(1)
    out["snap_verlaesslich"] = out["snap_dist_m"] <= SNAP_MAX_DIST_M
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=PROCESSED / "hast_snapped.csv")
    args = p.parse_args()

    print("→ snapping geocodete Stationen an den raeumlichen Graphen")
    df = snap_stations()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"  → {args.out}")

    n_ok = int(df["snap_verlaesslich"].sum())
    print(f"\n{len(df)} Stationen gesnappt")
    print(f"  Distanz: Median {df['snap_dist_m'].median():.1f} m, "
          f"p90 {df['snap_dist_m'].quantile(0.9):.1f} m, "
          f"max {df['snap_dist_m'].max():.1f} m")
    print(f"  {n_ok} innerhalb {SNAP_MAX_DIST_M:.0f} m, "
          f"{len(df) - n_ok} darueber (Verortung nicht verlaesslich)")
