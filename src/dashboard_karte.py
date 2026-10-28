"""Modellergebnisse für die Netzkarte (Notebook 35, ``notebooks/dashboard_final.py``).

Dieses Modul rechnet keine Modelle. Es liest die Tabellen, die
``python -m src.dashboard_daten`` nach ``outputs/dashboard/`` schreibt, und macht
daraus kleine, JSON-fähige Einträge je Zähler. Das Kartenskript schreibt sie in
die HTML-Datei.

Je Zähler:

- **Empfehlung** und **Dringlichkeit** (Empfehlungssystem, `dashboard_daten.empfehlungen`)
- **Verdacht auf eine Fehlerart:** Ventil, Dämmung, Kapazität (Klassifizierung,
  Paket ``fehlerklassen``)
- **Stand im Netz** und **Potenzial** (Stationsleistung, Netzvergleich von Modell Ivelina)
- **Meldungen** der Wächter, je Tag mit dem Hauptkanal

Hauptkanal (Notebook 34, Abschnitt 13): An einem Tag, an dem Ivelinas
Tagesmonitor rechnet (Heiztag, Referenz vorhanden), zählt seine Meldung. Sonst
zählt das Prognose-LSTM (warme Tage, Stationen ohne Referenz). LSTM-Meldungen an
Tagen des Tagesmonitors bleiben als Hinweis in der Liste, färben die Karte aber
nicht. So meldet für jede Station und jeden Tag genau ein Wächter.

Nur Zählernummern, keine Adressen.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ORDNER = ROOT / "outputs" / "dashboard"

#Reihenfolge wie dashboard_daten.HANDLUNGEN; bei mehreren Maßnahmen färbt die erste die Karte.
#Regelungsoptimierung fehlt bewusst: kein Modell erkennt sie (Notebook 34, Test C)
MASSNAHMEN = {"Reparatur: Regelventil tauschen": "reparatur",
              "Kapazitätsanpassung prüfen": "kapazitaet",
              "Dämmung prüfen": "daemmung",
              "Daten prüfen": "daten"}
DRINGLICHKEIT = {"keine": 0, "niedrig": 1, "mittel": 2, "hoch": 3}
POTENZIAL = {"gering": 1, "mittel": 2, "hoch": 3}
QUELLEN = ("Tagesmonitor", "Prognose-LSTM")
#Grenzen, falls meta.json sie noch nicht enthält (Paket fehlerklassen)
GRENZEN = {"ventil": 0.5, "daemmung": 0.5, "vertrag": 0.69}
#Richtung einer Meldung in Worten: (Kanal, Richtung)
KANAL_TEXT = {("kwh_pro_m3", -1): "weniger Abkühlung", ("kwh_pro_m3", 1): "mehr Abkühlung",
              ("log_volumen", 1): "mehr Wasser", ("log_volumen", -1): "weniger Wasser",
              ("ruecklauf", 1): "Rücklauf höher als erwartet",
              ("ruecklauf", -1): "Rücklauf niedriger als erwartet",
              ("nachtdurchfluss", 1): "mehr Nachtdurchfluss als erwartet",
              ("nachtdurchfluss", -1): "weniger Nachtdurchfluss als erwartet"}


def zaehler_text(z) -> str:
    """Zählernummer als Text ohne führende Nullen, wie ``norm_z`` in Notebook 16."""
    if isinstance(z, float) and z.is_integer():
        z = int(z)
    return re.sub(r"\D", "", str(z)).lstrip("0")


def _zahl(x, stellen: int = 2) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, stellen) if math.isfinite(x) else None


def _text(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x)


def _ja(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x)) and bool(x)


# --- Laden ---------------------------------------------------------------------

def lade(ordner: Path = ORDNER) -> dict:
    """Tabellen aus ``outputs/dashboard/`` lesen.

    Pflicht: ``stationen.parquet``, ``alarme.parquet``, ``meta.json``. Ohne die
    Verläufe der Wächter fehlt nur der Status „überwacht, keine Meldung“.
    """
    ordner = Path(ordner)
    fehlt = [d for d in ("stationen.parquet", "alarme.parquet", "meta.json") if not (ordner / d).exists()]
    if fehlt:
        raise FileNotFoundError(f"{ordner} fehlt {fehlt}: zuerst `python -m src.dashboard_daten` ausführen")
    daten = {"stationen": pd.read_parquet(ordner / "stationen.parquet"),
             "alarme": pd.read_parquet(ordner / "alarme.parquet"),
             "meta": json.loads((ordner / "meta.json").read_text(encoding="utf-8"))}
    for name, datei, spalten in (("tm_tage", "waechter_tagesmonitor.parquet", ["zaehler", "datum"]),
                                 ("lstm_tage", "waechter_lstm.parquet", ["zaehler", "tag"]),
                                 ("effizienz", "netzeffizienz.parquet", None)):
        p = ordner / datei
        daten[name] = pd.read_parquet(p, columns=spalten) if p.exists() else None
    return daten


# --- Meldungen -----------------------------------------------------------------

def _tage(df: Optional[pd.DataFrame], spalte: str, quelle: str) -> pd.DataFrame:
    if df is None or not len(df):
        return pd.DataFrame(columns=["zaehler", "datum", "quelle"])
    return (pd.DataFrame({"zaehler": df["zaehler"].astype(int).to_numpy(),
                          "datum": pd.to_datetime(df[spalte]).dt.normalize().astype("datetime64[ns]").to_numpy()})
            .drop_duplicates().assign(quelle=quelle))


def hauptkanal(tm_tage: Optional[pd.DataFrame], lstm_tage: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Je Stationstag der Wächter, der zählt: Tagesmonitor, wo er rechnet, sonst Prognose-LSTM."""
    alle = pd.concat([_tage(tm_tage, "datum", QUELLEN[0]), _tage(lstm_tage, "tag", QUELLEN[1])],
                     ignore_index=True)
    #eine leere Tabelle macht die Spalten sonst zu object
    alle = alle.astype({"zaehler": "int64", "datum": "datetime64[ns]"})
    alle["_r"]= alle["quelle"].map({q: i for i, q in enumerate(QUELLEN)})
    return (alle.sort_values(["zaehler", "datum", "_r"])
            .drop_duplicates(["zaehler", "datum"]).drop(columns="_r").reset_index(drop=True))


def meldungen(alarme: pd.DataFrame, kanal: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Alarme mit Spalte ``haupt``: kommt die Meldung vom Hauptkanal dieses Tages?

    Ohne Kanaltabelle zählt jede Meldung.
    """
    a = alarme.assign(zaehler=alarme["zaehler"].astype(int),
                      datum=pd.to_datetime(alarme["datum"]).dt.normalize().astype("datetime64[ns]"))
    if kanal is None or not len(kanal):
        return a.assign(haupt=True)
    k = kanal.rename(columns={"quelle": "_haupt"})
    a = a.merge(k, on=["zaehler", "datum"], how="left")
    #ein Alarm ohne Kanaltag (z. B. Rand des Verlaufs) zählt für seinen eigenen Wächter
    a["haupt"] = a["_haupt"].isna() | (a["_haupt"] == a["quelle"])
    return a.drop(columns="_haupt")


def meldungen_je_zaehler(meld: pd.DataFrame, tag0, n_tage: int) -> dict:
    """``{zähler: [[tag, ±1, quelle, netz, haupt, text], …]}`` für Tage im Kartenzeitraum.

    ``tag`` zählt ab ``tag0``, ``+1`` heißt schlechter, ``quelle`` ist der Index in
    ``QUELLEN``, ``netz`` markiert Tage, an denen viele Stationen zugleich
    schlechter wurden (eher Wetter oder Netz).
    """
    tag0 = pd.Timestamp(tag0).normalize()
    m = meld.assign(tag_nr=(meld["datum"] - tag0).dt.days)
    m = m[(m["tag_nr"] >= 0) & (m["tag_nr"] < n_tage)].sort_values(["zaehler", "tag_nr"])
    aus: dict = {}
    for r in m.itertuples(index=False):
        text = KANAL_TEXT.get((str(r.kanal), int(r.richtung)), str(r.kanal))
        aus.setdefault(zaehler_text(r.zaehler), []).append(
            [int(r.tag_nr), 1 if r.bewertung == "schlechter" else -1, QUELLEN.index(r.quelle),
             int(_ja(getattr(r, "netzereignis", False))), int(bool(r.haupt)), text])
    return aus


def ueberwacht(kanal: pd.DataFrame, tag0, n_tage: int) -> dict:
    """``{zähler: "0110…"}``: an welchen Tagen ein Wächter die Station bewertet."""
    tag0 = pd.Timestamp(tag0).normalize()
    aus = {}
    for z, g in kanal.groupby("zaehler"):
        t = (g["datum"] - tag0).dt.days
        t = t[(t >= 0) & (t < n_tage)]
        if not len(t):
            continue
        zeichen = ["0"] * n_tage
        for i in t:
            zeichen[int(i)] = "1"
        aus[zaehler_text(z)] = "".join(zeichen)
    return aus


# --- Stationen -----------------------------------------------------------------

def ventil_stufe(p, grenze: float = GRENZEN["ventil"]) -> str:
    """Ventilverdacht in Worten, nur an der geprüften Grenze (Notebook 34, Test C).

    Der Score ist eine Rangfolge, keine Wahrscheinlichkeit. Stufen wie „hoch ab 0,8“
    sind nirgends geprüft und fehlen deshalb.
    """
    p = _zahl(p, 4)
    if p is None:
        return ""
    return "Verdacht" if p >= grenze else "kein Verdacht"


def massnahmen(handlung) -> list:
    """Codes der Maßnahmen in der Reihenfolge von ``MASSNAHMEN``."""
    teile = {t.strip() for t in _text(handlung).split(";")}
    return [c for t, c in MASSNAHMEN.items() if t in teile]


def eintrag(z: pd.Series, grenzen: Optional[dict] = None) -> dict:
    """Ein Zähler aus ``stationen.parquet`` als kleines Wörterbuch für die Karte."""
    g = {**GRENZEN, **{k: v for k, v in (grenzen or {}).items() if v is not None}}
    rang = _zahl(z.get("netz_rang"), 0)
    return {"z": zaehler_text(z["zaehler"]),
            "rang": int(z["rang"]) if _zahl(z.get("rang"), 0) is not None else None,
            "dr": DRINGLICHKEIT.get(_text(z.get("dringlichkeit")), 0),
            "ma": massnahmen(z.get("handlung")),
            "empfehlung": _text(z.get("handlung")) or "keine",
            "warum": _text(z.get("begruendung")),
            "klasse": _text(z.get("klasse")),
            "ventil": ventil_stufe(z.get("p_ventil"), g["ventil"]),
            "p_ventil": _zahl(z.get("p_ventil")),
            "sommernacht": _zahl(z.get("sommer_durchlauf_anteil")),
            "daemmung": _ja(z.get("hinweis_daemmung")),
            "p_daemmung": _zahl(z.get("p_daemmung")),
            "kapazitaet": _ja(z.get("hinweis_vertrag")),
            "auslastung": _zahl(z.get("auslastung")),
            "netz_rang": int(rang) if rang is not None else None,
            "netz_n": int(z["n_stationen"]) if _zahl(z.get("n_stationen"), 0) is not None else None,
            "netz_winter": _text(z.get("netz_winter")),
            "fehlerbild": _text(z.get("netz_fehlerbild")),
            "potenzial": _text(z.get("potenzial")),
            "luecke": _text(z.get("luecke_text")),
            "symptom": _text(z.get("symptom")),
            "veraenderung": _text(z.get("veraenderung")),
            "ursache": _text(z.get("vermutete_ursache")),
            "befund": _text(z.get("befund")) or "nie begangen",
            "sonderfall": _text(z.get("sonderfall_grund")),
            "vor": eintrag_vor(z, g)}


def eintrag_vor(z: pd.Series, grenzen: Optional[dict] = None) -> Optional[dict]:
    """Stand vor den Begehungen (Spalten mit ``_vor``), ``None`` ohne diesen Stand."""
    if not _text(z.get("dringlichkeit_vor")):
        return None
    g = {**GRENZEN, **(grenzen or {})}
    rang = _zahl(z.get("rang_vor"), 0)
    return {"rang": int(rang) if rang is not None else None,
            "dr": DRINGLICHKEIT.get(_text(z.get("dringlichkeit_vor")), 0),
            "ma": massnahmen(z.get("handlung_vor")),
            "empfehlung": _text(z.get("handlung_vor")) or "keine",
            "warum": _text(z.get("begruendung_vor")),
            "ventil": ventil_stufe(z.get("p_ventil_vor_begehung"), g["ventil"]),
            "p_ventil": _zahl(z.get("p_ventil_vor_begehung")),
            "sommernacht": _zahl(z.get("sommer_durchlauf_anteil_vor")),
            "daemmung": _ja(z.get("hinweis_daemmung_vor")),
            "p_daemmung": _zahl(z.get("p_daemmung_vor_begehung")),
            "kapazitaet": _ja(z.get("hinweis_vertrag_vor")),
            "auslastung": _zahl(z.get("auslastung_vor")),
            "fehlerbild": _text(z.get("netz_fehlerbild_vor")),
            "sonderfall": _text(z.get("sonderfall_grund_vor"))}


def haus(eintraege: Iterable[dict]) -> Optional[dict]:
    """Zusammenfassung für ein Haus mit einem oder mehreren Zählern.

    Dringlichkeit und Potenzial: der schlechteste Zähler. Maßnahme: die
    vorderste nach ``MASSNAHMEN``, sonst „keine“.
    """
    e = list(eintraege)
    if not e:
        return None
    codes = {c for x in e for c in x["ma"]}
    ma = next((c for c in MASSNAHMEN.values() if c in codes), "keine")
    po = max((POTENZIAL.get(x.get("potenzial", ""), 0) for x in e), default=0)
    return {"dr": max(x["dr"] for x in e), "ma": ma, "po": po}


def effizienz_monate(eff: Optional[pd.DataFrame]) -> list:
    """Netzeffizienz je Monat: kWh je m³, Rücklauf und Spreizung, volumengewichtet."""
    if eff is None or not len(eff):
        return []
    return [{"m": pd.Timestamp(r.monat).strftime("%Y-%m"), "kwh_m3": _zahl(getattr(r, "kwh_pro_m3", None), 1),
             "rl": _zahl(r.ruecklauf_c, 1), "spr": _zahl(r.spreizung_k, 1), "n": int(r.stationen),
             "ok": bool(r.vergleichbar)} for r in eff.itertuples(index=False)]


# --- Gesamt --------------------------------------------------------------------

def karten_daten(daten: dict, start, ende) -> dict:
    """Alles, was die Karte braucht, für den Zeitraum ``start`` bis ``ende``."""
    tag0 = pd.Timestamp(start).normalize()
    n_tage = int((pd.Timestamp(ende).normalize() - tag0).days) + 1
    meta = daten["meta"]
    st = daten["stationen"]
    stationen = {e["z"]: e for e in (eintrag(z, meta.get("grenzen")) for _, z in st.iterrows())}
    kanal = hauptkanal(daten.get("tm_tage"), daten.get("lstm_tage"))
    meld = meldungen(daten["alarme"], kanal)
    return {"tag0": str(tag0.date()), "n_tage": n_tage,
            "stationen": stationen,
            "meldungen": meldungen_je_zaehler(meld, tag0, n_tage),
            "ueberwacht": ueberwacht(kanal, tag0, n_tage),
            "effizienz": effizienz_monate(daten.get("effizienz")),
            "meta": {"winter": meta.get("winter_name", ""), "erstellt": meta.get("erstellt", ""),
                     "datenende": _text(meta.get("datenende"))[:10], "pakete": meta.get("pakete", {}),
                     "grenzen": {**GRENZEN, **{k: v for k, v in (meta.get("grenzen") or {}).items()
                                               if v is not None}},
                     "stationen": int(len(st)),
                     "vor": meta.get("vorher")}}


def abgleich(karte_zaehler: Iterable, stationen: dict) -> dict:
    """Welche Zähler stehen auf der Karte ohne Modellergebnis, welche fehlen auf der Karte?"""
    karte = {zaehler_text(z) for z in karte_zaehler}
    modell = set(stationen)
    return {"auf_karte_ohne_modell": sorted(karte - modell), "modell_nicht_auf_karte": sorted(modell - karte)}
