"""Alarmbewertung: Schwelle des Tagesmonitors, Alarmrichtung, Priorität,
Fehlerbild und Baujahr als Kontext.

Setzt auf dem Ergebnis von `stationsblatt.rechne` auf und rechnet nichts an
den Stundenreihen neu. Vier Fragen aus der Bewertung des finalen Modells:

1. Wie ändern Treffer und Alarmlast sich mit der CUSUM-Schwelle h?
2. Kommt der Treffer bei Begehungen von Alarmen in Richtung schlechter
   (Fehler) oder besser (Reparatur)? Warnt der CUSUM vor einer Begehung?
3. Priorität je Station: im Netz auffällig und Verschlechterungsalarm in
   derselben Heizperiode.
4. Fehlerbild aus dem Muster der schlechten Netzkennzahlen und Baujahr als
   Kontext (Freitext der Begehung, sonst Zensus 2022 im 100-m-Gitter).

Alle Texte beschreiben ein Muster, sie nennen keine Ursache und keine
Maßnahme. Die Zuordnung Fehlerbild -> Maßnahme ist eine Teamentscheidung.

    python -m src.alarmbewertung
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from . import netzvergleich as nv
from . import tagesmonitor as tm

ROOT = Path(__file__).resolve().parents[1]

SCHWELLEN = (5.0, 8.0, 10.0, 15.0, 20.0)
#Das Konto darf bis 2 h steigen, bei h = 5 ist das der alte Deckel 10
DECKEL_FAKTOR = 2.0
#Alarmrichtung, die eine Verschlechterung beschreibt
SCHLECHTER = {("kwh_pro_m3", -1), ("log_volumen", 1)}
VORLAUF_TAGE = 180
VORLAUF_ABSTAND = 7
#Heizperiode zum Kernwinter: 1. Oktober bis 30. April
HEIZPERIODE_START = (10, 1)
HEIZPERIODE_ENDE = (4, 30)
#Ein Winter zählt als "vor der Begehung", wenn sie danach in diesem Abstand liegt
MAX_TAGE_BIS_BEGEHUNG = 400
STUFEN = ("hoch", "mittel", "niedrig")
#Baujahr vor der ersten Wärmeschutzverordnung (1977) gilt als alt
BAUJAHR_GRENZE = 1979
ZENSUS_ALT = ["Vor1919", "a1919bis1949", "a1950bis1959", "a1960bis1969",
              "a1970bis1979"]
ZENSUS_NEU = ["a1980bis1989", "a1990bis1999", "a2000bis2009",
              "a2010bis2015", "a2016undspaeter"]
GEBIET_ANTEIL = (1 / 3, 2 / 3)
ZENSUS_GLOB = "zensus/**/Zensus2022_Baujahr_JZ_100m-Gitter.csv"


def alarme_mit_schwelle(verlauf: pd.DataFrame, h: float,
                        k: float = tm.CUSUM_K,
                        deckel_faktor: float = DECKEL_FAKTOR) -> pd.DataFrame:
    """CUSUM-Alarme aus den gespeicherten z-Werten mit anderer Schwelle h.

    Der Deckel wächst mit h mit, sonst gäbe es ab h = 10 keinen Alarm mehr.
    """
    zeilen = []
    if len(verlauf) == 0:
        return pd.DataFrame(columns=tm.ALARM_SPALTEN)
    for (meter, kanal), g in verlauf.sort_values("datum").groupby(
            ["meter", "kanal"], sort=True):
        _, _, al = tm.cusum(g["z"].to_numpy(dtype=float), k=k, h=h,
                            deckel=deckel_faktor * h)
        datum = g["datum"].to_numpy()
        for i, richtung, start in al:
            zeilen.append({"meter": int(meter), "kanal": kanal,
                           "datum": pd.Timestamp(datum[i]),
                           "richtung": int(richtung),
                           "beginn": pd.Timestamp(datum[start])})
    return pd.DataFrame(zeilen, columns=tm.ALARM_SPALTEN)


def heiztage(verlauf: pd.DataFrame, kanal: str = "kwh_pro_m3") -> int:
    return int((verlauf["kanal"] == kanal).sum()) if len(verlauf) else 0


def schwellentest(verlauf: pd.DataFrame, faelle: pd.DataFrame,
                  termine: Mapping[int, Sequence],
                  schwellen: Sequence[float] = SCHWELLEN) -> pd.DataFrame:
    """Treffertest und Alarmlast je Schwelle h, eine Zeile je h und Prüfung."""
    beob = tm.beobachtete_tage(verlauf)
    n_tage = heiztage(verlauf)
    stuecke = []
    for h in schwellen:
        a = alarme_mit_schwelle(verlauf, h)
        b = tm.bilanz(tm.treffertest(faelle, a, beob, termine), ["pruefung"])
        b.insert(0, "h", float(h))
        b["alarme"] = len(a)
        b["stationen_mit_alarm"] = int(a["meter"].nunique())
        b["je_100_heiztage"] = 100 * len(a) / n_tage if n_tage else np.nan
        stuecke.append(b)
    return pd.concat(stuecke, ignore_index=True) if stuecke else pd.DataFrame()


def bewerte_richtung(alarme: pd.DataFrame) -> pd.DataFrame:
    """Spalte ``bewertung``: schlechter (weniger Abkühlung, mehr Wasser)
    oder besser."""
    a = alarme.copy()
    schluessel = list(zip(a["kanal"], a["richtung"].astype(int))) if len(a) else []
    a["bewertung"] = ["schlechter" if s in SCHLECHTER else "besser"
                      for s in schluessel]
    return a


def richtungstest(alarme: pd.DataFrame, faelle: pd.DataFrame,
                  verlauf: pd.DataFrame, termine: Mapping[int, Sequence],
                  vorlauf: int = VORLAUF_TAGE,
                  abstand: int = VORLAUF_ABSTAND) -> pd.DataFrame:
    """Treffertest getrennt nach Alarmrichtung und Fenster.

    "um die Begehung" ist das Fenster aus NB 21 (7 Tage vor bis 60 nach).
    "davor" reicht von ``vorlauf`` bis ``abstand`` Tage vor der Begehung
    und fragt, ob der CUSUM vorwarnt.
    """
    a = bewerte_richtung(alarme)
    beob = tm.beobachtete_tage(verlauf)
    pruef = {"beide Kanäle": list(tm.KANAELE)}
    fenster = {"um die Begehung": (tm.FENSTER_VOR, tm.FENSTER_NACH),
               "davor": (vorlauf, -abstand)}
    stuecke = []
    for richtung, teil in (("alle", a), ("schlechter", a[a["bewertung"] == "schlechter"]),
                           ("besser", a[a["bewertung"] == "besser"])):
        for name, (vor, nach) in fenster.items():
            t = tm.treffertest(faelle, teil, beob, termine, pruefungen=pruef,
                               fenster_vor=vor, fenster_nach=nach)
            if len(t) == 0:
                continue
            b = tm.bilanz(t, ["pruefung"]).drop(columns="pruefung")
            b.insert(0, "fenster", name)
            b.insert(0, "richtung", richtung)
            stuecke.append(b)
    return pd.concat(stuecke, ignore_index=True) if stuecke else pd.DataFrame()


def heizperiode(winter: str) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Heizperiode zu einem Kernwinter wie "23/24": 01.10.2023 bis 30.04.2024."""
    ende = nv.winter_ende_jahr(winter)
    return (pd.Timestamp(ende - 1, *HEIZPERIODE_START),
            pd.Timestamp(ende, *HEIZPERIODE_ENDE))


def stufe(auffaellig: bool, alarm_schlechter: bool) -> str:
    if auffaellig and alarm_schlechter:
        return "hoch"
    if auffaellig or alarm_schlechter:
        return "mittel"
    return "niedrig"


def prioritaet_je_winter(markiert: pd.DataFrame,
                         alarme: pd.DataFrame) -> pd.DataFrame:
    """Eine Zeile je Station und Kernwinter mit Netzwert.

    hoch: im Netz auffällig und mindestens ein Verschlechterungsalarm in der
    Heizperiode dieses Winters. mittel: eins von beiden. niedrig: keins.
    """
    spalten = ["meter", "winter", "auffaellig", "alarme_schlechter",
               "alarme_besser", "prioritaet"]
    if len(markiert) == 0:
        return pd.DataFrame(columns=spalten)
    m = markiert[markiert["score"].notna()]
    a = bewerte_richtung(alarme)
    a = a.assign(meter=a["meter"].astype(int),
                 datum=pd.to_datetime(a["datum"]))
    zeilen = []
    for r in m.itertuples(index=False):
        lo, hi = heizperiode(r.winter)
        eigen = a[(a["meter"] == int(r.meter)) & (a["datum"] >= lo)
                  & (a["datum"] <= hi)]
        n_s = int((eigen["bewertung"] == "schlechter").sum())
        auff = bool(r.auffaellig)
        zeilen.append({"meter": int(r.meter), "winter": r.winter,
                       "auffaellig": auff, "alarme_schlechter": n_s,
                       "alarme_besser": int(len(eigen) - n_s),
                       "prioritaet": stufe(auff, n_s > 0)})
    return pd.DataFrame(zeilen, columns=spalten)


def juengster_winter(tab: pd.DataFrame) -> pd.DataFrame:
    """Jüngster Kernwinter je Station, Index ist die Zählernummer."""
    if len(tab) == 0:
        return tab.set_index("meter") if "meter" in tab else tab
    t = tab.assign(_j=tab["winter"].map(nv.winter_ende_jahr))
    return (t.sort_values("_j").groupby("meter").tail(1)
            .drop(columns="_j").set_index("meter"))


#Reihenfolge zählt, das erste passende Muster gewinnt
FEHLERBILDER: List[Tuple[str, Callable[[set], bool], str]] = [
    ("ventil", lambda s: {"steigung", "spreizung_ref_k"} <= s,
     "Volumenstrom folgt der Leistung kaum, kleine Spreizung; konsistent "
     "mit offenem oder nicht regelndem Ventil"),
    ("durchfluss", lambda s: "spreizung_ref_k" in s
     and bool(s & {"rl_ueber_50_anteil", "flow_spez_lh_kw"}),
     "viel Wasser bei kleiner Spreizung oder hohem Rücklauf; konsistent mit "
     "zu hohem Durchfluss"),
    ("unruhig", lambda s: "residuum_sd" in s,
     "Kennlinie unruhig; konsistent mit taktender Regelung oder Messproblem"),
    ("regelung", lambda s: "steigung" in s,
     "Volumenstrom folgt der Leistung kaum; konsistent mit Regelungsproblem"),
    ("rücklauf", lambda s: "rl_ueber_50_anteil" in s,
     "oft Rücklauf über 50 °C"),
    ("durchfluss_je_kw", lambda s: "flow_spez_lh_kw" in s,
     "hoher Volumenstrom je kW Anschlusswert"),
]
FEHLERBILD_TEXT: Dict[str, str] = {code: text for code, _, text in FEHLERBILDER}


def fehlerbild(schlechte: Sequence[str]) -> str:
    """Code des ersten passenden Musters, "" ohne schlechte Kennzahl."""
    s = {str(k) for k in schlechte if k}
    for code, passt, _ in FEHLERBILDER:
        if passt(s):
            return code
    return ""


def fehlerbild_je_winter(markiert: pd.DataFrame,
                         kennzahlen: Sequence[str]) -> pd.DataFrame:
    """Fehlerbild je Station und Kernwinter aus den schlechten Kennzahlen."""
    spalten = ["meter", "winter", "auffaellig", "n_schlecht",
               "schlechte_kennzahlen", "fehlerbild"]
    if len(markiert) == 0:
        return pd.DataFrame(columns=spalten)
    m = markiert[markiert["score"].notna()]
    zeilen = []
    for _, r in m.iterrows():
        schlecht = [k for k in kennzahlen if bool(r.get(f"schlecht_{k}", False))]
        zeilen.append({"meter": int(r["meter"]), "winter": r["winter"],
                       "auffaellig": bool(r["auffaellig"]),
                       "n_schlecht": len(schlecht),
                       "schlechte_kennzahlen": ",".join(schlecht),
                       "fehlerbild": fehlerbild(schlecht)})
    return pd.DataFrame(zeilen, columns=spalten)


def befund_nach_winter(tab: pd.DataFrame, kodiert: pd.DataFrame,
                       kategorien: Mapping[str, Sequence[str]],
                       max_tage: int = MAX_TAGE_BIS_BEGEHUNG) -> pd.DataFrame:
    """Stationswinter, denen innerhalb von ``max_tage`` nach der Heizperiode
    eine Begehung mit Freitext folgt, mit deren Befund.

    ``kodiert`` ist `befundcodes.kodiere_begehungen`, ``kategorien`` bildet
    einen Befundnamen auf Spalten daraus ab (wahr, wenn eine davon wahr ist).
    Zählt nur die erste Begehung nach dem Winter, so liegt der Befund
    zeitlich nach der Messung.
    """
    k = kodiert.dropna(subset=["meter", "datum"]).copy()
    k["meter"] = k["meter"].astype(int)
    k["datum"] = pd.to_datetime(k["datum"]).dt.normalize()
    flags = {}
    for name, spalten in kategorien.items():
        da = [c for c in spalten if c in k.columns]
        flags[name] = (k[da].fillna(False).astype(bool).any(axis=1)
                       if da else pd.Series(False, index=k.index))
    k = k.assign(**flags)
    je = k.groupby(["meter", "datum"])[list(kategorien)].any().reset_index()
    zeilen = []
    for _, r in tab.iterrows():
        _, hi = heizperiode(r["winter"])
        g = je[(je["meter"] == int(r["meter"])) & (je["datum"] > hi)
               & (je["datum"] <= hi + pd.Timedelta(days=max_tage))]
        if g.empty:
            continue
        erste = g.sort_values("datum").iloc[0]
        zeilen.append({**r.to_dict(), "begehung": erste["datum"],
                       **{n: bool(erste[n]) for n in kategorien}})
    return pd.DataFrame(zeilen, columns=[*tab.columns, "begehung", *kategorien])


def vierfeld(merkmal: pd.Series, befund: pd.Series) -> dict:
    """Vierfeldertafel und einseitiger Fisher-Test (Merkmal -> mehr Befund)."""
    x = merkmal.astype(bool).to_numpy()
    y = befund.astype(bool).to_numpy()
    a, b = int((x & y).sum()), int((x & ~y).sum())
    c, d = int((~x & y).sum()), int((~x & ~y).sum())
    p = stats.fisher_exact([[a, b], [c, d]], alternative="greater").pvalue \
        if len(x) else np.nan
    return {"n": len(x), "merkmal_mit_befund": a, "merkmal_ohne_befund": b,
            "rest_mit_befund": c, "rest_ohne_befund": d,
            "quote_merkmal": a / (a + b) if a + b else np.nan,
            "quote_rest": c / (c + d) if c + d else np.nan,
            "p (einseitig)": float(p)}


def lade_zensus(pfad: Optional[Path] = None,
                rahmen: Optional[Tuple[float, float, float, float]] = None,
                root: Path = ROOT) -> pd.DataFrame:
    """Zensus-2022-Gitter "Gebäude nach Baujahr (Jahrzehnte)", 100 m.

    Liegt lokal unter data/raw/zensus (gitignored). ``rahmen`` ist
    (x_min, x_max, y_min, y_max) in EPSG:3035 und spart Speicher, die
    Datei hat 200 MB. "–" heißt kein Wert.
    """
    if pfad is None:
        treffer = sorted((Path(root) / "data" / "raw").glob(ZENSUS_GLOB))
        if not treffer:
            raise FileNotFoundError("Zensus-Baujahrgitter nicht gefunden")
        pfad = treffer[0]
    stuecke = []
    for teil in pd.read_csv(pfad, sep=";", dtype=str, chunksize=500_000,
                            usecols=lambda c: c != "GITTER_ID_100M"):
        x = pd.to_numeric(teil["x_mp_100m"], errors="coerce")
        y = pd.to_numeric(teil["y_mp_100m"], errors="coerce")
        if rahmen is not None:
            x0, x1, y0, y1 = rahmen
            teil = teil[x.between(x0, x1) & y.between(y0, y1)]
        stuecke.append(teil)
    z = pd.concat(stuecke, ignore_index=True)
    for spalte in z.columns:
        z[spalte] = pd.to_numeric(z[spalte].str.replace("–", "", regex=False),
                                  errors="coerce")
    return z


def gitterzelle(lat, lon) -> Tuple[np.ndarray, np.ndarray]:
    """Mittelpunkt der 100-m-Zelle in EPSG:3035 wie in der Zensusdatei."""
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 3035, always_xy=True)
    x, y = tr.transform(np.asarray(lon, dtype=float),
                        np.asarray(lat, dtype=float))
    x, y = np.asarray(x), np.asarray(y)
    return (np.floor(x / 100) * 100 + 50, np.floor(y / 100) * 100 + 50)


def gebiet(anteil_alt: float, grenzen: Tuple[float, float] = GEBIET_ANTEIL) -> str:
    if anteil_alt is None or not np.isfinite(anteil_alt):
        return "unbekannt"
    if anteil_alt >= grenzen[1]:
        return "überwiegend alt"
    if anteil_alt <= grenzen[0]:
        return "überwiegend neu"
    return "gemischt"


def zensus_gebiet(koordinaten: pd.DataFrame,
                  zensus: pd.DataFrame) -> pd.DataFrame:
    """Baujahrgebiet je Zähler aus der Zensuszelle seines Standorts.

    ``koordinaten`` braucht meter, lat, lon und ``genau`` (Hausnummer
    getroffen). Ohne Hausnummer liegt der Punkt irgendwo auf der Straße,
    das Gebiet ist dann nur ein Straßenmittel. Gitter-IDs und Koordinaten
    kommen nicht in die Ausgabe.
    """
    k = koordinaten.dropna(subset=["lat", "lon"]).copy()
    gx, gy = gitterzelle(k["lat"], k["lon"])
    k["x_mp_100m"], k["y_mp_100m"] = gx, gy
    alt = [c for c in ZENSUS_ALT if c in zensus.columns]
    neu = [c for c in ZENSUS_NEU if c in zensus.columns]
    z = zensus[["x_mp_100m", "y_mp_100m", "Insgesamt_Gebaeude", *alt, *neu]]
    k = k.merge(z, on=["x_mp_100m", "y_mp_100m"], how="left")
    n_alt = k[alt].sum(axis=1, min_count=1)
    n_neu = k[neu].sum(axis=1, min_count=1)
    bekannt = n_alt.fillna(0) + n_neu.fillna(0)
    k["anteil_alt"] = (n_alt.fillna(0) / bekannt).where(bekannt > 0)
    k["gebiet_baujahr"] = [gebiet(a) for a in k["anteil_alt"]]
    k["lage"] = np.where(k["genau"].astype(bool), "Hausnummer", "Straße")
    return k[["meter", "anteil_alt", "gebiet_baujahr", "lage"]].reset_index(drop=True)


def koordinaten(root: Path = ROOT) -> pd.DataFrame:
    """Geokodierte Standorte aus data/processed/hast_geocoded.csv."""
    g = pd.read_csv(Path(root) / "data" / "processed" / "hast_geocoded.csv")
    note = g.get("note", pd.Series("", index=g.index)).fillna("")
    return pd.DataFrame({
        "meter": pd.to_numeric(g["Zählernummer"], errors="coerce"),
        "lat": g["lat"], "lon": g["lon"],
        "genau": note.str.startswith("exact_house_number")}
    ).dropna(subset=["meter"]).astype({"meter": int})


def baujahr_kontext(labels: pd.DataFrame,
                    gebiet_tab: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Baujahr aus dem Begehungsfreitext, daneben das Zensusgebiet.

    ``labels`` ist `befundcodes.labels_je_zaehler`. ``baujahr_alt`` nimmt
    das Freitextbaujahr, wenn es eins gibt, sonst das Zensusgebiet
    (überwiegend alt/neu); gemischt und unbekannt bleiben leer.
    """
    b = pd.DataFrame({"meter": labels["meter"].astype(int),
                      "baujahr_begehung": pd.to_numeric(labels.get("baujahr"),
                                                        errors="coerce")})
    if gebiet_tab is not None and len(gebiet_tab):
        b = b.merge(gebiet_tab[["meter", "gebiet_baujahr", "lage"]],
                    on="meter", how="outer")
    else:
        b["gebiet_baujahr"], b["lage"] = "unbekannt", ""
    b["gebiet_baujahr"] = b["gebiet_baujahr"].fillna("unbekannt")
    alt = pd.Series(np.nan, index=b.index, dtype=object)
    alt[b["gebiet_baujahr"] == "überwiegend alt"] = True
    alt[b["gebiet_baujahr"] == "überwiegend neu"] = False
    quelle = pd.Series("", index=b.index)
    quelle[alt.notna()] = "Zensus"
    hat = b["baujahr_begehung"].notna()
    alt[hat] = b.loc[hat, "baujahr_begehung"] < BAUJAHR_GRENZE
    quelle[hat] = "Begehung"
    b["baujahr_alt"], b["baujahr_quelle"] = alt, quelle
    return b.drop_duplicates("meter").reset_index(drop=True)


def lade_baujahr(labels: pd.DataFrame, root: Path = ROOT) -> pd.DataFrame:
    """Baujahrkontext mit Zensus, ohne Zensusdatei nur aus dem Freitext."""
    try:
        k = koordinaten(root)
        gx, gy = gitterzelle(k["lat"], k["lon"])
        rahmen = (gx.min() - 200, gx.max() + 200, gy.min() - 200, gy.max() + 200)
        geb = zensus_gebiet(k, lade_zensus(rahmen=rahmen, root=root))
    except (FileNotFoundError, KeyError):
        geb = None
    return baujahr_kontext(labels, geb)


def main() -> None:
    import pickle
    pfad = ROOT / "outputs" / "cache" / "stationsblatt_erg.pkl"
    with open(pfad, "rb") as f:
        erg = pickle.load(f)
    from . import befundcodes as bc
    r = erg["tagesmonitor"]
    faelle = tm.faelle(bc.kodiere_begehungen())
    print(schwellentest(r["verlauf"], faelle, erg["termine"]).round(3)
          .to_string(index=False))
    print(richtungstest(r["alarme"], faelle, r["verlauf"], erg["termine"])
          .round(3).to_string(index=False))


if __name__ == "__main__":
    main()
