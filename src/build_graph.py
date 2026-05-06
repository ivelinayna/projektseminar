"""
Graph construction for the heating network.

Two complementary graphs are built:

  * `build_logical_graph` - undirected graph from the addresses + edges
    in Nodes_Edges.ods. Carries customer attributes (Anschlusswert,
    Zählernummer) and inspection findings as node attributes.

  * `build_spatial_graph` - undirected graph from the LineString
    shapefile, with pipe segments as edges (physical layout, lengths,
    materials). Endpoints are auto-detected from segment coordinates.

Both use NetworkX; later, the spatial graph can be matched to the logical
one once we have address geocodes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point

from . import load_data as ld


# --- Logical graph (from the ODS topology) --------------------------------

def build_logical_graph(
    nodes_df: Optional[pd.DataFrame] = None,
    edges_df: Optional[pd.DataFrame] = None,
    inspections_df: Optional[pd.DataFrame] = None,
) -> nx.Graph:
    """Build NetworkX graph from logical address topology.

    Nodes are addresses (normalised); attributes carry meter number,
    customer ID, contracted load, and any matching inspection record.
    """
    if nodes_df is None:
        nodes_df = ld.load_logical_nodes()
    if edges_df is None:
        edges_df = ld.load_logical_edges()
    if inspections_df is None:
        try:
            inspections_df = ld.load_inspections()
        except Exception:
            inspections_df = None

    g = nx.Graph()

    # Add HAST nodes from the Nodes sheet
    for _, row in nodes_df.iterrows():
        addr = row["address_norm"]
        if not addr:
            continue
        g.add_node(
            addr,
            display=row["address"],
            zaehlernummer=row.get("Zählernummer"),
            kundennummer=row.get("Kundennummer"),
            anschlusswert_kw=row.get("Anschlusswert"),
            kind="HAST",
        )

    # Add edges (creates "transit" nodes implicitly when endpoints aren't
    # in the Nodes sheet - those are pure topology junctions)
    for _, row in edges_df.iterrows():
        a, b = row["from_norm"], row["to_norm"]
        if not a or not b:
            continue
        for n in (a, b):
            if n not in g:
                g.add_node(n, display=n.title(), kind="junction")
        g.add_edge(a, b)

    # Annotate with inspection findings
    if inspections_df is not None:
        ins_by_addr = inspections_df.groupby("address_norm").size()
        for addr, count in ins_by_addr.items():
            if addr in g:
                g.nodes[addr]["inspections"] = int(count)
                g.nodes[addr]["inspected"] = True

    return g


# --- Spatial graph (from shapefile geometry) ------------------------------

def build_spatial_graph(
    pipes: Optional[gpd.GeoDataFrame] = None,
    snap_tolerance: float = 0.05,  # metres (UTM coords)
) -> nx.Graph:
    """Build NetworkX graph from pipe LineStrings.

    Each segment endpoint becomes a node (snapped at `snap_tolerance` to
    deduplicate coincident endpoints). Each pipe segment becomes an
    edge with length, material, type. Self-loops are dropped.
    """
    if pipes is None:
        pipes = ld.load_pipes()

    g = nx.Graph()

    def snap(coord):
        x, y = coord
        return (round(x / snap_tolerance) * snap_tolerance,
                round(y / snap_tolerance) * snap_tolerance)

    for _, row in pipes.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiLineString) else [geom]
        for part in parts:
            coords = list(part.coords)
            if len(coords) < 2:
                continue
            # treat each consecutive coord pair as a sub-edge so the
            # resulting graph respects the actual pipe routing.
            for c1, c2 in zip(coords[:-1], coords[1:]):
                u, v = snap(c1), snap(c2)
                if u == v:
                    continue
                length = LineString([c1, c2]).length  # in metres
                if g.has_edge(u, v):
                    # parallel pipes - keep the shorter edge length
                    g[u][v]["length_m"] = min(g[u][v]["length_m"], length)
                else:
                    g.add_edge(
                        u, v,
                        length_m=length,
                        material=row.get("material", ""),
                        pipe_type=row.get("pipe_type", ""),
                        fid=row.get("FID"),
                    )

    # Add coordinates as node attribute for plotting
    for n in g.nodes:
        g.nodes[n]["x"], g.nodes[n]["y"] = n
    return g


def largest_component(g: nx.Graph) -> nx.Graph:
    """Return the largest connected component of g as a fresh subgraph."""
    if g.number_of_nodes() == 0:
        return g.copy()
    nodes = max(nx.connected_components(g), key=len)
    return g.subgraph(nodes).copy()


def graph_summary(g: nx.Graph, name: str = "graph") -> str:
    """Compact summary suitable for logs and the README."""
    n_components = nx.number_connected_components(g)
    largest = max((len(c) for c in nx.connected_components(g)), default=0)
    deg = dict(g.degree())
    avg_deg = sum(deg.values()) / max(len(deg), 1)

    total_length = None
    if any("length_m" in d for _, _, d in g.edges(data=True)):
        total_length = sum(d.get("length_m", 0) for _, _, d in g.edges(data=True))

    out = [
        f"=== {name} ===",
        f"  nodes: {g.number_of_nodes()}",
        f"  edges: {g.number_of_edges()}",
        f"  connected components: {n_components}",
        f"  largest component: {largest} nodes",
        f"  average degree: {avg_deg:.2f}",
    ]
    if total_length is not None:
        out.append(f"  total pipe length: {total_length/1000:.2f} km")
    return "\n".join(out)


if __name__ == "__main__":
    log = build_logical_graph()
    print(graph_summary(log, "Logical graph (Prichsenstadt HAST)"))
    print()
    spa = build_spatial_graph()
    print(graph_summary(spa, "Spatial graph (full Mainfranken)"))
