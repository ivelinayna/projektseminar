# dashboard_monitor.py
# Kopie von dashboard_export.py aus Notebook 16 (Netz), erweitert um den Status des
# Kennlinien-Monitors (Notebooks 21 bis 24). Das Original bleibt unverändert.
# Im Notebook 25 ausführen, dort sind serien, knoten, G, pos, roh und ROOT gesetzt.
#
# Erzeugt eine eigenständige HTML-Datei: Karte mit Zeitregler (stündlich), Fließanimation entlang
# der Kanten, Färbung der Häuser nach Spreizung/Vorlauf/Rücklauf/Durchfluss/Leistung und Verläufen.
# Dazu kommen zwei Färbungen aus dem Monitor (Priorität je Winter, Alarme der letzten 14 Tage),
# Monitorzeilen im Hausfenster und ein Hinweis, wenn der Zeitpunkt in einer Netzereignis-Episode liegt.
# Über "Ganze Analyse" im Hausfenster öffnet sich das Stationsblatt des Zählers mit Befundtext,
# dazu Carpet und Dauerlinie. Die Bilder werden verlinkt, nicht eingebettet.
# Eingaben: outputs/monitor_status.csv, outputs/monitor_alarme.csv, outputs/netzereignistage.csv,
# outputs/stationsblatt/ (python -m src.stationsblatt), outputs/stationsbilder/carpet, .../dauerlinie

import json
import base64
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx

# ------------------------------------------------------------------ Einstellungen
START = "2024-01-01 00:00"      # Zeitraum mit konsistenten Daten
ENDE = "2025-05-31 23:00"
FLUSS_MIN_LH = 0.5              # Stunden mit Durchfluss bis zu diesem Wert haben keine aussagekräftige Spreizung
AUSGABE = globals().get("AUSGABE_MONITOR", "netzkarte_monitor.html")
MONITOR_ORDNER = Path(globals().get("ROOT", Path.cwd())) / "outputs"
ALARM_FENSTER_TAGE = 14         #Färbung "Alarme": Alarmbeginn (CUSUM-Schätzung) höchstens so weit vor dem Zeitpunkt

# Hintergrundkarte beim Öffnen: "webkarte" (amtliche Webkarte Bayern), "grau", "luftbild", "osm" oder "keiner".
# Im Dashboard oben rechts umschaltbar. OpenStreetMap blockiert Seiten, die direkt als Datei geöffnet werden.
HINTERGRUND = "webkarte"
BG_PUFFER_M = 200               # Rohrplan und Gebäudekanten werden bis zu diesem Abstand um die Häuser mitgezeichnet

# ------------------------------------------------------------------ Voraussetzungen prüfen
fehlt = [n for n in ("serien", "knoten", "G", "pos", "roh") if n not in globals()]
if fehlt:
    raise SystemExit(f"Diese Variablen fehlen im Notebook: {fehlt}. "
                     "Bitte zuerst die Zellen für Zeitreihen (serien) und Kanten-Karte (knoten, G, pos, roh) ausführen.")

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
    ds = [serien[z].reindex(idx) for z in zs if z in serien]
    if not ds:
        continue
    meter[r.edge_node] = {"ds": ds, "z": ", ".join(zs), "k": len(zs), "adresse": str(r.adresse)}

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

# ------------------------------------------------------------------ Monitorstatus je Haus
#Mehrere Zähler an einem Knoten: schlechteste Priorität zählt, Alarme werden zusammengelegt
PRIO_CODE = {"hoch": 3, "mittel": 2, "niedrig": 1}
t0_tag = idx[0].normalize()


def _stunde(d):
    return int((pd.Timestamp(d).normalize() - t0_tag) / pd.Timedelta(hours=1))


mon_status = pd.read_csv(MONITOR_ORDNER / "monitor_status.csv", dtype={"meter": str})
mon_alarme = pd.read_csv(MONITOR_ORDNER / "monitor_alarme.csv", dtype={"meter": str},
                         parse_dates=["datum", "beginn"])
mon_ereig = pd.read_csv(MONITOR_ORDNER / "netzereignistage.csv", parse_dates=["von", "bis"])
for t in (mon_status, mon_alarme):
    t["meter"] = t["meter"].map(norm_z)

mit_status = set()
for n, nj in zip(nodes, nodes_js):
    if nj["m"] < 0:
        continue
    zs = nj["z"].split(", ")
    st = mon_status[mon_status["meter"].isin(zs)]
    win = {}
    for w, g in st.groupby("winter"):
        g = g.assign(code=g["prioritaet"].map(PRIO_CODE).fillna(0)).sort_values(["code", "score"])
        top = g.iloc[-1]
        win[w] = {"p": int(top["code"]), "sc": None if pd.isna(top["score"]) else round(float(top["score"]), 2),
                  "rg": None if pd.isna(top["rang"]) else int(top["rang"]),
                  "fb": "" if pd.isna(top["fehlerbild"]) else str(top["fehlerbild"]),
                  "ch": bool(g["chronisch"].any()),
                  "ns": int(g["alarme_schlechter"].sum()), "nb": int(g["alarme_besser"].sum()),
                  "ne": int(g["alarme_netzereignis"].sum()), "nn": int(g["alarme_nachbar"].sum())}
    al = mon_alarme[mon_alarme["meter"].isin(zs)]
    nj["mon"] = {"w": win,
                 "a": [[_stunde(r.datum), _stunde(r.beginn), 1 if r.bewertung == "schlechter" else -1,
                        int(bool(r.netzereignis)), int(bool(r.nachbar_gleichzeitig)), str(r.kanal)]
                       for r in al.itertuples()]}
    if win:
        mit_status.add(n)

ereignisse_js = [[_stunde(r.von), _stunde(r.bis) + 23, str(r.richtung), int(r.n_stationen)]
                 for r in mon_ereig.itertuples()]
print(f"Monitorstatus: {len(mit_status)} von {M} Häusern mit Zeitreihe haben einen Status, "
      f"{mon_status['meter'].nunique()} Zähler im Monitor, {len(ereignisse_js)} Netzereignis-Episoden")

#Analysebilder je Zähler, Pfade relativ zur HTML-Datei, damit der Ordner outputs/ verschiebbar bleibt
if str(MONITOR_ORDNER.parent) not in sys.path:
    sys.path.insert(0, str(MONITOR_ORDNER.parent))
from src.stationsblatt import statustext

BILDER = {"blatt": MONITOR_ORDNER / "stationsblatt",
          "carpet": MONITOR_ORDNER / "stationsbilder" / "carpet",
          "dauer": MONITOR_ORDNER / "stationsbilder" / "dauerlinie"}
html_ordner = Path(AUSGABE).resolve().parent
blatt_status = pd.read_csv(BILDER["blatt"] / "status.csv", dtype={"meter": str})
blatt_status["meter"] = blatt_status["meter"].map(norm_z)
blatt_text = {r["meter"]: statustext(r) for r in blatt_status.to_dict("records")}
n_blatt = 0
for nj in nodes_js:
    eintraege = []
    for z in ([] if nj["m"] < 0 else nj["z"].split(", ")):
        pfade = {k: os.path.relpath(o / f"{z}.png", html_ordner).replace("\\", "/")
                 for k, o in BILDER.items() if (o / f"{z}.png").exists()}
        if pfade:
            eintraege.append([z, pfade, blatt_text.get(z, "")])
    nj["bl"] = eintraege
    n_blatt += bool(eintraege)
print(f"Ganze Analyse: {n_blatt} von {M} Häusern mit Zeitreihe haben ein Stationsblatt oder Stationsbild")

# Startzeitpunkt: Werktag 8 Uhr im Winter mit möglichst vielen Zählern
cand = np.asarray(idx.month.isin([12, 1, 2]) & (idx.hour == 8) & (idx.dayofweek < 5))
start_idx = int(np.argmax(np.where(cand, valid, -1))) if cand.any() else int(np.argmax(valid))

# ------------------------------------------------------------------ Hintergrund aus deinen Plandaten (funktioniert ohne Internet)
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
        raise ValueError("keine Rohrlinien (linien / kml_linien) im Notebook gefunden")
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
           "basis": HINTERGRUND, "bg": bg, "ereig": ereignisse_js, "afenster": ALARM_FENSTER_TAGE,
           "b64": base64.b64encode(raw).decode("ascii")}
daten = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

VORLAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fernwärme-Dashboard mit Monitor</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--bg:#f2f5f8;--panel:#fff;--ink:#1b2631;--muted:#5d6b79;--line:#d5dce3;--vor:#d6402d;--rueck:#2e6db3;--sel:#0a7d6b;--btn:#f6f8fa;--accent:#c2410c}
@media (prefers-color-scheme:dark){:root{--bg:#12171d;--panel:#1a222b;--ink:#e6ebf1;--muted:#98a5b3;--line:#2c3743;--vor:#ff6b57;--rueck:#5aa2ee;--sel:#3ed1b8;--btn:#222c36;--accent:#fb923c}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
.app{display:grid;grid-template-columns:minmax(0,1fr) 390px;grid-template-rows:auto minmax(0,1fr);height:100vh}
.bar{grid-column:1 / 3;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 12px;background:var(--panel);border-bottom:1px solid var(--line)}
.bar strong{font-size:16px;margin-right:6px}
.bar input[type=range]{flex:1 1 220px;min-width:140px;accent-color:var(--sel)}
button,select,input[type=datetime-local]{font:inherit;color:var(--ink);background:var(--btn);border:1px solid var(--line);border-radius:5px;padding:5px 9px}
button{cursor:pointer}
button:hover{border-color:var(--muted)}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--sel);outline-offset:2px}
#play{min-width:70px;background:var(--ink);color:var(--panel);border-color:var(--ink)}
#tlabel{font-weight:600;min-width:150px}
.mapwrap{position:relative;min-height:0}
#map{position:absolute;inset:0}
.legend{position:absolute;left:10px;bottom:22px;z-index:500;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px;font-size:12px;width:210px}
.legend .grad{height:10px;border-radius:3px;margin:5px 0 3px}
.legend .row{display:flex;justify-content:space-between;color:var(--muted)}
.legend .l2{margin-top:6px;color:var(--muted);line-height:1.5}
.side{overflow:auto;background:var(--panel);border-left:1px solid var(--line)}
.side section{padding:12px 14px;border-bottom:1px solid var(--line)}
h2{font-size:15px;margin:0 0 8px}
.kv{display:flex;justify-content:space-between;gap:10px;padding:2px 0}
.kv span{color:var(--muted)}
.muted{color:var(--muted)}
canvas{display:block;width:100%;height:130px;margin-top:6px}
#cNet{touch-action:none;cursor:pointer}
.side select{width:100%;margin-bottom:6px}
.side ul{margin:0;padding-left:18px;color:var(--muted);font-size:13px}
.side li{margin:3px 0}
.flow-v{animation:fv 1.2s linear infinite}
.flow-r{animation:fr 1.2s linear infinite}
@keyframes fv{to{stroke-dashoffset:-15}}
@keyframes fr{to{stroke-dashoffset:15}}
@media (prefers-reduced-motion:reduce){.flow-v,.flow-r{animation:none}}
@media (max-width:900px){
  .app{display:block;height:auto}
  .mapwrap{height:60vh}
  .side{border-left:0}
}
.btn-analyse{width:100%;margin:8px 0 4px;background:var(--sel);color:#fff;border-color:var(--sel);font-weight:600}
.ov{position:fixed;inset:0;z-index:3000;background:rgba(0,0,0,.55);display:none;align-items:center;justify-content:center}
.ov.auf{display:flex}
.ovbox{background:var(--panel);color:var(--ink);width:min(1600px,97vw);height:95vh;border-radius:8px;display:grid;grid-template-rows:auto minmax(0,1fr);overflow:hidden}
.ovkopf{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 12px;border-bottom:1px solid var(--line)}
.ovkopf b{font-size:15px;margin-right:8px}
.ovkopf .tab.an{background:var(--ink);color:var(--panel);border-color:var(--ink)}
.ovinhalt{display:grid;grid-template-columns:minmax(0,1fr) 380px;min-height:0}
.ovbild{overflow:auto;padding:8px;background:#fff}
.ovbild img{max-width:100%;height:auto;display:block;margin:0 auto;cursor:zoom-in}
.ovbild.gross img{max-width:none;cursor:zoom-out}
.ovtext{overflow:auto;padding:12px 14px;border-left:1px solid var(--line);font-size:13px}
.ovtext pre{white-space:pre-wrap;font:12px/1.45 ui-monospace,Consolas,monospace;margin:0 0 12px}
.ovtext ol{margin:0;padding-left:20px}
.ovtext li{margin:5px 0}
@media (max-width:900px){.ovinhalt{grid-template-columns:1fr}.ovtext{border-left:0;border-top:1px solid var(--line)}}
</style>
</head>
<body>
<div class="app">
  <div class="bar">
    <strong>Fernwärme-Dashboard</strong>
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
      <option value="24">1 Tag / Schritt</option>
    </select>
    <select id="metric" title="Färbung der Häuser">
      <option value="prio" selected>Monitor: Priorität im Winter</option>
      <option value="alarm">Monitor: Alarme der letzten Tage</option>
      <option value="spr">Häuser: Spreizung</option>
      <option value="vor">Häuser: Vorlauf</option>
      <option value="rueck">Häuser: Rücklauf</option>
      <option value="fluss">Häuser: Durchfluss</option>
      <option value="leist">Häuser: Leistung</option>
    </select>
  </div>

  <div class="mapwrap">
    <div id="map"></div>
    <div class="legend" id="legend"></div>
  </div>

  <aside class="side">
    <section><h2>Netz zum gewählten Zeitpunkt</h2><div id="stats"></div></section>
    <section><h2>Monitor zum gewählten Zeitpunkt</h2><div id="monStats"></div></section>
    <section>
      <h2>Gesamtleistung im Zeitverlauf</h2>
      <canvas id="cNet"></canvas>
      <div class="muted" style="font-size:12px">Klicken oder ziehen setzt den Zeitpunkt.</div>
    </section>
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
      <h2>So liest du die Karte</h2>
      <ul>
        <li>Rote Linie = Vorlauf, blaue Linie = Rücklauf. Die Pfeilrichtung der Bewegung folgt der Richtung in deiner Kantendatei.</li>
        <li>Dicke der Leitung = Wärmeleistung, die stromabwärts abgenommen wird. Die Punkte laufen bei hoher Leistung schneller.</li>
        <li>Blasse Leitungen: mindestens ein Haus stromabwärts hat in dieser Stunde keine Daten, der Wert ist dann zu niedrig.</li>
        <li>Wo mehrere Leitungen in einen Punkt münden, wird die Last gleichmäßig aufgeteilt. Das ist eine Annahme.</li>
        <li>Dünne graue Linien im Hintergrund sind Gebäudekanten und Rohrplan aus deinen Plandaten. Hintergrund und Ebenen schaltest du oben rechts in der Karte um.</li>
        <li>Graue Punkte sind Abzweige ohne Zähler. Punkte mit rotem Ring sind Quellen im Graphen. Linien sind Luftlinien, nicht der Rohrverlauf.</li>
        <li>Monitor: Priorität: Farbe aus der Alarmbewertung des Kennlinien-Monitors für den Winter, in dem der Zeitpunkt liegt. Zwischen Mai und September gilt der letzte Winter. Bei mehreren Zählern an einem Haus zählt der schlechteste.</li>
        <li>Monitor: Alarme: Alarme, die laut CUSUM-Schätzung in den letzten Tagen vor dem Zeitpunkt begonnen haben. Gemeldet werden sie oft erst Tage später. Orange heißt, alle Verschlechterungen fallen auf eine Episode, in der viele Stationen gleichzeitig alarmieren. Das ist ein Hinweis auf eine Ursache im Netz oder im Wetter, kein Nachweis.</li>
        <li>Der Monitor läuft nur in der Heizperiode. Im Sommer gibt es keine Alarme.</li>
        <li>Ganze Analyse: Haus wählen und im Hausfenster auf den Knopf klicken. Dann öffnet sich das Stationsblatt mit allen Schritten des Monitors, dazu Carpet und Dauerlinie. Die Bilder liegen in outputs/stationsblatt und outputs/stationsbilder und werden nur verlinkt.</li>
      </ul>
    </section>
  </aside>
</div>

<div id="ov" class="ov" role="dialog" aria-modal="true" aria-labelledby="ovTitel">
  <div class="ovbox">
    <div class="ovkopf"><b id="ovTitel"></b><span id="ovTabs"></span><span style="flex:1"></span><button id="ovZu" title="Schließen (Esc)">Schließen</button></div>
    <div class="ovinhalt"><div class="ovbild" id="ovBild"></div><div class="ovtext" id="ovText"></div></div>
  </div>
</div>

<script>
(function(){
const D = __DATA__;
const H = D.H, M = D.M, SC = D.scale, NA = -32768, FMIN = D.fluss_min;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

// ---- Daten entpacken
const bin = atob(D.b64), u8 = new Uint8Array(bin.length);
for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
const I16 = new Int16Array(u8.buffer);
function val(m, f, h){ const v = I16[(m*4+f)*H+h]; return v === NA ? NaN : v / SC[f]; }
function spr(m, h){
  const v = val(m,0,h), r = val(m,1,h), f = val(m,2,h);
  return (f > FMIN && !isNaN(v) && !isNaN(r)) ? v - r : NaN;
}

// ---- Zeit
const T0 = Date.UTC(+D.t0.slice(0,4), +D.t0.slice(5,7)-1, +D.t0.slice(8,10), +D.t0.slice(11,13));
const HMS = 3600000, WD = ['So','Mo','Di','Mi','Do','Fr','Sa'];
const p2 = n => String(n).padStart(2, '0');
function fmt(h){ const d = new Date(T0 + h*HMS); return `${WD[d.getUTCDay()]}, ${p2(d.getUTCDate())}.${p2(d.getUTCMonth()+1)}.${d.getUTCFullYear()}, ${p2(d.getUTCHours())}:00`; }
function fmtDate(h){ const d = new Date(T0 + h*HMS); return `${p2(d.getUTCDate())}.${p2(d.getUTCMonth()+1)}.${String(d.getUTCFullYear()).slice(2)}`; }
function toInput(h){ const d = new Date(T0 + h*HMS); return `${d.getUTCFullYear()}-${p2(d.getUTCMonth()+1)}-${p2(d.getUTCDate())}T${p2(d.getUTCHours())}:00`; }

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

// ---- Monitor (Kennlinien-Monitor, Notebooks 21 bis 24)
const AF = D.afenster, EV = D.ereig;
const PRIO_NAME = ['kein Status', 'niedrig', 'mittel', 'hoch'];
const PRIO_FARBE = ['#bbbbbb', '#1a9850', '#fc8d59', '#d73027'];
const A_FARBE = {schl:'#d73027', netz:'#f59e0b', bess:'#2563eb', ruhig:'#a6d96a', aus:'#bbbbbb'};
function winterAt(h){
  const d = new Date(T0 + h*HMS), y = d.getUTCFullYear(), mo = d.getUTCMonth() + 1;
  const a = mo >= 10 ? y : y - 1;
  return {w: p2(a % 100) + '/' + p2((a + 1) % 100), sommer: mo >= 5 && mo <= 9};
}
function monW(n){ const w = winterAt(h).w; return n.mon && n.mon.w[w] ? n.mon.w[w] : null; }
function monAlarme(n){ return n.mon ? n.mon.a.filter(a => a[1] <= h && a[1] > h - AF*24) : []; }
function alarmKlasse(n){
  if (!n.mon || !Object.keys(n.mon.w).length) return 'aus';
  const a = monAlarme(n), s = a.filter(x => x[2] > 0);
  if (s.length) return s.every(x => x[3]) ? 'netz' : 'schl';
  return a.length ? 'bess' : 'ruhig';
}
const KAT = {
  prio: {name:'Priorität im Winter', farbe:n => { const w = monW(n); return PRIO_FARBE[w ? w.p : 0]; },
         leg:() => [3,2,1,0].map(i => [PRIO_FARBE[i], PRIO_NAME[i]]),
         l2:() => { const w = winterAt(h); return 'Winter ' + w.w + (w.sommer ? ' (Sommer, letzter Winter)' : ''); }},
  alarm:{name:'Alarme der letzten ' + AF + ' Tage', farbe:n => A_FARBE[alarmKlasse(n)],
         leg:() => [[A_FARBE.schl,'Verschlechterung'],[A_FARBE.netz,'Verschlechterung, nur in Netzereignis'],
                    [A_FARBE.bess,'nur Verbesserung'],[A_FARBE.ruhig,'kein Alarm'],[A_FARBE.aus,'nicht im Monitor']],
         l2:() => 'Alarmbeginn zwischen ' + fmtDate(Math.max(0, h - AF*24)) + ' und ' + fmtDate(h)}
};
function ereignisAt(h){ return EV.filter(e => h >= e[0] && h <= e[1]); }
const hexRGB = c => [1,3,5].map(i => parseInt(c.slice(i,i+2),16));
function colorAt(stops, t){
  t = Math.max(0, Math.min(1, t));
  const n = stops.length-1, x = t*n, i = Math.min(Math.floor(x), n-1), u = x-i;
  const a = hexRGB(stops[i]), b = hexRGB(stops[i+1]);
  return 'rgb(' + a.map((v,k) => Math.round(v + (b[k]-v)*u)).join(',') + ')';
}

// ---- Zustand
let h = Math.max(0, Math.min(H-1, D.start)), metric = document.getElementById('metric').value, sel = -1, timer = null;

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
  const r = n.m >= 0 ? 6 + 2*Math.min((n.k||1)-1, 3) : 3.5;
  n.mk = L.circleMarker([n.lat, n.lon], {radius:r, weight:n.src ? 3 : 1, color:n.src ? '#e11d48' : '#222222', fillColor:'#aaaaaa', fillOpacity:0.95}).addTo(map);
  n.mk.bindTooltip(() => nodeTip(n), {sticky:true});
  n.mk.on('click', () => { if (n.m >= 0) select(i); });
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
  if (n.m < 0) return '<b>' + esc(n.name) + '</b><br>Abzweig oder Punkt ohne Zähler';
  const m = n.m;
  return `<b>${esc(n.name)}</b><br>Vorlauf ${f1(val(m,0,h))} °C · Rücklauf ${f1(val(m,1,h))} °C<br>Spreizung ${f1(spr(m,h))} K<br>Durchfluss ${f1(val(m,2,h),0)} l/h · Leistung ${f1(val(m,3,h))} kW`
    + monTip(n)
    + (n.est ? '<br><i>Position geschätzt</i>' : '');
}
function monTip(n){
  const w = monW(n);
  if (!w) return '<br>Monitor: kein Status im Winter ' + winterAt(h).w;
  const a = monAlarme(n);
  return `<br>Monitor ${winterAt(h).w}: Priorität ${PRIO_NAME[w.p]}` + (w.fb ? `, Fehlerbild ${esc(w.fb)}` : '')
    + (w.ch ? ', chronisch' : '') + (a.length ? `<br>${a.length} Alarm(e) in den letzten ${AF} Tagen` : '');
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
  const K_ = KAT[metric];
  if (K_){
    N.forEach((n, i) => {
      if (n.m < 0){ n.mk.setStyle({fillColor:'#aaaaaa', fillOpacity:0.8}); return; }
      const c = K_.farbe(n), leer = c === '#bbbbbb';
      n.mk.setStyle({fillColor:c, fillOpacity:leer ? 0.45 : 0.95,
                     weight:i === sel ? 4 : (n.src ? 3 : 1), color:i === sel ? css('--sel') : (n.src ? '#e11d48' : '#222222')});
      if (i === sel) n.mk.bringToFront();
    });
    return;
  }
  const M_ = MET[metric], lo = M_.r[0], hi = M_.r[1];
  N.forEach((n, i) => {
    if (n.m < 0){ n.mk.setStyle({fillColor:'#aaaaaa', fillOpacity:0.8}); return; }
    const v = M_.fn(n.m, h);
    n.mk.setStyle({fillColor:isNaN(v) ? '#bbbbbb' : colorAt(M_.stops, (v-lo)/(hi-lo)), fillOpacity:isNaN(v) ? 0.45 : 0.95,
                   weight:i === sel ? 4 : (n.src ? 3 : 1), color:i === sel ? css('--sel') : (n.src ? '#e11d48' : '#222222')});
    if (i === sel) n.mk.bringToFront();
  });
}
function updateLegend(){
  const K_ = KAT[metric];
  if (K_){
    $('legend').innerHTML = `<b>Monitor: ${K_.name}</b>`
      + K_.leg().map(([c, t]) => `<div class="kv" style="justify-content:flex-start"><span style="color:${c}">●</span>&nbsp;${t}</div>`).join('')
      + `<div class="l2">${K_.l2()}</div>`;
    return;
  }
  const M_ = MET[metric];
  const grad = 'linear-gradient(90deg,' + M_.stops.join(',') + ')';
  $('legend').innerHTML = `<b>${M_.name} in ${M_.unit}</b><div class="grad" style="background:${grad}"></div>`
    + `<div class="row"><span>${M_.r[0].toFixed(1)}</span><span>${M_.r[1].toFixed(1)}</span></div>`
    + `<div class="l2">Grau: keine Daten oder kein Durchfluss</div>`;
}
function updateStats(){
  let n = 0, nf = 0, wf = 0, sv_ = 0, sr = 0, sf = 0;
  for (let m = 0; m < M; m++){
    const v = val(m,0,h), r = val(m,1,h), f = val(m,2,h);
    if (!isNaN(v)) n++;
    if (f > FMIN && !isNaN(v) && !isNaN(r)){ nf++; wf += f; sv_ += v*f; sr += r*f; }
  }
  const row = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
  $('stats').innerHTML =
    row('Gesamtleistung', f1(sumP[h]) + ' kW') +
    row('Vorlauf (Durchfluss-gewichtet)', wf ? (sv_/wf).toFixed(1) + ' °C' : '–') +
    row('Rücklauf (Durchfluss-gewichtet)', wf ? (sr/wf).toFixed(1) + ' °C' : '–') +
    row('Spreizung (Durchfluss-gewichtet)', wf ? ((sv_ - sr)/wf).toFixed(1) + ' K' : '–') +
    row('Häuser mit Messwerten', n + ' von ' + M) +
    row('Häuser mit Durchfluss', nf + ' von ' + M);
  $('tlabel').textContent = fmt(h) + (n === 0 ? ' (keine Daten)' : '');
  updateMonStats();
}
function updateMonStats(){
  const row = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
  const wi = winterAt(h), zahl = [0,0,0,0], ak = {schl:0, netz:0, bess:0};
  N.forEach(n => {
    if (n.m < 0) return;
    const w = monW(n); zahl[w ? w.p : 0]++;
    const k = alarmKlasse(n); if (k in ak) ak[k]++;
  });
  const ev = ereignisAt(h);
  $('monStats').innerHTML =
    row('Winter', wi.w + (wi.sommer ? ' (Sommer, letzter Winter)' : '')) +
    row('Priorität hoch / mittel / niedrig', zahl[3] + ' / ' + zahl[2] + ' / ' + zahl[1]) +
    row('Häuser ohne Status', zahl[0]) +
    row('Verschlechterung in ' + AF + ' Tagen', ak.schl + ak.netz + (ak.netz ? ' (davon ' + ak.netz + ' nur Netzereignis)' : '')) +
    row('Nur Verbesserung in ' + AF + ' Tagen', ak.bess) +
    row('Netzereignis-Episode', ev.length ? ev.map(e => e[2] + ', ' + e[3] + ' Stationen, ' + fmtDate(e[0]) + '–' + fmtDate(e[1])).join('; ') : 'nein');
  if (KAT[metric]) updateLegend();
}
function updateNodeInfo(){
  if (sel < 0){ $('nodeInfo').innerHTML = '<p class="muted">Haus auf der Karte oder in der Liste auswählen.</p>'; return; }
  const n = N[sel], m = n.m;
  const row = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
  $('nodeInfo').innerHTML = `<p style="margin:4px 0"><span class="muted">Zähler ${esc(n.z)}${n.est ? ' · Position geschätzt' : ''}</span></p>`
    + (n.bl && n.bl.length ? '<button id="bAnalyse" class="btn-analyse">Ganze Analyse anzeigen</button>'
                           : '<p class="muted" style="margin:4px 0">Für dieses Haus gibt es kein Stationsblatt.</p>')
    + row('Vorlauf', f1(val(m,0,h)) + ' °C') + row('Rücklauf', f1(val(m,1,h)) + ' °C')
    + row('Spreizung', f1(spr(m,h)) + ' K') + row('Durchfluss', f1(val(m,2,h),0) + ' l/h')
    + row('Leistung', f1(val(m,3,h)) + ' kW')
    + monInfo(n);
  const b = $('bAnalyse'); if (b) b.addEventListener('click', () => analyseAuf(sel));
}
function monInfo(n){
  const row = (a, b) => `<div class="kv"><span>${a}</span><b>${b}</b></div>`;
  const wi = winterAt(h), w = monW(n);
  let s = `<p style="margin:8px 0 2px"><b>Monitor, Winter ${wi.w}</b></p>`;
  if (!w) return s + '<p class="muted" style="margin:2px 0">Kein Status in diesem Winter.</p>';
  s += row('Priorität', PRIO_NAME[w.p]) + row('Rang / Score', (w.rg === null ? '–' : w.rg) + ' / ' + (w.sc === null ? '–' : w.sc.toFixed(2)))
    + row('Fehlerbild', w.fb || '–') + row('Chronisch', w.ch ? 'ja' : 'nein')
    + row('Alarme verschlechtert / verbessert', w.ns + ' / ' + w.nb)
    + row('davon in Netzereignis / mit Nachbar', w.ne + ' / ' + w.nn);
  const a = n.mon.a.filter(x => x[1] <= h).sort((x, y) => x[1] - y[1]).slice(-5).reverse();
  if (a.length) s += '<p class="muted" style="margin:6px 0 2px">Letzte Alarme bis zum Zeitpunkt (Beginn)</p>'
    + a.map(x => `<div class="kv"><span>${fmtDate(x[1])} ${esc(x[5])}</span><b style="color:${x[2] > 0 ? A_FARBE.schl : A_FARBE.bess}">${x[2] > 0 ? 'verschlechtert' : 'verbessert'}${x[3] ? ', Netz' : ''}${x[4] ? ', Nachbar' : ''}</b></div>`).join('');
  return s;
}

//---- Ganze Analyse je Zähler (Stationsblatt, Carpet, Dauerlinie)
const ANSICHTEN = [['blatt', 'Stationsblatt'], ['carpet', 'Carpet'], ['dauer', 'Dauerlinie']];
const ERKLAERUNG = {
  blatt: '<h2>So liest du das Stationsblatt</h2><ol>'
    + '<li>Steigung der Kennlinie. Für jedes 14-Tage-Fenster, täglich weitergeschoben, wird log Volumenstrom gegen log Leistung gefittet. Die Steigung sagt, wie stark der Durchfluss der Wärmeabnahme folgt. Nahe 1 geht der Durchfluss mit der Last mit, nahe 0 fließt immer etwa gleich viel Wasser, egal wie viel Wärme gebraucht wird. Das ist ein Hinweis auf ein offenes Ventil oder eine Regelung, die nicht eingreift. Graues Band: 10 bis 90 % aller Stationen am selben Tag (ohne BHKW), gestrichelt der Median. Das Band ist der Normalbetrieb des Netzes, also der Vergleich mit den anderen HAST. Blau hinterlegt: Kernwinter Dezember bis Februar.</li>'
    + '<li>Spreizung im Fenster. Median aus Vorlauf minus Rücklauf im selben Fenster, wieder vor dem Netzband. Mehr Spreizung heißt mehr Wärme je m³ Wasser. Liegt die Station unter dem Band, kommt das Wasser zu warm zurück.</li>'
    + '<li>Tagesmonitor (CUSUM). Grau hinterlegt ist die Referenzzeit, der eigene Normalbetrieb der Station: ihr erstes Jahr, höchstens bis 14 Tage vor der ersten Begehung, mindestens 60 Heiztage. Dort lernt der Monitor, wie Abkühlung (kWh/m³, rot) und Wassermenge (blau) von der Tagesmitteltemperatur abhängen. Danach wird an jedem Heiztag (Tagesmittel unter 15 °C) die Abweichung von dieser eigenen Kennlinie aufsummiert, mit Toleranz k = 0,5 und gedeckelt bei ±10. Erreicht die Summe ±5 (gepunktete Linie), gibt es einen Alarm. Gefülltes Dreieck = verschlechtert, leeres = verbessert. Beides heißt nur: anders als im eigenen Referenzjahr. Ob die Station im Vergleich zu den anderen gut oder schlecht ist, zeigt allein der Netzvergleich. Eine reparierte Station bekommt also einen Verbesserungsalarm, auch wenn sie im Netz noch schlecht dasteht, so wie eine Note von 5 auf 4 eine Verbesserung ist, aber noch keine gute Note.</li>'
    + '<li>Kennlinie je Kernwinter. Stundenpunkte Volumenstrom gegen Leistung aus dem jüngsten Winter, eine Linie je Kernwinter in fester Farbe (22/23 orange, 23/24 grün, 24/25 lila). Verglichen wird Winter mit Winter, etwa vor und nach einer Begehung, nicht Winter mit Sommer. In der Legende stehen Steigung, Referenzspreizung und Rang im Netz.</li>'
    + '<li>Netzvergleich je Winter. Fünf Kennzahlen als robuster z-Wert gegen alle Stationen desselben Winters (ohne BHKW). Positiv (gelb bis rot) heißt schlechter als das Netz, negativ (grün) besser. Eine Kennzahl gilt als schlecht, wenn sie bei den schlechtesten 10 % liegt und über null ist. Ab 2 schlechten Kennzahlen ist die Station in dem Winter auffällig (Stern am Winter). Score = Mittel der z-Werte, Rang 1 = schlechteste Station.</li>'
    + '<li>Priorität. Hoch: im Netz auffällig und mindestens ein Verschlechterungsalarm in der Heizperiode dieses Winters. Mittel: eins von beiden. Niedrig: keins. Das Fehlerbild beschreibt nur das Messmuster und ist keine Diagnose.</li></ol>',
  carpet: '<h2>So liest du den Carpet</h2><p>Kalendertag nach rechts, Tagesstunde nach oben, einmal für den Rücklauf und einmal für den Durchfluss. Weiß heißt Stillstand oder keine Daten. Man sieht Nachtabsenkung, Sommerbetrieb, Ausfalltage und Zeitpunkte, an denen sich am Betrieb etwas ändert, etwa nach einer Begehung.</p>',
  dauer: '<h2>So liest du die Dauerlinie</h2><p>Alle Werte einer Station absteigend sortiert über dem Anteil der Zeit, Links der Rücklauf als Stundenwerte (gestrichelt 50 °C), rechts die Abkühlung in kWh/m³ als Tageswerte. Oben nach Saison, unten vor und nach der Begehung. Die Frage dahinter: nicht ob ein schlechter Zustand vorkommt, sondern wie lange er anliegt.</p>'
};
let ovN = null, ovM = 0, ovA = 'blatt';
function analyseAuf(i){
  const n = N[i];
  if (!n || !n.bl || !n.bl.length) return;
  ovN = n; ovM = 0; ovA = 'blatt';
  zeigeAnalyse();
  $('ov').classList.add('auf');
  $('ovZu').focus();
}
function analyseZu(){ $('ov').classList.remove('auf'); ovN = null; }
function zeigeAnalyse(){
  const b = ovN.bl[ovM], pfade = b[1];
  if (!pfade[ovA]) ovA = ANSICHTEN.map(a => a[0]).find(k => pfade[k]);
  $('ovTitel').textContent = 'Ganze Analyse, Zähler ' + b[0];
  let tabs = '';
  if (ovN.bl.length > 1) tabs += ovN.bl.map((x, k) => `<button class="tab${k === ovM ? ' an' : ''}" data-m="${k}">Zähler ${esc(x[0])}</button>`).join(' ') + ' <span class="muted">|</span> ';
  tabs += ANSICHTEN.filter(a => pfade[a[0]]).map(a => `<button class="tab${a[0] === ovA ? ' an' : ''}" data-a="${a[0]}">${a[1]}</button>`).join(' ');
  $('ovTabs').innerHTML = tabs;
  const bild = $('ovBild');
  bild.classList.remove('gross');
  bild.innerHTML = `<img src="${esc(pfade[ovA])}" alt="${esc(ANSICHTEN.find(a => a[0] === ovA)[1])} Zähler ${esc(b[0])}" title="Klick: Originalgröße">`;
  bild.querySelector('img').addEventListener('error', () => {
    bild.innerHTML = '<p class="muted">Bild nicht gefunden: ' + esc(pfade[ovA]) + '. Die HTML-Datei muss in outputs/netz liegen, die Bilder in outputs/stationsblatt und outputs/stationsbilder (python -m src.stationsblatt).</p>';
  });
  const wi = winterAt(h);
  $('ovText').innerHTML = '<h2>Befund laut Stationsblatt</h2>'
    + (b[2] ? `<pre>${esc(b[2])}</pre>` : '<p class="muted">Keine Statuszeile.</p>')
    + `<h2>Monitor auf der Karte (${esc(wi.w)})</h2>` + monInfo(ovN).replace(/^<p[^>]*><b>[^<]*<\/b><\/p>/, '')
    + ERKLAERUNG[ovA];
}
$('ovTabs').addEventListener('click', e => {
  const t = e.target.closest('button'); if (!t || !ovN) return;
  if (t.dataset.m !== undefined){ ovM = +t.dataset.m; ovA = 'blatt'; }
  if (t.dataset.a !== undefined) ovA = t.dataset.a;
  zeigeAnalyse();
});
$('ovBild').addEventListener('click', e => { if (e.target.tagName === 'IMG') $('ovBild').classList.toggle('gross'); });
$('ovZu').addEventListener('click', analyseZu);
$('ov').addEventListener('click', e => { if (e.target === $('ov')) analyseZu(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && ovN) analyseZu(); });
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

// ---- Steuerung
function refresh(){ updateEdges(); updateNodes(); updateStats(); updateNodeInfo(); drawCharts(); }
function setH(v){
  h = Math.max(0, Math.min(H-1, Math.round(v)));
  $('slider').value = h; $('dt').value = toInput(h);
  refresh();
}
function select(i){
  sel = i;
  $('selNode').value = String(i);
  updateNodes(); updateNodeInfo(); drawCharts();
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
$('selNode').addEventListener('change', e => select(+e.target.value));

const opts = ['<option value="-1">– Haus wählen –</option>'];
N.map((n, i) => ({n, i})).filter(x => x.n.m >= 0).sort((a, b) => a.n.name.localeCompare(b.n.name, 'de'))
  .forEach(x => opts.push(`<option value="${x.i}">${esc(x.n.name)}</option>`));
$('selNode').innerHTML = opts.join('');
$('selNode').addEventListener('change', e => { if (+e.target.value < 0){ sel = -1; updateNodes(); updateNodeInfo(); drawCharts(); } });

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

updateLegend();
setH(h);
})();
</script>
</body>
</html>
"""

html = VORLAGE.replace("__DATA__", daten)
Path(AUSGABE).write_text(html, encoding="utf-8")

_ziel = Path(AUSGABE).resolve()
_zeige = _ziel.relative_to(Path(ROOT).resolve()) if "ROOT" in globals() else _ziel
print(f"Geschrieben: {_zeige}  ({_ziel.stat().st_size / 1e6:.1f} MB)")
print(f"Zeitraum: {idx[0]} bis {idx[-1]} ({H} Stunden)")
print(f"Häuser mit Zeitreihe: {M} | Nodes: {len(nodes_js)} | Kanten: {len(edges_js)}"
      + (f" ({ohne_pos} ohne Position, nicht gezeigt)" if ohne_pos else ""))
print("Graph ist ohne Kreise:", ist_dag, "| Quellen:", len(quellen))
if not ist_dag:
    print("WARNUNG: Der Graph hat Kreise. Die Leistung wird nur entlang eines Spannbaums von den Quellen aus berechnet.")
if clip_count:
    print(f"WARNUNG: {clip_count} Werte lagen außerhalb des Speicherbereichs und wurden gekappt.")
print("Startzeitpunkt im Dashboard:", idx[start_idx])
print("Datei im Browser öffnen (Doppelklick). Karte und Hintergrundkacheln brauchen Internet (Leaflet und Webkarte Bayern).")
print("Hintergrund oben rechts in der Karte umschaltbar. OpenStreetMap geht nur, wenn die Datei über einen lokalen Server geöffnet wird:")
print("  Terminal im Ordner der Datei:  python -m http.server 8000   dann im Browser  http://localhost:8000/" + AUSGABE)
print("Achtung: Die Datei enthält Adressen und Zählerdaten. Nicht weitergeben.")
