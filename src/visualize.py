"""
Visualisations for the heating network.

  * `plot_logical_topology` - 2D matplotlib drawing of the address graph.
    Spring layout (no spatial coords yet); nodes coloured by HAST vs
    junction and sized by Anschlusswert. Inspected HAST are ringed.

  * `make_folium_map` - interactive Leaflet map of the spatial pipe
    network from the shapefile. Used for the eventual dashboard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import folium
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.lines import Line2D
from shapely.geometry import LineString, MultiLineString


# --- Logical (topological) drawing ----------------------------------------

def plot_logical_topology(g: nx.Graph, out_path: Path, seed: int = 7) -> Path:
    """Draw the address graph with HAST highlighted and write a PNG."""
    fig, ax = plt.subplots(figsize=(14, 10), dpi=110)

    # Use Kamada-Kawai for treelike networks - cleaner than spring
    pos = nx.kamada_kawai_layout(g)

    hast = [n for n, d in g.nodes(data=True) if d.get("kind") == "HAST"]
    junc = [n for n, d in g.nodes(data=True) if d.get("kind") != "HAST"]
    inspected = [n for n in hast if g.nodes[n].get("inspected")]

    # Anschlusswert -> size
    sizes_hast = []
    for n in hast:
        kw = g.nodes[n].get("anschlusswert_kw") or 10
        sizes_hast.append(40 + 2 * float(kw))

    nx.draw_networkx_edges(g, pos, ax=ax, edge_color="#888", width=0.8, alpha=0.7)

    nx.draw_networkx_nodes(
        g, pos, nodelist=junc, ax=ax,
        node_color="#999", node_size=18, alpha=0.7, label="Junction",
    )
    nx.draw_networkx_nodes(
        g, pos, nodelist=hast, ax=ax,
        node_color="#1f77b4", node_size=sizes_hast, alpha=0.85,
        edgecolors="white", linewidths=0.5, label="HAST",
    )
    nx.draw_networkx_nodes(
        g, pos, nodelist=inspected, ax=ax,
        node_color="none", node_size=[s * 2.2 for s in
            [40 + 2 * float(g.nodes[n].get('anschlusswert_kw') or 10) for n in inspected]],
        edgecolors="#d62728", linewidths=1.4, label="Inspected (in Excel)",
    )

    ax.set_title(
        f"Prichsenstadt heating network - logical topology\n"
        f"{g.number_of_nodes()} nodes, {g.number_of_edges()} edges, "
        f"{len(hast)} HAST, {len(inspected)} inspected",
        fontsize=13,
    )
    ax.set_axis_off()

    # Custom legend
    legend_elems = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#1f77b4",
               markersize=10, label="HAST (size = Anschlusswert)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor="#d62728", markeredgewidth=1.5, markersize=14,
               label="Begehung dokumentiert"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#999",
               markersize=6, label="Junction (kein HAST)"),
    ]
    ax.legend(handles=legend_elems, loc="lower left", frameon=True, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


# --- Spatial folium map ---------------------------------------------------

def make_folium_map(pipes_gdf, points_gdf, out_path: Path,
                    bounds: Optional[tuple] = None) -> Path:
    """Render the pipe network on an interactive OpenStreetMap layer.

    `bounds` is an optional (minx, miny, maxx, maxy) UTM-32N rectangle
    used to crop to the relevant cluster (e.g. just Prichsenstadt rather
    than the whole Mainfranken extent).
    """
    pipes = pipes_gdf.copy()
    if bounds is not None:
        minx, miny, maxx, maxy = bounds
        pipes = pipes.cx[minx:maxx, miny:maxy]
    pipes_wgs = pipes.to_crs("EPSG:4326")

    if pipes_wgs.empty:
        raise ValueError("No pipe segments inside the requested bounds")

    # Centre map
    bbox = pipes_wgs.total_bounds  # minx, miny, maxx, maxy = lon/lat
    cy, cx = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
    m = folium.Map(location=[cy, cx], zoom_start=16, tiles="OpenStreetMap")

    # Colour by pipe type
    type_colour = {
        "Vorlauf (single)":          "#d62728",
        "Rücklauf (single)":         "#1f77b4",
        "Doppelrohr (combined)":     "#2ca02c",
        "Hausanschluss":             "#ff7f0e",
        "Sonstige":                  "#9467bd",
        "Knotenpunkt / Station":     "#000000",
    }

    for _, row in pipes_wgs.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]
        colour = type_colour.get(row.get("pipe_type", ""), "#888")
        for part in parts:
            coords = [(y, x) for x, y in part.coords]
            folium.PolyLine(
                coords, color=colour, weight=3, opacity=0.85,
                tooltip=f"{row.get('material','?')} ({row.get('pipe_type','?')})",
            ).add_to(m)

    # Plot any points inside bounds too
    if points_gdf is not None and len(points_gdf):
        pts = points_gdf.copy()
        if bounds is not None:
            pts = pts.cx[bounds[0]:bounds[2], bounds[1]:bounds[3]]
        pts_wgs = pts.to_crs("EPSG:4326")
        for _, row in pts_wgs.iterrows():
            pt = row.geometry
            if pt is None or pt.is_empty:
                continue
            folium.CircleMarker(
                location=[pt.y, pt.x], radius=5, color="#000",
                fill=True, fill_color="#fff", fill_opacity=1,
                tooltip=row.get("point_type", "Knotenpunkt"),
            ).add_to(m)

    # Legend
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background:white; padding:10px 14px; border:1px solid #888;
                font-family:sans-serif; font-size:12px; line-height:1.5;">
    <b>Pipe type</b><br/>
    <span style="color:#d62728">━━</span> Vorlauf<br/>
    <span style="color:#1f77b4">━━</span> Rücklauf<br/>
    <span style="color:#2ca02c">━━</span> Doppelrohr<br/>
    <span style="color:#ff7f0e">━━</span> Hausanschluss<br/>
    <span style="color:#000">●</span> Knotenpunkt
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(str(out_path))
    return out_path


def find_main_cluster(pipes_gdf, eps: float = 500.0,
                      min_samples: int = 20, sample: int = 8000):
    """Find the largest spatial cluster of pipe coords -> bounding box.

    Used to crop the full Mainfranken shapefile to just the Prichsenstadt
    network. Returns (minx, miny, maxx, maxy) in UTM-32N metres.
    """
    from sklearn.cluster import DBSCAN
    import random

    coords = []
    for geom in pipes_gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]
        for part in parts:
            coords.extend(part.coords)
    if len(coords) > sample:
        coords = random.sample(coords, sample)
    arr = np.array(coords)

    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(arr)
    counts = {c: (labels == c).sum() for c in set(labels) if c != -1}
    if not counts:
        return tuple(pipes_gdf.total_bounds)
    biggest = max(counts, key=counts.get)
    pts = arr[labels == biggest]
    pad = 50
    return (pts[:, 0].min() - pad, pts[:, 1].min() - pad,
            pts[:, 0].max() + pad, pts[:, 1].max() + pad)
