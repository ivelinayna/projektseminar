"""Fernwärme-Dashboard als Streamlit-App.

    streamlit run src/dashboard_app.py

Dasselbe Dashboard wie die frühere HTML-Datei aus Notebook 37, mit denselben drei Reitern,
Bedienelementen und Regeln:

- Karte: Zeitregler mit Abspielen, Färbung nach Dringlichkeit, Maßnahme, Meldungen, Potenzial oder
  Messwerten, Stand der Bewertung, Rohrbaum mit Fließrichtung, rechts Netz, Hausfenster und
  Gesamtleistung (Klick setzt den Zeitpunkt)
- Handlungsliste: Filter, gekoppelter Stand, Sprung vor/nach die Begehungen, „Karte“ zeigt das Haus
- So funktioniert's

Die Rechenregeln stehen in ``src/dashboard_app_logik.py`` (Nachbau des JavaScript, geprüft in
``tests/test_dashboard_app.py``). Die Daten schreibt Notebook 37 nach ``outputs/dashboard/app/``.
Die App rechnet keine Modelle.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import folium
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import PolyLineOffset
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[1]
#"streamlit run" startet ohne Paketkontext, deshalb den Projektordner selbst eintragen
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import dashboard_app_logik as lg  # noqa: E402

st.set_page_config(page_title="Fernwärme-Dashboard", layout="wide", initial_sidebar_state="collapsed")
ss = st.session_state

#Breite der Diagramme in der rechten Spalte, für die Mittelung wie im Canvas der HTML-Fassung
DIAGRAMM_BREITE = 356
KARTE_HOEHE = 720
SPALTE_HOEHE = 790
ABSPIELEN_MS = 250


# --- Daten ----------------------------------------------------------------------------------

def _stempel() -> tuple:
    return tuple((p.name, p.stat().st_mtime) for p in sorted(lg.ORDNER.glob("*")) if p.is_file())


@st.cache_resource(show_spinner="Lade Dashboard-Daten …")
def _dashboard(stempel: tuple) -> lg.Dashboard:
    daten, roh = lg.lade(lg.ORDNER)
    return lg.Dashboard(daten, roh)


try:
    db = _dashboard(_stempel())
except FileNotFoundError as ex:
    st.title("Fernwärme-Dashboard")
    st.error(str(ex))
    st.markdown("Reihenfolge: Notebook 00, `python -m src.weather`, Modellpakete (Notebook 35), "
                "`python -m src.dashboard_daten`, Notebook 31, Notebook 37. Danach diese Seite neu laden.")
    st.stop()

_thema = getattr(getattr(st.context, "theme", None), "type", None)
F = lg.FARBEN["dark" if _thema == "dark" else "light"]
LAGE = {(round(n["lat"], 9), round(n["lon"], 9)): i for i, n in enumerate(db.N) if n["m"] >= 0}


# --- Zustand --------------------------------------------------------------------------------
# Eigene Schlüssel neben den Widgets: Widgets in einem gerade versteckten Reiter verlieren sonst
# ihren Wert. Vor jedem Widget wird sein Wert aus dem Zustand gesetzt, die Rückrufe schreiben zurück.

for k, v in {"h": db.start_h(), "metric": "dring", "sel": -1, "wahl": "auto", "win": 336, "step": 24,
             "playing": False, "tab": "karte", "fm": "", "alle": False, "ansicht": None, "klick_alt": None,
             "netz_nr": 0}.items():
    ss.setdefault(k, v)


def set_h(v) -> None:
    ss.h = db.set_h(v)


def _cb(feld, wkey, umwandeln=None):
    def f():
        wert = ss[wkey]
        if wert is None:
            return
        ss[feld] = umwandeln(wert) if umwandeln else wert
    return f


def cb_slider():
    set_h(db.h_von(ss.w_slider))


def cb_datum():
    if ss.w_datum is None:
        return
    d = ss.w_datum
    set_h(db.h_von(datetime(d.year, d.month, d.day, int(ss.w_stunde))))


def cb_play():
    ss.playing = not ss.playing


def cb_schritt(n):
    return lambda: set_h(ss.h + n)


def cb_vor():
    ss.wahl = "auto"
    set_h(db.h_vor_begehungen())


def cb_heute():
    ss.wahl = "auto"
    set_h(db.H - 1)


def cb_karte_zeigen(i):
    ss.tab = "karte"
    n = db.N[i]
    #kleiner Versatz, damit die Karte auch beim zweiten Mal auf dasselbe Haus springt
    ss.ansicht = (n["lat"] + (1e-9 if ss.ansicht and ss.ansicht[0] == n["lat"] else 0), n["lon"], 18)
    ss.sel = i


def cb_klick():
    r = ss.get("karte") or {}
    k = r.get("last_object_clicked")
    if not k or k == ss.klick_alt:
        return
    ss.klick_alt = k
    i = LAGE.get((round(k["lat"], 9), round(k["lng"], 9)))
    if i is not None:
        ss.sel = i


def cb_netz():
    auswahl = ss.get(f"cNet{ss.netz_nr}")
    punkte = (auswahl or {}).get("selection", {}).get("points") or []
    if punkte:
        set_h(punkte[0]["x"])
        ss.netz_nr += 1     #neues Diagramm, damit ein zweiter Klick auf dieselbe Stelle wieder zählt


def setze(wkey, wert):
    ss[wkey] = wert


# --- Aussehen -------------------------------------------------------------------------------

st.markdown(f"""<style>
.block-container{{padding-top:3rem;padding-bottom:1rem;max-width:100%}}
.fw .kv{{display:flex;justify-content:space-between;gap:10px;padding:2px 0}}
.fw .kv span{{color:{F['muted']}}}
.fw .kv b{{text-align:right}}
.fw .muted{{color:{F['muted']}}}
.fw .klein{{font-size:12px}}
.fw .blk{{margin:8px 0}}
.fw .blk > span{{display:block;color:{F['muted']};font-size:12px}}
.fw .emp{{border-left:4px solid {F['line']};padding:6px 0 6px 10px;margin:8px 0}}
.fw .emp .kopf{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:3px}}
.fw .badge,.badge{{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;font-weight:600;color:#111;white-space:nowrap}}
.fw .zaehler + .zaehler{{border-top:1px dashed {F['line']};margin-top:8px;padding-top:6px}}
.fw h3{{font-size:13px;margin:12px 0 4px;color:{F['muted']};font-weight:600;padding:0}}
.fw{{font-size:14px;line-height:1.4}}
.fw-h2{{font-size:15px;font-weight:700;margin:0 0 4px}}
.legwrap{{position:relative;height:0;z-index:500}}
.legwrap .legend{{position:absolute;left:10px;bottom:calc(22px + 1rem);background:{F['panel']};color:{F['ink']};
  border:1px solid {F['line']};border-radius:6px;padding:8px 10px;font-size:12px;width:230px;line-height:1.4}}
.legend .grad{{height:10px;border-radius:3px;margin:5px 0 3px}}
.legend .row{{display:flex;justify-content:space-between;color:{F['muted']}}}
.legend .kat{{display:flex;align-items:center;gap:6px;margin:2px 0}}
.legend .kat i{{width:11px;height:11px;border-radius:50%;flex:none;border:1px solid #2226}}
.legend .kat b{{margin-left:auto;font-weight:600}}
.legend .l2{{margin-top:6px;color:{F['muted']};line-height:1.5}}
.tlabel{{font-weight:600;padding-top:.45rem;white-space:nowrap}}
.lkopf{{font-size:12px;color:{F['muted']};font-weight:600;border-bottom:1px solid {F['line']};padding-bottom:4px}}
.lzeile{{font-size:13px}}
.info{{max-width:1100px;margin:0 auto}}
.info p{{max-width:75ch}}
.info h3{{font-size:15px;margin:22px 0 8px}}
.info .tabwrap{{overflow-x:auto}}
.info table{{border-collapse:collapse;width:100%;font-size:13px}}
.info th,.info td{{padding:7px 8px;border-bottom:1px solid {F['line']};text-align:left;vertical-align:top}}
.info th{{font-size:12px;color:{F['muted']};font-weight:600}}
.info .muted{{color:{F['muted']}}}
.info .klein{{font-size:12px}}
.info .fluss{{display:flex;flex-wrap:wrap;gap:6px;align-items:stretch;margin:8px 0}}
.info .fluss div{{border:1px solid {F['line']};border-radius:6px;padding:8px 10px;flex:1 1 170px}}
.info .fluss div b{{display:block}}
@media (max-width:900px){{.legwrap .legend{{width:auto;max-width:58%;font-size:11px;padding:6px 8px}}.legwrap .l2{{display:none}}}}
</style>""", unsafe_allow_html=True)


def html(inhalt: str) -> None:
    st.markdown(f'<div class="fw">{inhalt}</div>', unsafe_allow_html=True)


# --- Kopfzeile ------------------------------------------------------------------------------

REITER = {"karte": "Karte", "liste": "Handlungsliste", "info": "So funktioniert's"}
k1, k2 = st.columns([1, 3], vertical_alignment="center")
k1.markdown("#### Fernwärme-Dashboard")
setze("w_tab", ss.tab)
k2.segmented_control("Ansicht", list(REITER), format_func=REITER.get, key="w_tab",
                     on_change=_cb("tab", "w_tab"), label_visibility="collapsed")


def zeitleiste() -> None:
    """Zeitregler und Auswahlfelder, nur im Reiter Karte (wie die Leiste der HTML-Fassung)."""
    z = st.columns([0.9, 0.75, 0.75, 6, 0.75, 0.75], vertical_alignment="center")
    z[0].button("Pause" if ss.playing else "Start", on_click=cb_play, type="primary", width="stretch")
    z[1].button("−1 T", on_click=cb_schritt(-24), help="1 Tag zurück", width="stretch")
    z[2].button("−1 h", on_click=cb_schritt(-1), help="1 Stunde zurück", width="stretch")
    setze("w_slider", db.zeit(ss.h))
    z[3].slider("Zeitpunkt", min_value=db.zeit(0), max_value=db.zeit(db.H - 1), step=timedelta(hours=1),
                format="DD.MM.YYYY HH:mm", key="w_slider", on_change=cb_slider, label_visibility="collapsed")
    z[4].button("+1 h", on_click=cb_schritt(1), help="1 Stunde vor", width="stretch")
    z[5].button("+1 T", on_click=cb_schritt(24), help="1 Tag vor", width="stretch")

    z = st.columns([1.6, 1.1, 0.7, 1.1, 2.2, 2.2], vertical_alignment="center")
    z[0].markdown(f'<div class="tlabel">{lg.esc(db.zeit_label(ss.h))}</div>', unsafe_allow_html=True)
    setze("w_datum", db.zeit(ss.h).date())
    setze("w_stunde", db.zeit(ss.h).hour)
    z[1].date_input("Zeitpunkt wählen", min_value=db.zeit(0).date(), max_value=db.zeit(db.H - 1).date(),
                    format="DD.MM.YYYY", key="w_datum", on_change=cb_datum, label_visibility="collapsed")
    z[2].selectbox("Stunde", list(range(24)), format_func=lambda x: f"{x:02d}:00", key="w_stunde",
                   on_change=cb_datum, label_visibility="collapsed")
    setze("w_step", ss.step)
    z[3].selectbox("Schrittweite beim Abspielen", list(lg.SCHRITTE), format_func=lg.SCHRITTE.get, key="w_step",
                   on_change=_cb("step", "w_step"), label_visibility="collapsed",
                   help="Schrittweite beim Abspielen")
    setze("w_metric", ss.metric)
    z[4].selectbox("Färbung der Häuser", list(lg.FAERBUNGEN),
                   format_func=lambda k: lg.FAERBUNGEN[k] if k in lg.MODELL_FAERBUNGEN
                   else f"Messwert: {lg.FAERBUNGEN[k]}", key="w_metric", on_change=_cb("metric", "w_metric"),
                   label_visibility="collapsed", help="Färbung der Häuser. Oben die Ergebnisse der Modelle, "
                                                      "unten die Messwerte zur gewählten Stunde.")
    if db.VOR:
        setze("w_kstand", ss.wahl)
        z[5].selectbox("Stand der Bewertung", list(lg.STAENDE), format_func=lambda k: "Bewertung: " + lg.STAENDE[k],
                       key="w_kstand", on_change=_cb("wahl", "w_kstand"), label_visibility="collapsed",
                       help="Welcher Stand der Bewertung auf Karte, Hausfenster und Liste gilt")


# --- Karte ----------------------------------------------------------------------------------

BY_ATT = "© Bayerische Vermessungsverwaltung, GeoBasis-DE / BKG (Daten verändert)"
BASIS = [("Webkarte Bayern (amtlich)", "webkarte", "by_webkarte"), ("Webkarte Bayern grau", "grau", "by_webkarte_grau"),
         ("Luftbild Bayern", "luftbild", "by_dop"), ("OpenStreetMap (nur über lokalen Server)", "osm", None),
         ("Kein Hintergrund", "keiner", None)]
#Fließpunkte: Tempo je Leitung über eine Klasse je Hundertstelsekunde (wie animationDuration im Browser)
KARTE_CSS = ("<style>.ni{pointer-events:none}"
             ".flow-v{animation:fv 1.2s linear infinite}.flow-r{animation:fr 1.2s linear infinite}"
             "@keyframes fv{to{stroke-dashoffset:-15}}@keyframes fr{to{stroke-dashoffset:15}}"
             + "".join(f".d{n}{{animation-duration:{n / 100:.2f}s}}" for n in range(100, 1001))
             + "@media (prefers-reduced-motion:reduce){.flow-v,.flow-r{animation:none}}"
             ".leaflet-tooltip{font:12px/1.4 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif}</style>")


def basiskarte() -> folium.Map:
    """Alles, was sich nicht mit der Zeit ändert: Hintergründe, Plandaten, Ebenenwahl, Ausschnitt."""
    lats = [n["lat"] for n in db.N]
    lons = [n["lon"] for n in db.N]
    m = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=15, tiles=None,
                   min_zoom=10, max_zoom=21, control_scale=False)
    basis = db.D["basis"] if db.D["basis"] in {b[1] for b in BASIS} else "webkarte"
    for name, k, ebene in BASIS:
        if k == "keiner":
            folium.FeatureGroup(name=name, overlay=False, show=basis == k).add_to(m)
        elif k == "osm":
            folium.TileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", name=name, max_zoom=19,
                             attr="© OpenStreetMap-Mitwirkende", overlay=False, show=basis == k).add_to(m)
        else:
            folium.TileLayer(f"https://wmtsod{{s}}.bayernwolke.de/wmts/{ebene}/smerc/{{z}}/{{x}}/{{y}}", name=name,
                             attr=BY_ATT, subdomains="123456789", max_native_zoom=19, max_zoom=21, overlay=False,
                             show=basis == k).add_to(m)
    bg = db.D["bg"]
    for titel, linien, farbe, breite, deck in (
            (f"Gebäudekanten (Plan, {len(bg['geb'])})", bg["geb"], "#7b8591", 1, 0.85),
            (f"Rohrplan (Shapefile und KML, {len(bg['rohr'])})", bg["rohr"], "#8aa0b8", 1.5, 0.8)):
        fg = folium.FeatureGroup(name=titel, show=True)
        if linien:
            folium.PolyLine(linien, color=farbe, weight=breite, opacity=deck, class_name="ni").add_to(fg)
        fg.add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30))
    #Plugin einmal in der Grundkarte, damit sein Skript geladen ist
    PolyLineOffset([[lats[0], lons[0]], [lats[0], lons[0]]], offset=0, opacity=0, class_name="ni").add_to(m)
    m.get_root().header.add_child(folium.Element(KARTE_CSS))
    return m


def netzebene(h: int) -> folium.FeatureGroup:
    """Alles, was der Zeitregler und die Auswahl ändern: Leitungen (``updateEdges``) und Häuser (``updateNodes``)."""
    fg = folium.FeatureGroup(name="Netz", control=False)
    for e in db.E:
        k = db.kante(e, h)
        w = 1 if k["w"] != k["w"] else k["w"]          #NaN zeichnet der Browser mit 1 px
        dw = 1 if k["dw"] != k["dw"] else k["dw"]
        tempo = f" d{round(float(k['dur'][:-1]) * 100)}" if k["dur"] and 1 <= float(k["dur"][:-1]) <= 10 else ""
        for versatz, farbe, richtung in ((5, F["vor"], "flow-v"), (-5, F["rueck"], "flow-r")):
            PolyLineOffset(e["P"], offset=versatz, color=farbe, weight=w, opacity=k["op"], line_cap="round",
                           class_name="ni").add_to(fg)
            PolyLineOffset(e["P"], offset=versatz, color="#ffffff", weight=dw, dash_array="1 14",
                           opacity=0.85 if k["aktiv"] else 0, line_cap="round",
                           class_name=f"ni {richtung}{tempo}").add_to(fg)
        folium.PolyLine(e["P"], color="#000", weight=14, opacity=0,
                        tooltip=folium.Tooltip(db.edge_tip(e, k), sticky=True)).add_to(fg)
    reihenfolge = [i for i in range(len(db.N)) if i != ss.sel] + ([ss.sel] if ss.sel >= 0 else [])
    for i in reihenfolge:
        n = db.N[i]
        s = db.haus_stil(i, h, ss.wahl, ss.metric, ss.sel)
        if s["radius"] == 0:
            continue    #Abzweige ohne Zähler sind unsichtbar, außer PUNKTE_ZEIGEN
        folium.CircleMarker([n["lat"], n["lon"]], radius=s["radius"], weight=s["weight"],
                            color=s["color"] or F["sel"], fill=True, fill_color=s["fill"], fill_opacity=s["op"],
                            tooltip=folium.Tooltip(db.node_tip(n, h, ss.wahl, ss.metric), sticky=True)).add_to(fg)
    return fg


def diagramm(reihen: list, i0: int, i1: int, zero: bool, hoehe: int, klickbar: bool = False) -> go.Figure:
    """``drawChart`` mit Plotly: gleiche Mittelung, Achsen und Markierung des Zeitpunkts."""
    d = db.diagramm([r[0] for r in reihen], i0, i1, zero, DIAGRAMM_BREITE)
    fig = go.Figure()
    for (xs, ys), (_, farbe, breite) in zip(d["linien"], reihen):
        fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color=farbe, width=breite), connectgaps=False,
                        hoverinfo="skip")
    if klickbar:
        xs, ys = d["linien"][0]
        fig.add_scatter(x=xs, y=[d["lo"] + (d["hi"] - d["lo"]) / 2] * len(xs), mode="markers",
                        marker=dict(size=14, opacity=0), customdata=[db.fmt(db.set_h(x)) for x in xs],
                        hovertemplate="%{customdata}<extra></extra>")
    if i0 <= ss.h <= i1:
        fig.add_vline(x=ss.h, line_width=1, line_dash="dash", line_color=F["ink"])
    fig.update_layout(height=hoehe, margin=dict(l=38, r=6, t=6, b=18), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", dragmode=False,
                      font=dict(size=10, color=F["muted"]), hovermode="x" if klickbar else "closest")
    #Datum links und rechts unter der Zeichenfläche wie im Canvas (Ticks am Rand schneidet Plotly ab)
    fig.update_xaxes(range=[i0, max(i1, i0 + 1)], showticklabels=False, showgrid=False, zeroline=False,
                     fixedrange=True)
    for x, text, ausr in ((0, db.fmt_date(i0), "left"), (1, db.fmt_date(i1), "right")):
        fig.add_annotation(x=x, y=0, xref="paper", yref="paper", yshift=-3, text=text, showarrow=False,
                           xanchor=ausr, yanchor="top", font=dict(size=10, color=F["muted"]))
    fig.update_yaxes(range=[d["lo"], d["hi"]], tickvals=d["ticks"], ticktext=d["labels"], gridcolor=F["line"],
                     zeroline=False, fixedrange=True)
    return fig


def reiter_karte() -> None:
    zeitleiste()
    h = ss.h
    links, rechts = st.columns([2.7, 1], gap="small")
    with links:
        st_folium(basiskarte(), key="karte", height=KARTE_HOEHE, use_container_width=True,
                  feature_group_to_add=netzebene(h), returned_objects=["last_object_clicked"],
                  center=ss.ansicht[:2] if ss.ansicht else None, zoom=ss.ansicht[2] if ss.ansicht else None,
                  on_change=cb_klick)
        st.markdown(f'<div class="legwrap"><div class="legend">{db.legende_html(ss.metric, h, ss.wahl)}</div></div>',
                    unsafe_allow_html=True)
    with rechts, st.container(height=SPALTE_HOEHE, border=False):
        st.markdown('<div class="fw-h2">Netz</div>', unsafe_allow_html=True)
        html(db.stats_html(h, ss.wahl))
        st.divider()
        st.markdown('<div class="fw-h2">Haus</div>', unsafe_allow_html=True)
        setze("w_sel", ss.sel)
        st.selectbox("Haus wählen", [-1, *db.auswahl], key="w_sel", on_change=_cb("sel", "w_sel"),
                     format_func=lambda i: "– Haus wählen –" if i < 0 else db.N[i]["name"],
                     label_visibility="collapsed")
        html(db.node_info_html(ss.sel, h, ss.wahl))
        setze("w_win", ss.win)
        st.selectbox("Zeitfenster", list(lg.FENSTER), format_func=lg.FENSTER.get, key="w_win",
                     on_change=_cb("win", "w_win"), label_visibility="collapsed")
        html(f'<div class="muted klein">Vorlauf <span style="color:{F["vor"]}">■</span> / Rücklauf '
             f'<span style="color:{F["rueck"]}">■</span> in °C</div>')
        if ss.sel >= 0:
            m = db.N[ss.sel]["m"]
            i0, i1 = db.win_range(h, ss.win)
            st.plotly_chart(diagramm([(db.werte[m, 0], F["vor"], 1.3), (db.werte[m, 1], F["rueck"], 1.3)],
                                     i0, i1, False, 150), width="stretch", config={"displayModeBar": False})
        else:
            st.container(height=150, border=False)
        html('<div class="muted klein">Spreizung in K (nur Stunden mit Durchfluss)</div>')
        if ss.sel >= 0:
            st.plotly_chart(diagramm([(db.spreizung[m], F["ink"], 1.3)], i0, i1, True, 150),
                            width="stretch", config={"displayModeBar": False})
        else:
            st.container(height=150, border=False)
        st.divider()
        st.markdown('<div class="fw-h2">Gesamtleistung im Zeitverlauf</div>', unsafe_allow_html=True)
        st.plotly_chart(diagramm([(db.sumP, F["accent"], 1.2)], 0, db.H - 1, True, 150, klickbar=True),
                        width="stretch", key=f"cNet{ss.netz_nr}", on_select=cb_netz,
                        selection_mode="points", config={"displayModeBar": False})
        html('<div class="muted klein">Klicken setzt den Zeitpunkt. Erklärungen im Reiter „So funktioniert\'s“.</div>')


# --- Handlungsliste -------------------------------------------------------------------------

def reiter_liste() -> None:
    h = ss.h
    st.markdown("### Handlungsliste")
    wechsel = ("<span>Mit „Saison wie Zeitregler“ zeigt sie vor dem 01.09.2024 den Stand vor den Begehungen, danach den "
               "heutigen. Die Saison lässt sich hier oder auf der Karte im Feld „Bewertung“ fest wählen, beide Felder "
               "sind gekoppelt.</span> ") if db.VOR else ""
    html(f'<p class="muted">Alle Zähler mit Modellergebnis, die dringendsten zuerst. Stand: '
         f'<b>{lg.esc(db.stand_text(db.stand(h, ss.wahl)))}</b>. {wechsel}„Karte“ zeigt das Haus. Warum eine Station '
         'hier steht, steht in der Spalte „Warum“. Wie die Reihenfolge entsteht, erklärt der Reiter „So funktioniert\'s“.</p>')
    zeilen = db.liste(h, ss.wahl, ss.fm, ss.alle)
    f = st.columns([1.6, 1.6, 2.2, 1.6, 1.1, 1.2], vertical_alignment="center")
    if db.VOR:
        setze("w_fstand", ss.wahl)
        f[0].selectbox("Saison der Empfehlung", list(lg.STAENDE), format_func=lg.STAENDE.get, key="w_fstand",
                       on_change=_cb("wahl", "w_fstand"), label_visibility="collapsed")
    setze("w_fm", ss.fm)
    f[1].selectbox("Maßnahme", list(lg.MASS_FILTER), format_func=lg.MASS_FILTER.get, key="w_fm",
                   on_change=_cb("fm", "w_fm"), label_visibility="collapsed")
    setze("w_alle", ss.alle)
    f[2].checkbox("auch Zähler ohne Handlungsbedarf", key="w_alle", on_change=_cb("alle", "w_alle"))
    if db.VOR:
        f[3].button("Stand vor den Begehungen", on_click=cb_vor, width="stretch")
        f[4].button("Stand heute", on_click=cb_heute, width="stretch")
    f[5].markdown(f'<span style="color:{F["muted"]}">{len(zeilen)} Zähler</span>', unsafe_allow_html=True)

    breiten = [0.5, 0.9, 1.1, 2.0, 3.2, 3.2, 0.9]
    kopf = st.columns(breiten)
    for c, t in zip(kopf, ["Platz", "Zähler", "Dringlichkeit", "Empfohlene Maßnahme", "Warum", "Befund bei der Begehung", ""]):
        c.markdown(f'<div class="lkopf">{t}&nbsp;</div>', unsafe_allow_html=True)
    if not zeilen:
        html('<p class="muted">Keine Zähler für diese Auswahl.</p>')
    for z, k, s in zeilen:
        c = st.columns(breiten, vertical_alignment="top")
        rang = s.get("rang")
        werte = [lg.js_str(rang) if lg.wahr(rang) else "", lg.esc(z),
                 f'<span class="badge" style="background:{lg.DR_FARBE[s["dr"]]}">{lg.esc(lg.DR_NAME[s["dr"]])}</span>',
                 lg.esc(s["empfehlung"]), f'<span class="klein">{lg.esc(s["warum"])}</span>',
                 f'<span class="klein">{lg.esc(s.get("befund", lg.UNDEF))}</span>']
        for spalte, w in zip(c, werte):
            spalte.markdown(f'<div class="fw lzeile">{w}</div>', unsafe_allow_html=True)
        if k >= 0:
            c[6].button("Karte", key=f"k_{z}", on_click=cb_karte_zeigen, args=(k,))
        else:
            c[6].markdown('<div class="fw"><span class="muted klein">nicht auf der Karte</span></div>',
                          unsafe_allow_html=True)


# --- So funktioniert's ----------------------------------------------------------------------

#Text wie im Reiter der HTML-Fassung (notebooks/dashboard_final.py), Werte aus den Paketen eingesetzt
INFO_HTML = r"""
<h2>So funktioniert das Dashboard</h2>
<p>Das Dashboard beantwortet für jede Hausstation die Fragen der Aufgabenstellung: Wie läuft das Netz, wie läuft die
  Station, hat sich etwas verändert, welcher Fehler steckt dahinter und was soll zuerst gemacht werden. Jede Anzeige
  kommt von dem Modell, das im Vergleich in Notebook 35 dafür am besten abgeschnitten hat. Kein Modell kann alles,
  deshalb arbeiten zwei Ansätze zusammen:</p>
<ul>
  <li><b>Monitoring-Modell:</b> Jede Station hat eine Kennlinie über der Außentemperatur. Ein Konto (CUSUM) zählt, ob sie über
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
      <td>Monitoring-Modell: Netzvergleich je Winter (Notebook 19) und Abstand zum besten Viertel (Notebook 22)</td>
      <td>Nur der Vergleich mit den anderen Stationen sieht eine Station, die schon immer schlecht läuft. Ein Wächter, der
        jede Station mit sich selbst vergleicht, hält das für normal (Notebook 35, Test D).</td>
      <td>Beschreibt, wo die Station steht. Sagt keine Einsparung voraus.</td></tr>
    <tr><td><b>Hat sich an einer Station etwas verändert?</b><br><span class="muted">Anomalieerkennung</span></td>
      <td>Färbung „Meldungen“, Hausfenster „Veränderung“</td>
      <td>An Heiztagen das Monitoring-Modell (Tagesmonitor: Kennlinie und CUSUM-Konto). An warmen Tagen und bei Stationen ohne
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
        Bestätigung durch das Fehlerbild „ventil“ aus dem Monitoring-Modell.</td>
      <td>Test C (Kreuzvalidierung über Stationsgruppen): AUC 0,83, findet 8 von 11 Ventilfällen bei 4 Fehlalarmen
        (Notebook 35). Mit der Wahl des Modells ohne die Teststationen kommt dasselbe heraus (0,84, Abschnitt 16). Die
        einfache Regel „nachts im Sommer fließt Wasser“ ist genauso gut (0,85). Das Fehlerbild aus dem Monitoring-Modell ist 4 von 4 richtig,
        findet aber nur 4. Es ist dasselbe Modell wie auf der Folie. Weil die Regel genauso gut und leicht verständlich
        ist, steht der Sommernacht-Anteil als Erklärung daneben.</td>
      <td>Pilot. Der Score ist eine Rangfolge, keine Wahrscheinlichkeit.</td></tr>
    <tr><td><b>Sind Leitungen ungedämmt?</b><br><span class="muted">Klassifizierung → Dämmung</span></td>
      <td>Färbung „Maßnahme“, Hausfenster „Verdacht“</td>
      <td>LSTM-Modell: eigenes Dämmungsmodell, Hinweis ab Score <span class="g-daemmung"></span></td>
      <td>Keine einzelne Regel kommt über AUC 0,61, auch wenn man sie an den Befunden einstellt. Die KI findet ein Muster
        in der LSTM-Zusammenfassung, Test C 0,79 (findet 15 von 22 bei 7 Fehlalarmen). Der Vorsprung (+0,18) ist knapp nicht gesichert
        (Notebook 35, Abschnitt 16b).</td>
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
      <td><b>hoch:</b> Reparatur, bestätigt durch das Fehlerbild „ventil“ aus dem Monitoring-Modell (4 von 4 richtig).
        <b>mittel:</b> Reparatur nur nach dem Ventil-Score (Test C: 8 von 11 gefunden bei 4 Fehlalarmen).
        <b>niedrig:</b> nur Kapazität, Dämmung (Hinweis) oder Daten prüfen. Innerhalb einer Stufe nach Ventil-Score:
        Unter den ersten 10 nach Score hatten 7 einen Ventilbefund, Zufall wären etwa 2 (Notebook 35, Test E).</td>
      <td>Die Stufen sind gesetzt, nicht gelernt. Ob die Reihenfolge im Betrieb trägt, zeigt erst eine Begehung nach der
        Liste.</td></tr>
  </tbody>
</table>
</div>

<h3>Warum zwei Ansätze und nicht ein Modell für alles?</h3>
<ul>
  <li>Keins der beiden Modelle ist allein besser. Sie können Verschiedenes (Notebook 35).</li>
  <li>Wir haben ein LSTM gebaut, das genauso arbeitet wie der Tagesmonitor aus dem Monitoring-Modell: feste Referenz statt Vergleich mit der
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
  <li><b>Nachbarn im Rohrbaum als Merkmal:</b> Nachbarn teilen kaum Signal (Notebook 32) und verbessern weder Meldung noch
    Erkennung (Notebook 34).</li>
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
    Bestätigung durch das Fehlerbild aus dem Monitoring-Modell.</li>
  <li><b>Reparatur bei Sonderfällen:</b> Bei Stationen mit Werten außerhalb dessen, woraus die Modelle gelernt haben, oder mit
    einem großen Teil des Netzvolumens ist kein Score geprüft. Sie bekommen nur „Daten prüfen“.</li>
  <li><b>Einspar-Schätzung für das Netz:</b> Sie hätte angenommen, dass jede Station mit Maßnahme den Rücklauf der besten
    Gruppe erreicht. Ob Begehungen den Rücklauf messbar senken, ist nicht gesichert (Notebook 35, Test D).</li>
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
  <div><b>Notebook 35</b>Modelle gelernt, geprüft und als Pakete gespeichert</div>
  <div><b>python -m src.dashboard_daten</b>Pakete auf die aktuellen Daten angewendet, ohne neu zu lernen</div>
  <div><b>Notebook 37</b>Rohrbaum aus Notebook 32, Karte gebaut</div>
</div>
<p class="muted klein" id="infoStand"></p>
"""


def reiter_info() -> None:
    w = db.info_werte()
    text = (INFO_HTML.replace('<span class="g-winter"></span>', lg.esc(w["winter"]))
            .replace('<span class="g-daemmung"></span>', lg.esc(w["daemmung"]))
            .replace('<span class="g-vertrag"></span>', lg.esc(w["vertrag"]))
            .replace('<span id="punkteText"></span>', lg.esc(w["punkte"]))
            .replace('<p class="muted klein" id="infoStand"></p>', f'<p class="muted klein">{lg.esc(w["stand"])}</p>'))
    #ohne Einrückung und Leerzeilen, sonst liest Markdown Teile als Codeblock
    text = "\n".join(z.strip() for z in text.splitlines() if z.strip())
    st.markdown(f'<div class="info">{text}</div>', unsafe_allow_html=True)


# --- Seite ----------------------------------------------------------------------------------

{"karte": reiter_karte, "liste": reiter_liste, "info": reiter_info}[ss.tab]()

#Abspielen: wie setInterval in der HTML-Fassung, ein Schritt je Durchlauf
if ss.playing:
    time.sleep(ABSPIELEN_MS / 1000)
    nh = ss.h + ss.step
    set_h(0 if nh >= db.H else nh)
    st.rerun()
