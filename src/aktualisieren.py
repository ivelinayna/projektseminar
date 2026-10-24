"""Aktualisierung mit neuen Zählerdaten in einem Schritt.

Für den Betrieb nach der Projektphase: neue Exporte in `data/raw/` legen,
dann

    python -m src.aktualisieren

Der Lauf macht nacheinander, was sonst von Hand passiert:

1. NB 00 ausführen (einziger Ladeweg für die Stundenreihen). Das Notebook
   selbst wird dabei nicht verändert, die Ausgabe landet im Log.
2. Außentemperatur vom DWD neu holen. Ohne Netz bleibt der alte Cache,
   mit Warnung, wenn er nicht bis zum Datenende reicht.
3. Netzvergleich, Tagesmonitor und Priorität rechnen, Stationsblätter
   und `status.csv` schreiben (`stationsblatt`).
4. Kurzbericht `bericht.txt`: Priorität und Potenzial im jüngsten
   Kernwinter, Alarme der letzten Tage, Änderungen gegenüber dem letzten
   Lauf.

Netzkarte (NB 24 und NB 25) gehört nicht dazu, die wird bei Bedarf danach
in Jupyter ausgeführt. Alles ohne Adressen, nur Zählernummern.
"""

from __future__ import annotations

import ast
import contextlib
import io
import os
import shutil
import warnings
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NB00 = ROOT / "notebooks" / "00_eda_hast_stationsprofile.ipynb"
LOG_DIR = ROOT / "outputs" / "aktualisierung"
TAGE_AKTUELL = 14
#ab so vielen Stationen mit Verschlechterung im selben Zeitraum eher Wetter oder Netz (NB 24)
NETZEREIGNIS_STATIONEN = 11
PRIO_REIHENFOLGE = ("hoch", "mittel", "niedrig")


def nb00_ausfuehren(pfad: Path = NB00, log: Optional[Path] = None) -> int:
    """Codezellen von NB 00 der Reihe nach ausführen, ohne Jupyter.

    Läuft wie im Notebook mit ``notebooks/`` als Arbeitsordner. Abbildungen
    werden nicht angezeigt, Textausgaben gehen in ``log``. Bei einem Fehler
    bricht der Lauf mit der Zellennummer ab. Rückgabe: Zahl der Zellen.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import nbformat

    nb = nbformat.read(pfad, as_version=4)
    zellen = [z for z in nb.cells if z.cell_type == "code"]
    puffer = io.StringIO()
    namensraum = {"__name__": "__main__", "display": lambda *a, **k: None}
    alt = Path.cwd()
    os.chdir(Path(pfad).parent)
    try:
        for i, zelle in enumerate(zellen, start=1):
            quelle = "".join(zelle.source)
            print(f"--- Zelle {i}", file=puffer)
            try:
                with contextlib.redirect_stdout(puffer), warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    exec(compile(ast.parse(quelle), f"<NB 00 Zelle {i}>",
                                 "exec"), namensraum)
            except Exception as exc:
                raise RuntimeError(f"NB 00, Zelle {i} von {len(zellen)}: "
                                   f"{type(exc).__name__}: {exc}") from exc
            finally:
                plt.close("all")
    finally:
        os.chdir(alt)
        if log is not None:
            Path(log).parent.mkdir(parents=True, exist_ok=True)
            Path(log).write_text(puffer.getvalue(), encoding="utf-8")
    return len(zellen)


def wetter_aktualisieren(offline: bool = False) -> tuple:
    """DWD-Cache neu holen, bei Netzfehler den alten behalten.

    Rückgabe: (letzter Zeitstempel im Cache, Hinweistext oder "").
    """
    from . import weather

    pfad = weather.cache_path(weather.DEFAULT_STATION_ID)
    hinweis = ""
    if not offline:
        try:
            weather.refresh_cache(weather.DEFAULT_STATION_ID)
        except (weather.WeatherDownloadError, OSError) as exc:
            hinweis = f"DWD nicht erreichbar, alter Wetter-Cache genutzt ({exc})"
    if not pfad.exists():
        raise SystemExit(
            "Kein Wetter-Cache und kein Download möglich. Archiv von "
            "opendata.dwd.de laden und mit 'python -m src.weather --archive "
            "<zip>' einspielen.")
    ende = pd.read_csv(pfad, usecols=["timestamp_utc"])["timestamp_utc"].max()
    return pd.Timestamp(ende).tz_localize(None), hinweis


def datenende(serien) -> pd.Timestamp:
    """Letzte Stunde mit Messwert über alle Zähler."""
    return max(df.dropna(how="all").index.max() for df in serien.values()
               if len(df))


def _ja(wert) -> bool:
    return str(wert).strip().lower() in ("true", "1", "1.0")


def _text(wert) -> Optional[str]:
    """Fehlende Werte als None, egal ob NaN, None oder leerer String."""
    if wert is None or (isinstance(wert, float) and pd.isna(wert)):
        return None
    s = str(wert).strip()
    return s if s and s.lower() != "nan" else None


def _int(wert) -> str:
    try:
        return str(int(float(wert)))
    except (TypeError, ValueError):
        return "0"


def bericht(status: pd.DataFrame, alarme: pd.DataFrame,
            ende: pd.Timestamp, vorher: Optional[pd.DataFrame] = None,
            tage: int = TAGE_AKTUELL, wetter_ende=None,
            hinweise: Sequence[str] = ()) -> str:
    """Kurzbericht als Text, nur Zählernummern.

    ``status`` ist die Statustabelle aus `stationsblatt`, ``alarme`` die
    bewerteten Tagesmonitor-Alarme (Spalte ``bewertung``), ``vorher`` die
    Statustabelle des letzten Laufs.
    """
    ende = pd.Timestamp(ende)
    z: List[str] = [f"Aktualisierung vom {date.today().isoformat()}, "
                    f"Zählerdaten bis {ende.date().isoformat()}"]
    if wetter_ende is not None:
        z.append(f"Außentemperatur (DWD) bis {pd.Timestamp(wetter_ende).date().isoformat()}")
    z.extend(hinweise)
    z.append("")

    mess = (status[status["grund"].fillna("") == "keine_hast"]
            if "grund" in status.columns else status.iloc[:0])
    status = status.drop(mess.index)

    mit = status[status["winter"].notna()]
    if len(mit):
        winter = mit["winter"].mode().iloc[0]
        akt = mit[mit["winter"] == winter]
        n = akt["prioritaet"].value_counts()
        teile = [f"{int(n.get(p, 0))} {p}" for p in PRIO_REIHENFOLGE]
        z.append(f"Priorität im Kernwinter {winter}: " + ", ".join(teile)
                 + f" (von {len(akt)} Stationen)")
        rest = len(status) - len(akt)
        if rest:
            z.append(f"  {rest} Stationen ohne Einstufung in {winter} "
                     "(zu wenig Daten, älterer Winter oder BHKW)")
        hoch = akt[akt["prioritaet"] == "hoch"].sort_values("rang")
        if len(hoch):
            z.append("Priorität hoch, zuerst ansehen:")
            for _, r in hoch.iterrows():
                beg = (f"letzte Begehung {_text(r.get('letzte_begehung'))}"
                       if _text(r.get("letzte_begehung"))
                       else "keine Begehung bekannt")
                bild = _text(r.get("fehlerbild")) or "ohne Fehlerbild"
                z.append(f"  {int(r['meter'])}  Rang {_int(r['rang'])}, {bild}, "
                         f"{_int(r['alarme_schlechter_winter'])} Alarme "
                         f"verschlechtert, {beg}")
        if "potenzial" in akt.columns and akt["potenzial"].map(_text).notna().any():
            n = akt["potenzial"].value_counts()
            z.append(f"Potenzial gegen das beste Viertel in {winter}: "
                     + ", ".join(f"{int(n.get(p, 0))} {p}"
                                 for p in ("hoch", "mittel", "gering")))
            still = akt[(akt["potenzial"] == "hoch")
                        & (akt["prioritaet"] != "hoch")]
            if len(still):
                z.append("Potenzial hoch, aber Priorität nicht hoch "
                         "(weit hinter dem besten Viertel, ohne Alarm "
                         "oder ohne Auffälligkeit im Netzvergleich):")
                from .stationsblatt import luecke_text
                for _, r in still.sort_values("potenzial_score",
                                              ascending=False).iterrows():
                    k = _text(r.get("groesste_luecke"))
                    luecke = (luecke_text(k, r.get(f"bw_abstand_{k}"))
                              if k else "keine Lücke")
                    z.append(f"  {int(r['meter'])}  Priorität {r['prioritaet']}, "
                             f"{luecke}")
    else:
        z.append("Noch kein Kernwinter mit genug Daten, keine Priorität.")
    if len(mess):
        n_m = len(mess)
        z.append(f"{n_m} Messstelle{'n' if n_m > 1 else ''} ohne Übergabestation "
                 "(nur Temperaturen) nicht bewertet: "
                 + ", ".join(str(int(m)) for m in sorted(mess["meter"])))
    z.append("")

    seit = ende.normalize() - pd.Timedelta(days=tage)
    neu = alarme[pd.to_datetime(alarme["datum"]) > seit] if len(alarme) else alarme
    z.append(f"Alarme im Tagesmonitor seit {seit.date().isoformat()} "
             f"(letzte {tage} Tage der Daten):")
    if len(neu) == 0:
        z.append("  keine")
    for bewertung, wort in (("schlechter", "verschlechtert"),
                            ("besser", "verbessert")):
        teil = neu[neu["bewertung"] == bewertung] if len(neu) else neu
        if len(teil) == 0:
            continue
        zaehler = sorted(teil["meter"].astype(int).unique())
        z.append(f"  {wort}: {len(zaehler)} Stationen: "
                 + ", ".join(str(m) for m in zaehler))
        if bewertung == "schlechter" and len(zaehler) >= NETZEREIGNIS_STATIONEN:
            z.append("  Viele Stationen gleichzeitig, das ist eher ein Hinweis "
                     "auf Wetter oder Netz als auf einzelne Häuser.")
    ohne = status[status["tm_status"].fillna("") != "ok"]
    if len(ohne):
        z.append(f"  Tagesmonitor noch nicht aktiv bei {len(ohne)} Stationen "
                 "(Referenzzeit fehlt oder zu kurz)")
    z.append("")

    if vorher is not None and len(vorher):
        alt = vorher.set_index(vorher["meter"].astype(int))
        neu_st = status.set_index(status["meter"].astype(int))
        aend = []
        for m in neu_st.index:
            p_neu = _text(neu_st.at[m, "prioritaet"])
            if m not in alt.index:
                aend.append(f"  {m}  neu dazugekommen")
                continue
            p_alt = _text(alt.at[m, "prioritaet"])
            if p_neu != p_alt:
                aend.append(f"  {m}  Priorität {p_alt or '-'} -> {p_neu or '-'}")
            elif _ja(neu_st.at[m, "auffaellig"]) != _ja(alt.at[m, "auffaellig"]):
                wort = "auffällig" if _ja(neu_st.at[m, "auffaellig"]) else "unauffällig"
                aend.append(f"  {m}  jetzt {wort} im Netzvergleich")
        z.append("Geändert seit dem letzten Lauf:")
        z.extend(aend or ["  nichts"])
    return "\n".join(z) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> None:
    import argparse

    from . import alarmbewertung as ab
    from . import stationsblatt as sbl

    p = argparse.ArgumentParser(description="Alles neu rechnen mit den Daten in data/raw")
    p.add_argument("--ohne-nb00", action="store_true",
                   help="NB 00 überspringen, wenn es schon gelaufen ist")
    p.add_argument("--offline", action="store_true",
                   help="Wetter nicht neu laden, vorhandenen Cache nutzen")
    p.add_argument("--tage", type=int, default=TAGE_AKTUELL,
                   help="Zeitraum für 'aktuelle Alarme' in Tagen")
    p.add_argument("--out", type=Path, default=sbl.OUT_DIR)
    args = p.parse_args(argv)

    if args.ohne_nb00:
        print("1/4 NB 00 übersprungen")
    else:
        print("1/4 NB 00: Stundenreihen aufbereiten ...", flush=True)
        n = nb00_ausfuehren(log=LOG_DIR / "nb00.log")
        print(f"    {n} Zellen ausgeführt, Log in {LOG_DIR / 'nb00.log'}")

    print("2/4 Außentemperatur vom DWD ...", flush=True)
    wetter_ende, w_hinweis = wetter_aktualisieren(args.offline)
    hinweise = [w_hinweis] if w_hinweis else []
    if w_hinweis:
        print("    " + w_hinweis)

    print("3/4 Netzvergleich, Tagesmonitor, Stationsblätter ...", flush=True)
    e = sbl.eingaben()
    ende = datenende(e["serien"])
    if pd.Timestamp(wetter_ende) < ende - pd.Timedelta(days=2):
        text = (f"Wetter reicht nur bis {pd.Timestamp(wetter_ende).date()}, "
                f"Zählerdaten bis {ende.date()}: die letzten Tage fehlen im "
                "Tagesmonitor")
        hinweise.append(text)
        print("    " + text)
    ergebnis = sbl.rechne(e["serien"], e["termine"], e["anschlusswerte"],
                          e["bhkw"], e["ohne_datum"], baujahr=e["baujahr"],
                          fortschritt=True)
    vorher_pfad = Path(args.out) / "status.csv"
    vorher = pd.read_csv(vorher_pfad) if vorher_pfad.exists() else None
    if vorher is not None:
        shutil.copy(vorher_pfad, Path(args.out) / "status_vorher.csv")
    status = sbl.exportiere(ergebnis, args.out)

    print("4/4 Bericht ...", flush=True)
    tm_erg = ergebnis.get("tagesmonitor")
    alarme = (ab.bewerte_richtung(tm_erg["alarme"])
              if tm_erg is not None and len(tm_erg["alarme"])
              else pd.DataFrame(columns=["meter", "datum", "bewertung"]))
    text = bericht(status, alarme, ende, vorher, args.tage, wetter_ende,
                   hinweise)
    (Path(args.out) / "bericht.txt").write_text(text, encoding="utf-8")
    print()
    print(text)
    print(f"Stationsblätter, status.csv und bericht.txt in {args.out}")


if __name__ == "__main__":
    main()
