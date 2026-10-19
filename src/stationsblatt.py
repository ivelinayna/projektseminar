"""Stationsblatt: Monitorbild je Station mit dem Netz als Maßstab.

Der Monitor aus NB 14 vergleicht eine Station nur mit ihrer eigenen
Vergangenheit. Das Stationsblatt stellt ihre Kennlinie im gleitenden
Fenster vor das Band aller Stationen am selben Tag und vergleicht die
Kennlinie Kernwinter gegen Kernwinter. Gerechnet wird kaum etwas Neues,
das Modul setzt `netzvergleich`, `kennlinien_monitor` und
`stationsbilder` zusammen. Alarme kommen nur aus dem Tagesmonitor
(`tagesmonitor`), vom Monitor aus NB 14 bleiben nur die Fensterkurven.
Ausgabe je Zähler ein PNG und eine Zeile der Statustabelle, ohne Adressen.

    python -m src.stationsblatt
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import alarmbewertung as ab
from . import befundcodes as bc
from . import kennlinien_monitor as km
from . import load_begehungen as lb
from . import load_data as ld
from . import netzvergleich as nv
from . import stationsbilder as sb
from . import tagesmonitor as tm
from . import ternaer as tn

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "stationsblatt"

BAND_QUANTILE = (0.1, 0.5, 0.9)
#Spalten der Fenstertabelle im Zeitverlauf, Vorzeichen wie in netzvergleich
KANAELE: Dict[str, int] = {"steigung": nv.KENNZAHLEN["steigung"],
                           "dt_median_k": nv.KENNZAHLEN["spreizung_ref_k"]}


def _endliche(fenster: Optional[pd.DataFrame], spalte: str) -> pd.DataFrame:
    """Zeilen mit endlichem Wert in ``spalte``, Zählernummer als int."""
    if fenster is None or len(fenster) == 0 or spalte not in fenster.columns:
        return pd.DataFrame({"meter": pd.Series(dtype="int64"),
                             "datum": pd.Series(dtype="datetime64[ns]"),
                             spalte: pd.Series(dtype=float)})
    teil = pd.DataFrame({
        "meter": fenster["meter"].astype(int).to_numpy(),
        "datum": pd.to_datetime(fenster["datum"]).to_numpy(),
        spalte: pd.to_numeric(fenster[spalte], errors="coerce")
        .to_numpy(dtype=float)})
    return teil[np.isfinite(teil[spalte].to_numpy())].reset_index(drop=True)


def netzband(fenster: Optional[pd.DataFrame], spalte: str,
             ausschluss: Sequence[int] = (),
             min_stationen: int = nv.MIN_STATIONEN_WINTER,
             quantile: Sequence[float] = BAND_QUANTILE,
             best_vorzeichen: Optional[int] = None) -> pd.DataFrame:
    """Quantile einer Fensterspalte über alle Stationen je Kalendertag.

    Stationen aus ``ausschluss`` (BHKW) zählen nicht mit. Tage mit weniger
    als ``min_stationen`` Werten behalten ihre Zeile mit ``n``, die
    Quantile bleiben dort leer und das Band hat eine Lücke. Mit
    ``best_vorzeichen`` kommt die Spalte ``best`` dazu, der Median des
    besten Viertels am Tag (Vorzeichen wie in `netzvergleich.KENNZAHLEN`).
    """
    namen = [f"q{int(round(q * 100))}" for q in quantile]
    if best_vorzeichen is not None:
        namen.append("best")
        halb = nv.BESTWERT_ANTEIL / 2
        quantile = [*quantile, halb if best_vorzeichen > 0 else 1.0 - halb]
    teil = _endliche(fenster, spalte)
    teil = teil[~teil["meter"].isin({int(m) for m in ausschluss})]
    if len(teil) == 0:
        return pd.DataFrame(columns=["datum", "n", *namen])
    g = teil.groupby("datum")[spalte]
    out = pd.DataFrame({"n": g.size()})
    for q, name in zip(quantile, namen):
        out[name] = g.quantile(q)
    out.loc[out["n"] < int(min_stationen), namen] = np.nan
    return out.reset_index()[["datum", "n", *namen]]


def netz_z_tag(fenster: Optional[pd.DataFrame], spalte: str,
               ausschluss: Sequence[int] = (),
               min_stationen: int = nv.MIN_STATIONEN_WINTER,
               vorzeichen: Optional[int] = None) -> pd.DataFrame:
    """Robuster z-Wert jeder Station gegen das Netz desselben Tages.

    Positiv heißt schlechter, das Vorzeichen kommt aus ``KANAELE``.
    Stationen aus ``ausschluss`` bekommen einen Wert, bestimmen Median und
    Streuung aber nicht mit. Tage mit weniger als ``min_stationen``
    Referenzwerten fehlen.
    """
    vz = KANAELE[spalte] if vorzeichen is None else int(vorzeichen)
    teil = _endliche(fenster, spalte)
    aus = {int(m) for m in ausschluss}
    stuecke = []
    for datum, g in teil.groupby("datum"):
        ref = g.loc[~g["meter"].isin(aus), spalte]
        if len(ref) < int(min_stationen):
            continue
        stuecke.append(pd.DataFrame({
            "meter": g["meter"].to_numpy(), "datum": datum,
            "z": nv.robust_z(g[spalte], ref, vz)}))
    if not stuecke:
        return pd.DataFrame(columns=["meter", "datum", "z"])
    return pd.concat(stuecke, ignore_index=True)


HINWEISTEXT: Dict[str, str] = {
    "steigung": "Steigung niedrig",
    "spreizung_ref_k": "Referenzspreizung klein",
    "residuum_sd": "Kennlinie unruhig",
    "rl_ueber_50_anteil": "oft Rücklauf über 50 °C",
    "flow_spez_lh_kw": "hoher Volumenstrom je kW",
}
GRUNDTEXT: Dict[str, str] = {
    "keine_hast": ("nur Temperaturen, nie Durchfluss oder Leistung "
                   "(Messstelle, keine Übergabestation)"),
    "keine_daten": "keine Betriebsstunden im Kernwinter",
    "zu_wenig_stunden": (f"weniger als {nv.MIN_STUNDEN_WINTER} "
                         "Betriebsstunden im Kernwinter"),
    "kein_fit": "Kennlinie nicht schätzbar",
    "kein_netzwinter": "zu wenige Vergleichsstationen im selben Winter",
}
STATUS_SPALTEN = [
    "meter", "bhkw", "anschlusswert_kw", "winter", "rang", "n_stationen",
    "score", "auffaellig", "schlechte_kennzahlen", "n_winter_score",
    "n_winter_auffaellig", "chronisch", "fehlerbild", "prioritaet",
    "alarme_schlechter_winter", "letzte_begehung",
    "begangen_ohne_datum", "baujahr", "baujahr_quelle", "gebiet_baujahr",
    "wv_status", "wv_datum", "wv_winter_vor",
    "wv_winter_nach", "wv_flow_vor_lh", "wv_flow_nach_lh",
    "wv_flow_verhaeltnis", "wv_steigung_vor", "wv_steigung_nach",
    "wv_d_steigung", "wv_rang_vor", "wv_rang_nach", "wv_residuum_kreuz",
    "tm_status", "tm_alarme", "tm_alarme_schlechter", "tm_letzter_alarm",
    "tm_letzter_kanal", "tm_letzte_richtung", "norm5_winter",
    "norm5_kwh_m3", "norm5_abstand_k", "norm5_rang",
    "netz_z_steigung_aktuell", "netz_z_spreizung_aktuell",
    "datum_z_steigung", "datum_z_spreizung", "grund", "hinweis",
    "potenzial", "potenzial_score", "groesste_luecke",
    *[f"bw_abstand_{k}" for k in nv.KENNZAHLEN],
]
#Spalte im Wintervergleich -> Spalte in der Statustabelle
WV_SPALTEN: Dict[str, str] = {
    "flow_median_lh_vor": "wv_flow_vor_lh",
    "flow_median_lh_nach": "wv_flow_nach_lh",
    "flow_verhaeltnis": "wv_flow_verhaeltnis",
    "steigung_vor": "wv_steigung_vor", "steigung_nach": "wv_steigung_nach",
    "d_steigung": "wv_d_steigung", "rang_vor": "wv_rang_vor",
    "rang_nach": "wv_rang_nach", "residuum_kreuz": "wv_residuum_kreuz",
}


def eingaben(root: Path = ROOT) -> dict:
    """Serien und Kontext so laden wie NB 20, Zelle 1.

    Stundenreihen kommen nur aus NB 00 (`data/processed/real_meters`).
    Anschlusswert aus Nodes_Edges, BHKW aus der Zuordnungsexcel.
    """
    root = Path(root)
    serien = tn.lade_serien(root / "data" / "processed" / "real_meters")
    termine = {int(k): list(v)
               for k, v in lb.begehung_dates_by_meter().items()}
    datiert = {m for m, d in termine.items() if d}
    beg_alle = lb.begehungen_mit_zaehler()
    ohne_datum = set(beg_alle["meter"].dropna().astype(int)) - datiert

    nodes = ld.load_logical_nodes()
    aw_tab = pd.DataFrame({
        "meter": pd.to_numeric(nodes["Zählernummer"], errors="coerce"),
        "kw": pd.to_numeric(nodes["Anschlusswert"], errors="coerce"),
    }).dropna()
    anschlusswerte = (aw_tab.groupby(aw_tab["meter"].astype(int))["kw"]
                      .max().to_dict())

    pfad = root / "data" / "raw" / "Zuordnung.xlsx"
    #jedes Jahresblatt mit V-PIN zählt, damit neue Jahre ohne Codeänderung dazukommen
    blaetter = pd.read_excel(pfad, sheet_name=None, dtype={"V-PIN": str})
    vpin = pd.concat([b[["Zählernummer", "V-PIN"]] for b in blaetter.values()
                      if {"Zählernummer", "V-PIN"} <= set(b.columns)])
    vpin["Zählernummer"] = pd.to_numeric(vpin["Zählernummer"],
                                         errors="coerce")
    bhkw = set(vpin.loc[vpin["V-PIN"] == "BHKW", "Zählernummer"]
               .dropna().astype(int))
    #Baujahr nur als Kontext, ohne Zensusdatei bleibt der Freitext
    labels = bc.labels_je_zaehler(bc.kodiere_begehungen())
    baujahr = ab.lade_baujahr(labels, root)
    return {"serien": serien, "termine": termine,
            "anschlusswerte": anschlusswerte, "bhkw": bhkw,
            "ohne_datum": ohne_datum, "baujahr": baujahr}


def rechne(serien: Mapping[int, pd.DataFrame],
           termine: Optional[Mapping] = None,
           anschlusswerte: Optional[Mapping] = None,
           bhkw: Sequence[int] = (),
           ohne_datum: Sequence[int] = (),
           heizgradstunden: Optional[pd.DataFrame] = None,
           min_stunden: int = nv.MIN_STUNDEN_WINTER,
           min_stationen: int = nv.MIN_STATIONEN_WINTER,
           tagestemperatur: Optional[pd.Series] = None,
           tagesmonitor: bool = True,
           baujahr: Optional[pd.DataFrame] = None,
           fortschritt: bool = False) -> dict:
    """Alles, was Blatt und Statustabelle brauchen, in einem Durchlauf.

    Dieselbe Kette wie NB 20: Punkttabellen, Winterkennzahlen, Netzbezug
    ohne BHKW, Score, Markierung, Übersicht, Wintervergleich. Dazu der
    Monitor aus NB 14 mit Netzband und Tages-z-Wert je Kanal und der
    Tagesmonitor aus NB 21 (CUSUM, Abkühlung bei 5 °C). Ohne
    ``tagestemperatur`` holt der Tagesmonitor das Tagesmittel aus dem
    DWD-Cache. Priorität je Station und Winter kommt aus `alarmbewertung`,
    ``baujahr`` (`alarmbewertung.baujahr_kontext`) wird nur durchgereicht.
    """
    serien = nv.int_schluessel(serien)
    termine = {int(m): list(d)
               for m, d in nv.int_schluessel(termine or {}).items()}
    aw = nv.int_schluessel(anschlusswerte or {})
    bhkw = {int(m) for m in bhkw}
    ref_aus = tuple(sorted(bhkw)) or nv.REFERENZ_AUSSCHLUSS

    punkte = {m: sb.punkttabelle(df, m, "stunde") for m, df in serien.items()}
    tabelle, ausschluss = nv.winterkennzahlen(punkte, aw, termine,
                                              min_stunden=min_stunden)
    bezogen = nv.netzbezug(tabelle, referenz_ausschluss=ref_aus,
                           min_stationen=min_stationen)
    kz, _ = nv.score_kennzahlen(bezogen)
    markiert = nv.markiere(bezogen, kz)
    potenzial = nv.potenzial_je_winter(tabelle, kz, ref_aus, min_stationen)
    uebersicht = nv.stationsuebersicht(markiert)
    vergleich = km.wintervergleich(punkte, termine, aw, markiert,
                                   heizgradstunden, min_stunden=min_stunden)
    monitor = km.monitor_alle(serien, fortschritt=fortschritt)
    fenster = monitor.get("fenster")
    baender = {k: netzband(fenster, k, ref_aus, min_stationen,
                           best_vorzeichen=vz)
               for k, vz in KANAELE.items()}
    z_tag = {k: netz_z_tag(fenster, k, ref_aus, min_stationen)
             for k in KANAELE}
    tagesmon = (tm.rechne(serien, termine, tagestemperatur,
                          min_stationen=min_stationen)
                if tagesmonitor else None)
    alarme = (tagesmon["alarme"] if tagesmon is not None
              else pd.DataFrame(columns=tm.ALARM_SPALTEN))
    prio = ab.prioritaet_je_winter(markiert, alarme)
    return {"meters": sorted(serien), "punkte": punkte, "tabelle": tabelle,
            "ausschluss": ausschluss, "markiert": markiert,
            "kennzahlen": kz, "uebersicht": uebersicht,
            "vergleich": vergleich, "monitor": monitor, "baender": baender,
            "z_tag": z_tag, "termine": termine, "anschlusswerte": aw,
            "bhkw": bhkw, "ohne_datum": {int(m) for m in ohne_datum},
            "tagesmonitor": tagesmon, "prioritaet": prio,
            "baujahr": baujahr, "potenzial": potenzial,
            "messstellen": messstellen(serien)}


def messstellen(serien: Mapping[int, pd.DataFrame]) -> set:
    """Zähler mit Messwerten, aber nie Durchfluss und nie Leistung.

    Das sind Temperaturfühler ohne Übergabestation, etwa im Heizhaus.
    Erkannt wird das an den Daten, damit kein Netz eigene Zählernummern
    pflegen muss.
    """
    out = set()
    for m, df in serien.items():
        if len(df) == 0 or not {"flow", "power"} <= set(df.columns):
            continue
        werte = df[["flow", "power"]].apply(pd.to_numeric, errors="coerce")
        if werte.notna().any().any() and not (werte.abs() > 0).any().any():
            out.add(int(m))
    return out


def hinweis(schlechte: Sequence[str], hat_score: bool = True) -> str:
    """Beschreibender Kurztext zu den schlechten Kennzahlen.

    Nennt nur, was gemessen auffällt, keine Ursache und keine Maßnahme.
    """
    if not hat_score:
        return ""
    teile = [HINWEISTEXT[k] for k in schlechte if k in HINWEISTEXT]
    if not teile:
        return "Im Netzvergleich unauffällig"
    text = ", ".join(teile)
    return text[0].upper() + text[1:]


def _datumstext(wert) -> str:
    return "" if wert is None or pd.isna(wert) else \
        pd.Timestamp(wert).date().isoformat()


def _wintertext(wert) -> str:
    return "" if wert is None or (isinstance(wert, float) and np.isnan(wert)) \
        else str(wert)


def _grund(meter: int, ergebnis: Mapping) -> str:
    """Warum eine Station keinen Netzwert hat."""
    t = ergebnis["tabelle"]
    if len(t) and (t["meter"].astype(int) == meter).any():
        return "kein_netzwinter"
    aus = ergebnis["ausschluss"]
    eigen = aus[aus["meter"].astype(int) == meter] if len(aus) else aus
    if len(eigen) == 0:
        return "keine_daten"
    jahr = eigen["winter"].map(lambda w: nv.winter_ende_jahr(w) if w else 0)
    return str(eigen.assign(_j=jahr).sort_values("_j")["grund"].iloc[-1])


def _wv_werte(vergleich: Optional[pd.DataFrame], meter: int) -> dict:
    """Jüngste Begehung mit gültigem Winterpaar, sonst die jüngste überhaupt."""
    out = {ziel: np.nan for ziel in WV_SPALTEN.values()}
    out.update(wv_status="", wv_datum="", wv_winter_vor="", wv_winter_nach="")
    if vergleich is None or len(vergleich) == 0:
        return out
    eigen = vergleich[vergleich["meter"].astype(int) == meter]
    if len(eigen) == 0:
        return out
    ok = eigen[eigen["status"] == "ok"]
    zeile = (ok if len(ok) else eigen).sort_values("datum").iloc[-1]
    out.update(wv_status=str(zeile["status"]),
               wv_datum=_datumstext(zeile["datum"]),
               wv_winter_vor=_wintertext(zeile["winter_vor"]),
               wv_winter_nach=_wintertext(zeile["winter_nach"]))
    if len(ok):
        for quelle, ziel in WV_SPALTEN.items():
            if quelle in zeile.index:
                out[ziel] = zeile[quelle]
    return out


def _letzter_z(z_tag: Optional[pd.DataFrame], meter: int):
    """Letzter endlicher Tages-z-Wert einer Station und sein Datum."""
    if z_tag is None or len(z_tag) == 0:
        return np.nan, ""
    z = pd.to_numeric(z_tag["z"], errors="coerce").to_numpy(dtype=float)
    eigen = z_tag[(z_tag["meter"].astype(int) == meter) & np.isfinite(z)]
    if len(eigen) == 0:
        return np.nan, ""
    letzte = eigen.sort_values("datum").iloc[-1]
    return float(letzte["z"]), _datumstext(letzte["datum"])


def _tm_werte(tagesmon: Optional[Mapping], norm_akt: pd.DataFrame,
              meter: int) -> dict:
    """Stand des Tagesmonitors und Abkühlung bei 5 °C im jüngsten Winter."""
    out = {"tm_status": "", "tm_alarme": 0, "tm_letzter_alarm": "",
           "tm_letzter_kanal": "", "tm_letzte_richtung": np.nan,
           "norm5_winter": "", "norm5_kwh_m3": np.nan,
           "norm5_abstand_k": np.nan, "norm5_rang": np.nan}
    if tagesmon is None:
        return out
    stand = tm.stationsstand(meter, tagesmon["referenz"], tagesmon["alarme"])
    stand["tm_letzter_alarm"] = _datumstext(stand["tm_letzter_alarm"])
    out.update(stand)
    if len(norm_akt) and meter in norm_akt.index:
        n = norm_akt.loc[meter]
        out.update(norm5_winter=str(n["winter"]),
                   norm5_kwh_m3=float(n["norm_kwh_m3"]),
                   norm5_abstand_k=float(n["abstand_k"]),
                   norm5_rang=float(n["rang"]))
    return out


def statustabelle(ergebnis: Mapping) -> pd.DataFrame:
    """Eine Zeile je Zähler: Netzstand, Wintervergleich, Monitor.

    Stationen ohne Netzwert bleiben drin und tragen in ``grund``, warum.
    Keine Adressen, das Dashboard verknüpft über die Zählernummer.
    """
    m = ergebnis["markiert"]
    if len(m):
        m = m[m["score"].notna()].assign(meter=lambda d: d["meter"].astype(int))
    ue = ergebnis["uebersicht"]
    if len(ue):
        ue = ue.assign(meter=ue["meter"].astype(int)).set_index("meter")
    kz = list(ergebnis["kennzahlen"])
    tagesmon = ergebnis.get("tagesmonitor")
    norm_akt = (tm.norm_aktuell(tagesmon["norm"]) if tagesmon is not None
                else pd.DataFrame())
    alarme = (ab.bewerte_richtung(tagesmon["alarme"]) if tagesmon is not None
              else pd.DataFrame(columns=[*tm.ALARM_SPALTEN, "bewertung"]))
    prio = ergebnis.get("prioritaet")
    if prio is None:
        prio = ab.prioritaet_je_winter(ergebnis["markiert"], alarme)
    prio = prio.set_index(["meter", "winter"]) if len(prio) else prio
    bj = ergebnis.get("baujahr")
    bj = (bj.assign(meter=bj["meter"].astype(int)).set_index("meter")
          if bj is not None and len(bj) else None)
    pot = ergebnis.get("potenzial")
    pot = (pot.assign(meter=pot["meter"].astype(int))
           .set_index(["meter", "winter"])
           if pot is not None and len(pot) else None)

    zeilen = []
    for meter in ergebnis["meters"]:
        meter = int(meter)
        z = dict.fromkeys(STATUS_SPALTEN, np.nan)
        z.update(meter=meter, bhkw=meter in ergebnis["bhkw"],
                 anschlusswert_kw=ergebnis["anschlusswerte"].get(meter, np.nan),
                 winter="", auffaellig=False, schlechte_kennzahlen="",
                 n_winter_score=0, n_winter_auffaellig=0, chronisch=False,
                 fehlerbild="", prioritaet="", alarme_schlechter_winter=0,
                 letzte_begehung="", baujahr=np.nan, baujahr_quelle="",
                 gebiet_baujahr="unbekannt", grund="", potenzial="",
                 groesste_luecke="")
        eigen = m[m["meter"] == meter] if len(m) else m
        schlecht: list = []
        if len(eigen):
            eigen = (eigen.assign(_j=eigen["winter"].map(nv.winter_ende_jahr))
                     .sort_values("_j"))
            letzte = eigen.iloc[-1]
            w = letzte["winter"]
            schlecht = [k for k in kz if bool(letzte.get(f"schlecht_{k}", False))]
            z.update(winter=w, rang=float(letzte["rang"]),
                     n_stationen=int((m["winter"] == w).sum()),
                     score=float(letzte["score"]),
                     auffaellig=bool(letzte["auffaellig"]),
                     schlechte_kennzahlen=",".join(schlecht),
                     fehlerbild=ab.fehlerbild(schlecht))
            if len(prio) and (meter, w) in prio.index:
                p = prio.loc[(meter, w)]
                z.update(prioritaet=str(p["prioritaet"]),
                         alarme_schlechter_winter=int(p["alarme_schlechter"]))
            if pot is not None and (meter, w) in pot.index:
                b = pot.loc[(meter, w)]
                z.update(potenzial=str(b["potenzial"]),
                         potenzial_score=float(b["potenzial_score"]),
                         groesste_luecke=str(b["groesste_luecke"]))
                for k in kz:
                    z[f"bw_abstand_{k}"] = float(b[f"abstand_{k}"])
        else:
            z["grund"] = ("keine_hast"
                          if meter in ergebnis.get("messstellen", ())
                          else _grund(meter, ergebnis))
        if len(ue) and meter in ue.index:
            u = ue.loc[meter]
            z.update(n_winter_score=int(u["n_winter"]),
                     n_winter_auffaellig=int(u["n_auffaellig"]),
                     chronisch=bool(u["chronisch"]))
        termine = sorted(pd.Timestamp(d)
                         for d in ergebnis["termine"].get(meter, []))
        if termine:
            z["letzte_begehung"] = termine[-1].date().isoformat()
        z["begangen_ohne_datum"] = meter in ergebnis["ohne_datum"]
        if bj is not None and meter in bj.index:
            b = bj.loc[meter]
            z.update(baujahr=b["baujahr_begehung"],
                     baujahr_quelle=str(b["baujahr_quelle"] or ""),
                     gebiet_baujahr=str(b["gebiet_baujahr"]))
        z.update(_wv_werte(ergebnis["vergleich"], meter))
        z.update(_tm_werte(ergebnis.get("tagesmonitor"), norm_akt, meter))
        z["tm_alarme_schlechter"] = int(
            ((alarme["meter"].astype(int) == meter)
             & (alarme["bewertung"] == "schlechter")).sum()) if len(alarme) else 0
        #Beide Kanäle enden nicht am selben Tag, deshalb je ein Datum
        z["netz_z_steigung_aktuell"], z["datum_z_steigung"] = _letzter_z(
            ergebnis["z_tag"].get("steigung"), meter)
        z["netz_z_spreizung_aktuell"], z["datum_z_spreizung"] = _letzter_z(
            ergebnis["z_tag"].get("dt_median_k"), meter)
        z["hinweis"] = hinweis(schlecht, hat_score=bool(len(eigen)))
        zeilen.append(z)
    return pd.DataFrame(zeilen, columns=STATUS_SPALTEN)


WV_TEXT: Dict[str, str] = {
    "keine_daten": "keine Betriebsstunden im Kernwinter",
    "kein_vorwinter": "kein Kernwinter vor der Begehung",
    "kein_nachwinter": "noch kein Kernwinter nach der Begehung",
    "zu_wenig_punkte": "zu wenige Stunden in einem der Winter",
    "zu_wenig_stunden": "zu wenige Stunden in einem der Winter",
    "kein_fit": "Kennlinie in einem der Winter nicht schätzbar",
}
KANALTITEL = {"steigung": "Steigung der Kennlinie (gleitendes Fenster)",
              "dt_median_k": "Spreizung im Fenster, Median [K]"}
KENNZAHLKURZ = {"spreizung_ref_k": "Spreizung", "steigung": "Steigung",
                "residuum_sd": "Streuung", "rl_ueber_50_anteil": "RL > 50 °C",
                "flow_spez_lh_kw": "l/h je kW"}
#Richtung eines CUSUM-Alarms, beschreibend
RICHTUNGSTEXT = {("kwh_pro_m3", 1): "mehr Abkühlung",
                 ("kwh_pro_m3", -1): "weniger Abkühlung",
                 ("log_volumen", 1): "mehr Wasser",
                 ("log_volumen", -1): "weniger Wasser"}
CUSUM_FARBEN = {"kwh_pro_m3": "C3", "log_volumen": "C0"}
#Abstand zum besten Viertel in Worten: Name, Einheit, Faktor
LUECKE_EINHEIT = {"spreizung_ref_k": ("Spreizung", "K", 1.0, 1),
                  "steigung": ("Steigung", "", 1.0, 2),
                  "residuum_sd": ("Streuung", "", 1.0, 2),
                  "rl_ueber_50_anteil": ("RL > 50 °C", "Prozentpunkte", 100.0, 0),
                  "flow_spez_lh_kw": ("Volumenstrom", "l/h je kW", 1.0, 1)}


def luecke_text(kennzahl: str, abstand) -> str:
    """Zum Beispiel "Spreizung 12,3 K unter dem besten Viertel"."""
    name, einheit, faktor, stellen = LUECKE_EINHEIT.get(
        kennzahl, (kennzahl, "", 1.0, 2))
    wort = "unter" if nv.KENNZAHLEN.get(kennzahl, 1) < 0 else "über"
    try:
        wert = _de(float(abstand) * faktor, stellen)
    except (TypeError, ValueError):
        wert = "–"
    return f"{name} {wert} {einheit} {wort} dem besten Viertel".replace("  ", " ")


def _de(wert, stellen: int = 2, vorzeichen: bool = False) -> str:
    """Zahl mit Dezimalkomma, "–" für fehlende Werte."""
    try:
        x = float(wert)
    except (TypeError, ValueError):
        return "–"
    if not np.isfinite(x):
        return "–"
    text = f"{x:+.{stellen}f}" if vorzeichen else f"{x:.{stellen}f}"
    return text.replace(".", ",")


def _leer(wert) -> bool:
    return wert is None or (isinstance(wert, float) and np.isnan(wert)) \
        or str(wert) in ("", "nan")


def statustext(zeile: Mapping) -> str:
    """Mehrzeiliger Kurztext zur Statuszeile, beschreibend."""
    z = dict(zeile)
    zeilen = []
    if not _leer(z.get("winter")):
        zeilen.append(f"Kernwinter {z['winter']}: Rang {int(z['rang'])} "
                      f"von {int(z['n_stationen'])}, Score {_de(z['score'])}")
        n_w = int(z.get("n_winter_score") or 0)
        n_a = int(z.get("n_winter_auffaellig") or 0)
        teil = f"Auffällig in {n_a} von {n_w} Wintern"
        if bool(z.get("chronisch")):
            teil += ", chronisch"
        zeilen.append(teil)
        zeilen.append(f"Muster: {z.get('hinweis') or '–'}")
        code = "" if _leer(z.get("fehlerbild")) else str(z["fehlerbild"])
        if code:
            zeilen.extend(textwrap.wrap(
                f"Fehlerbild: {ab.FEHLERBILD_TEXT.get(code, code)}", 66,
                subsequent_indent="  "))
        stufe = "" if _leer(z.get("prioritaet")) else str(z["prioritaet"])
        if stufe:
            n_s = int(z.get("alarme_schlechter_winter") or 0)
            grund = []
            if bool(z.get("auffaellig")):
                grund.append("Netz auffällig")
            if n_s:
                grund.append(f"{n_s} Alarm{'e' if n_s > 1 else ''} verschlechtert")
            zeilen.append(f"Priorität {z['winter']}: {stufe}"
                          + (f" ({', '.join(grund)})" if grund else ""))
        if not _leer(z.get("potenzial")):
            teil = (f"Gegen bestes Viertel: Potenzial {z['potenzial']} "
                    f"({_de(z.get('potenzial_score'), 1)})")
            k = "" if _leer(z.get("groesste_luecke")) else str(z["groesste_luecke"])
            if k:
                teil += f", größte Lücke {luecke_text(k, z.get(f'bw_abstand_{k}'))}"
            zeilen.extend(textwrap.wrap(teil, 66, subsequent_indent="  "))
    else:
        grund = GRUNDTEXT.get(str(z.get("grund")), str(z.get("grund") or ""))
        zeilen.append(f"Kein Netzvergleich: {grund}")
    if bool(z.get("bhkw")):
        zeilen.append("BHKW, nicht Teil der Netzreferenz")

    if not _leer(z.get("letzte_begehung")):
        zeilen.append(f"Letzte Begehung: {z['letzte_begehung']}")
    elif bool(z.get("begangen_ohne_datum")):
        zeilen.append("Begangen, Datum unbekannt")
    else:
        zeilen.append("Keine Begehung bekannt")
    quelle = "" if _leer(z.get("baujahr_quelle")) else str(z["baujahr_quelle"])
    gebiet = "" if _leer(z.get("gebiet_baujahr")) else str(z["gebiet_baujahr"])
    if quelle == "Begehung" and not _leer(z.get("baujahr")):
        zeilen.append(f"Baujahr {int(float(z['baujahr']))} (Begehung)")
    elif gebiet and gebiet != "unbekannt":
        zeilen.append(f"Baujahrgebiet {gebiet} (Zensus-Gitter, grob)")

    status = "" if _leer(z.get("wv_status")) else str(z["wv_status"])
    if status == "ok":
        zeilen.append(f"Winter {z['wv_winter_vor']} → {z['wv_winter_nach']} "
                      f"(Begehung {z['wv_datum']})")
        zeilen.append(f"  Volumenstrom {_de(z['wv_flow_vor_lh'], 0)} → "
                      f"{_de(z['wv_flow_nach_lh'], 0)} l/h, Steigung "
                      f"{_de(z['wv_steigung_vor'])} → "
                      f"{_de(z['wv_steigung_nach'])}")
        if not _leer(z.get("wv_rang_vor")) or not _leer(z.get("wv_rang_nach")):
            zeilen.append(f"  Rang {_de(z.get('wv_rang_vor'), 0)} → "
                          f"{_de(z.get('wv_rang_nach'), 0)}")
    elif status:
        zeilen.append(f"Wintervergleich: {WV_TEXT.get(status, status)}")

    tm_status = "" if _leer(z.get("tm_status")) else str(z["tm_status"])
    if tm_status == "ok":
        n = int(z.get("tm_alarme") or 0)
        teil = f"Tagesmonitor (CUSUM): {n} Alarme"
        if n:
            teil += f", davon {int(z.get('tm_alarme_schlechter') or 0)} verschlechtert"
        richtung = z.get("tm_letzte_richtung")
        if n and not _leer(z.get("tm_letzter_alarm")) and not _leer(richtung):
            schluessel = (str(z.get("tm_letzter_kanal")), int(float(richtung)))
            teil += (f", zuletzt {z['tm_letzter_alarm']} "
                     f"{RICHTUNGSTEXT.get(schluessel, '')}").rstrip()
        zeilen.extend(textwrap.wrap(teil, 66, subsequent_indent="  "))
    elif tm_status:
        zeilen.append(f"Tagesmonitor: {tm_status}")
    if not _leer(z.get("norm5_winter")):
        abst = z.get("norm5_abstand_k")
        teil = (f"Abkühlung bei 5 °C ({z['norm5_winter']}): "
                f"{_de(z.get('norm5_kwh_m3'), 1)} kWh/m³")
        if not _leer(abst):
            wort = "schlechter" if float(abst) > 0 else "besser"
            teil += f", {_de(abs(float(abst)), 1)} K {wort} als Netz"
        zeilen.append(teil)
    for name, wert, datum in (
            ("Steigung", "netz_z_steigung_aktuell", "datum_z_steigung"),
            ("Spreizung", "netz_z_spreizung_aktuell", "datum_z_spreizung")):
        if not _leer(z.get(datum)):
            zeilen.append(f"Netz-z {name} am {z[datum]}: "
                          f"{_de(z[wert], 1, True)}")
    return "\n".join(zeilen)


def _kernwinter_flaechen(ax, start, ende) -> None:
    """Kernwinter (1. Dez. bis 1. März) hellblau hinterlegen."""
    for jahr in range(start.year - 1, ende.year + 1):
        lo = max(pd.Timestamp(jahr, 12, 1), start)
        hi = min(pd.Timestamp(jahr + 1, 3, 1), ende)
        if lo < hi:
            ax.axvspan(lo, hi, color="#dbe9f6", alpha=0.6, lw=0, zorder=0)


def _zeitachse(ax, meter, kanal, ergebnis) -> None:
    fenster = ergebnis["monitor"].get("fenster")
    eigen = _endliche(fenster, kanal)
    eigen = eigen[eigen["meter"] == meter].sort_values("datum")
    band = ergebnis["baender"][kanal]
    ax.set_title(KANALTITEL[kanal], loc="left", fontsize=10)
    if len(eigen) == 0:
        ax.text(0.5, 0.5, "keine Fensterwerte", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        #nicht set_xticks, die x-Achse ist mit dem anderen Kanal geteilt
        ax.tick_params(left=False, labelleft=False, bottom=False,
                       labelbottom=False)
        return
    start, ende = eigen["datum"].min(), eigen["datum"].max()
    _kernwinter_flaechen(ax, start, ende)
    if len(band):
        b = band[(band["datum"] >= start) & (band["datum"] <= ende)]
        ax.fill_between(b["datum"], b["q10"].astype(float),
                        b["q90"].astype(float), color="0.85", lw=0,
                        label="Netz 10–90 %")
        ax.plot(b["datum"], b["q50"].astype(float), color="0.4", ls="--",
                lw=1, label="Netz Median")
        if "best" in b.columns:
            ax.plot(b["datum"], b["best"].astype(float), color="#2ca02c",
                    ls=":", lw=1.2, label="bestes Viertel")
    ax.plot(eigen["datum"], eigen[kanal], color="C0", lw=1.4,
            label="Station")
    for d in ergebnis["termine"].get(meter, []):
        ax.axvline(pd.Timestamp(d), color="red", ls="--", lw=1)
    #Alarme kommen nur noch aus dem Tagesmonitor (CUSUM-Zeile), der
    #Fensteralarm aus NB 14 traf Begehungen kaum besser als Zufall
    ax.set_xlim(start, ende)
    #Legende über der Achse rechts, damit sie keine Werte verdeckt
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), fontsize=8,
              ncol=4, frameon=False, borderaxespad=0.2)


#Rot ist für Begehungen reserviert, Blau für die Station in den Zeitreihen
WINTER_FARBEN = ["#8c564b", "#ff7f0e", "#2ca02c", "#9467bd", "#17becf",
                 "#e377c2", "#bcbd22"]


def winter_farbe(winter: str) -> str:
    """Feste Farbe je Kernwinter, auf allen Stationsblättern gleich (22/23 orange)."""
    return WINTER_FARBEN[(nv.winter_ende_jahr(winter) - 2022) % len(WINTER_FARBEN)]


def _kennlinie(ax, meter, ergebnis) -> None:
    ax.set_title("Kennlinie je Kernwinter", loc="left", fontsize=10)
    t = ergebnis["tabelle"]
    eigen = t[t["meter"].astype(int) == meter] if len(t) else t
    tab = ergebnis["punkte"].get(meter)
    if len(eigen) == 0 or tab is None or len(tab) == 0:
        ax.text(0.5, 0.5, "keine Kennlinie im Kernwinter", ha="center",
                va="center", transform=ax.transAxes, color="grey")
        ax.set_xticks([]), ax.set_yticks([])
        return
    m = ergebnis["markiert"]
    rang = m[m["meter"].astype(int) == meter].set_index("winter") \
        if len(m) else pd.DataFrame()
    betrieb = nv.betriebsstunden(tab)
    w_std = nv.heizperiode(betrieb["zeit"])
    eintraege = []
    for _, zeile in eigen.iterrows():
        w = zeile["winter"]
        farbe = winter_farbe(w)
        p = betrieb.loc[w_std == w, "power_kw"].to_numpy(dtype=float)
        if len(p) == 0:
            continue
        lo, hi = np.quantile(p, [0.05, 0.95])
        x = np.geomspace(max(lo, 1e-3), max(hi, lo * 1.01), 50)
        y = np.exp(zeile["achsenabschnitt"] + zeile["steigung"] * np.log(x))
        text = (f"{w}: Steigung {_de(zeile['steigung'])}, "
                f"{_de(zeile['spreizung_ref_k'], 1)} K")
        if w in rang.index and np.isfinite(rang.loc[w, "rang"]):
            n = int(((m["winter"] == w) & m["score"].notna()).sum())
            text += f", Rang {int(rang.loc[w, 'rang'])}/{n}"
        eintraege.append((pd.Timestamp(nv.winter_ende_jahr(w), 2, 28),
                          x, y, farbe, text))
    if eintraege:
        letzt = eigen["winter"].iloc[-1]
        punkte = betrieb[w_std == letzt]
        ax.scatter(punkte["power_kw"], punkte["flow_lh"], s=3, alpha=0.12,
                   color=eintraege[-1][3], lw=0)
    for d in ergebnis["termine"].get(meter, []):
        eintraege.append((pd.Timestamp(d), None, None, "red",
                          f"Begehung {pd.Timestamp(d).date().isoformat()}"))
    for _, x, y, farbe, text in sorted(eintraege, key=lambda e: e[0]):
        if x is None:
            ax.plot([], [], color=farbe, ls="--", lw=1, label=text)
        else:
            ax.plot(x, y, color=farbe, lw=2, label=text)
    ax.set_xscale("log"), ax.set_yscale("log")
    ax.set_xlabel("Leistung [kW]"), ax.set_ylabel("Volumenstrom [l/h]")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.85)


def _heatmap(ax, meter, ergebnis) -> None:
    ax.set_title("Netzvergleich je Winter (z, positiv = schlechter)",
                 loc="left", fontsize=10)
    m = ergebnis["markiert"]
    kz = list(ergebnis["kennzahlen"])
    eigen = m[(m["meter"].astype(int) == meter) & m["score"].notna()] \
        if len(m) else m
    if len(eigen) == 0 or not kz:
        ax.text(0.5, 0.5, "kein Netzwert", ha="center", va="center",
                transform=ax.transAxes, color="grey")
        ax.set_xticks([]), ax.set_yticks([])
        return
    eigen = eigen.assign(_j=eigen["winter"].map(nv.winter_ende_jahr)) \
        .sort_values("_j")
    werte = eigen[[f"z_{k}" for k in kz]].to_numpy(dtype=float)
    ax.imshow(np.clip(werte, -3, 6), cmap="RdYlGn_r", vmin=-3, vmax=6,
              aspect="auto")
    for i in range(werte.shape[0]):
        for j in range(werte.shape[1]):
            dunkel = np.isfinite(werte[i, j]) and not -2 < werte[i, j] < 4.5
            ax.text(j, i, _de(werte[i, j], 1), ha="center", va="center",
                    fontsize=8, color="white" if dunkel else "black")
    ax.set_xticks(range(len(kz)))
    ax.set_xticklabels([KENNZAHLKURZ.get(k, k) for k in kz], fontsize=8)
    ax.set_yticks(range(len(eigen)))
    ax.set_yticklabels([w + (" *" if bool(a) else "") for w, a in
                        zip(eigen["winter"], eigen["auffaellig"])], fontsize=8)


def _cusum_achse(ax, meter, ergebnis) -> None:
    """CUSUM-Konten des Tagesmonitors, S+ nach oben und S- nach unten."""
    ax.set_title("Tagesmonitor (CUSUM) gegen eigene Referenz",
                 loc="left", fontsize=10)
    tagesmon = ergebnis.get("tagesmonitor")
    v = (tagesmon["verlauf"] if tagesmon is not None
         else pd.DataFrame(columns=tm.VERLAUF_SPALTEN))
    v = v[v["meter"].astype(int) == meter] if len(v) else v
    if len(v) == 0:
        ax.text(0.5, 0.5, "keine nutzbaren Heiztage nach der Referenz",
                ha="center", va="center", transform=ax.transAxes,
                color="grey")
        ax.tick_params(left=False, labelleft=False)
        return
    ref = tagesmon["referenz"]
    if meter in ref.index:
        ax.axvspan(ref.at[meter, "ref_start"], ref.at[meter, "ref_ende"],
                   color="0.9", lw=0, label="Referenz")
    for kanal, titel in (("kwh_pro_m3", "kWh/m³"),
                         ("log_volumen", "Wassermenge")):
        k = v[v["kanal"] == kanal].sort_values("datum")
        if k.empty:
            continue
        farbe = CUSUM_FARBEN[kanal]
        #Lücken über eine Woche (Sommer) nicht durchziehen
        datum = pd.to_datetime(k["datum"]).reset_index(drop=True)
        luecke = datum.diff() > pd.Timedelta(days=7)
        sp = k["s_plus"].astype(float).reset_index(drop=True).mask(luecke)
        sm = k["s_minus"].astype(float).reset_index(drop=True).mask(luecke)
        ax.plot(datum, sp, color=farbe, lw=1.1, label=titel)
        ax.plot(datum, -sm, color=farbe, lw=1.1)
    for h in (tm.CUSUM_H, -tm.CUSUM_H):
        ax.axhline(h, color="0.5", ls=":", lw=1)
    ax.axhline(0, color="0.7", lw=0.6)
    for d in ergebnis["termine"].get(meter, []):
        ax.axvline(pd.Timestamp(d), color="red", ls="--", lw=1)
    a = tagesmon["alarme"]
    a = a[a["meter"].astype(int) == meter] if len(a) else a
    a = ab.bewerte_richtung(a)
    for _, al in a.iterrows():
        y = tm.CUSUM_H if int(al["richtung"]) > 0 else -tm.CUSUM_H
        farbe = CUSUM_FARBEN[al["kanal"]]
        ax.plot(pd.Timestamp(al["datum"]), y,
                "^" if y > 0 else "v", color=farbe, ms=6, ls="none",
                mfc=farbe if al["bewertung"] == "schlechter" else "white")
    if len(a):
        ax.plot([], [], "v", color="0.3", ms=6, ls="none",
                label="Alarm verschlechtert")
        ax.plot([], [], "^", color="0.3", mfc="white", ms=6, ls="none",
                label="verbessert")
    ax.set_ylim(-tm.CUSUM_MAX - 1, tm.CUSUM_MAX + 1)
    ax.set_ylabel("S+ / −S−", fontsize=8)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), fontsize=8,
              ncol=5, frameon=False, borderaxespad=0.2)


def zeichne_stationsblatt(meter: int, ergebnis: Mapping,
                          zeile: Optional[Mapping] = None):
    """Monitorbild einer Station mit Netzband, CUSUM und Wintervergleich."""
    import matplotlib.pyplot as plt

    meter = int(meter)
    if zeile is None:
        tab = statustabelle(ergebnis)
        zeile = tab[tab["meter"] == meter].iloc[0]
    fig = plt.figure(figsize=(14, 13.5))
    gs = fig.add_gridspec(5, 2, height_ratios=[1, 1, 0.8, 1.1, 0.75],
                          width_ratios=[1.15, 1], hspace=0.5, wspace=0.18,
                          top=0.94)
    ax_st = fig.add_subplot(gs[0, :])
    ax_dt = fig.add_subplot(gs[1, :], sharex=ax_st)
    ax_cu = fig.add_subplot(gs[2, :], sharex=ax_st)
    ax_kl = fig.add_subplot(gs[3:, 0])
    ax_hm = fig.add_subplot(gs[3, 1])
    ax_tx = fig.add_subplot(gs[4, 1])

    _zeitachse(ax_st, meter, "steigung", ergebnis)
    _zeitachse(ax_dt, meter, "dt_median_k", ergebnis)
    _cusum_achse(ax_cu, meter, ergebnis)
    _kennlinie(ax_kl, meter, ergebnis)
    _heatmap(ax_hm, meter, ergebnis)
    ax_tx.axis("off")
    ax_tx.text(0.0, 1.0, statustext(zeile), va="top", ha="left",
               fontsize=9, family="monospace", transform=ax_tx.transAxes)

    try:
        aw = float(ergebnis["anschlusswerte"].get(meter, np.nan))
    except (TypeError, ValueError):
        aw = np.nan
    titel = f"Zähler {meter}"
    if np.isfinite(aw):
        titel += f", Anschlusswert {_de(aw, 0)} kW"
    if meter in ergebnis["bhkw"]:
        titel += ", BHKW"
    fig.suptitle(titel, x=0.01, ha="left", fontsize=13)
    return fig


def exportiere(ergebnis: Mapping, out_dir: Path = OUT_DIR, dpi: int = 110,
               meters: Optional[Sequence[int]] = None,
               fortschritt: bool = False) -> pd.DataFrame:
    """Ein PNG je Zähler und ``status.csv`` mit allen Zählern.

    Messstellen ohne Übergabestation bekommen nur eine Statuszeile, ein
    altes Bild von ihnen wird gelöscht.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    tab = statustabelle(ergebnis)
    auswahl = ergebnis["meters"] if meters is None else [int(m) for m in meters]
    unbekannt = set(auswahl) - set(ergebnis["meters"])
    if unbekannt:
        raise KeyError(f"Zähler nicht im Ergebnis: {sorted(unbekannt)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    ohne_blatt = set(ergebnis.get("messstellen", ()))
    for meter in ohne_blatt & set(auswahl):
        (out_dir / f"{meter}.png").unlink(missing_ok=True)
    auswahl = [m for m in auswahl if m not in ohne_blatt]
    for i, meter in enumerate(auswahl, start=1):
        zeile = tab[tab["meter"] == meter].iloc[0]
        fig = zeichne_stationsblatt(meter, ergebnis, zeile)
        fig.savefig(out_dir / f"{meter}.png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        if fortschritt and (i % 10 == 0 or i == len(auswahl)):
            print(f"{i}/{len(auswahl)} Blätter")
    tab.to_csv(out_dir / "status.csv", index=False)
    return tab


def main(argv: Optional[Sequence[str]] = None) -> None:
    import argparse

    p = argparse.ArgumentParser(description="Stationsblätter exportieren")
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--zaehler", type=int, nargs="*", default=None)
    args = p.parse_args(argv)
    e = eingaben()
    ergebnis = rechne(e["serien"], e["termine"], e["anschlusswerte"],
                      e["bhkw"], e["ohne_datum"], baujahr=e["baujahr"],
                      fortschritt=True)
    tab = exportiere(ergebnis, args.out, meters=args.zaehler,
                     fortschritt=True)
    print(f"{len(tab)} Statuszeilen, Bilder in {args.out}")


if __name__ == "__main__":
    main()
