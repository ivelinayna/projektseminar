"""
Combined map: pipe network + geocoded HAST + inspection findings + predicted faults.

This is the first version of the dashboard the project ultimately aims
for. Each HAST appears as a coloured marker:

  * green  - healthy according to both inspection and time-series rules
  * yellow - inspected and only minor actions taken
  * orange - 1 fault flag (from inspection or from rule classifier)
  * red    - 2+ fault flags
  * grey   - never inspected and not predicted faulty (or no time-series)

Tooltips show: address, Anschlusswert, inspection findings, predicted
fault, raw rule reasons. A separate layer shows the pipe network so the
HAST can be cross-checked against the topology.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import math
import re

import folium
import pandas as pd
from shapely.geometry import MultiLineString, LineString, Point
from pyproj import Transformer

from . import load_data as ld
from .geocode import geocode_nodes, validate_results
from .inspections import tidy_inspections
from .visualize import find_main_cluster


SEVERITY_COLOUR = {
    "healthy":     "#2ca02c",
    "minor":       "#d4a017",
    "warn":        "#ff7f0e",
    "alarm":       "#d62728",
    "unknown":     "#888888",
}

OVERRIDE_PATH = Path("data/manual/address_overrides.csv")


def _norm_address(value: object) -> str:
    """Normalize addresses so override file and raw data match robustly."""
    s = str(value or "").strip().lower()
    s = s.replace("straße", "strasse")
    s = s.replace("str.", "strasse")
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" - ", "-")
    return s


def _house_number_key(address: object) -> tuple:
    """Stable order for plotting duplicate street-level coordinates."""
    s = str(address or "")
    street = re.sub(r"\d.*$", "", s).strip().lower()
    m = re.search(r"(\d+)", s)
    number = int(m.group(1)) if m else 9999
    suffix = s[m.end():].strip() if m else ""
    return street, number, suffix, s


def apply_manual_overrides(geo: pd.DataFrame) -> pd.DataFrame:
    """
    Replace geocoded coordinates with manually checked coordinates.

    Expected file:
        data/manual/address_overrides.csv

    Required columns:
        address, manual_lat, manual_lon

    Optional:
        comment, coord_source

    If manual_lat/manual_lon are empty, the normal geocode stays unchanged.
    """
    out = geo.copy()

    if "coord_source" not in out.columns:
        out["coord_source"] = "nominatim"
    if "coord_quality" not in out.columns:
        out["coord_quality"] = "geocoded"

    if not OVERRIDE_PATH.exists():
        return out

    overrides = pd.read_csv(OVERRIDE_PATH, dtype=str)

    # tolerate different column names
    if "lat" in overrides.columns and "manual_lat" not in overrides.columns:
        overrides = overrides.rename(columns={"lat": "manual_lat"})
    if "lon" in overrides.columns and "manual_lon" not in overrides.columns:
        overrides = overrides.rename(columns={"lon": "manual_lon"})

    required = {"address", "manual_lat", "manual_lon"}
    missing = required - set(overrides.columns)
    if missing:
        raise ValueError(
            f"{OVERRIDE_PATH} fehlt Spalten: {sorted(missing)}. "
            "Benötigt: address, manual_lat, manual_lon"
        )

    overrides["address_key"] = overrides["address"].map(_norm_address)
    overrides["manual_lat"] = pd.to_numeric(overrides["manual_lat"], errors="coerce")
    overrides["manual_lon"] = pd.to_numeric(overrides["manual_lon"], errors="coerce")

    overrides = overrides.dropna(subset=["manual_lat", "manual_lon"])
    overrides = overrides.drop_duplicates("address_key", keep="last")

    if overrides.empty:
        return out

    out["address_key"] = out["address"].map(_norm_address)

    use_cols = ["address_key", "manual_lat", "manual_lon"]
    if "comment" in overrides.columns:
        use_cols.append("comment")
    if "coord_source" in overrides.columns:
        use_cols.append("coord_source")

    out = out.merge(
        overrides[use_cols],
        on="address_key",
        how="left",
        suffixes=("", "_override"),
    )

    mask = out["manual_lat"].notna() & out["manual_lon"].notna()

    out.loc[mask, "lat"] = out.loc[mask, "manual_lat"]
    out.loc[mask, "lon"] = out.loc[mask, "manual_lon"]
    out.loc[mask, "coord_source"] = "manual_override"
    out.loc[mask, "coord_quality"] = "exact_or_manually_checked"

    out = out.drop(columns=[c for c in ["manual_lat", "manual_lon", "address_key"] if c in out.columns])

    return out


def _line_parts(geometry):
    """Return LineString parts from LineString or MultiLineString."""
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    return []


def _nearest_pipe_line(point: Point, pipes_in) -> LineString | None:
    """Find nearest pipe line in projected CRS."""
    if pipes_in.empty:
        return None

    distances = pipes_in.geometry.distance(point)
    nearest_geom = pipes_in.geometry.loc[distances.idxmin()]
    parts = _line_parts(nearest_geom)

    if not parts:
        return None

    return min(parts, key=lambda line: line.distance(point))


def make_plot_coordinates(df_hits: pd.DataFrame, pipes_in) -> pd.DataFrame:
    """
    Create plot_lat/plot_lon for the dashboard.

    Manual coordinates stay unchanged.
    Duplicate street-level geocodes are spread along the nearest pipe line,
    instead of being displayed as artificial circles.
    """
    out = df_hits.copy()
    out["plot_lat"] = out["lat"]
    out["plot_lon"] = out["lon"]
    out["plot_note"] = ""

    if out.empty:
        return out

    pipe_crs = pipes_in.crs or "EPSG:25832"

    to_pipe_crs = Transformer.from_crs("EPSG:4326", pipe_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(pipe_crs, "EPSG:4326", always_xy=True)

    duplicate_groups = out.groupby(["lat", "lon"]).groups

    for (lat, lon), idxs in duplicate_groups.items():
        idxs = list(idxs)

        if len(idxs) <= 1:
            continue

        # If all points in a duplicate group are manually checked,
        # they are correct as-is - don't spread them.
        if "coord_source" in out.columns:
            sources = out.loc[idxs, "coord_source"].astype(str)
            if (sources == "manual_override").all():
                continue

        # If every point in this group came from an exact OSM
        # housenumber match, then they're correctly placed at distinct
        # buildings - the only reason they share coords is a rare OSM
        # quirk (multiple buildings tagged at the same node). Skip
        # spreading; let folium handle the overlap visually.
        if "note" in out.columns:
            notes = out.loc[idxs, "note"].astype(str)
            if all("exact_house_number_osm" in n for n in notes):
                continue

        x, y = to_pipe_crs.transform(lon, lat)
        base_point = Point(x, y)

        line = _nearest_pipe_line(base_point, pipes_in)
        if line is None or line.length == 0:
            continue

        base_dist = line.project(base_point)

        ordered_idxs = sorted(idxs, key=lambda i: _house_number_key(out.at[i, "address"]))
        n = len(ordered_idxs)

        # Abstand zwischen visualisierten Punkten in Metern
        spacing_m = 10.0
        side_offset_m = 2.0

        for rank, idx in enumerate(ordered_idxs):
            offset = (rank - (n - 1) / 2.0) * spacing_m
            d = max(0.0, min(line.length, base_dist + offset))

            p = line.interpolate(d)

            # kleine seitliche Verschiebung, damit Marker nicht exakt auf der Leitung liegen
            d1 = max(0.0, d - 0.5)
            d2 = min(line.length, d + 0.5)
            p1 = line.interpolate(d1)
            p2 = line.interpolate(d2)

            dx = p2.x - p1.x
            dy = p2.y - p1.y
            norm = math.hypot(dx, dy) or 1.0

            side = side_offset_m if rank % 2 == 0 else -side_offset_m
            px = p.x - (dy / norm) * side
            py = p.y + (dx / norm) * side

            plot_lon, plot_lat = to_wgs84.transform(px, py)

            out.at[idx, "plot_lat"] = plot_lat
            out.at[idx, "plot_lon"] = plot_lon
            out.at[idx, "plot_note"] = "street-level geocode visually spread along nearest pipe"

    return out

def _classify_severity(row) -> tuple[str, str]:
    """Pick a severity level + label for a HAST row.

    Combines (a) inspection action count, (b) predicted-fault flag.
    """
    n_actions = row.get("n_actions", 0)
    predicted = row.get("predicted_fault", "healthy")
    inspected = row.get("inspected", False)

    if predicted not in ("healthy", "", None) and n_actions >= 2:
        return "alarm", f"Predicted: {predicted}; {n_actions} inspection actions"
    if predicted not in ("healthy", "", None):
        return "warn", f"Predicted: {predicted}"
    if n_actions >= 2:
        return "warn", f"{n_actions} inspection actions"
    if n_actions == 1:
        return "minor", "1 inspection action"
    if inspected:
        return "healthy", "Inspected, no issues found"
    return "unknown", "Not inspected, no time-series prediction"


def build_combined_map(out_path: Path,
                      crop_to_main_cluster: bool = True) -> Path:
    """Build the combined HAST-status map and save to `out_path`."""
    # 1. Pipes ---------------------------------------------------------
    pipes = ld.load_pipes()
    bounds = find_main_cluster(pipes) if crop_to_main_cluster else None

    if bounds is not None:
        pipes_in = pipes.cx[bounds[0]:bounds[2], bounds[1]:bounds[3]]
    else:
        pipes_in = pipes
    pipes_wgs = pipes_in.to_crs("EPSG:4326")
    bbox = pipes_wgs.total_bounds  # lon/lat
    cy, cx = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2

    m = folium.Map(location=[cy, cx], zoom_start=16, tiles="OpenStreetMap")

    pipe_layer = folium.FeatureGroup(name="Wärmeleitungen", show=True)
    for _, row in pipes_wgs.iterrows():
        g = row.geometry
        if g is None or g.is_empty:
            continue
        parts = list(g.geoms) if isinstance(g, MultiLineString) else [g]
        for part in parts:
            folium.PolyLine(
                [(y, x) for x, y in part.coords],
                color="#666", weight=2.5, opacity=0.6,
                tooltip=row.get("material", ""),
            ).add_to(pipe_layer)
    pipe_layer.add_to(m)

    # 2. HAST status ---------------------------------------------------
    geo = geocode_nodes()
    geo = apply_manual_overrides(geo)
    geo = validate_results(geo)
    insp = tidy_inspections()

    # Aggregate inspection rows per address (some addresses have 2 records)
    insp_agg = (insp.groupby("address_norm")
                    .agg(n_actions=("n_actions", "max"),
                         filter_gereinigt=("filter_gereinigt", "any"),
                         durchfluss_neu=("durchfluss_neu", "any"),
                         daemmung_neu=("daemmung_neu", "any"),
                         vertrag_changed=("vertrag_changed", "any"),
                         sonstiges=("sonstiges", lambda s: " | ".join(
                             x for x in s.fillna("").astype(str)
                             if x and x != "nan")))
                    .reset_index())

    df = geo.merge(insp_agg, left_on="address_norm",
                   right_on="address_norm", how="left")
    df["inspected"] = df["n_actions"].notna()
    df["n_actions"] = df["n_actions"].fillna(0).astype(int)

    # Optional: pull in time-series predictions if they exist
    pred_path = Path("data/processed/predictions.csv")
    if pred_path.exists():
        preds = pd.read_csv(pred_path)
        if "Zählernummer" in preds.columns:
            df = df.merge(preds[["Zählernummer", "predicted_fault", "reasons"]],
                          on="Zählernummer", how="left")
        else:
            df["predicted_fault"] = "healthy"
            df["reasons"] = ""
    else:
        df["predicted_fault"] = "healthy"
        df["reasons"] = ""
    df["predicted_fault"] = df["predicted_fault"].fillna("healthy")
    df["reasons"] = df["reasons"].fillna("")

    # Build the marker layer (only HAST that geocoded successfully)
    hast_layer = folium.FeatureGroup(name="HAST mit Status", show=True)
    df_hits = df[df["lat"].notna() & df["in_expected_area"]].copy()
    df_hits = make_plot_coordinates(df_hits, pipes_in)

    for _, row in df_hits.iterrows():
        sev, sev_label = _classify_severity(row)
        colour = SEVERITY_COLOUR[sev]

        actions = []
        if row.get("filter_gereinigt"):    actions.append("Filter gereinigt")
        if row.get("durchfluss_neu"):      actions.append("Durchfluss neu eingestellt")
        if row.get("daemmung_neu"):        actions.append("Leitungen neu gedämmt")
        if row.get("vertrag_changed"):     actions.append("Vertragsleistung geändert")

        tip = (
            f"<b>{row['address']}</b><br/>"
            f"Zählernr: {int(row['Zählernummer']) if pd.notna(row.get('Zählernummer')) else '?'}<br/>"
            f"Anschlusswert: {row.get('Anschlusswert', '?')} kW<br/>"
            f"<b>Status:</b> {sev_label}<br/>"
            f"<b>Begehung-Befunde:</b> "
            f"{', '.join(actions) if actions else 'keine'}<br/>"
            f"<b>Predicted:</b> {row.get('predicted_fault', 'healthy')}"
        )

        radius = 5 + 0.15 * float(row.get("Anschlusswert", 10) or 10)
        radius = min(radius, 18)

        folium.CircleMarker(
            location=[row["plot_lat"], row["plot_lon"]],
            radius=radius,
            color="white", weight=1.5,
            fill=True, fill_color=colour, fill_opacity=0.85,
            tooltip=tip,
        ).add_to(hast_layer)

    hast_layer.add_to(m)

    # 3. Legend --------------------------------------------------------
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background:white; padding:10px 14px; border:1px solid #888;
                font-family:sans-serif; font-size:12px; line-height:1.5;
                max-width: 240px;">
    <b>HAST-Status</b><br/>
    <span style="color:#2ca02c">●</span> gesund (begangen, ohne Befund)<br/>
    <span style="color:#d4a017">●</span> 1 Befund<br/>
    <span style="color:#ff7f0e">●</span> ≥ 2 Befunde<i>oder</i> Anomalie aus Zeitreihe<br/>
    <span style="color:#d62728">●</span> 2+ Befunde <b>und</b> Anomalie<br/>
    <span style="color:#888">●</span> noch keine Daten<br/>
    <hr style="margin:4px 0"/>
    Markergröße ∝ Anschlusswert (kW)<br/>
    <span style="color:#666">━━</span> Wärmeleitung
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    folium.LayerControl().add_to(m)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out_path))
    return out_path


if __name__ == "__main__":
    out = build_combined_map(Path("outputs/dashboard_map.html"))
    print(f"wrote {out}")
