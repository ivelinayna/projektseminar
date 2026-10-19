"""
Tests fuer Graphaufbau und interaktive Visualisierungen.

Prueft logischen Graph, raeumlichen Graph und die HTML-Exporte
fuer UEZ Mainfranken.
"""

from pathlib import Path
import networkx as nx
import pytest

from src.build_graph import (
    build_logical_graph,
    build_spatial_graph,
    largest_component,
    graph_summary,
)
from src.network_graph import (
    annotate_graph_with_results,
    export_interactive_topology,
)
from src.dashboard_map import build_combined_map

ROOT = Path(__file__).resolve().parents[1]


def test_build_logical_graph_properties():
    #Logischer Graph aus Nodes_Edges.ods
    g = build_logical_graph()
    assert len(g.nodes) >= 100
    assert len(g.edges) >= 100

    #Hauptkomponente hat mindestens 100 Knoten
    main_g = largest_component(g)
    assert len(main_g) >= 100

    #Waisen-Knoten pruefen
    orphan_count = sum(1 for c in nx.connected_components(g) if len(c) == 1)
    assert orphan_count >= 5

    summary = graph_summary(g, "Test Logical")
    assert "Test Logical" in summary


def test_annotate_and_export_topology(tmp_path):
    #Interaktiven Netzgraphen annotieren und exportieren
    g = build_logical_graph()
    g_annotated = annotate_graph_with_results(g)

    #Mindestens ein Knoten hat Ruecklauf annotiert
    has_rt = any(d.get("rt_winter") is not None for _, d in g_annotated.nodes(data=True))
    assert has_rt

    out_file = tmp_path / "test_topology.html"
    res = export_interactive_topology(out_path=out_file, g=g_annotated)
    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "vis-network" in content
    assert "network-container" in content


def test_build_combined_map(tmp_path):
    #Geografische Folium-Karte exportieren
    out_file = tmp_path / "test_dashboard_map.html"
    res = build_combined_map(out_path=out_file, crop_to_main_cluster=True)
    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "leaflet" in content.lower() or "folium" in content.lower()
