"""
Interaktive Visualisierung des logischen HAST-Netzgraphen.

Baut auf build_logical_graph auf und erzeugt eine eigenstaendige HTML-Datei
mit Vis.js Network. Die Datei benoetigt keinen Server und laeuft direkt
im Browser fuer UEZ Mainfranken.

Knoten zeigen HAST und Abzweige, Kanten die Leitungsverbindungen.
Farbe richtet sich nach der gemessenen Ruecklauftemperatur im Winter bzw.
der Prioritaet aus der unueberwachten Empfehlungsliste.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import networkx as nx
import pandas as pd

from .build_graph import build_logical_graph, largest_component
from .load_begehungen import meter_to_address
from .load_data import _normalize_address

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"


def _status_color(rt: Optional[float], has_rec: bool, stufe: str) -> tuple[str, str]:
    """Farbe und Label anhand Winter-Ruecklauf und Empfehlungsstufe."""
    if has_rec:
        if stufe == "hoch":
            return "#d62728", "Auffaellig (Prioritaet hoch)"
        if stufe == "mittel":
            return "#ff7f0e", "Auffaellig (Prioritaet mittel)"
        return "#d4a017", "Auffaellig (Prioritaet niedrig)"
    if rt is None or pd.isna(rt):
        return "#9e9e9e", "Keine Zaehlerdaten / Junction"
    if rt < 45.0:
        return "#2ca02c", f"Normal (< 45 C: {rt:.1f} C)"
    if rt < 50.0:
        return "#bcbd22", f"Leicht erhoeht (45-50 C: {rt:.1f} C)"
    if rt < 55.0:
        return "#ff7f0e", f"Erhoeht (50-55 C: {rt:.1f} C)"
    return "#d62728", f"Kritisch (> 55 C: {rt:.1f} C)"


def annotate_graph_with_results(g: nx.Graph) -> nx.Graph:
    """Reichert Knoten des Graphen mit Features und Empfehlungen an."""
    m2a = meter_to_address()

    # Echte Features laden
    feats_path = PROCESSED / "features_real.csv"
    rt_map: dict[str, float] = {}
    if feats_path.exists():
        df_f = pd.read_csv(feats_path)
        for _, row in df_f.iterrows():
            m = row.get("Z\u00e4hlernummer") or row.get("Zaehlernummer")
            if pd.notna(m) and pd.notna(row.get("rt_mean_winter")):
                addr = m2a.get(int(m))
                if addr:
                    norm = _normalize_address(addr)
                    rt_map[norm] = float(row["rt_mean_winter"])

    # Empfehlungen laden
    empf_path = PROCESSED / "empfehlungsliste.csv"
    empf_map: dict[str, dict] = {}
    if empf_path.exists():
        df_e = pd.read_csv(empf_path)
        for _, row in df_e.iterrows():
            m = row["meter"]
            addr = m2a.get(int(m))
            if addr:
                norm = _normalize_address(addr)
                empf_map[norm] = {
                    "meter": int(m),
                    "muster": str(row.get("muster", "")),
                    "stufe": str(row.get("stufe", "")),
                    "massnahme": str(row.get("massnahme", "")),
                    "begruendung": str(row.get("begruendung_kurz", "")),
                    "punkte": float(row.get("punkte", 0.0)),
                }

    # Knoten annotieren
    for n in g.nodes:
        kind = g.nodes[n].get("kind", "junction")
        rt = rt_map.get(n)
        rec = empf_map.get(n)

        has_rec = rec is not None
        stufe = rec["stufe"] if rec else ""
        color, status_text = _status_color(rt, has_rec, stufe)

        g.nodes[n]["rt_winter"] = rt
        g.nodes[n]["color"] = color
        g.nodes[n]["status_text"] = status_text
        g.nodes[n]["has_recommendation"] = has_rec
        if rec:
            g.nodes[n]["empfehlung"] = rec

    return g


def export_interactive_topology(
    out_path: Path = OUTPUTS / "network_topology.html",
    g: Optional[nx.Graph] = None,
) -> Path:
    """Erzeugt eine interaktive Vis.js-Visualisierung des Netzgraphen."""
    if g is None:
        g = build_logical_graph()
    g = annotate_graph_with_results(g)

    nodes_data = []
    for n in g.nodes:
        d = g.nodes[n]
        kind = d.get("kind", "junction")
        kw = d.get("anschlusswert_kw")
        display = d.get("display", n)
        meter = d.get("zaehlernummer")
        rt = d.get("rt_winter")
        rec = d.get("empfehlung")

        # Knotengroesse nach Leistung oder Standard
        if kind == "HAST":
            size = 14 + min(int((kw or 10) / 10), 22)
            shape = "dot"
        else:
            size = 8
            shape = "diamond"

        label = display if kind == "HAST" else f"Abzweig: {display}"
        tooltip_lines = [
            f"<b>{display}</b>",
            f"Typ: {kind}",
            f"Anschlusswert: {kw} kW" if kw else "Anschlusswert: unbekannt",
            f"Zaehlernummer: {meter}" if meter else "",
            f"Winter-Ruecklauf: {rt:.1f} C" if rt else "Winter-Ruecklauf: k.A.",
            f"Status: {d.get('status_text')}",
        ]
        if rec:
            tooltip_lines.extend([
                f"<hr style='margin:4px 0;'>",
                f"<b>Muster:</b> {rec['muster']}",
                f"<b>Prioritaet:</b> {rec['stufe']} ({rec['punkte']:.1f} Pkt.)",
                f"<b>Massnahme:</b> {rec['massnahme']}",
            ])

        title = "<br>".join(l for l in tooltip_lines if l)

        nodes_data.append({
            "id": n,
            "label": display if kind == "HAST" else "",
            "title": title,
            "color": d.get("color", "#9e9e9e"),
            "size": size,
            "shape": shape,
            "kind": kind,
            "kw": kw,
            "rt": rt,
            "meter": meter,
            "has_rec": d.get("has_recommendation", False),
            "display": display,
            "massnahme": rec.get("massnahme", "") if rec else "",
            "muster": rec.get("muster", "") if rec else "",
            "stufe": rec.get("stufe", "") if rec else "",
        })

    edges_data = []
    for u, v in g.edges:
        edges_data.append({
            "from": u,
            "to": v,
            "color": {"color": "#b0bec5", "highlight": "#1976d2"},
            "width": 1.5,
        })

    html_template = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Fernwaermenetz Wiesentheid - Topologischer Netzgraph</title>
  <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      display: flex;
      height: 100vh;
      background-color: #f8f9fa;
      color: #212529;
    }
    #sidebar {
      width: 360px;
      padding: 16px;
      background: #ffffff;
      box-shadow: 2px 0 8px rgba(0,0,0,0.08);
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      z-index: 10;
    }
    #network-container {
      flex: 1;
      height: 100vh;
      position: relative;
    }
    h2 { margin: 0 0 4px 0; font-size: 1.15rem; color: #1a202c; }
    h3 { margin: 12px 0 6px 0; font-size: 0.95rem; color: #2d3748; }
    p { margin: 0; font-size: 0.85rem; color: #4a5568; line-height: 1.4; }
    .card {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 10px;
      font-size: 0.85rem;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.8rem;
      margin-bottom: 4px;
    }
    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      display: inline-block;
    }
    .legend-diamond {
      width: 10px;
      height: 10px;
      transform: rotate(45deg);
      display: inline-block;
      background: #9e9e9e;
    }
    input[type="text"] {
      width: 100%;
      padding: 8px;
      box-sizing: border-box;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      font-size: 0.85rem;
    }
    button {
      padding: 6px 12px;
      background: #0284c7;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.8rem;
    }
    button:hover { background: #0369a1; }
    .badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div id="sidebar">
    <div>
      <h2>HAST-Netztopologie</h2>
      <p>Logischer Leitungsverlauf und hydraulische Nachbarschaften im Teilnetz Wiesentheid (UEZ Mainfranken).</p>
    </div>

    <div>
      <input type="text" id="search-input" placeholder="Station suchen (z. B. Blumenstr.)..." oninput="searchStation()">
    </div>

    <div class="card" id="detail-card">
      <h3>Stationsdetails</h3>
      <p id="detail-hint">Klicken Sie auf einen Knoten im Graphen, um Details, Messwerte und Handlungsempfehlungen anzuzeigen.</p>
      <div id="detail-content" style="display:none;"></div>
    </div>

    <div class="card">
      <h3>Legende</h3>
      <div class="legend-item"><span class="legend-dot" style="background:#2ca02c;"></span> Normal (< 45 C)</div>
      <div class="legend-item"><span class="legend-dot" style="background:#bcbd22;"></span> Leicht erhoeht (45-50 C)</div>
      <div class="legend-item"><span class="legend-dot" style="background:#ff7f0e;"></span> Auffaellig (mittel / 50-55 C)</div>
      <div class="legend-item"><span class="legend-dot" style="background:#d62728;"></span> Kritisch / Hohe Prioritaet (> 55 C)</div>
      <div class="legend-item"><span class="legend-diamond"></span> Abzweig / Junction</div>
      <div class="legend-item"><span class="legend-dot" style="background:#9e9e9e;"></span> Keine Messdaten / Waisen-Knoten</div>
      <p style="font-size:0.75rem; color:#64748b; margin-top:6px;">Knotengroesse entspricht der vertraglichen Anschlussleistung (kW).</p>
    </div>

    <div style="display:flex; gap:6px;">
      <button onclick="network.fit({animation:true})">Netz zentrieren</button>
      <button onclick="togglePhysics()" id="btn-physics">Stabilisieren</button>
    </div>
  </div>

  <div id="network-container"></div>

  <script>
    const nodes = new vis.DataSet(NODES_PLACEHOLDER);
    const edges = new vis.DataSet(EDGES_PLACEHOLDER);

    const container = document.getElementById("network-container");
    const data = { nodes: nodes, edges: edges };
    const options = {
      nodes: {
        borderWidth: 1.5,
        borderWidthSelected: 3,
        font: { size: 11, face: "sans-serif", color: "#333" }
      },
      edges: {
        smooth: { type: "continuous" }
      },
      physics: {
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
          gravitationalConstant: -35,
          centralGravity: 0.005,
          springLength: 45,
          springConstant: 0.18
        },
        stabilization: { iterations: 150 }
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        navigationButtons: true,
        keyboard: true
      }
    };

    const network = new vis.Network(container, data, options);
    let physicsEnabled = true;

    function togglePhysics() {
      physicsEnabled = !physicsEnabled;
      network.setOptions({ physics: { enabled: physicsEnabled } });
      document.getElementById("btn-physics").innerText = physicsEnabled ? "Fixieren" : "Entspannen";
    }

    network.on("click", function(params) {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = nodes.get(nodeId);
        showDetails(node);
      }
    });

    function showDetails(node) {
      document.getElementById("detail-hint").style.display = "none";
      const div = document.getElementById("detail-content");
      div.style.display = "block";

      let html = `<p><b>${node.display || node.id}</b></p>`;
      html += `<p style='margin-top:4px;'><b>Typ:</b> ${node.kind}</p>`;
      if (node.kw) html += `<p><b>Anschlusswert:</b> ${node.kw} kW</p>`;
      if (node.meter) html += `<p><b>Zaehlernummer:</b> ${node.meter}</p>`;
      if (node.rt) html += `<p><b>Winter-Ruecklauf:</b> ${node.rt.toFixed(1)} C</p>`;

      if (node.has_rec) {
        html += `<div style='margin-top:8px; padding:6px; background:#fff; border-left:3px solid ${node.color}; border-radius:3px;'>`;
        html += `<p><b>Muster:</b> ${node.muster}</p>`;
        html += `<p><b>Dringlichkeit:</b> <span class='badge' style='background:${node.color}; color:#fff;'>${node.stufe}</span></p>`;
        html += `<p style='margin-top:4px;'><b>Empfohlene Massnahme:</b><br>${node.massnahme}</p>`;
        html += `</div>`;
      } else if (node.kind === "HAST") {
        html += `<p style='color:#16a34a; margin-top:6px;'>Keine unueberwachte Anomalie festgestellt.</p>`;
      }

      // Verbundene Nachbarknoten anzeigen
      const connected = network.getConnectedNodes(node.id);
      if (connected.length > 0) {
        html += `<p style='margin-top:8px; font-weight:600;'>Hydraulische Nachbarn (${connected.length}):</p>`;
        html += `<ul style='margin:4px 0 0 16px; padding:0; font-size:0.8rem; color:#475569;'>`;
        connected.forEach(cid => {
          const cnode = nodes.get(cid);
          html += `<li>${cnode.display || cid}</li>`;
        });
        html += `</ul>`;
      }

      div.innerHTML = html;
    }

    function searchStation() {
      const q = document.getElementById("search-input").value.trim().toLowerCase();
      if (!q) return;
      const match = nodes.get({
        filter: function(item) {
          return (item.display && item.display.toLowerCase().includes(q)) ||
                 (item.id && item.id.toLowerCase().includes(q)) ||
                 (item.meter && String(item.meter).includes(q));
        }
      });
      if (match.length > 0) {
        network.selectNodes([match[0].id]);
        network.focus(match[0].id, { scale: 1.2, animation: true });
        showDetails(match[0]);
      }
    }
  </script>
</body>
</html>"""

    nodes_json = json.dumps(nodes_data, ensure_ascii=False)
    edges_json = json.dumps(edges_data, ensure_ascii=False)

    rendered = html_template.replace("NODES_PLACEHOLDER", nodes_json).replace("EDGES_PLACEHOLDER", edges_json)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    p = export_interactive_topology()
    print("Exported network topology to:", p)
