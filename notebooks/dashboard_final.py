# dashboard_final.py
# Kopie von dashboard_export.py (Notebook 16) in der Rohrbaum-Fassung aus Notebook 28, erweitert um die
# Ergebnisse der Modelle aus Notebook 34. Das Original dashboard_export.py bleibt unverändert.
#
# Ausführen in Notebook 35 mit runpy.run_path("dashboard_final.py", init_globals={...}).
# Gebraucht werden serien, knoten, G, pos, roh und optional linien, kml_linien, geschaetzt.
# Die Modellergebnisse kommen fertig aus outputs/dashboard/ (python -m src.dashboard_daten),
# gelesen über src/dashboard_karte.py. Dieses Skript rechnet keine Modelle.
#
# Drei Reiter in einer HTML-Datei:
#   Karte              Färbung nach Dringlichkeit (Start), Maßnahme, Meldungen der Wächter, Potenzial oder
#                      Messwerten; Hausfenster mit Empfehlung, Verdacht, Stand im Netz, Veränderung, Befund
#   Handlungsliste     alle Zähler nach Dringlichkeit, Klick zeigt das Haus auf der Karte
#   So funktioniert's  welche Frage mit welchem Modell beantwortet wird und warum

import json
import base64
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx

# ------------------------------------------------------------------ Einstellungen
START = globals().get("START", "2024-01-01 00:00")
ENDE = globals().get("ENDE", "2025-09-30 23:00")       # bis Ende Sommer 2025, damit die LSTM-Meldungen drin sind
FLUSS_MIN_LH = 0.5              # Stunden mit Durchfluss bis zu diesem Wert haben keine aussagekräftige Spreizung
AUSGABE = globals().get("AUSGABE", "fernwaerme_dashboard_final.html")
HINTERGRUND = globals().get("HINTERGRUND", "webkarte")
BG_PUFFER_M = 200               # Rohrplan und Gebäudekanten werden bis zu diesem Abstand um die Häuser mitgezeichnet
PUNKTE_ZEIGEN = bool(globals().get("PUNKTE_ZEIGEN", False))   # Abzweige und Anschlussstellen als graue Punkte
MELDUNG_TAGE = 14               # Färbung "Meldungen": Meldungen der letzten so vielen Tage

# ------------------------------------------------------------------ Voraussetzungen prüfen
fehlt = [n for n in ("serien", "knoten", "G", "pos", "roh") if n not in globals()]
if fehlt:
    raise SystemExit(f"Diese Variablen fehlen: {fehlt}. Notebook 35 von oben ausführen.")

ROOT = globals().get("ROOT") or next(
    (p for p in [Path.cwd(), *Path.cwd().parents] if (p / "src" / "dashboard_karte.py").exists()), None)
if ROOT is None:
    raise SystemExit("Repo-Ordner mit src/dashboard_karte.py nicht gefunden, bitte ROOT übergeben.")
ROOT = Path(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src import dashboard_karte as dk

MODELL_ORDNER = Path(globals().get("MODELL_ORDNER") or ROOT / "outputs" / "dashboard")

if "norm_z" not in globals():
    def norm_z(s):
        return re.sub(r"\D", "", str(s)).lstrip("0")

est = set(globals().get("geschaetzt", []))

idx = pd.date_range(START, ENDE, freq="1h")
H = len(idx)

# ------------------------------------------------------------------ Knoten und Zähler
nodes = [n for n in G.nodes if n in pos]
if len(nodes) < G.number_of_nodes():
    print(f"Hinweis: {G.number_of_nodes() - len(nodes)} Nodes ohne Position werden nicht gezeigt.")
nid = {n: i for i, n in enumerate(nodes)}

meter = {}
for r in knoten.itertuples():
    if r.edge_node not in nid:
        continue
    zs = [norm_z(z) for z in str(r.zaehler).split(",") if norm_z(z)]
    zs = [z for z in zs if z in serien]
    if not zs:
        continue
    meter[r.edge_node] = {"ds": [serien[z].reindex(idx) for z in zs], "zs": zs, "z": ", ".join(zs), "k": len(zs)}

meter_keys = list(meter)
mindex = {k: i for i, k in enumerate(meter_keys)}
M = len(meter_keys)
if M == 0:
    raise SystemExit("Keine Zähler mit Zeitreihen und Position gefunden.")


def agg(ds, col, how):
    f = pd.concat([d[col] for d in ds], axis=1)
    return f.mean(axis=1) if how == "mean" else f.sum(axis=1, min_count=1)


SCALE = (100, 100, 10, 100)         # Vorlauf, Rücklauf (x100 °C), Durchfluss (x10 l/h), Leistung (x100 kW)
blocks, clip_count = [], 0
valid = np.zeros(H)
for key in meter_keys:
    ds = meter[key]["ds"]
    cols = [agg(ds, "vor", "mean"), agg(ds, "rueck", "mean"), agg(ds, "fluss", "sum"), agg(ds, "leistung", "sum")]
    for j, (c, sc) in enumerate(zip(cols, SCALE)):
        a = c.to_numpy(dtype=float)
        nan = np.isnan(a)
        x = np.round(np.nan_to_num(a) * sc)
        clip_count += int((np.abs(x[~nan]) > 32767).sum())
        x = np.clip(x, -32767, 32767)
        x[nan] = -32768
        blocks.append(x.astype("<i2"))
        if j == 0:
            valid += (~nan)
raw = np.concatenate(blocks).tobytes()

# ------------------------------------------------------------------ Kanten und Leistungsaufteilung
quellen = {n for n in G if G.in_degree(n) == 0}
ist_dag = nx.is_directed_acyclic_graph(G)

if ist_dag:
    HG = G
else:
    HG = nx.DiGraph()
    HG.add_nodes_from(G)
    start_knoten = list(quellen) or [max(G, key=G.out_degree)]
    gesehen, fifo = set(start_knoten), list(start_knoten)
    for u in fifo:
        for v in G.successors(u):
            if v not in gesehen:
                gesehen.add(v)
                HG.add_edge(u, v)
                fifo.append(v)

# Pro Node: welche Zähler hängen stromabwärts und mit welchem Anteil
down = {}
for n in reversed(list(nx.topological_sort(HG))):
    d = {}
    if n in mindex:
        d[mindex[n]] = 1.0
    for s in HG.successors(n):
        share = 1.0 / max(HG.in_degree(s), 1)
        for k, v in down[s].items():
            d[k] = d.get(k, 0.0) + v * share
    down[n] = d

edges_js, ohne_pos = [], 0
for u, v in G.edges:
    if u not in nid or v not in nid:
        ohne_pos += 1
        continue
    if HG.has_edge(u, v):
        koef = {k: val / max(HG.in_degree(v), 1) for k, val in down[v].items()}
    else:
        koef = {}
    edges_js.append({"a": nid[u], "b": nid[v],
                     "c": [[int(k), round(float(c), 5)] for k, c in koef.items()]})

nodes_js = []
for n in nodes:
    mi = mindex.get(n, -1)
    nodes_js.append({"name": str(roh.get(n, n)), "lat": float(pos[n][0]), "lon": float(pos[n][1]),
                     "m": mi, "z": meter[n]["z"] if mi >= 0 else "", "k": meter[n]["k"] if mi >= 0 else 0,
                     "est": n in est, "src": n in quellen})

# ------------------------------------------------------------------ Modellergebnisse je Haus
modell = dk.karten_daten(dk.lade(MODELL_ORDNER), START, ENDE)
mst = modell["stationen"]
for n, n_js in zip(nodes, nodes_js):
    mit = [z for z in (meter[n]["zs"] if n in meter else []) if z in mst]
    n_js["st"] = mit
    n_js["hs"] = dk.haus(mst[z] for z in mit)
    n_js["hs_vor"] = dk.haus(mst[z]["vor"] for z in mit if mst[z].get("vor"))
zu_knoten = {z: nid[n] for n in meter for z in meter[n]["zs"]}
reihe = sorted(mst.values(), key=lambda e: (e["rang"] is None, e["rang"] or 0))
modell["liste"] = [[e["z"], zu_knoten.get(e["z"], -1)] for e in reihe]
reihe_vor = sorted((e for e in mst.values() if e.get("vor")),
                   key=lambda e: (e["vor"]["rang"] is None, e["vor"]["rang"] or 0))
modell["liste_vor"] = [[e["z"], zu_knoten.get(e["z"], -1)] for e in reihe_vor]
abgleich = dk.abgleich(zu_knoten, mst)

# Startzeitpunkt: Werktag 8 Uhr im Winter mit möglichst vielen Zählern
cand = np.asarray(idx.month.isin([12, 1, 2]) & (idx.hour == 8) & (idx.dayofweek < 5))
start_idx = int(np.argmax(np.where(cand, valid, -1))) if cand.any() else int(np.argmax(valid))

# ------------------------------------------------------------------ Hintergrund aus den Plandaten (funktioniert ohne Internet)
bg = {"geb": [], "rohr": []}
try:
    import geopandas as gpd
    from shapely.geometry import box

    p_ = gpd.GeoSeries(gpd.points_from_xy([n["lon"] for n in nodes_js], [n["lat"] for n in nodes_js]), crs=4326).to_crs(25832)
    x0, y0, x1, y1 = p_.total_bounds
    fenster = box(x0 - BG_PUFFER_M, y0 - BG_PUFFER_M, x1 + BG_PUFFER_M, y1 + BG_PUFFER_M)

    def als_linien(gdf, limit=30000):
        gdf = gdf[gdf.geometry.notna()]
        if gdf.crs is None or gdf.crs.to_epsg() != 25832:
            gdf = gdf.to_crs(25832)
        g = gdf[gdf.intersects(fenster)].geometry.intersection(fenster).explode(index_parts=False)
        g = g[(g.geom_type == "LineString") & (~g.is_empty)]
        g = g.simplify(0.3).to_crs(4326)
        return [[[round(c[1], 6), round(c[0], 6)] for c in ln.coords] for ln in list(g)[:limit]]

    if "linien" in globals():
        typ = globals()["linien"]["LINIENTYP"]
        bg["geb"] = als_linien(globals()["linien"][typ == 6.0])
        bg["rohr"] += als_linien(globals()["linien"][typ != 6.0])
    if "kml_linien" in globals():
        bg["rohr"] += als_linien(globals()["kml_linien"])
    print(f"Hintergrund: {len(bg['geb'])} Gebäudelinien (Typ 6), {len(bg['rohr'])} Rohrplan-Linien (Shapefile und KML)")
except Exception as ex:
    print("Hintergrund aus Plandaten übersprungen:", type(ex).__name__, ex)

# ------------------------------------------------------------------ Kanten auf die Rohre legen
ROUTE_MAX_ABST_M = 40           # Haus weiter als so weit vom Rohrnetz: Kante bleibt eine gerade Linie
ROUTE_LUECKE_M = 2.5            # kleine Lücken im Plan bis zu diesem Abstand werden überbrückt
try:
    import math
    import shapely
    import geopandas as gpd
    from shapely.geometry import box, LineString
    from shapely.ops import unary_union
    from scipy.spatial import cKDTree
    from pyproj import Transformer

    pn = gpd.GeoSeries(gpd.points_from_xy([n["lon"] for n in nodes_js], [n["lat"] for n in nodes_js]), crs=4326).to_crs(25832)
    xy = np.column_stack([pn.x.values, pn.y.values])
    fe = box(xy[:, 0].min() - 150, xy[:, 1].min() - 150, xy[:, 0].max() + 150, xy[:, 1].max() + 150)
    teile = []
    if "linien" in globals():
        L_ = globals()["linien"]
        teile.append(L_[L_["LINIENTYP"] != 6.0])
    if "kml_linien" in globals():
        teile.append(globals()["kml_linien"])
    geoms = []
    for g in teile:
        g = g[g.geometry.notna()]
        if g.crs is None or g.crs.to_epsg() != 25832:
            g = g.to_crs(25832)
        geoms += [shapely.force_2d(x) for x in g.geometry if x.intersects(fe)]
    if not geoms:
        raise ValueError("keine Rohrlinien (linien / kml_linien) gefunden")
    merged = shapely.segmentize(unary_union([x.intersection(fe) for x in geoms]), 2.0)

    Gp = nx.Graph()
    kz = lambda c: (round(c[0], 1), round(c[1], 1))
    for ln in getattr(merged, "geoms", [merged]):
        if ln.geom_type != "LineString":
            continue
        c = list(ln.coords)
        for a_, b_ in zip(c[:-1], c[1:]):
            ka, kb = kz(a_), kz(b_)
            if ka != kb:
                Gp.add_edge(ka, kb, len=math.hypot(ka[0] - kb[0], ka[1] - kb[1]))
    V = list(Gp.nodes)
    comp = {}
    for i_, cc in enumerate(nx.connected_components(Gp)):
        for n_ in cc:
            comp[n_] = i_
    for i_, j_ in cKDTree(np.array(V)).query_pairs(ROUTE_LUECKE_M):
        if comp[V[i_]] != comp[V[j_]]:
            Gp.add_edge(V[i_], V[j_], len=math.hypot(V[i_][0] - V[j_][0], V[i_][1] - V[j_][1]))
    comp = {}
    gross = {}
    for i_, cc in enumerate(nx.connected_components(Gp)):
        for n_ in cc:
            comp[n_] = i_
        gross[i_] = len(cc)
    V = [v_ for v_ in Gp.nodes if gross[comp[v_]] >= 25]      # Splitter unter ca. 50 m ignorieren
    tree = cKDTree(np.array(V))
    dist_, ix_ = tree.query(xy)
    snap = [V[i_] for i_ in ix_]

    tr = Transformer.from_crs(25832, 4326, always_xy=True)
    ok = fern = 0
    for e_ in edges_js:
        a_, b_ = e_["a"], e_["b"]
        if dist_[a_] > ROUTE_MAX_ABST_M or dist_[b_] > ROUTE_MAX_ABST_M:
            fern += 1
            continue
        sa, sb = snap[a_], snap[b_]
        if sa == sb or comp[sa] != comp[sb]:
            continue
        pfad = nx.shortest_path(Gp, sa, sb, weight="len")
        pts = [tuple(xy[a_])] + pfad + [tuple(xy[b_])]
        ln = LineString(pts).simplify(0.5)
        e_["p"] = [[round(la, 6), round(lo, 6)] for lo, la in (tr.transform(x_, y_) for x_, y_ in ln.coords)]
        ok += 1
    print(f"Kanten auf Rohren: {ok} von {len(edges_js)} | zu weit vom Rohrnetz: {fern} | "
          f"ohne Rohrverbindung: {len(edges_js) - ok - fern} (diese bleiben gerade Linien)")
except Exception as ex:
    print("Rohrführung übersprungen (Kanten bleiben gerade Linien):", type(ex).__name__, ex)

payload = {"t0": idx[0].strftime("%Y-%m-%dT%H:%M"), "H": H, "M": M, "scale": list(SCALE),
           "fluss_min": FLUSS_MIN_LH, "start": start_idx, "nodes": nodes_js, "edges": edges_js,
           "basis": HINTERGRUND, "bg": bg, "punkte": PUNKTE_ZEIGEN, "mt": MELDUNG_TAGE, "modell": modell,
           "b64": base64.b64encode(raw).decode("ascii")}
daten = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
#wissensstand schreibt "Modell LSTM" in die Ursache, im Dashboard heißt es LSTM-Modell
daten = daten.replace("Modell LSTM", "LSTM-Modell").replace("Modell Ivelina", "Modell Monitoring")

VORLAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fernwärme-Dashboard</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--bg:#f2f5f8;--panel:#fff;--ink:#1b2631;--muted:#5d6b79;--line:#d5dce3;--vor:#d6402d;--rueck:#2e6db3;--sel:#0a7d6b;--btn:#f6f8fa;--accent:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#12171d;--panel:#1a222b;--ink:#e6ebf1;--muted:#98a5b3;--line:#2c3743;--vor:#ff6b57;--rueck:#5aa2ee;--sel:#3ed1b8;--btn:#222c36;--accent:#fb923c}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
.app{display:grid;grid-template-columns:minmax(0,1fr) 400px;grid-template-rows:auto minmax(0,1fr);height:100vh}
.bar{grid-column:1 / 3;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 12px;background:var(--panel);border-bottom:1px solid var(--line)}
.bar strong{font-size:16px;margin-right:6px}
.zeit{display:flex;flex-wrap:wrap;gap:8px;align-items:center;flex:1 1 560px}
.bar input[type=range]{flex:1 1 200px;min-width:140px;accent-color:var(--sel)}
button,select,input[type=datetime-local]{font:inherit;color:var(--ink);background:var(--btn);border:1px solid var(--line);border-radius:5px;padding:5px 9px}
button{cursor:pointer}
button:hover{border-color:var(--muted)}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--sel);outline-offset:2px}
#play{min-width:70px;background:var(--ink);color:var(--panel);border-color:var(--ink)}
#tlabel{font-weight:600;min-width:150px}
.tabs{display:flex;gap:2px;padding:2px;border:1px solid var(--line);border-radius:7px;background:var(--btn)}
.tabs button{border:0;background:transparent;padding:4px 11px;border-radius:5px}
.tabs button[aria-selected=true]{background:var(--ink);color:var(--panel)}
.mapwrap{position:relative;min-height:0}
#map{position:absolute;inset:0}
.legend{position:absolute;left:10px;bottom:22px;z-index:500;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px;font-size:12px;width:230px}
.legend .grad{height:10px;border-radius:3px;margin:5px 0 3px}
.legend .row{display:flex;justify-content:space-between;color:var(--muted)}
.legend .kat{display:flex;align-items:center;gap:6px;margin:2px 0}
.legend .kat i{width:11px;height:11px;border-radius:50%;flex:none;border:1px solid #2226}
.legend .kat b{margin-left:auto;font-weight:600}
.legend .l2{margin-top:6px;color:var(--muted);line-height:1.5}
.side{overflow:auto;background:var(--panel);border-left:1px solid var(--line)}
.side section{padding:12px 14px;border-bottom:1px solid var(--line)}
h2{font-size:15px;margin:0 0 8px}
h3{font-size:13px;margin:12px 0 4px;color:var(--muted);font-weight:600}
.kv{display:flex;justify-content:space-between;gap:10px;padding:2px 0}
.kv span{color:var(--muted)}
.kv b{text-align:right}
.muted{color:var(--muted)}
.klein{font-size:12px}
.blk{margin:8px 0}
.blk > span{display:block;color:var(--muted);font-size:12px}
.emp{border-left:4px solid var(--line);padding:6px 0 6px 10px;margin:8px 0}
.emp .kopf{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:3px}
.badge{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;font-weight:600;color:#111;white-space:nowrap}
.zaehler + .zaehler{border-top:1px dashed var(--line);margin-top:8px;padding-top:6px}
canvas{display:block;width:100%;height:130px;margin-top:6px}
#cNet{touch-action:none;cursor:pointer}
.side select{width:100%;margin-bottom:6px}
.side ul,.panel ul{margin:0;padding-left:18px}
.side li,.panel li{margin:3px 0}
.panel{grid-column:1 / 3;overflow:auto;padding:16px 16px 48px;display:none}
.inner{max-width:1100px;margin:0 auto}
.panel h2{font-size:18px;margin:4px 0 10px}
.panel h3{font-size:15px;color:var(--ink);margin:22px 0 8px}
.panel p{max-width:75ch}
.karte{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0}
.tabwrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;background:var(--panel)}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--panel)}
.filter{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
.fluss{display:flex;flex-wrap:wrap;gap:6px;align-items:stretch;margin:8px 0}
.fluss div{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px;flex:1 1 170px}
.fluss div b{display:block}
.app.t-liste .mapwrap,.app.t-liste .side,.app.t-liste .zeit,.app.t-info .mapwrap,.app.t-info .side,.app.t-info .zeit{display:none}
.app.t-liste #vListe,.app.t-info #vInfo{display:block}
.flow-v{animation:fv 1.2s linear infinite}
.flow-r{animation:fr 1.2s linear infinite}
@keyframes fv{to{stroke-dashoffset:-15}}
@keyframes fr{to{stroke-dashoffset:15}}
@media (prefers-reduced-motion:reduce){.flow-v,.flow-r{animation:none}}
@media (max-width:900px){
  .app{display:block;height:auto}
  .mapwrap{height:60vh}
  .side{border-left:0}
  .legend{width:auto;max-width:58%;font-size:11px;padding:6px 8px;bottom:18px}
  .legend .l2{display:none}
}
</style>
</head>
<body>
<div class="app t-karte" id="app">
  <div class="bar">
    <strong>Fernwärme-Dashboard</strong>
    <nav class="tabs" role="tablist" aria-label="Ansicht">
      <button role="tab" data-tab="karte" aria-selected="true">Karte</button>
      <button role="tab" data-tab="liste" aria-selected="false">Handlungsliste</button>
      <button role="tab" data-tab="info" aria-selected="false">So funktioniert's</button>
    </nav>
    <div class="zeit">
      <button id="play">Start</button>
      <button id="bD" title="1 Tag zurück">−1 T</button>
      <button id="bH" title="1 Stunde zurück">−1 h</button>
      <input id="slider" type="range" min="0" value="0" aria-label="Zeitpunkt">
      <button id="fH" title="1 Stunde vor">+1 h</button>
      <button id="fD" title="1 Tag vor">+1 T</button>
      <span id="tlabel"></span>
      <input id="dt" type="datetime-local" aria-label="Zeitpunkt wählen">
      <select id="step" title="Schrittweite beim Abspielen">
        <option value="1">1 h / Schritt</option>
        <option value="6">6 h / Schritt</option>
        <option value="24" selected>1 Tag / Schritt</option>
      </select>
      <select id="metric" title="Färbung der Häuser">
        <optgroup label="Ergebnis der Modelle">
          <option value="dring" selected>Dringlichkeit der Empfehlung</option>
          <option value="mass">Maßnahme und Verdacht auf Fehlerart</option>
          <option value="meld">Meldungen der Wächter</option>
          <option value="pot">Potenzial im Netzvergleich</option>
        </optgroup>
        <optgroup label="Messwerte zur gewählten Stunde">
          <option value="spr">Spreizung</option>
          <option value="vor">Vorlauf</option>
          <option value="rueck">Rücklauf</option>
          <option value="fluss">Durchfluss</option>
          <option value="leist">Leistung</option>
        </optgroup>
      </select>
      <select id="kStand" title="Welcher Stand der Bewertung auf Karte, Hausfenster und Liste gilt" aria-label="Stand der Bewertung">
        <option value="auto">Bewertung: Saison wie Zeitregler</option>
        <option value="vor">Bewertung: vor den Begehungen</option>
        <option value="heute">Bewertung: Stand heute</option>
      </select>
    </div>
  </div>

  <div class="mapwrap">
    <div id="map"></div>
    <div class="legend" id="legend"></div>
  </div>

  <aside class="side">
    <section><h2>Netz</h2><div id="stats"></div></section>
    <section>
      <h2>Haus</h2>
      <select id="selNode" aria-label="Haus wählen"></select>
      <div id="nodeInfo"></div>
      <select id="win" aria-label="Zeitfenster">
        <option value="72">Fenster: 3 Tage</option>
        <option value="336" selected>Fenster: 14 Tage</option>
        <option value="1440">Fenster: 60 Tage</option>
      </select>
      <div class="muted" style="font-size:12px">Vorlauf <span style="color:var(--vor)">■</span> / Rücklauf <span style="color:var(--rueck)">■</span> in °C</div>
      <canvas id="cTemp"></canvas>
      <div class="muted" style="font-size:12px">Spreizung in K (nur Stunden mit Durchfluss)</div>
      <canvas id="cSpr"></canvas>
    </section>
    <section>
      <h2>Gesamtleistung im Zeitverlauf</h2>
      <canvas id="cNet"></canvas>
      <div class="muted" style="font-size:12px">Klicken oder ziehen setzt den Zeitpunkt. Erklärungen im Reiter „So funktioniert's“.</div>
    </section>
  </aside>

  <section class="panel" id="vListe" aria-label="Handlungsliste">
    <div class="inner">
      <h2>Handlungsliste</h2>
      <p class="muted">Alle Zähler mit Modellergebnis, die dringendsten zuerst. Stand: <b id="lStand"></b>.
        <span id="lWechsel">Mit „Saison wie Zeitregler“ zeigt sie vor dem 01.09.2024 den Stand vor den Begehungen, danach den heutigen.
          Die Saison lässt sich hier oder auf der Karte im Feld „Bewertung“ fest wählen, beide Felder sind gekoppelt.</span>
        „Karte“ zeigt das Haus. Warum eine Station hier steht, steht in der Spalte „Warum“. Wie die Reihenfolge entsteht, erklärt der Reiter „So funktioniert's“.</p>
      <div class="filter">
        <select id="fStand" aria-label="Saison der Empfehlung">
          <option value="auto">Saison wie Zeitregler</option>
          <option value="vor">vor den Begehungen</option>
          <option value="heute">Stand heute</option>
        </select>
        <select id="fMass" aria-label="Maßnahme">
          <option value="">alle Maßnahmen</option>
          <option value="reparatur">Reparatur (Regelventil)</option>
          <option value="kapazitaet">Kapazitätsanpassung prüfen</option>
          <option value="daemmung">Dämmung prüfen</option>
          <option value="daten">Daten prüfen</option>
        </select>
        <label><input type="checkbox" id="fAlle"> auch Zähler ohne Handlungsbedarf</label>
        <button type="button" id="bVor">Stand vor den Begehungen</button>
        <button type="button" id="bHeute">Stand heute</button>
        <span class="muted" id="lZahl"></span>
      </div>
      <div class="tabwrap">
        <table>
          <thead><tr><th>Platz</th><th>Zähler</th><th>Dringlichkeit</th><th>Empfohlene Maßnahme</th><th>Warum</th><th>Befund bei der Begehung</th><th></th></tr></thead>
          <tbody id="lBody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="panel" id="vInfo" aria-label="So funktioniert das Dashboard">
    <div class="inner">
      <h2>So funktioniert das Dashboard</h2>
      <p>Das Dashboard beantwortet für jede Hausstation die Fragen der Aufgabenstellung: Wie läuft das Netz, wie läuft die
        Station, hat sich etwas verändert, welcher Fehler steckt dahinter und was soll zuerst gemacht werden. Jede Anzeige
        kommt von dem Modell, das im Vergleich in Notebook 34 dafür am besten abgeschnitten hat. Kein Modell kann alles,
        deshalb arbeiten zwei Ansätze zusammen:</p>
      <ul>
        <li><b>Modell Monitoring:</b> Jede Station hat eine Kennlinie über der Außentemperatur. Ein Konto (CUSUM) zählt, ob sie über
          mehrere Tage davon wegläuft. Dazu wird jede Station mit allen anderen im selben Winter verglichen.</li>
        <li><b>LSTM-Modell:</b> Ein neuronales Netz sagt aus der letzten Woche voraus, wie der heutige Tag aussehen müsste. Ein
          zweites fasst jede Station in wenigen Zahlen zusammen. Daraus schätzt eine Regression die Fehlerart.</li>
      </ul>

      <h3>Drei Reiter</h3>
      <ul>
        <li><b>Karte:</b> die Häuser auf dem Rohrbaum vom Erzeuger. Oben die Färbung wählen, ein Klick auf ein Haus öffnet rechts
          das Hausfenster. Es zeigt immer dieselben Punkte: Empfehlung, Leistung im Netz, Verdacht, Veränderung, Befund.</li>
        <li><b>Handlungsliste:</b> alle Zähler, die dringendsten zuerst.</li>
        <li><b>So funktioniert's:</b> diese Seite.</li>
      </ul>

      <h3>Welche Frage womit beantwortet wird</h3>
      <div class="tabwrap">
      <table>
        <thead><tr><th>Frage</th><th>Wo im Dashboard</th><th>Womit</th><th>Warum dieses Modell</th><th>Wie belastbar</th></tr></thead>
        <tbody>
          <tr><td><b>Wie effizient arbeitet das Netz?</b><br><span class="muted">Datenanalyse, Visualisierung</span></td>
            <td>Seitenleiste „Netz“</td>
            <td>Messwerte, nach Durchfluss gewichtet</td>
            <td>Rücklauf, Spreizung und Wärme je m³ sind Messgrößen. Dafür braucht es kein Modell.</td>
            <td>Messwert. Monate, in denen nur wenige Stationen Daten haben, sind markiert.</td></tr>
          <tr><td><b>Wie gut läuft eine Station im Vergleich, wo liegt Potenzial?</b><br><span class="muted">Datenanalyse, Visualisierung</span></td>
            <td>Färbung „Potenzial“, Hausfenster „Leistung im Netz“</td>
            <td>Modell Monitoring: Netzvergleich je Winter (Notebook 20) und Abstand zum besten Viertel (Notebook 27)</td>
            <td>Nur der Vergleich mit den anderen Stationen sieht eine Station, die schon immer schlecht läuft. Ein Wächter, der
              jede Station mit sich selbst vergleicht, hält das für normal (Notebook 34, Test D).</td>
            <td>Beschreibt, wo die Station steht. Sagt keine Einsparung voraus.</td></tr>
          <tr><td><b>Hat sich an einer Station etwas verändert?</b><br><span class="muted">Anomalieerkennung</span></td>
            <td>Färbung „Meldungen“, Hausfenster „Veränderung“</td>
            <td>An Heiztagen Modell Monitoring (Tagesmonitor: Kennlinie und CUSUM-Konto). An warmen Tagen und bei Stationen ohne
              Referenz das LSTM-Modell (Prognose-LSTM mit CUSUM).</td>
            <td>Der Tagesmonitor bemerkt echte Begehungen am deutlichsten (18 von 43 gegen 24 % an Vergleichsstationen) und
              findet im Winter eingebaute Fehler am besten (Rücklauf +5 K: 47 % gegen 33 %). An warmen Tagen rechnet er nicht.
              Dort findet das LSTM 78 % eines eingebauten Dauerdurchflusses bei 5 % Fehlalarmen, das Wochenmittel nur 45 %.
              Im Winter ergänzt das LSTM die Kennlinie: Es findet plötzliche Sprünge, die sie übersieht (eingebaute Fehler
              51 → 60 %, ohne zusätzliche Fehlalarme). Deshalb stehen seine Meldungen an Heiztagen als Hinweis im Hausfenster.</td>
            <td>Pilot mit Einschränkungen. Eine pendelnde Regelung (Hysterese) findet kein Wächter.</td></tr>
          <tr><td><b>Ist das Regelventil offen?</b><br><span class="muted">Klassifizierung → Reparatur</span></td>
            <td>Färbung „Maßnahme“, Hausfenster „Verdacht“</td>
            <td>LSTM-Modell: logistische Regression nur auf der LSTM-Zusammenfassung (16 Zahlen), nur auf begangenen Stationen gelernt.
              Bestätigung durch das Fehlerbild „ventil“ aus Modell Monitoring.</td>
            <td>Test C (Kreuzvalidierung über Stationsgruppen): AUC 0,83, findet 8 von 11 Ventilfällen bei 4 Fehlalarmen
              (Notebook 34). Mit der Wahl des Modells ohne die Teststationen kommt dasselbe heraus (0,84, Abschnitt 16). Die
              einfache Regel „nachts im Sommer fließt Wasser“ ist genauso gut (0,85). Das Fehlerbild aus Modell Monitoring ist 4 von 4 richtig,
              findet aber nur 4. Es ist dasselbe Modell wie auf der Folie. Weil die Regel genauso gut und leicht verständlich
              ist, steht der Sommernacht-Anteil als Erklärung daneben.</td>
            <td>Pilot. Der Score ist eine Rangfolge, keine Wahrscheinlichkeit.</td></tr>
          <tr><td><b>Sind Leitungen ungedämmt?</b><br><span class="muted">Klassifizierung → Dämmung</span></td>
            <td>Färbung „Maßnahme“, Hausfenster „Verdacht“</td>
            <td>LSTM-Modell: eigenes Dämmungsmodell, Hinweis ab Score <span class="g-daemmung"></span></td>
            <td>Keine einzelne Regel kommt über AUC 0,61, auch wenn man sie an den Befunden einstellt. Die KI findet ein Muster
              in der LSTM-Zusammenfassung, Test C 0,79 (findet 15 von 22 bei 7 Fehlalarmen). Der Vorsprung (+0,18) ist knapp nicht gesichert
              (Notebook 34, Abschnitt 16b).</td>
            <td>Nur Hinweis: Was das Muster physikalisch bedeutet, ist offen, gedämmt wurde eher an Stationen, die im Winter gut
              laufen. Dämmung ist bei 41 % der begangenen Stationen eingetragen, entsprechend oft erscheint der Hinweis.</td></tr>
          <tr><td><b>Ist der Anschluss zu groß?</b><br><span class="muted">Klassifizierung → Kapazitätsanpassung</span></td>
            <td>Färbung „Maßnahme“, Hausfenster „Verdacht“</td>
            <td>Regel ohne Lernen: Spitzenlast im Winter höchstens <span class="g-vertrag"></span> des Anschlusswerts</td>
            <td>AUC 0,76, findet 5 von 9 bei 1 Fehlalarm. Gelernte Modelle kommen nicht über 0,53.</td>
            <td>Pilot mit Einschränkungen, nur 9 Fälle.</td></tr>
          <tr><td><b>Muss die Regelung eingestellt werden?</b><br><span class="muted">Klassifizierung → Regelungsoptimierung</span></td>
            <td>nirgends, bewusst</td>
            <td>–</td>
            <td>Keins der Modelle erkennt sie. Mit K-Means (Folie 5) landen 24 bzw. 25 von 31 Stationen, an denen Durchfluss
              oder Sollwert eingestellt wurden, in „kein Handlungsbedarf“.</td>
            <td>Wird nicht empfohlen. Eine Empfehlung ohne Treffer wäre geraten.</td></tr>
          <tr><td><b>Was soll zuerst gemacht werden?</b><br><span class="muted">Empfehlungssystem</span></td>
            <td>Färbung „Dringlichkeit“, Reiter „Handlungsliste“</td>
            <td>Feste Regel auf den geprüften Ergebnissen oben</td>
            <td><b>hoch:</b> Reparatur, bestätigt durch das Fehlerbild „ventil“ aus Modell Monitoring (4 von 4 richtig).
              <b>mittel:</b> Reparatur nur nach dem Ventil-Score (Test C: 8 von 11 gefunden bei 4 Fehlalarmen).
              <b>niedrig:</b> nur Kapazität, Dämmung (Hinweis) oder Daten prüfen. Innerhalb einer Stufe nach Ventil-Score:
              Unter den ersten 10 nach Score hatten 7 einen Ventilbefund, Zufall wären etwa 2 (Notebook 34, Test E).</td>
            <td>Die Stufen sind gesetzt, nicht gelernt. Ob die Reihenfolge im Betrieb trägt, zeigt erst eine Begehung nach der
              Liste.</td></tr>
        </tbody>
      </table>
      </div>

      <h3>Warum zwei Ansätze und nicht ein Modell für alles?</h3>
      <ul>
        <li>Keins der beiden Modelle ist allein besser. Sie können Verschiedenes (Notebook 34).</li>
        <li>Wir haben ein LSTM gebaut, das genauso arbeitet wie der Tagesmonitor aus Modell Monitoring: feste Referenz statt Vergleich mit der
          Vorwoche. Es ist gleich gut wie die Kennlinie. Den Unterschied macht also die Bauweise, nicht der Modelltyp. Bei
          Gleichstand bleibt das einfachere Modell.</li>
        <li>Das Prognose-LSTM vergleicht jeden Tag mit der Woche davor. Es merkt plötzliche Sprünge, gewöhnt sich aber an
          bleibende Veränderungen. Deshalb färbt es die Karte nur an Tagen, an denen der Tagesmonitor nicht rechnet. An
          Heiztagen stehen seine Meldungen als Hinweis im Hausfenster.</li>
        <li>Für die Fehlerart lernen die Modelle nur auf begangenen Stationen, wie vorgegeben. Die Wächter lernen das
          Normalverhalten auf allen Stationen, die sie überwachen.</li>
      </ul>

      <h3>Geprüft und nicht eingebaut</h3>
      <ul>
        <li><b>XGBoost</b> für die Fehlerart: nicht verlässlich besser, schwankt je nach Startwerten stark.</li>
        <li><b>LSTM mit fester Referenz:</b> gleich gut wie die Kennlinie, also bleibt die einfachere Kennlinie.</li>
        <li><b>Eigenes Sommer-LSTM:</b> nur ein Sommer zum Lernen, kein Vorteil.</li>
        <li><b>Nachbarn im Rohrbaum als Merkmal:</b> Nachbarn teilen kaum Signal (Notebook 28) und verbessern weder Meldung noch
          Erkennung (Notebook 32).</li>
        <li><b>Filter, Sollwert, Durchfluss einstellen und Regelhysterese als Fehlerart:</b> in den Daten nicht erkennbar
          (AUC 0,26 bis 0,57). Sie erscheinen höchstens als Symptom.</li>
      </ul>

      <h3>Bewusst weggelassen, weil die Prüfung es nicht trägt</h3>
      <ul>
        <li><b>Regelungsoptimierung als Empfehlung:</b> K-Means „schlechter als die Optimum-Gruppe“ trifft die Stationen
          nicht, an denen wirklich Regelung oder Durchfluss eingestellt wurde (Kappa 0,21).</li>
        <li><b>Reihenfolge nach Meldungen des Tagesmonitors:</b> Vor Begehungen mit Befund gab es nicht mehr Verschlechterungen
          als bei Kontrollen. Die Meldungen stehen im Hausfenster, ändern die Reihenfolge aber nicht.</li>
        <li><b>Reihenfolge nach Potenzial:</b> Das Potenzial sagt nicht vorher, wo eine Begehung am meisten bringt (rho = 0,16).
          Es bleibt als Beschreibung auf der Karte.</li>
        <li><b>Stufe „hoch“ allein ab einem Ventil-Score von 0,8:</b> Diese Grenze ist nirgends geprüft. „Hoch“ gibt es nur mit
          Bestätigung durch das Fehlerbild aus Modell Monitoring.</li>
        <li><b>Reparatur bei Sonderfällen:</b> Bei Stationen mit Werten außerhalb dessen, woraus die Modelle gelernt haben, oder mit
          einem großen Teil des Netzvolumens ist kein Score geprüft. Sie bekommen nur „Daten prüfen“.</li>
        <li><b>Einspar-Schätzung für das Netz:</b> Sie hätte angenommen, dass jede Station mit Maßnahme den Rücklauf der besten
          Gruppe erreicht. Ob Begehungen den Rücklauf messbar senken, ist nicht gesichert (Notebook 34, Test D).</li>
      </ul>

      <h3>Richtig lesen</h3>
      <ul>
        <li><b>Keine Meldung heißt nicht „in Ordnung“.</b> Es heißt nur: Der Wächter hat nichts Neues gesehen.</li>
        <li><b>„Keine Maßnahme erkannt“ heißt nicht „kein Handlungsbedarf“.</b> Regelungsfehler zum Beispiel erkennt kein
          Modell.</li>
        <li><b>Empfehlung und Verdacht gelten für eine ganze Saison,</b> weil ihre Kennzahlen einen Winter und den Sommer danach
          zusammenfassen. Steht der Zeitregler vor dem 01.09.2024, zeigen Liste, Färbung und Hausfenster den Stand vor den
          Begehungen (Winter 23/24 und Sommer 2024, nur Tage vor der ersten Begehung). Danach den heutigen Stand (Winter
          <span class="g-winter"></span> mit dem Sommer danach). So sieht man, welche Stationen nach den Begehungen aus der Liste
          gefallen sind. Auf der Karte im Feld „Bewertung“ neben der Färbung und in der Handlungsliste lässt sich die Saison auch fest wählen, beide Felder sind gekoppelt.
          Das Potenzial bleibt beim heutigen Stand. Messwerte und Meldungen folgen dem Zeitregler stundengenau.</li>
        <li><b>„Dauerhaft anders als die Referenz“:</b> Das Konto des Tagesmonitors steht am Deckel und kann nichts Neues
          melden. Die Referenz sollte neu gelernt werden.</li>
        <li><b>Orange bei den Meldungen:</b> Viele Stationen wurden gleichzeitig schlechter. Das spricht eher für Wetter oder
          Netz als für das einzelne Haus.</li>
        <li>Stationen, die nie begangen wurden, sind unbekannt, nicht gesund. Eine echte Frühwarnung ist nicht geprüft, weil der
          Beginn eines Fehlers nie bekannt ist.</li>
        <li>Wenige Fälle: 43 Begehungen im Test, 11 Ventil- und 9 Vertragsfälle. „Nicht gesichert“ heißt: Die Daten reichen
          nicht.</li>
      </ul>

      <h3>So liest du die Karte</h3>
      <ul>
        <li>Rote Linie = Vorlauf, blaue Linie = Rücklauf. Die Bewegung folgt dem Rohrbaum vom Erzeuger weg.</li>
        <li>Dicke der Leitung = Wärmeleistung, die stromabwärts abgenommen wird. Die Punkte laufen bei hoher Leistung schneller.</li>
        <li>Blasse Leitungen: Mindestens ein Haus stromabwärts hat in dieser Stunde keine Daten, der Wert ist dann zu niedrig.</li>
        <li>Jedes Haus ist über den kürzesten Rohrweg mit dem Erzeuger verbunden. Ringe im Netz werden dabei aufgelöst, das ist
          eine Annahme.</li>
        <li>Dünne graue Linien im Hintergrund sind Gebäudekanten und Rohrplan aus den Plandaten. Hintergrund und Ebenen oben
          rechts in der Karte umschalten.</li>
        <li><span id="punkteText"></span>Der Punkt mit rotem Ring ist der Erzeuger. Leitungen folgen dem Rohrplan,
          Hausanschlüsse sind gerade Linien.</li>
      </ul>

      <h3>Wie die Daten ins Dashboard kommen</h3>
      <div class="fluss">
        <div><b>Notebook 00</b>Stundenreihen aller Zähler</div>
        <div><b>Notebook 34</b>Modelle gelernt, geprüft und als Pakete gespeichert</div>
        <div><b>python -m src.dashboard_daten</b>Pakete auf die aktuellen Daten angewendet, ohne neu zu lernen</div>
        <div><b>Notebook 35</b>Rohrbaum aus Notebook 28, Karte gebaut</div>
      </div>
      <p class="muted klein" id="infoStand"></p>
    </div>
  </section>
</div>

<script>
(function(){
const D = __DATA__;
const H = D.H, M = D.M, SC = D.scale, NA = -32768, FMIN = D.fluss_min;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const de = (x, d) => (x === null || x === undefined || isNaN(x)) ? '–' : Number(x).toFixed(d === undefined ? 2 : d).replace('.', ',');
const pz = x => (x === null || x === undefined || isNaN(x)) ? '–' : Math.round(100*x) + ' %';

// ---- Daten entpacken
const bin = atob(D.b64), u8 = new Uint8Array(bin.length);
for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
const I16 = new Int16Array(u8.buffer);
function val(m, f, h){ const v = I16[(m*4+f)*H+h]; return v === NA ? NaN : v / SC[f]; }
function spr(m, h){
  const v = val(m,0,h), r = val(m,1,h), f = val(m,2,h);
  return (f > FMIN && !isNaN(v) && !isNaN(r)) ? v - r : NaN;
}

// ---- Modellergebnisse
const MD = D.modell, MST = MD.stationen, MEL = MD.meldungen, UEB = MD.ueberwacht, MT = D.mt, G_ = MD.meta.grenzen;
const QN = ['Tagesmonitor', 'Prognose-LSTM'];
// Stand der Empfehlung: vor dem Wechseltag der Stand vor den Begehungen, danach der heutige
const VOR = MD.meta.vor || null;
const WECHSEL_MS = VOR ? Date.UTC(+VOR.wechsel.slice(0,4), +VOR.wechsel.slice(5,7)-1, +VOR.wechsel.slice(8,10)) : null;
const LEER_VOR = {dr:0, ma:[], rang:null, empfehlung:'keine', warum:'Für die Zeit vor den Begehungen gibt es zu wenige Daten.',
                  ventil:'', p_ventil:null, sommernacht:null, daemmung:false, p_daemmung:null, kapazitaet:false,
                  auslastung:null, fehlerbild:'', sonderfall:''};
//Auswahl auf der Karte bzw. in der Handlungsliste (gekoppelt): wie Zeitregler oder fest auf eine Saison, gilt auch für Karte und Hausfenster
const standWahl = () => $('fStand') ? $('fStand').value : 'auto';
function stand(){
  if (!VOR) return 'heute';
  if (standWahl() !== 'auto') return standWahl();
  return T0 + h*HMS < WECHSEL_MS ? 'vor' : 'heute';
}
function standText(){
  return stand() === 'vor' ? 'vor den Begehungen (Winter ' + VOR.winter_name + ' und Sommer 2024)'
                           : 'heute (Winter ' + MD.meta.winter + ' mit dem Sommer danach)';
}
function S(z){
  const s = MST[z];
  if (!s || stand() !== 'vor') return s;
  return Object.assign({}, s, s.vor || LEER_VOR);
}
const HS = n => stand() === 'vor' ? n.hs_vor : n.hs;
const DR_NAME = ['keine Maßnahme erkannt', 'niedrig', 'mittel', 'hoch'];
const DR_FARBE = ['#1a9850', '#fee08b', '#fc8d59', '#d73027'];
const MA = {reparatur:['Reparatur (Regelventil)', '#d73027'],
            kapazitaet:['Kapazitätsanpassung prüfen', '#8b5cf6'], daemmung:['Dämmung prüfen (Hinweis)', '#2563eb'],
            daten:['Daten prüfen', '#6b7280'], keine:['keine Maßnahme erkannt', '#1a9850']};
const PO = {3:['hoch', '#d73027'], 2:['mittel', '#fc8d59'], 1:['gering', '#1a9850']};
const ME = {schl:['Verschlechterung', '#d73027'], netz:['Verschlechterung, viele Stationen zugleich', '#f59e0b'],
            bess:['nur Verbesserung', '#2563eb'], ruhig:['überwacht, keine Meldung', '#a6d96a'], aus:['nicht überwacht', '#bbbbbb']};
const GRAU = '#bbbbbb';

// ---- Zeit
const T0 = Date.UTC(+D.t0.slice(0,4), +D.t0.slice(5,7)-1, +D.t0.slice(8,10), +D.t0.slice(11,13));
const TAG0 = Date.UTC(+MD.tag0.slice(0,4), +MD.tag0.slice(5,7)-1, +MD.tag0.slice(8,10));
const HMS = 3600000, DMS = 86400000, WD = ['So','Mo','Di','Mi','Do','Fr','Sa'];
const p2 = n => String(n).padStart(2, '0');
function fmt(h){ const d = new Date(T0 + h*HMS); return `${WD[d.getUTCDay()]}, ${p2(d.getUTCDate())}.${p2(d.getUTCMonth()+1)}.${d.getUTCFullYear()}, ${p2(d.getUTCHours())}:00`; }
function fmtDate(h){ const d = new Date(T0 + h*HMS); return `${p2(d.getUTCDate())}.${p2(d.getUTCMonth()+1)}.${String(d.getUTCFullYear()).slice(2)}`; }
function fmtTag(t){ const d = new Date(TAG0 + t*DMS); return `${p2(d.getUTCDate())}.${p2(d.getUTCMonth()+1)}.${String(d.getUTCFullYear()).slice(2)}`; }
function toInput(h){ const d = new Date(T0 + h*HMS); return `${d.getUTCFullYear()}-${p2(d.getUTCMonth()+1)}-${p2(d.getUTCDate())}T${p2(d.getUTCHours())}:00`; }
const tagAt = h => Math.floor((T0 + h*HMS - TAG0)/DMS);
const monatAt = h => { const d = new Date(T0 + h*HMS); return `${d.getUTCFullYear()}-${p2(d.getUTCMonth()+1)}`; };
const EFF = {}; MD.effizienz.forEach(e => { EFF[e.m] = e; });

// ---- Netzreihen über den ganzen Zeitraum
const sumP = new Float32Array(H), nVal = new Uint16Array(H);
for (let h = 0; h < H; h++){
  let s = 0, c = 0, n = 0;
  for (let m = 0; m < M; m++){
    const p = val(m,3,h); if (!isNaN(p)){ s += p; c++; }
    if (!isNaN(val(m,0,h))) n++;
  }
  sumP[h] = c ? s : NaN; nVal[h] = n;
}
const sv = Array.from(sumP).filter(x => !isNaN(x)).sort((a,b) => a-b);
const maxP = sv.length ? Math.max(sv[Math.floor(sv.length*0.99)], 1) : 1;

// ---- Metriken und Farben
const MET = {
  spr:  {name:'Spreizung',  unit:'K',   fn:spr,                       stops:['#d73027','#fee08b','#1a9850']},
  vor:  {name:'Vorlauf',    unit:'°C',  fn:(m,h)=>val(m,0,h),         stops:['#fff3b0','#f59e0b','#b91c1c']},
  rueck:{name:'Rücklauf',   unit:'°C',  fn:(m,h)=>val(m,1,h),         stops:['#e0f2fe','#38bdf8','#1e3a8a']},
  fluss:{name:'Durchfluss', unit:'l/h', fn:(m,h)=>val(m,2,h),         stops:['#f3e8ff','#a855f7','#4c1d95']},
  leist:{name:'Leistung',   unit:'kW',  fn:(m,h)=>val(m,3,h),         stops:['#f3e8ff','#a855f7','#4c1d95']}
};
function qrange(fn){
  const a = [];
  for (let m = 0; m < M; m++) for (let h = 0; h < H; h += 5){ const v = fn(m,h); if (!isNaN(v)) a.push(v); }
  a.sort((x,y) => x-y);
  if (!a.length) return [0,1];
  const lo = a[Math.floor(a.length*0.02)], hi = a[Math.floor(a.length*0.98)];
  return hi > lo ? [lo,hi] : [lo, lo+1];
}
for (const k in MET) MET[k].r = qrange(MET[k].fn);
const hexRGB = c => [1,3,5].map(i => parseInt(c.slice(i,i+2),16));
function colorAt(stops, t){
  t = Math.max(0, Math.min(1, t));
  const n = stops.length-1, x = t*n, i = Math.min(Math.floor(x), n-1), u = x-i;
  const a = hexRGB(stops[i]), b = hexRGB(stops[i+1]);
  return 'rgb(' + a.map((v,k) => Math.round(v + (b[k]-v)*u)).join(',') + ')';
}

// Meldungen eines Hauses in den letzten MT Tagen bis zum Zeitpunkt, nur vom Hauptkanal des Tages
function meldKlasse(n){
  if (!n.st || !n.st.length) return null;
  const t = tagAt(h); let schl = 0, schlNetz = 0, bess = 0, ueb = false;
  for (const z of n.st){
    for (const a of (MEL[z] || [])){
      if (!a[4] || a[0] > t || a[0] <= t - MT) continue;
      if (a[1] > 0){ schl++; if (a[3]) schlNetz++; } else bess++;
    }
    const u = UEB[z]; if (u && t >= 0 && t < u.length && u[t] === '1') ueb = true;
  }
  if (schl) return schl === schlNetz ? 'netz' : 'schl';
  if (bess) return 'bess';
  return ueb ? 'ruhig' : 'aus';
}

// Färbungen aus den Modellen: Klasse je Haus, null = keine Modellergebnisse
const KAT = {
  dring:{name:'Dringlichkeit der Empfehlung', klassen:[3,2,1,0].map(i => [i, DR_NAME[i], DR_FARBE[i]]),
         key:n => HS(n) ? HS(n).dr : null, l2:() => 'Stand ' + standText() + '.' + (!VOR ? '' : (standWahl() === 'auto' ? ' Wechselt mit dem Zeitregler am 01.09.2024.' : ' Saison fest gewählt.'))},
  mass: {name:'Maßnahme und Verdacht', klassen:Object.keys(MA).map(k => [k, MA[k][0], MA[k][1]]),
         key:n => HS(n) ? HS(n).ma : null, l2:() => 'Bei mehreren Maßnahmen zählt die vorderste. Stand ' + standText() + '.'},
  meld: {name:'Meldungen der Wächter', klassen:Object.keys(ME).map(k => [k, ME[k][0], ME[k][1]]),
         key:n => meldKlasse(n), l2:() => 'Meldungen der letzten ' + MT + ' Tage bis ' + fmtDate(h) + '. Heiztage: Tagesmonitor, sonst Prognose-LSTM.'},
  pot:  {name:'Potenzial im Netzvergleich', klassen:[3,2,1].map(i => [i, PO[i][0], PO[i][1]]),
         key:n => (n.hs && n.hs.po) ? n.hs.po : null, l2:() => 'Abstand zum besten Viertel, Winter ' + MD.meta.winter + '.'}
};
function katFarbe(K, k){ const e = K.klassen.find(x => x[0] === k); return e ? e[2] : null; }

// ---- Zustand
let h = Math.max(0, Math.min(H-1, D.start)), metric = 'dring', sel = -1, timer = null;

// ---- Karte
const map = L.map('map', {minZoom:10, maxZoom:21});
const BY_ATT = '© Bayerische Vermessungsverwaltung, GeoBasis-DE / BKG (Daten verändert)';
const by = layer => L.tileLayer('https://wmtsod{s}.bayernwolke.de/wmts/' + layer + '/smerc/{z}/{x}/{y}',
  {subdomains:'123456789', maxNativeZoom:19, maxZoom:21, attribution:BY_ATT});
const BASE = {
  'webkarte': by('by_webkarte'),
  'grau': by('by_webkarte_grau'),
  'luftbild': by('by_dop'),
  'osm': L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© OpenStreetMap-Mitwirkende'}),
  'keiner': L.layerGroup()
};
const BASE_NAMES = {
  'Webkarte Bayern (amtlich)': 'webkarte', 'Webkarte Bayern grau': 'grau', 'Luftbild Bayern': 'luftbild',
  'OpenStreetMap (nur über lokalen Server)': 'osm', 'Kein Hintergrund': 'keiner'
};
const baseForControl = {};
for (const k in BASE_NAMES) baseForControl[k] = BASE[BASE_NAMES[k]];
(BASE[D.basis] || BASE['webkarte']).addTo(map);

// Hintergrund aus den Plandaten: Gebäudekanten (Typ 6) und Rohrplan, funktioniert ohne Internet
const cr = L.canvas({padding:0.3});
const gebL = L.layerGroup(), rohrL = L.layerGroup();
D.bg.geb.forEach(c => L.polyline(c, {renderer:cr, interactive:false, color:'#7b8591', weight:1, opacity:0.85}).addTo(gebL));
D.bg.rohr.forEach(c => L.polyline(c, {renderer:cr, interactive:false, color:'#8aa0b8', weight:1.5, opacity:0.8}).addTo(rohrL));
gebL.addTo(map); rohrL.addTo(map);
const overl = {};
overl['Gebäudekanten (Plan, ' + D.bg.geb.length + ')'] = gebL;
overl['Rohrplan (Shapefile und KML, ' + D.bg.rohr.length + ')'] = rohrL;
L.control.layers(baseForControl, overl, {collapsed:true, position:'topright'}).addTo(map);
const N = D.nodes, E = D.edges;
const OFF = 5;

E.forEach(e => {
  const a = N[e.a], b = N[e.b];
  e.P = e.p && e.p.length > 1 ? e.p : [[a.lat, a.lon], [b.lat, b.lon]];
  const base = {interactive:false, lineCap:'round'};
  e.v  = L.polyline(e.P, Object.assign({}, base, {color:css('--vor'),   weight:3})).addTo(map);
  e.r  = L.polyline(e.P, Object.assign({}, base, {color:css('--rueck'), weight:3})).addTo(map);
  e.fv = L.polyline(e.P, Object.assign({}, base, {color:'#ffffff', weight:1.5, dashArray:'1 14', opacity:0.85, className:'flow-v'})).addTo(map);
  e.fr = L.polyline(e.P, Object.assign({}, base, {color:'#ffffff', weight:1.5, dashArray:'1 14', opacity:0.85, className:'flow-r'})).addTo(map);
  e.hit = L.polyline(e.P, {color:'#000', weight:14, opacity:0, className:'hit'}).addTo(map);
  e.hit.bindTooltip(() => edgeTip(e), {sticky:true});
});

N.forEach((n, i) => {
  // Punkte ohne Zähler (Abzweige, Anschlussstellen) nur auf Wunsch, der Erzeuger immer
  const r = n.m >= 0 ? 6 + 2*Math.min((n.k||1)-1, 3) : (n.src ? 7 : (D.punkte ? 3.5 : 0));
  n.mk = L.circleMarker([n.lat, n.lon], {radius:r, weight:n.src ? 3 : (n.m < 0 && !D.punkte ? 0 : 1),
    color:n.src ? '#e11d48' : '#222222', fillColor:'#aaaaaa', fillOpacity:0.95}).addTo(map);
  n.mk.bindTooltip(() => nodeTip(n), {sticky:true});
  n.mk.on('click', () => { if (n.m >= 0) select(i, true); });
});

function shiftLine(P, sgn, z){
  const q = P.map(p => map.project(p, z));
  return q.map((pt, i) => {
    let nx = 0, ny = 0, c = 0;
    for (const j of [i-1, i]) {
      if (j < 0 || j >= q.length-1) continue;
      const dx = q[j+1].x-q[j].x, dy = q[j+1].y-q[j].y, l = Math.hypot(dx, dy);
      if (!l) continue;
      nx += -dy/l; ny += dx/l; c++;
    }
    const l = Math.hypot(nx, ny);
    if (!c || !l) return map.unproject(pt, z);
    const sc = Math.min(1/Math.max(l/c, 0.5), 2);
    return map.unproject(L.point(pt.x + sgn*OFF*sc*nx/l, pt.y + sgn*OFF*sc*ny/l), z);
  });
}
function layout(){
  const z = map.getZoom();
  E.forEach(e => {
    const fwd = shiftLine(e.P, 1, z), bwd = shiftLine(e.P, -1, z);
    e.v.setLatLngs(fwd); e.fv.setLatLngs(fwd);
    e.r.setLatLngs(bwd); e.fr.setLatLngs(bwd);
    e.hit.setLatLngs(e.P);
  });
}
const lats = N.map(n => n.lat), lons = N.map(n => n.lon);
map.fitBounds([[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], {padding:[30,30]});
map.on('zoomend', layout);
layout();

// ---- Tooltips und Infos
const f1 = (v, d) => isNaN(v) ? '–' : v.toFixed(d === undefined ? 1 : d);
function nodeTip(n){
  if (n.src) return '<b>' + esc(n.name) + '</b><br>Erzeuger (Einspeisung)';
  if (n.m < 0) return '<b>' + esc(n.name) + '</b><br>Abzweig oder Punkt ohne Zähler';
  const m = n.m;
  let mod = '';
  const hs = HS(n);
  if (hs) mod = `<br><b>${esc(MA[hs.ma][0])}</b> · Dringlichkeit ${esc(DR_NAME[hs.dr])}`;
  if (metric === 'meld'){ const k = meldKlasse(n); if (k) mod += '<br>Meldungen: ' + esc(ME[k][0]); }
  return `<b>${esc(n.name)}</b>${mod}<br>Vorlauf ${f1(val(m,0,h))} °C · Rücklauf ${f1(val(m,1,h))} °C<br>Spreizung ${f1(spr(m,h))} K<br>Durchfluss ${f1(val(m,2,h),0)} l/h · Leistung ${f1(val(m,3,h))} kW`
    + (n.est ? '<br><i>Position geschätzt</i>' : '');
}
function edgeTip(e){
  const miss = e.tot === 0 ? 'Keine Zähler stromabwärts' : (e.miss > 0 ? `${e.miss} von ${e.tot} Häusern stromabwärts ohne Daten, Wert zu niedrig` : 'Alle Häuser stromabwärts mit Daten');
  return `<b>${esc(N[e.a].name)} → ${esc(N[e.b].name)}</b><br>Leistung ${f1(e.load)} kW<br><span style="opacity:.8">${miss}</span>`;
}

// ---- Aktualisierung
function updateEdges(){
  E.forEach(e => {
    let load = 0, miss = 0, tot = 0;
    for (const [m, c] of e.c){ tot++; const p = val(m,3,h); if (isNaN(p)) miss++; else load += p*c; }
    e.load = load; e.miss = miss; e.tot = tot;
    const rel = Math.min(load/maxP, 1), w = 2 + 5*Math.sqrt(rel);
    const op = tot === 0 ? 0.25 : (miss > 0 ? 0.45 : 0.95);
    e.v.setStyle({weight:w, opacity:op}); e.r.setStyle({weight:w, opacity:op});
    const dw = Math.max(w*0.45, 1.5), aktiv = load > 0.05;
    e.fv.setStyle({weight:dw, opacity:aktiv ? 0.85 : 0}); e.fr.setStyle({weight:dw, opacity:aktiv ? 0.85 : 0});
    const dur = (4/(0.4 + 3*rel)).toFixed(2) + 's';
    if (e.fv._path) e.fv._path.style.animationDuration = dur;
    if (e.fr._path) e.fr._path.style.animationDuration = dur;
  });
}
function updateNodes(){
  const K = KAT[metric], M_ = MET[metric];
  N.forEach((n, i) => {
    if (n.m < 0){ if (D.punkte && !n.src) n.mk.setStyle({fillColor:'#aaaaaa', fillOpacity:0.8}); return; }
    let fill, op;
    if (K){ const c = katFarbe(K, K.key(n)); fill = c || GRAU; op = c ? 0.95 : 0.45; }
    else { const v = M_.fn(n.m, h); fill = isNaN(v) ? GRAU : colorAt(M_.stops, (v-M_.r[0])/(M_.r[1]-M_.r[0])); op = isNaN(v) ? 0.45 : 0.95; }
    n.mk.setStyle({fillColor:fill, fillOpacity:op, weight:i === sel ? 4 : 1, color:i === sel ? css('--sel') : '#222222'});
    if (i === sel) n.mk.bringToFront();
  });
}
function zaehle(K){
  const c = new Map(); let ohne = 0;
  N.forEach(n => { if (n.m < 0) return; const k = K.key(n); if (k === null || k === undefined) ohne++; else c.set(k, (c.get(k) || 0) + 1); });
  return [c, ohne];
}
function updateLegend(){
  const K = KAT[metric];
  if (K){
    const [c, ohne] = zaehle(K);
    $('legend').innerHTML = `<b>${esc(K.name)}</b>`
      + K.klassen.map(([k, name, farbe]) => `<div class="kat"><i style="background:${farbe}"></i>${esc(name)}<b>${c.get(k) || 0}</b></div>`).join('')
      + (ohne ? `<div class="kat"><i style="background:${GRAU};opacity:.5"></i>keine Modellergebnisse<b>${ohne}</b></div>` : '')
      + `<div class="l2">Zahl = Häuser auf der Karte. ${esc(K.l2())}</div>`;
    return;
  }
  const M_ = MET[metric];
  const grad = 'linear-gradient(90deg,' + M_.stops.join(',') + ')';
  $('legend').innerHTML = `<b>${M_.name} in ${M_.unit}</b><div class="grad" style="background:${grad}"></div>`
    + `<div class="row"><span>${M_.r[0].toFixed(1)}</span><span>${M_.r[1].toFixed(1)}</span></div>`
    + `<div class="l2">Grau: keine Daten oder kein Durchfluss</div>`;
}
const row = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
function updateStats(){
  let n = 0, wf = 0, sv_ = 0, sr = 0;
  for (let m = 0; m < M; m++){
    const v = val(m,0,h), r = val(m,1,h), f = val(m,2,h);
    if (!isNaN(v)) n++;
    if (f > FMIN && !isNaN(v) && !isNaN(r)){ wf += f; sv_ += v*f; sr += r*f; }
  }
  const e = EFF[monatAt(h)];
  const [cm] = zaehle(KAT.meld), [cd] = zaehle(KAT.dring), [cp] = zaehle(KAT.pot);
  $('stats').innerHTML =
    row('Gesamtleistung', f1(sumP[h]) + ' kW') +
    row('Vorlauf / Rücklauf (gewichtet)', wf ? (sv_/wf).toFixed(1) + ' / ' + (sr/wf).toFixed(1) + ' °C' : '–') +
    row('Spreizung (gewichtet)', wf ? ((sv_ - sr)/wf).toFixed(1) + ' K' : '–') +
    row('Häuser mit Messwerten', n + ' von ' + M) +
    '<h3>Netzeffizienz im Monat</h3>' +
    (e ? row('Wärme je m³ Heizwasser', de(e.kwh_m3, 1) + ' kWh/m³') + row('Rücklauf / Spreizung', de(e.rl, 1) + ' °C / ' + de(e.spr, 1) + ' K')
         + (e.ok ? '' : `<div class="muted klein">Nur ${e.n} Stationen mit Daten, mit anderen Monaten nicht vergleichbar.</div>`)
       : '<div class="muted klein">kein Wert für diesen Monat</div>') +
    `<h3>Meldungen der letzten ${MT} Tage</h3>` +
    row('Häuser mit Verschlechterung', ((cm.get('schl') || 0) + (cm.get('netz') || 0)) + (cm.get('netz') ? ` (davon ${cm.get('netz')} zugleich mit vielen)` : '')) +
    row('Häuser nur mit Verbesserung', cm.get('bess') || 0) +
    `<h3>Handlungsbedarf, Winter ${esc(stand() === 'vor' ? VOR.winter_name : MD.meta.winter)}</h3>` +
    row('Dringlichkeit hoch / mittel / niedrig', (cd.get(3) || 0) + ' / ' + (cd.get(2) || 0) + ' / ' + (cd.get(1) || 0)) +
    row('Potenzial hoch', (cp.get(3) || 0) + ' Häuser');
  $('tlabel').textContent = fmt(h) + (n === 0 ? ' (keine Daten)' : '');
}
function blk(titel, inhalt){ return `<div class="blk"><span>${titel}</span>${inhalt}</div>`; }
function verdacht(s){
  const z = [];
  z.push('Ventil: ' + (s.ventil ? `${esc(s.ventil)} (Score ${de(s.p_ventil)}, Grenze ${de(G_.ventil, 1)})` : '–')
    + (s.sommernacht !== null ? ` · Durchfluss in ${pz(s.sommernacht)} der Sommernächte` : '')
    + (s.fehlerbild === 'ventil' ? ' · Fehlerbild „ventil“ im Netzvergleich' : ''));
  z.push('Dämmung: ' + (s.daemmung ? `Hinweis (Score ${de(s.p_daemmung)})` : 'kein Hinweis'));
  z.push('Kapazität: ' + (s.auslastung === null ? '–' : `Spitzenlast ${pz(s.auslastung)} des Anschlusswerts`
    + (s.kapazitaet ? ', Anschluss vermutlich zu groß' : '')));
  if (s.sonderfall) z.push('Sonderfall: ' + esc(s.sonderfall) + ', erst Messdaten prüfen');
  return z.join('<br>');
}
function letzteMeldungen(z){
  const t = tagAt(h), a = (MEL[z] || []).filter(x => x[0] <= t).slice(-4).reverse();
  if (!a.length) return '<span class="muted">keine bis zum gewählten Zeitpunkt</span>';
  return a.map(x => `${fmtTag(x[0])} · ${QN[x[2]]}: ${esc(x[5])}` + (x[1] > 0 ? ' (schlechter)' : ' (besser)')
    + (x[4] ? '' : ' · <i>nur Hinweis</i>') + (x[3] ? ' · viele Stationen zugleich' : '')).join('<br>');
}
function modellBlock(z){
  const s = S(z);
  if (!s) return `<div class="zaehler"><p class="muted">Zähler ${esc(z)}: keine Modellergebnisse.</p></div>`;
  const ma = s.ma.length ? s.ma[0] : 'keine';
  return `<div class="zaehler">`
    + `<div class="emp" style="border-color:${MA[ma][1]}"><div class="kopf"><span class="badge" style="background:${DR_FARBE[s.dr]}">`
    + (s.dr ? 'Dringlichkeit ' + DR_NAME[s.dr] : DR_NAME[0]) + '</span>'
    + `<span class="muted klein">Zähler ${esc(z)}${s.rang ? ' · Platz ' + s.rang + ' von ' + (stand() === 'vor' ? MD.liste_vor.length : MD.meta.stationen) : ''}</span></div>`
    + `<div class="muted klein">Stand ${esc(standText())}</div>`
    + `<b>${esc(s.empfehlung === 'keine' ? 'Keine Maßnahme empfohlen' : s.empfehlung)}</b>`
    + (s.warum ? `<div class="muted klein">${esc(s.warum)}</div>` : '') + '</div>'
    + blk('Leistung im Netz (Winter ' + esc(s.netz_winter || MD.meta.winter) + ')',
          s.netz_rang ? `Rang ${s.netz_rang} von ${s.netz_n} · Potenzial ${esc(s.potenzial || '–')}`
                        + (s.luecke ? `<br><span class="klein">${esc(s.luecke)}</span>` : '')
                      : '<span class="muted">kein Netzvergleich (zu wenige Winterdaten)</span>')
    + blk('Verdacht auf Fehlerart', verdacht(s))
    + blk('Veränderung, letzte Heizperiode', esc(s.veraenderung))
    + blk('Meldungen bis zum gewählten Zeitpunkt', letzteMeldungen(z))
    + blk('Befund bei der Begehung', esc(s.befund))
    + '</div>';
}
function updateNodeInfo(){
  if (sel < 0){ $('nodeInfo').innerHTML = '<p class="muted">Haus auf der Karte oder in der Liste auswählen.</p>'; return; }
  const n = N[sel], m = n.m;
  const zs = n.z ? n.z.split(', ') : [];
  $('nodeInfo').innerHTML = (n.est ? '<p class="muted klein">Position geschätzt</p>' : '')
    + zs.map(modellBlock).join('')
    + '<h3>Messwerte zur gewählten Stunde</h3>'
    + row('Vorlauf / Rücklauf', f1(val(m,0,h)) + ' / ' + f1(val(m,1,h)) + ' °C')
    + row('Spreizung', f1(spr(m,h)) + ' K') + row('Durchfluss', f1(val(m,2,h),0) + ' l/h')
    + row('Leistung', f1(val(m,3,h)) + ' kW');
}

// ---- Diagramme
function drawChart(cv, series, i0, i1, opt){
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, hh = cv.clientHeight;
  if (!w || !hh) return;
  cv.width = Math.round(w*dpr); cv.height = Math.round(hh*dpr);
  const g = cv.getContext('2d'); g.setTransform(dpr,0,0,dpr,0,0);
  const pl = 38, pr = 6, pt = 6, pb = 16, iw = w-pl-pr, ih = hh-pt-pb, n = i1-i0+1;
  let lo = Infinity, hi = -Infinity;
  for (const s of series) for (let i = i0; i <= i1; i++){ const v = s.get(i); if (!isNaN(v)){ if (v < lo) lo = v; if (v > hi) hi = v; } }
  if (!isFinite(lo)){ lo = 0; hi = 1; }
  if (opt.zero) lo = Math.min(lo, 0);
  if (hi - lo < 1e-6) hi = lo + 1;
  const pad = (hi-lo)*0.06; hi += pad; if (!opt.zero || lo < 0) lo -= pad;
  const X = i => pl + (i-i0)/Math.max(n-1,1)*iw, Y = v => pt + ih - (v-lo)/(hi-lo)*ih;
  g.font = '10px system-ui,sans-serif'; g.fillStyle = css('--muted'); g.strokeStyle = css('--line'); g.lineWidth = 1;
  g.textAlign = 'right'; g.textBaseline = 'middle';
  for (let k = 0; k <= 4; k++){
    const v = lo + (hi-lo)*k/4, y = Math.round(Y(v)) + 0.5;
    g.beginPath(); g.moveTo(pl, y); g.lineTo(w-pr, y); g.stroke();
    g.fillText((hi-lo) > 20 ? v.toFixed(0) : v.toFixed(1), pl-4, y);
  }
  g.textBaseline = 'top'; g.textAlign = 'left'; g.fillText(fmtDate(i0), pl, hh-pb+3);
  g.textAlign = 'right'; g.fillText(fmtDate(i1), w-pr, hh-pb+3);
  const step = Math.max(1, Math.floor(n/(iw*1.5)));
  for (const s of series){
    g.beginPath(); let pen = false;
    for (let i = i0; i <= i1; i += step){
      let sum = 0, c = 0;
      for (let j = i; j < Math.min(i+step, i1+1); j++){ const v = s.get(j); if (!isNaN(v)){ sum += v; c++; } }
      if (!c){ pen = false; continue; }
      const x = X(i + (step-1)/2), y = Y(sum/c);
      if (pen) g.lineTo(x, y); else { g.moveTo(x, y); pen = true; }
    }
    g.strokeStyle = s.color; g.lineWidth = s.w || 1.3; g.stroke();
  }
  if (h >= i0 && h <= i1){
    const x = Math.round(X(h)) + 0.5;
    g.strokeStyle = css('--ink'); g.lineWidth = 1; g.setLineDash([3,3]);
    g.beginPath(); g.moveTo(x, pt); g.lineTo(x, pt+ih); g.stroke(); g.setLineDash([]);
  }
}
function winRange(){
  const n = Math.min(+$('win').value, H);
  const i0 = Math.max(0, Math.min(H-n, h - Math.floor(n/2)));
  return [i0, i0+n-1];
}
function drawCharts(){
  drawChart($('cNet'), [{get:i => sumP[i], color:css('--accent'), w:1.2}], 0, H-1, {zero:true});
  if (sel < 0){
    for (const id of ['cTemp','cSpr']){ const cv = $(id), g = cv.getContext('2d'); g.setTransform(1,0,0,1,0,0); g.clearRect(0,0,cv.width,cv.height); }
    return;
  }
  const m = N[sel].m, [i0, i1] = winRange();
  drawChart($('cTemp'), [{get:i => val(m,0,i), color:css('--vor')}, {get:i => val(m,1,i), color:css('--rueck')}], i0, i1, {});
  drawChart($('cSpr'), [{get:i => spr(m,i), color:css('--ink')}], i0, i1, {zero:true});
}

// ---- Handlungsliste
function renderListe(){
  const fm = $('fMass').value, alle = $('fAlle').checked, zeilen = [];
  $('lStand').textContent = standText();
  for (const [z, k] of (stand() === 'vor' ? MD.liste_vor : MD.liste)){
    const s = S(z);
    if (!alle && s.dr === 0) continue;
    if (fm && !s.ma.includes(fm)) continue;
    zeilen.push(`<tr><td>${s.rang || ''}</td><td>${esc(z)}</td>`
      + `<td><span class="badge" style="background:${DR_FARBE[s.dr]}">${esc(DR_NAME[s.dr])}</span></td>`
      + `<td>${esc(s.empfehlung)}</td><td class="klein">${esc(s.warum)}</td><td class="klein">${esc(s.befund)}</td>`
      + `<td>${k >= 0 ? `<button data-k="${k}">Karte</button>` : '<span class="muted klein">nicht auf der Karte</span>'}</td></tr>`);
  }
  $('lBody').innerHTML = zeilen.join('') || '<tr><td colspan="7" class="muted">Keine Zähler für diese Auswahl.</td></tr>';
  $('lZahl').textContent = zeilen.length + ' Zähler';
}

// ---- Reiter
function showTab(t){
  $('app').className = 'app t-' + t;
  document.querySelectorAll('.tabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === t)));
  if (t === 'karte') setTimeout(() => { map.invalidateSize(); layout(); drawCharts(); }, 0);
}
document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
$('lBody').addEventListener('click', e => {
  const b = e.target.closest('button[data-k]'); if (!b) return;
  const i = +b.dataset.k;
  showTab('karte'); map.setView([N[i].lat, N[i].lon], Math.max(map.getZoom(), 18));
  setTimeout(() => select(i, true), 50);
});
$('fMass').addEventListener('change', renderListe);
$('fAlle').addEventListener('change', renderListe);
//Karte und Handlungsliste haben je ein Feld für den Stand, beide zeigen immer denselben Wert
function setStand(v){ $('fStand').value = v; $('kStand').value = v; refresh(); }
$('fStand').addEventListener('change', e => setStand(e.target.value));
$('kStand').addEventListener('change', e => setStand(e.target.value));
// Sprung in die Zeit vor bzw. nach den Begehungen; ohne Stand vor den Begehungen fallen die Knöpfe weg
if (VOR){
  $('bVor').addEventListener('click', () => { $('fStand').value = $('kStand').value = 'auto'; setH(Math.min(H-1, Math.max(0, (WECHSEL_MS - 14*DMS - T0)/HMS))); });
  $('bHeute').addEventListener('click', () => { $('fStand').value = $('kStand').value = 'auto'; setH(H-1); });
} else {
  $('bVor').hidden = true; $('bHeute').hidden = true; $('lWechsel').hidden = true; $('fStand').hidden = true; $('kStand').hidden = true;
}

// ---- Steuerung
let letzterStand = null;
function refresh(){
  updateEdges(); updateNodes(); updateLegend(); updateStats(); updateNodeInfo(); drawCharts();
  if (stand() !== letzterStand){ letzterStand = stand(); renderListe(); }
}
function setH(v){
  h = Math.max(0, Math.min(H-1, Math.round(v)));
  $('slider').value = h; $('dt').value = toInput(h);
  refresh();
}
function select(i, zeigen){
  sel = i;
  $('selNode').value = String(i);
  updateNodes(); updateNodeInfo(); drawCharts();
  // nach einem Klick auf Karte oder Liste das Hausfenster in den sichtbaren Bereich holen
  if (zeigen) $('nodeInfo').closest('section').scrollIntoView({block:'start', behavior:'smooth'});
}
function togglePlay(){
  if (timer){ clearInterval(timer); timer = null; $('play').textContent = 'Start'; return; }
  $('play').textContent = 'Pause';
  timer = setInterval(() => { let nh = h + (+$('step').value); if (nh >= H) nh = 0; setH(nh); }, 250);
}

$('slider').max = H-1;
$('dt').min = toInput(0); $('dt').max = toInput(H-1);
$('slider').addEventListener('input', e => setH(+e.target.value));
$('dt').addEventListener('change', e => {
  const v = e.target.value; if (!v) return;
  const t = Date.UTC(+v.slice(0,4), +v.slice(5,7)-1, +v.slice(8,10), +v.slice(11,13));
  setH((t - T0)/HMS);
});
$('play').addEventListener('click', togglePlay);
$('bH').addEventListener('click', () => setH(h-1));
$('fH').addEventListener('click', () => setH(h+1));
$('bD').addEventListener('click', () => setH(h-24));
$('fD').addEventListener('click', () => setH(h+24));
$('metric').addEventListener('change', e => { metric = e.target.value; updateLegend(); updateNodes(); });
$('win').addEventListener('change', drawCharts);

const opts = ['<option value="-1">– Haus wählen –</option>'];
N.map((n, i) => ({n, i})).filter(x => x.n.m >= 0).sort((a, b) => a.n.name.localeCompare(b.n.name, 'de'))
  .forEach(x => opts.push(`<option value="${x.i}">${esc(x.n.name)}</option>`));
$('selNode').innerHTML = opts.join('');
$('selNode').addEventListener('change', e => {
  const i = +e.target.value;
  if (i < 0){ sel = -1; updateNodes(); updateNodeInfo(); drawCharts(); } else select(i);
});

(function(){
  const cv = $('cNet'); let down = false;
  const f = e => {
    const r = cv.getBoundingClientRect();
    const x = (e.clientX - r.left - 38)/(r.width - 44);
    setH(Math.max(0, Math.min(1, x))*(H-1));
  };
  cv.addEventListener('pointerdown', e => { down = true; cv.setPointerCapture(e.pointerId); f(e); });
  cv.addEventListener('pointermove', e => { if (down) f(e); });
  cv.addEventListener('pointerup', () => { down = false; });
})();
window.addEventListener('resize', drawCharts);

// ---- Texte mit Werten aus den Paketen
document.querySelectorAll('.g-winter').forEach(x => { x.textContent = MD.meta.winter; });
document.querySelectorAll('.g-daemmung').forEach(x => { x.textContent = de(G_.daemmung, 1); });
document.querySelectorAll('.g-vertrag').forEach(x => { x.textContent = pz(G_.vertrag); });
$('punkteText').textContent = D.punkte ? 'Graue Punkte sind Abzweige und Anschlussstellen am Rohr. ' : '';
const pk = MD.meta.pakete || {};
$('infoStand').textContent = 'Stand: Modellpakete ' + Object.keys(pk).map(k => k + ' ' + pk[k]).join(', ')
  + '; angewendet am ' + String(MD.meta.erstellt).slice(0, 10) + '; Messdaten bis ' + MD.meta.datenende
  + '. Zahlen zur Güte aus Notebook 34.';

letzterStand = stand(); renderListe();
setH(h);
})();
</script>
</body>
</html>
"""

html = VORLAGE.replace("__DATA__", daten)
Path(AUSGABE).write_text(html, encoding="utf-8")

print(f"Geschrieben: {Path(AUSGABE).resolve()}  ({Path(AUSGABE).stat().st_size / 1e6:.1f} MB)")
print(f"Zeitraum: {idx[0]} bis {idx[-1]} ({H} Stunden)")
print(f"Häuser mit Zeitreihe: {M} | Nodes: {len(nodes_js)} | Kanten: {len(edges_js)}"
      + (f" ({ohne_pos} ohne Position, nicht gezeigt)" if ohne_pos else ""))
print(f"Modellergebnisse: {len(mst)} Zähler, Pakete {modell['meta']['pakete']}")
print(f"Häuser mit Modellergebnis: {sum(1 for n in nodes_js if n['hs'])} von {M} | "
      f"Zähler mit Modellergebnis, aber nicht auf der Karte: {len(abgleich['modell_nicht_auf_karte'])}")
print("Graph ist ohne Kreise:", ist_dag, "| Quellen:", len(quellen))
if not ist_dag:
    print("WARNUNG: Der Graph hat Kreise. Die Leistung wird nur entlang eines Spannbaums von den Quellen aus berechnet.")
if clip_count:
    print(f"WARNUNG: {clip_count} Werte lagen außerhalb des Speicherbereichs und wurden gekappt.")
print("Startzeitpunkt im Dashboard:", idx[start_idx])
print("Datei im Browser öffnen (Doppelklick). Karte und Hintergrundkacheln brauchen Internet (Leaflet und Webkarte Bayern).")
print("Achtung: Die Datei enthält Adressen und Zählerdaten. Nicht weitergeben.")
