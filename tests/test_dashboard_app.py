"""Streamlit-Dashboard gegen die HTML-Fassung.

Der JavaScript-Teil aus ``notebooks/dashboard_final.py`` läuft in Node.js auf denselben Daten
(``outputs/dashboard/app/``), mit Attrappen für Browser und Leaflet. Verglichen wird Zeichen für
Zeichen, was beide Fassungen anzeigen: Seitenleiste „Netz“, Legende, Hausfenster, Zeitangabe,
Farben und Tooltips der Häuser, Breite und Tempo der Leitungen, Handlungsliste.

Ohne Node.js oder ohne die Daten aus Notebook 37 werden die Vergleiche übersprungen.
"""

import base64
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src import dashboard_app_logik as lg

ROOT = Path(__file__).resolve().parents[1]
ORDNER = ROOT / "outputs" / "dashboard" / "app"


# --- Hilfsfunktionen ohne Daten ---------------------------------------------------------------

def test_to_fixed_wie_javascript():
    assert lg.to_fixed(12.5, 0) == "13"         #JavaScript rundet bei Gleichstand weg von null
    assert lg.to_fixed(-12.5, 0) == "-13"
    assert lg.to_fixed(0.125, 2) == "0.13"
    assert lg.to_fixed(1.005, 2) == "1.00"      #1.005 ist binär etwas kleiner
    assert lg.to_fixed(-0.0, 1) == "0.0"
    assert lg.to_fixed(-0.04, 1) == "-0.0"


def test_js_round_und_prozent():
    assert lg.js_round(2.5) == 3 and lg.js_round(-2.5) == -2
    assert lg.pz(0.695) == "70 %" and lg.pz(None) == "–" and lg.pz(lg.UNDEF) == "–"
    assert lg.de(0.5, 1) == "0,5" and lg.de(None) == "–"


def test_wahr_wie_javascript():
    assert lg.wahr([]) and lg.wahr({}) and lg.wahr("x") and lg.wahr(1)
    assert not any(lg.wahr(x) for x in (None, lg.UNDEF, 0, 0.0, "", float("nan"), False))


def test_color_at():
    stops = ["#000000", "#ffffff"]
    assert lg.color_at(stops, 0) == "rgb(0,0,0)"
    assert lg.color_at(stops, 0.5) == "rgb(128,128,128)"
    assert lg.color_at(stops, 2) == "rgb(255,255,255)"


# --- Vergleich mit dem JavaScript -------------------------------------------------------------

ATTRAPPEN = r"""
const VARS = {'--bg':'#f2f5f8','--panel':'#fff','--ink':'#1b2631','--muted':'#5d6b79','--line':'#d5dce3',
  '--vor':'#d6402d','--rueck':'#2e6db3','--sel':'#0a7d6b','--btn':'#f6f8fa','--accent':'#c2410c'};
const EL = {};
function el(id){
  if (!EL[id]) EL[id] = {id, value:'', textContent:'', innerHTML:'', checked:false, hidden:false, dataset:{},
    _h:{}, addEventListener(t, f){ this._h[t] = f; }, closest(){ return {scrollIntoView(){}}; },
    getContext(){ return new Proxy({}, {get:(o,k) => k in o ? o[k] : () => {}, set:(o,k,v) => { o[k]=v; return true; }}); },
    setAttribute(){}, setPointerCapture(){}, getBoundingClientRect(){ return {left:0, width:400}; },
    clientWidth:0, clientHeight:0};
  return EL[id];
}
const START = {fStand:'auto', kStand:'auto', metric:'dring', win:'336', step:'24', fMass:'', selNode:'-1'};
for (const k in START) el(k).value = START[k];
const KLASSEN = {'.g-winter':[el('_gw')], '.g-daemmung':[el('_gd')], '.g-vertrag':[el('_gv')]};
globalThis.document = {getElementById:el, querySelectorAll:s => KLASSEN[s] || [], documentElement:{}};
globalThis.getComputedStyle = () => ({getPropertyValue:v => VARS[v]});
globalThis.window = {devicePixelRatio:1, addEventListener(){}};
function schicht(){
  const o = {stil:{}, _path:{style:{}}, addTo(){ return o; }, setLatLngs(){ return o; },
    setStyle(s){ Object.assign(o.stil, s); return o; }, bindTooltip(f){ o.tip = f; return o; },
    on(){ return o; }, bringToFront(){ return o; }};
  return o;
}
globalThis.L = {
  map(){ return {project:p => ({x:p[1]*1e5, y:-p[0]*1e5}), unproject:p => [-p.y/1e5, p.x/1e5], getZoom:() => 15,
                 fitBounds(){}, on(){}, setView(){}, invalidateSize(){}, addLayer(){}}; },
  tileLayer:schicht, layerGroup:schicht, canvas:() => ({}),
  polyline:(P, o) => { const s = schicht(); Object.assign(s.stil, o); return s; },
  circleMarker:(p, o) => { const s = schicht(); Object.assign(s.stil, o); return s; },
  control:{layers:() => ({addTo(){}})}, point:(x, y) => ({x, y})
};
"""

ABLAUF = r"""
const T = globalThis.__T, aus = [];
const fall = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
for (const f of fall){
  el('fStand').value = f.wahl; el('kStand').value = f.wahl;
  el('metric')._h.change({target:{value:f.metric}});
  T.setH(f.h);
  if (f.sel >= 0) T.select(f.sel); else el('selNode')._h.change({target:{value:'-1'}});
  el('fMass').value = f.fm; el('fAlle').checked = f.alle; el('fMass')._h.change();
  aus.push({stats:el('stats').innerHTML, legend:el('legend').innerHTML, info:el('nodeInfo').innerHTML,
    tlabel:el('tlabel').textContent, liste:el('lBody').innerHTML, lStand:el('lStand').textContent,
    lZahl:el('lZahl').textContent, h:T.getH(),
    nodes:T.N.map(n => n.m >= 0 ? [n.mk.stil.fillColor, n.mk.stil.fillOpacity, n.mk.stil.weight, n.mk.stil.color,
                                    n.mk.stil.radius, n.mk.tip()] : [n.mk.stil.radius, n.mk.tip()]),
    edges:T.E.map(e => [e.v.stil.weight, e.v.stil.opacity, e.fv.stil.weight, e.fv.stil.opacity,
                        e.fv._path.style.animationDuration, e.hit.tip()])});
}
aus.push({gw:el('_gw').textContent, gd:el('_gd').textContent, gv:el('_gv').textContent,
          infoStand:el('infoStand').textContent, punkte:el('punkteText').textContent,
          auswahl:[...el('selNode').innerHTML.matchAll(/value="(-?\d+)"/g)].map(x => +x[1])});
console.log(JSON.stringify(aus));
"""


def _skript(daten: dict, roh: np.ndarray) -> str:
    quelle = (ROOT / "notebooks" / "dashboard_final.py").read_text(encoding="utf-8")
    vorlage = quelle.split('VORLAGE = r"""', 1)[1].split('"""', 1)[0]
    js = vorlage.split("<script>", 1)[1].split("</script>", 1)[0]
    payload = dict(daten, b64=base64.b64encode(roh.astype("<i2").tobytes()).decode("ascii"))
    js = js.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    js = js.replace("letzterStand = stand(); renderListe();",
                    "globalThis.__T = {setH, select, N, E, getH:() => h}; letzterStand = stand(); renderListe();")
    return ATTRAPPEN + js + ABLAUF


@pytest.fixture(scope="module")
def vergleich(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("Node.js fehlt")
    if not (ORDNER / "daten.json").exists():
        pytest.skip("outputs/dashboard/app/ fehlt, Notebook 37 ausführen")
    daten, roh = lg.lade(ORDNER)
    db = lg.Dashboard(json.loads(json.dumps(daten)), roh)
    H = db.H
    haeuser = db.haeuser
    mehrere = [i for i in haeuser if db.N[i]["k"] > 1][:2]
    geschaetzt = [i for i in haeuser if db.N[i].get("est")][:1]
    sels = [-1, haeuser[0], haeuser[len(haeuser) // 2], haeuser[-1], *mehrere, *geschaetzt]
    wechsel = int(db.h_von(db.WECHSEL)) if db.WECHSEL else H // 2
    stunden = [0, db.start_h(), 3000, wechsel - 1, wechsel, wechsel + 300, 9000, 12000, H - 1]
    faelle = []
    for j, h in enumerate(stunden):
        for wahl in ("auto", "vor", "heute"):
            for metric in lg.FAERBUNGEN:
                faelle.append({"h": h, "wahl": wahl, "metric": metric, "sel": sels[(j + len(faelle)) % len(sels)],
                               "fm": ["", "reparatur", "daemmung", "kapazitaet", "daten"][len(faelle) % 5],
                               "alle": len(faelle) % 2 == 0})
    tmp = tmp_path_factory.mktemp("js")
    (tmp / "d.js").write_text(_skript(daten, roh), encoding="utf-8")
    (tmp / "f.json").write_text(json.dumps(faelle), encoding="utf-8")
    lauf = subprocess.run(["node", str(tmp / "d.js"), str(tmp / "f.json")], capture_output=True, text=True,
                          timeout=600)
    assert lauf.returncode == 0, lauf.stderr[-3000:]
    js = json.loads(lauf.stdout)
    return db, faelle, js[:-1], js[-1]


def test_seitenleiste_legende_hausfenster(vergleich):
    db, faelle, js, _ = vergleich
    for f, j in zip(faelle, js):
        h = db.set_h(f["h"])
        assert j["h"] == h
        assert db.stats_html(h, f["wahl"]) == j["stats"], f
        assert db.legende_html(f["metric"], h, f["wahl"]) == j["legend"], f
        assert db.node_info_html(f["sel"], h, f["wahl"]) == j["info"], f
        assert db.zeit_label(h) == j["tlabel"], f


def test_haeuser_und_leitungen(vergleich):
    db, faelle, js, _ = vergleich
    for f, j in zip(faelle, js):
        h = db.set_h(f["h"])
        for i, (n, jn) in enumerate(zip(db.N, j["nodes"])):
            if n["m"] < 0:
                assert db.node_tip(n, h, f["wahl"], f["metric"]) == jn[1]
                continue
            s = db.haus_stil(i, h, f["wahl"], f["metric"], f["sel"])
            assert [s["fill"], s["op"], s["weight"], s["color"] or "#0a7d6b", s["radius"]] == jn[:5], (f, i)
            assert db.node_tip(n, h, f["wahl"], f["metric"]) == jn[5], (f, i)
        for e, je in zip(db.E, j["edges"]):
            k = db.kante(e, h)
            for py, j_ in ((k["w"], je[0]), (k["dw"], je[2])):
                assert (math.isnan(py) and j_ is None) or math.isclose(py, j_, abs_tol=1e-12)
            assert k["op"] == je[1] and (0.85 if k["aktiv"] else 0) == je[3]
            assert k["dur"] is None or k["dur"] == je[4]
            assert db.edge_tip(e, k) == je[5]


def test_handlungsliste(vergleich):
    db, faelle, js, _ = vergleich
    for f, j in zip(faelle, js):
        h = db.set_h(f["h"])
        zeilen = db.liste(h, f["wahl"], f["fm"], f["alle"])
        html = "".join(db.liste_zeile_html(*z) for z in zeilen) or \
            '<tr><td colspan="7" class="muted">Keine Zähler für diese Auswahl.</td></tr>'
        assert html == j["liste"], f
        assert f"{len(zeilen)} Zähler" == j["lZahl"]
        assert db.stand_text(db.stand(h, f["wahl"])) == j["lStand"]


def test_texte_im_info_reiter(vergleich):
    db, _, _, rest = vergleich
    w = db.info_werte()
    assert (w["winter"], w["daemmung"], w["vertrag"], w["stand"], w["punkte"]) == \
        (rest["gw"], rest["gd"], rest["gv"], rest["infoStand"], rest["punkte"])


def test_reihenfolge_haus_auswahl(vergleich):
    db, _, _, rest = vergleich
    assert [-1, *db.auswahl] == rest["auswahl"]
