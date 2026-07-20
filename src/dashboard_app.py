"""
Interaktives Dashboard fuer UEZ Mainfranken - Fernwaermenetz Wiesentheid.

    streamlit run src/dashboard_app.py

Grundentscheidung: Die Ampelfarben basieren NICHT auf der regelbasierten
Fehlererkennung (die ist auf echten Daten nicht trennscharf, siehe
docs/echte-daten-integration.md), sondern auf der direkt gemessenen
mittleren Winter-Ruecklauftemperatur - laut UEZ der zentrale
Effizienz-Indikator. Die Fehlererkennung erscheint als eigener, ehrlich
als "in Entwicklung" markierter Bereich.

Die App liest ausschliesslich vorhandene Pipeline-Artefakte aus
data/processed/ (keine Rohdaten, keine eigene Datenverarbeitung).
Fehlt ein Artefakt, startet die App trotzdem und sagt, wie man es
erzeugt. Terminologie: das hier ist die geografische Dashboard-Karte,
nicht der abstrakte logische Graph.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# pyarrow-Segfault-Schutz: pandas 3 erzeugt Strings standardmaessig
# arrow-gestuetzt; in dieser Umgebung segfaultet pyarrow, sobald ein
# Streamlit-Rerun (zweiter Script-Thread) Arrow-String-Arrays anlegt
# oder vergleicht. Python-Storage umgeht das vollstaendig.
pd.set_option("mode.string_storage", "python")

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
WINDOW_DIR = PROCESSED / "real_meters_window"

# "streamlit run src/dashboard_app.py" laeuft ohne Paketkontext; fuer
# die Overlay-/Snapping-Imports muss das src-Paket importierbar sein.
import sys  # noqa: E402
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from src.snap_hast import SNAP_MAX_DIST_M
except Exception:  # Rohdaten-/Import-Probleme duerfen die App nicht stoppen
    SNAP_MAX_DIST_M = 50.0

# --- Ampelschwellen: mittlere Winter-Ruecklauftemperatur (°C) ---------------
# STARTWERTE aus der Projektdiskussion - fachlich mit UEZ zu validieren!
# Hintergrund: ueberhoehter Ruecklauf ist der zentrale Effizienzverlust
# im Netz (schlechte Auskuehlung auf der Sekundaerseite).
RT_GREEN_MAX = 45.0   # gruen:  Ruecklauf unter 45 °C - gute Auskuehlung
RT_YELLOW_MAX = 50.0  # gelb:   45-50 °C - beobachten
RT_ORANGE_MAX = 55.0  # orange: 50-55 °C - auffaellig, pruefen
#                       rot:    ueber 55 °C - prioritaer begehen

# Statusfarben, validiert (dataviz-Sechs-Checks, Licht-Surface). Farbe
# steht nie allein: Emoji + Textlabel begleiten jede Verwendung.
AMPEL = {
    "gruen":  {"emoji": "🟢", "farbe": "#1a7f37", "rang": 4,
               "label": f"Grün (RT < {RT_GREEN_MAX:.0f} °C)"},
    "gelb":   {"emoji": "🟡", "farbe": "#bf9004", "rang": 3,
               "label": f"Gelb ({RT_GREEN_MAX:.0f}–{RT_YELLOW_MAX:.0f} °C)"},
    "orange": {"emoji": "🟠", "farbe": "#b1400f", "rang": 2,
               "label": f"Orange ({RT_YELLOW_MAX:.0f}–{RT_ORANGE_MAX:.0f} °C)"},
    "rot":    {"emoji": "🔴", "farbe": "#a31136", "rang": 1,
               "label": f"Rot (RT > {RT_ORANGE_MAX:.0f} °C)"},
    "grau":   {"emoji": "⚪", "farbe": "#6e7781", "rang": 5,
               "label": "Keine verlässlichen Daten"},
}

MEASURE_LABELS = {
    "filter_gereinigt": "Filter gereinigt",
    "durchfluss_neu": "Durchfluss neu eingestellt",
    "daemmung_neu": "Leitungen neu gedämmt",
    "stellmotor_getauscht": "Stellmotor getauscht",
    "stellventil_getauscht": "Stellventil getauscht",
    "regler_getauscht": "Regler getauscht",
    "vertrag_changed": "Vertragsleistung geändert",
}

# Artefakt -> (Pfad, Kommando zum Erzeugen)
ARTIFACTS = {
    "geocode": (PROCESSED / "hast_geocoded.csv",
                "python -m src.main --geocode"),
    "quality": (PROCESSED / "meter_quality.csv",
                "python -m src.meter_quality"),
    "features": (PROCESSED / "features_real.csv",
                 "python -m src.detect_real"),
    "inspections": (PROCESSED / "inspections_tidy.csv",
                    "python -m src.main"),
    "predictions": (PROCESSED / "predictions_real.csv",
                    "python -m src.detect_real"),
    "snapped": (PROCESSED / "hast_snapped.csv",
                "python -m src.snap_hast"),
    "priority": (PROCESSED / "priority_scores.csv",
                 "python -m src.priority"),
}


# --- Daten laden (nur Artefakte, mit Cache) ---------------------------------

def _plain_strings(df: pd.DataFrame) -> pd.DataFrame:
    """String-Spalten auf Objekt-Dtype casten.

    pandas 3 legt Strings arrow-gestuetzt ab; nach dem Roundtrip durch
    den st.cache_data-Cache segfaultet pyarrow in dieser Umgebung beim
    Vergleich aus einem zweiten Script-Thread (Streamlit-Rerun).
    Plain-object-Strings umgehen das.
    """
    for c in df.columns:
        if not (pd.api.types.is_numeric_dtype(df[c])
                or pd.api.types.is_datetime64_any_dtype(df[c])
                or pd.api.types.is_bool_dtype(df[c])):
            df[c] = df[c].astype(object)
    df.columns = df.columns.astype(object)  # auch die Spaltenlabels
    return df


@st.cache_data
def read_artifact(key: str) -> pd.DataFrame | None:
    path, _ = ARTIFACTS[key]
    if not path.exists():
        return None
    return _plain_strings(pd.read_csv(path))


def missing_artifact_warnings(keys: list[str]) -> list[str]:
    msgs = []
    for k in keys:
        path, cmd = ARTIFACTS[k]
        if not path.exists():
            msgs.append(f"`{path.relative_to(ROOT)}` fehlt → erzeugen mit `{cmd}`")
    return msgs


@st.cache_data
def build_stations() -> pd.DataFrame | None:
    """Eine Zeile je Messstelle (Zaehler) mit Ampel, Qualitaet, Begehung."""
    geo = read_artifact("geocode")
    if geo is None:
        return None
    df = geo[["Zählernummer", "Anschlusswert", "address", "address_norm",
              "lat", "lon", "note", "in_expected_area"]].copy()
    df["Zählernummer"] = df["Zählernummer"].astype(int)
    df["pos_unsicher"] = (df["note"].astype(str)
                          .str.contains("street_or_area_fallback"))

    quality = read_artifact("quality")
    if quality is not None:
        q = quality[["Zählernummer", "quality_class"]].copy()
        q["Zählernummer"] = q["Zählernummer"].astype(int)
        df = df.merge(q, on="Zählernummer", how="left")
    else:
        df["quality_class"] = pd.NA

    feats = read_artifact("features")
    if feats is not None:
        f = feats[["Zählernummer", "rt_mean_winter", "vl_mean_winter"]].copy()
        f["Zählernummer"] = f["Zählernummer"].astype(int)
        df = df.merge(f, on="Zählernummer", how="left")
    else:
        df["rt_mean_winter"] = pd.NA
        df["vl_mean_winter"] = pd.NA

    insp = read_artifact("inspections")
    if insp is not None:
        insp = insp.copy()
        insp["datum"] = pd.to_datetime(insp["datum"], errors="coerce")
        last = (insp.sort_values("datum")
                    .groupby("address_norm").last().reset_index())
        last["begehung_massnahmen"] = last.apply(
            lambda r: ", ".join(lbl for col, lbl in MEASURE_LABELS.items()
                                if bool(r.get(col))) or "keine Maßnahme notiert",
            axis=1)
        df = df.merge(
            last[["address_norm", "datum", "begehung_massnahmen"]],
            on="address_norm", how="left")
        df = df.rename(columns={"datum": "begehung_datum"})
    else:
        df["begehung_datum"] = pd.NaT
        df["begehung_massnahmen"] = pd.NA

    snap = read_artifact("snapped")
    if snap is not None:
        s = snap[["Zählernummer", "snap_dist_m", "snap_verlaesslich",
                  "node_lat", "node_lon"]].copy()
        s["Zählernummer"] = s["Zählernummer"].astype(int)
        df = df.merge(s, on="Zählernummer", how="left")
    else:
        df["snap_dist_m"] = pd.NA
        df["snap_verlaesslich"] = pd.NA
        df["node_lat"] = pd.NA
        df["node_lon"] = pd.NA

    prio = read_artifact("priority")
    prio_cols = ["prio_score", "prio_klasse", "begruendung_prio",
                 "beitrag_ruecklauf", "beitrag_last", "beitrag_begehung"]
    if prio is not None:
        pr = prio[["Zählernummer"] + prio_cols].copy()
        pr["Zählernummer"] = pr["Zählernummer"].astype(int)
        df = df.merge(pr, on="Zählernummer", how="left")
    else:
        for c in prio_cols:
            df[c] = pd.NA

    df[["kategorie", "begruendung"]] = df.apply(
        lambda r: pd.Series(ampel_category(r)), axis=1)
    return _plain_strings(df)  # pyarrow-Segfault-Schutz, siehe oben


@st.cache_data
def load_pipe_overlay() -> tuple[list, list] | None:
    """Rohrgeometrie des Wiesentheid-Clusters als Linienzuege (WGS84).

    Geografisches Overlay fuer die Dashboard-Karte - nicht der abstrakte
    logische Graph. Liest die Shapefiles ueber die bestehenden Loader
    und nutzt visualize.find_main_cluster fuers Cropping (keine
    Duplikation). Rueckgabe: (lats, lons) None-separiert fuer einen
    einzigen Plotly-Linientrace; None, wenn die Rohdaten fehlen.
    """
    try:
        from shapely.geometry import MultiLineString

        from src import load_data as ld
        from src.visualize import find_main_cluster
        pipes = ld.load_pipes()
    except Exception:
        return None
    b = find_main_cluster(pipes)
    crop = pipes.cx[b[0]:b[2], b[1]:b[3]].to_crs("EPSG:4326")
    lats: list = []
    lons: list = []
    for geom in crop.geometry:
        if geom is None or geom.is_empty:
            continue
        parts = geom.geoms if isinstance(geom, MultiLineString) else [geom]
        for part in parts:
            xs, ys = part.xy
            lons += list(xs) + [None]
            lats += list(ys) + [None]
    return lats, lons


def ampel_category(row: pd.Series) -> tuple[str, str]:
    """(Ampelkategorie, Begruendung) fuer eine Messstelle.

    Grau hat Vorrang: ohne verlaessliche Daten wird nie gruen gefaerbt.
    """
    qc = row.get("quality_class")
    if pd.isna(qc):
        return "grau", "keine Zeitreihen-Exporte für diesen Zähler vorhanden"
    if qc != "auswertbar":
        return "grau", f"Datenqualität: {qc}"
    rt = row.get("rt_mean_winter")
    if pd.isna(rt):
        return "grau", "kein Winter-Rücklaufwert im Analysefenster"
    reason = f"mittlerer Winter-Rücklauf {rt:.1f} °C"
    if rt < RT_GREEN_MAX:
        return "gruen", reason
    if rt < RT_YELLOW_MAX:
        return "gelb", reason
    if rt < RT_ORANGE_MAX:
        return "orange", reason
    return "rot", reason


def spread_shared_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Punkte mit identischen Koordinaten kompakt auffaechern.

    Betrifft die bekannten Strassenmittelpunkt-Fallbacks (mehrere HAST
    auf einer Koordinate). Sonnenblumen-Anordnung (goldener Winkel):
    deterministisch, dicht gepackt und optisch ruhig, Radius waechst
    mit sqrt(n) (~4-13 m). Die Streuung dient NUR der Sichtbarkeit und
    ist keine echte Position - kein Raten von Hauspositionen entlang
    der Strasse.
    """
    import math
    base_m = 4.0                     # Abstand-Basisradius in Metern
    golden = math.pi * (3 - 5 ** 0.5)  # goldener Winkel ~2.4 rad
    m_lat = 111_320.0                # Meter je Breitengrad
    out = df.copy()
    out["lat_plot"], out["lon_plot"] = out["lat"], out["lon"]
    for (lat0, _), grp in out.groupby(["lat", "lon"]):
        if len(grp) < 2:
            continue
        m_lon = m_lat * math.cos(math.radians(lat0))
        idx = grp.sort_values("Zählernummer").index
        for i, ix in enumerate(idx):
            r = base_m * math.sqrt(i + 1)
            ang = i * golden
            out.loc[ix, "lat_plot"] = out.loc[ix, "lat"] + r * math.sin(ang) / m_lat
            out.loc[ix, "lon_plot"] = out.loc[ix, "lon"] + r * math.cos(ang) / m_lon
    return out


def street_of(address: str) -> str:
    """Strassenname ohne Hausnummer ('Blumenstr. 8' -> 'Blumenstr.').

    Die Strassenzuordnung ist - anders als die Hausposition - auch bei
    Strassenmittelpunkt-Geocoding verlaesslich.
    """
    return re.sub(r"\s*\d+.*$", "", str(address)).strip()


# --- UI ----------------------------------------------------------------------

st.set_page_config(page_title="ÜZ Fernwärme Wiesentheid",
                   page_icon="♨️", layout="wide")

# Minimales, dokumentiertes CSS - rein kosmetisch: Header-Banner,
# Kennzahlen-Kacheln, Ampel-Badges. Theme-Variablen mit Fallbacks,
# damit Light- und Dark-Mode funktionieren; als einzige interne
# Streamlit-Struktur wird die stabile Metric-Test-ID angesprochen.
st.markdown("""
<style>
  .dash-header {
    background: linear-gradient(100deg, #16324f 0%, #1f5c8b 70%, #2c7bb5 100%);
    color: #ffffff; border-radius: 12px;
    padding: 1.1rem 1.4rem 0.9rem 1.4rem; margin-bottom: 0.6rem;
  }
  .dash-header h1 { color: #ffffff; font-size: 1.55rem; margin: 0 0 0.15rem 0; }
  .dash-header .sub  { color: #cfe3f3; font-size: 0.92rem; margin: 0; }
  .dash-header .hint { color: #9ec7e8; font-size: 0.8rem; margin: 0.45rem 0 0 0; }
  [data-testid="stMetric"] {
    background: var(--secondary-background-color, #f6f8fa);
    border: 1px solid rgba(110, 119, 129, 0.25);
    border-radius: 10px; padding: 0.7rem 1rem;
  }
  .ampel-badge {
    display: inline-block; margin: 0.15rem 0.5rem 0.15rem 0;
    padding: 0.15rem 0.6rem; border-radius: 999px;
    border: 1px solid rgba(110, 119, 129, 0.3); font-size: 0.85rem;
  }
  .ampel-badge .dot {
    display: inline-block; width: 0.6rem; height: 0.6rem;
    border-radius: 50%; margin-right: 0.35rem;
  }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="dash-header">'
    '<h1>♨️ Fernwärmenetz Wiesentheid — Stationsübersicht</h1>'
    '<p class="sub">ÜZ Mainfranken · Projektseminar JMU Würzburg · '
    'geografische Dashboard-Karte (nicht der abstrakte Netzgraph)</p>'
    '<p class="hint">Ampel = gemessener Winter-Rücklauf je '
    'Hausübergabestation (HAST); Schwellen sind Startwerte und fachlich '
    'mit ÜZ zu validieren.</p>'
    '</div>', unsafe_allow_html=True)

warns = missing_artifact_warnings(list(ARTIFACTS))
if warns:
    st.warning("**Fehlende Datenartefakte** — betroffene Bereiche bleiben "
               "leer:\n\n" + "\n".join(f"- {w}" for w in warns))

stations = build_stations()
if stations is None:
    st.error("Ohne `hast_geocoded.csv` kann keine Stationsliste aufgebaut "
             "werden. Erzeugen mit: `python -m src.main --geocode` "
             "(fragt Nominatim ab, braucht Netz).")
    st.stop()

# --- 1. Kopfbereich: Netz-Kennzahlen -----------------------------------------

bewertet = stations[stations["kategorie"] != "grau"]
n_grau = int((stations["kategorie"] == "grau").sum())
med_rt = bewertet["rt_mean_winter"].median()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Messstellen gesamt", f"{len(stations)}")
c2.metric("Mit Ampel bewertbar", f"{len(bewertet)}",
          help="Qualitätsklasse 'auswertbar' und Winter-Rücklauf im "
               "Analysefenster vorhanden")
c3.metric("Ohne verlässliche Daten", f"{n_grau}",
          f"{n_grau / len(stations) * 100:.0f} % der Messstellen",
          delta_color="off")
c4.metric("Winter-Rücklauf (Median, bewertete)",
          f"{med_rt:.1f} °C" if pd.notna(med_rt) else "—",
          help="Median der mittleren Winter-Rücklauftemperaturen über "
               "alle bewerteten Stationen")

badges = "".join(
    f'<span class="ampel-badge"><span class="dot" '
    f'style="background:{AMPEL[k]["farbe"]}"></span>'
    f'{AMPEL[k]["emoji"]} {AMPEL[k]["label"]}: '
    f'<b>{int((stations["kategorie"] == k).sum())}</b></span>'
    for k in ["rot", "orange", "gelb", "gruen", "grau"])
st.markdown(badges, unsafe_allow_html=True)


tab_karte, tab_prio, tab_gesamt, tab_dev = st.tabs([
    "🗺️ Netzkarte & Stationsdetail",
    "🎯 Priorisierung & Stationsliste",
    "📊 Netz-Gesamtschau",
    "🚧 Fehlererkennung (in Entwicklung)",
])

# --- 1b. Top-Handlungsempfehlungen -------------------------------------------
with tab_prio:
    if stations["prio_score"].notna().any():
        st.markdown("#### Top-Handlungsempfehlungen")
        st.caption(
            "Priorisierte Handlungsempfehlung auf Basis aktueller Messwerte "
            "und dokumentierter Begehungen — **keine Ausfallvorhersage**. "
            "Transparenter Score (Rücklauf / Anschlusswert / Begehungsalter, "
            "`src/priority.py`); Gewichte und Schwellen sind mit ÜZ zu "
            "validieren.")
        top = (stations[stations["prio_score"].notna()]
               .sort_values("prio_score", ascending=False).head(8))
        top_tbl = pd.DataFrame({
            "Ampel": [f"{AMPEL[r['kategorie']]['emoji']}"
                      for _, r in top.iterrows()],
            "Adresse": top["address"].values,
            "Score": top["prio_score"].values,
            "Warum": top["begruendung_prio"].values,
        })
        st.dataframe(top_tbl, hide_index=True, width="stretch",
                     column_config={"Score": st.column_config.NumberColumn(
                         "Score (0–100)", format="%.0f")})
    else:
        st.info("Keine Prioritäts-Scores vorhanden — erzeugen mit "
                "`python -m src.priority`.")

# --- 2. Karte + 3. Detailpanel ------------------------------------------------
with tab_karte:
    map_col, detail_col = st.columns([3, 2], gap="large")

    with map_col:
        st.subheader("Netzkarte")
        zeige_snap = st.checkbox(
            f"Zuordnung Station → nächster Rohrknoten einblenden "
            f"(nur Stationen mit Distanz ≤ {SNAP_MAX_DIST_M:.0f} m)",
            value=False)
        plot_df = stations[stations["lat"].notna()
                           & stations["in_expected_area"].fillna(False)]
        n_no_coord = len(stations) - len(plot_df)
        if plot_df.empty:
            st.info("Keine Koordinaten im erwarteten Gebiet vorhanden.")
        else:
            plot_df = spread_shared_coords(plot_df)
            fig = go.Figure()

            # Rohrgeometrie dezent UNTER die Stationspunkte legen
            overlay = load_pipe_overlay()
            if overlay is not None:
                fig.add_trace(go.Scattermap(
                    lat=overlay[0], lon=overlay[1], mode="lines",
                    line=dict(color="#9aa0a6", width=1.3),
                    name="Leitungsnetz (Rohrgeometrie)",
                    hoverinfo="skip",
                ))

            # optionale Zuordnungslinien Station -> Rohrknoten, bewusst nur
            # fuer verlaesslich gesnappte Stationen (keine falsche Genauigkeit)
            if zeige_snap:
                ok = plot_df[(plot_df["snap_verlaesslich"] == True)  # noqa: E712
                             & plot_df["node_lat"].notna()]
                if ok.empty:
                    st.info("Keine Snapping-Daten vorhanden — erzeugen mit "
                            "`python -m src.snap_hast`.")
                else:
                    s_lat: list = []
                    s_lon: list = []
                    for _, r in ok.iterrows():
                        s_lat += [r["lat_plot"], r["node_lat"], None]
                        s_lon += [r["lon_plot"], r["node_lon"], None]
                    fig.add_trace(go.Scattermap(
                        lat=s_lat, lon=s_lon, mode="lines",
                        line=dict(color="#57606a", width=1),
                        name="Zuordnung zum Rohrknoten",
                        hoverinfo="skip",
                    ))

            for k in ["gruen", "gelb", "orange", "rot", "grau"]:
                sub = plot_df[plot_df["kategorie"] == k]
                if sub.empty:
                    continue
                hover = [
                    f"{r['address']}<br>{AMPEL[k]['label']}<br>{r['begruendung']}"
                    + ("<br>⚠️ Position unsicher (Straßenmitte, "
                       "OSM-Hausnummernlücke)" if r["pos_unsicher"] else "")
                    for _, r in sub.iterrows()]
                fig.add_trace(go.Scattermap(
                    lat=sub["lat_plot"], lon=sub["lon_plot"],
                    mode="markers",
                    name=f"{AMPEL[k]['emoji']} {AMPEL[k]['label']}",
                    marker=dict(
                        size=(6 + sub["Anschlusswert"].fillna(10) ** 0.5 * 1.6)
                             .clip(9, 34),
                        color=AMPEL[k]["farbe"],
                        opacity=[0.55 if u else 0.95
                                 for u in sub["pos_unsicher"]],
                    ),
                    text=hover, hoverinfo="text",
                    customdata=sub["Zählernummer"],
                ))
            fig.update_layout(
                map=dict(style="open-street-map",
                         center=dict(lat=float(plot_df["lat"].mean()),
                                     lon=float(plot_df["lon"].mean())),
                         zoom=15),
                height=560, margin=dict(l=0, r=0, t=0, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.01),
            )
            # dauerhafter Unsicherheits-Hinweis direkt auf der Karte
            fig.add_annotation(
                xref="paper", yref="paper", x=0.5, y=0.015,
                xanchor="center", yanchor="bottom", showarrow=False,
                text=("⚠️ Stationspunkte straßenweise gruppiert — genaue "
                      "Hausposition unbekannt (ÜZ-Koordinaten ausstehend)"),
                font=dict(size=12, color="#24292f"),
                bgcolor="rgba(255,255,255,0.88)",
                bordercolor="#8a6d00", borderwidth=1, borderpad=4,
            )
            event = st.plotly_chart(fig, width="stretch",
                                    on_select="rerun", key="netzkarte")
            try:
                pts = event.selection.points  # type: ignore[union-attr]
            except AttributeError:
                pts = []
            if pts:
                st.session_state["sel_meter"] = int(pts[0]["customdata"])

            n_uns = int(plot_df["pos_unsicher"].sum())
            st.caption(
                f"Punktgröße = Anschlusswert. **{n_uns} von {len(plot_df)} "
                f"Positionen sind unsicher** (halbtransparent): OSM kennt im "
                f"Neubaugebiet keine Hausnummern, diese HAST liegen auf "
                f"Straßenmittelpunkten und sind zur Sichtbarkeit leicht "
                f"aufgefächert (~15 m). "
                + (f"{n_no_coord} Messstellen ohne brauchbare Koordinaten "
                   f"fehlen auf der Karte. " if n_no_coord else "")
                + ("" if overlay is not None else
                   "Rohrgeometrie nicht verfügbar (Shapefiles in `data/raw/` "
                   "fehlen in dieser Umgebung)."))


    with detail_col:
        st.subheader("Stationsdetail")
        opts = stations.sort_values("address")
        labels = {int(r["Zählernummer"]): f"{r['address']}  (Zähler {int(r['Zählernummer'])})"
                  for _, r in opts.iterrows()}
        ids = list(labels)
        default = st.session_state.get("sel_meter", ids[0])
        sel = st.selectbox("Station wählen (oder Punkt auf der Karte anklicken)",
                           ids, index=ids.index(default) if default in ids else 0,
                           format_func=lambda z: labels[z])
        row = stations[stations["Zählernummer"] == sel].iloc[0]
        k = row["kategorie"]

        st.markdown(
            f"### {AMPEL[k]['emoji']} {AMPEL[k]['label']}\n"
            f"**{row['address']}** — Zähler {int(row['Zählernummer'])}, "
            f"Anschlusswert {row['Anschlusswert']:.0f} kW\n\n"
            f"*Einstufung:* {row['begruendung']}  \n"
            f"*Datenqualität:* {row['quality_class'] if pd.notna(row['quality_class']) else 'keine Zeitreihen vorhanden'}"
            + ("  \n⚠️ *Kartenposition unsicher (Straßenmitte)*"
               if row["pos_unsicher"] else ""))

        if pd.notna(row.get("prio_score")):
            st.markdown(
                f"**Priorität: {row['prio_score']:.0f} / 100** — "
                f"Rücklauf {row['beitrag_ruecklauf']:.0f} + "
                f"Anschlusswert {row['beitrag_last']:.0f} + "
                f"Begehungsalter {row['beitrag_begehung']:.0f} Punkte  \n"
                f"{row['begruendung_prio']}")
            st.caption("Handlungsempfehlung aus aktuellen Messwerten, keine "
                       "Ausfallvorhersage; Gewichte mit ÜZ zu validieren.")
        elif isinstance(row.get("prio_klasse"), str):
            st.markdown(f"**Priorität:** {row['begruendung_prio']}")
        else:
            st.markdown("**Priorität:** keine Scores vorhanden "
                        "(`python -m src.priority`)")

        snap_d = row.get("snap_dist_m")
        if pd.notna(snap_d):
            if row.get("snap_verlaesslich") == True:  # noqa: E712
                st.markdown(f"**Leitungsnetz:** nächster Rohrknoten in "
                            f"{snap_d:.0f} m")
            else:
                st.markdown(
                    f"**Leitungsnetz:** ⚠️ nächster Rohrknoten erst in "
                    f"{snap_d:.0f} m (Schwelle {SNAP_MAX_DIST_M:.0f} m) — "
                    f"Position unsicher, Zuordnung zum Leitungsnetz nur "
                    f"näherungsweise; echte HAST-Koordinaten von ÜZ "
                    f"ausstehend.")
        else:
            st.markdown("**Leitungsnetz:** keine Snapping-Daten "
                        "(`python -m src.snap_hast`)")

        if pd.notna(row.get("begehung_datum")):
            st.markdown(
                f"**Letzte Begehung:** "
                f"{pd.Timestamp(row['begehung_datum']).date()} — "
                f"{row['begehung_massnahmen']}")
        else:
            st.markdown("**Letzte Begehung:** keine dokumentiert")

        ts_path = WINDOW_DIR / f"{int(row['Zählernummer'])}.csv"
        if ts_path.exists():
            ts = pd.read_csv(ts_path, parse_dates=["Timestamp"])
            ts = ts.set_index("Timestamp").sort_index()
            daily = ts.resample("D").mean(numeric_only=True)
            temps = daily[["Return temperature (°C)",
                           "Flow temperature (°C)"]].rename(columns={
                "Return temperature (°C)": "Rücklauf",
                "Flow temperature (°C)": "Vorlauf"})
            st.markdown(f"**Temperaturen** (Tagesmittel, °C — "
                        f"Ampelschwellen {RT_GREEN_MAX:.0f}/"
                        f"{RT_YELLOW_MAX:.0f}/{RT_ORANGE_MAX:.0f})")
            st.line_chart(temps, color=["#0969da", "#b35900"], height=200)
            st.markdown("**Leistung** (Tagesmittel, kW)")
            st.line_chart(daily[["Power (kW)"]].rename(
                columns={"Power (kW)": "Leistung"}),
                color=["#57606a"], height=160)
            st.caption("Rohwerte des Analysefensters (letzte 365 Tage je "
                       "Zähler), zu Tagesmitteln verdichtet.")
        else:
            st.info("Kein Zeitreihen-Fenster für diese Station materialisiert "
                    "(nur für auswertbare, zugeordnete Zähler; erzeugen mit "
                    "`python -m src.detect_real`).")

# --- 3b. Netz-Gesamtschau ----------------------------------------------------
with tab_gesamt:
    st.subheader("Netz-Gesamtschau")
    st.caption(
        "Aggregierte Effizienz-Sicht auf Basis der gemessenen "
        "Winter-Rücklauftemperatur (nicht der Fehlererkennung). "
        "**Die Straßen-Aggregation ist belastbarer als die "
        "Einzelstation-Position:** die Straßenzuordnung jeder Station ist "
        "sicher, nur die genaue Hausposition ist es nicht.")

    bew = stations[stations["rt_mean_winter"].notna()]
    if bew.empty:
        st.info("Keine Winter-Rücklaufwerte vorhanden — erzeugen mit "
                "`python -m src.detect_real`.")
    else:
        hist_col, kpi_col = st.columns([3, 2], gap="large")

        with hist_col:
            st.markdown(f"**Verteilung Winter-Rücklauf** "
                        f"({len(bew)} bewertete Stationen)")
            rt = bew["rt_mean_winter"].astype(float)
            edges = np.arange(np.floor(rt.min()), np.ceil(rt.max()) + 1)
            counts, _ = np.histogram(rt, bins=edges)
            centers = edges[:-1] + 0.5

            def _band(c: float) -> str:
                if c < RT_GREEN_MAX:
                    return AMPEL["gruen"]["farbe"]
                if c < RT_YELLOW_MAX:
                    return AMPEL["gelb"]["farbe"]
                if c < RT_ORANGE_MAX:
                    return AMPEL["orange"]["farbe"]
                return AMPEL["rot"]["farbe"]

            fig_h = go.Figure(go.Bar(
                x=centers, y=counts, width=0.9,
                marker_color=[_band(c) for c in centers],
                hovertemplate="%{x:.0f} °C: %{y} Stationen<extra></extra>",
            ))
            for t in (RT_GREEN_MAX, RT_YELLOW_MAX, RT_ORANGE_MAX):
                fig_h.add_vline(x=t, line_dash="dash", line_width=1,
                                line_color="#57606a",
                                annotation_text=f"{t:.0f}",
                                annotation_position="top",
                                annotation_font_size=11)
            fig_h.update_layout(
                height=260, margin=dict(l=0, r=0, t=24, b=0),
                xaxis_title="Winter-Rücklauf (°C)", yaxis_title="Stationen",
                showlegend=False, bargap=0.08,
            )
            st.plotly_chart(fig_h, width="stretch", key="rt_histogramm")
            st.caption("Balkenfarbe = Ampelband; gestrichelte Linien = "
                       "Ampelschwellen (mit ÜZ zu validieren).")

        with kpi_col:
            st.markdown("**Netz-Kennzahlen**")
            kat_rows = [
                {"Kategorie": f"{AMPEL[k]['emoji']} {AMPEL[k]['label']}",
                 "Stationen": int((stations["kategorie"] == k).sum()),
                 "Anteil": f"{(stations['kategorie'] == k).mean() * 100:.0f} %"}
                for k in ["rot", "orange", "gelb", "gruen", "grau"]]
            st.dataframe(pd.DataFrame(kat_rows), hide_index=True,
                         width="stretch")
            st.markdown(
                f"Winter-Rücklauf über die bewerteten Stationen: "
                f"**Median {rt.median():.1f} °C**, Mittel {rt.mean():.1f} °C, "
                f"Spanne {rt.min():.0f}–{rt.max():.0f} °C.  \n"
                f"{int((stations['kategorie'] == 'grau').sum())} Stationen "
                f"ohne verlässliche Daten (separat, nicht bewertet).")

        st.markdown("**Straßenzüge im Vergleich** — Straßenzuordnung ist "
                    "auch bei unsicherer Hausposition verlässlich")
        strassen = stations.copy()
        # ueber die NORMALISIERTE Adresse gruppieren, sonst zaehlen
        # Schreibvarianten (Rosenstr. / Rosenstraße) als zwei Strassen
        strassen["_key"] = strassen["address_norm"].map(street_of)
        strassen["_name"] = strassen["address"].map(street_of)
        agg = strassen.groupby("_key").agg(
            Straße=("_name", lambda s: s.mode().iat[0]),
            Stationen=("Zählernummer", "size"),
            bewertet=("rt_mean_winter", lambda s: int(s.notna().sum())),
            median_rt=("rt_mean_winter", "median"),
            max_rt=("rt_mean_winter", "max"),
        ).reset_index(drop=True).sort_values("median_rt", ascending=False,
                                             na_position="last")

        def _street_ampel(v: float) -> str:
            if pd.isna(v):
                return f"{AMPEL['grau']['emoji']} keine Daten"
            for k, mx in [("gruen", RT_GREEN_MAX), ("gelb", RT_YELLOW_MAX),
                          ("orange", RT_ORANGE_MAX)]:
                if v < mx:
                    return AMPEL[k]["emoji"]
            return AMPEL["rot"]["emoji"]

        agg.insert(1, "Ampel (Median)", agg["median_rt"].map(_street_ampel))
        st.dataframe(
            agg, hide_index=True, width="stretch",
            column_config={
                "bewertet": "davon bewertet",
                "median_rt": st.column_config.NumberColumn(
                    "Median Winter-Rücklauf °C", format="%.1f"),
                "max_rt": st.column_config.NumberColumn(
                    "Max °C", format="%.1f"),
            })

# --- 4. Liste / Wartungspriorisierung ----------------------------------------
with tab_prio:
    st.subheader("Stationsliste — auffälligste zuerst")
    st.caption("Spaltenköpfe anklicken zum Umsortieren. Stationen ohne "
               "verlässliche Daten haben keinen Score ('erst Daten klären') "
               "und stehen am Ende.")
    sortierung = st.radio(
        "Sortierung", ["Priorität (höchste zuerst)", "Ampel / Winter-Rücklauf"],
        horizontal=True, label_visibility="collapsed")

    tbl = stations.copy()
    tbl["Ampel"] = tbl["kategorie"].map(
        lambda k: f"{AMPEL[k]['emoji']} {k if k != 'grau' else 'keine Daten'}")
    tbl["_rang"] = tbl["kategorie"].map(lambda k: AMPEL[k]["rang"])
    if sortierung.startswith("Priorität"):
        tbl = tbl.sort_values(["prio_score", "_rang"],
                              ascending=[False, True], na_position="last")
    else:
        tbl = tbl.sort_values(["_rang", "rt_mean_winter"],
                              ascending=[True, False])
    st.dataframe(
        tbl[["Ampel", "address", "prio_score", "rt_mean_winter",
             "Anschlusswert", "quality_class", "begehung_datum",
             "begehung_massnahmen"]],
        width="stretch", hide_index=True,
        column_config={
            "address": "Adresse",
            "prio_score": st.column_config.NumberColumn(
                "Priorität (0–100)", format="%.0f"),
            "rt_mean_winter": st.column_config.NumberColumn(
                "Winter-Rücklauf °C", format="%.1f"),
            "Anschlusswert": st.column_config.NumberColumn(
                "Anschluss kW", format="%.0f"),
            "quality_class": "Datenqualität",
            "begehung_datum": st.column_config.DateColumn("Letzte Begehung"),
            "begehung_massnahmen": "Maßnahmen damals",
        })

# --- 5. Fehlererkennung (in Entwicklung) --------------------------------------
with tab_dev:
    st.subheader("🚧 Fehlererkennung (in Entwicklung)")
    st.markdown(
        "Die automatische Fehlererkennung ist **bewusst nicht** Grundlage "
        "der Ampel. Stand der Evaluation auf echten Daten "
        "(Details: `docs/echte-daten-integration.md`):\n\n"
        "- Die regelbasierte Baseline wurde mit den Begehungen als Ground "
        "Truth evaluiert und ist **noch nicht trennscharf**: sie meldet "
        "derzeit für praktisch jede Station einen Fehler, weil die "
        "Schwellen auf synthetischen Daten kalibriert wurden.\n"
        "- Hauptursache: die Oszillations-Regel (FFT) schlägt bei ~95 % "
        "der echten Zähler an — reales Zapfverhalten oszilliert "
        "naturgemäß.\n"
        "- Nächste Schritte: Schwellen auf echten Daten rekalibrieren, "
        "danach ML-Klassifikator mit Begehungslabels; ein GNN auf dem "
        "Netzgraphen ist geplant, sobald Baseline und Graph-Join stehen.")

    preds = read_artifact("predictions")
    if preds is not None:
        with st.expander("Aktueller Baseline-Output (nur zur Transparenz — "
                         "nicht für Entscheidungen nutzen)"):
            dist = preds["predicted_fault"].value_counts().reset_index()
            dist.columns = ["Vorhergesagter Fehler", "Anzahl Zähler"]
            st.dataframe(dist, hide_index=True)
            n_healthy = int((preds["predicted_fault"] == "healthy").sum())
            st.caption(
                f"{len(preds)} ausgewertete Zähler, davon {n_healthy} als "
                f"unauffällig eingestuft — diese fehlende Differenzierung "
                f"ist genau der Grund, warum die Ampel auf dem gemessenen "
                f"Rücklauf basiert.")

