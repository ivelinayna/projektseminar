"""Normalverhaltensmodell als Wächter im Betrieb (Tagesmonitor als Paket).

Das Normalverhaltensmodell stammt aus Notebook 17 (Seb). `src/tagesmonitor.py`
rechnet dieselbe Idee auf den Stundenreihen aus Notebook 00: je Station und
Kanal (Abkühlung in kWh/m³, logarithmiertes Tagesvolumen) eine Kennlinie
gegen die Tagesmitteltemperatur aus dem ersten Jahr, danach ein CUSUM auf
den Abweichungen. Auf Sebs Prüfung sind beide gleichwertig (Notebook 32:
29 gegen 30 von 43 Begehungen bemerkt, im 14-Tage-Fenster der Tagesmonitor
vorn). Für den Betrieb wird der Tagesmonitor genommen, weil er als Modul
auf neuen Daten läuft.

Dieses Modul legt die gelernten Kennlinien als Modellpaket ab und wendet
sie auf neue Tage an, ohne neu zu lernen:

- `paket_bauen`: Referenz je Station und Kennlinien speichern
- `lade` / `anwenden`: Kennlinien auf Tageswerte anwenden, CUSUM, Alarme

Die Referenz ist das erste Jahr jeder Station (spätestens 14 Tage vor der
ersten Begehung). Ein neu gebautes Paket ändert deshalb an bestehenden
Stationen nichts, solange sich deren erstes Jahr nicht ändert; neue
Stationen kommen dazu, sobald sie 60 Referenz-Heiztage haben.

    python -m src.normalmodell_waechter --bauen
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import modellpaket as mp
from . import tagesmonitor as tm

ROOT = Path(__file__).resolve().parents[1]
PAKETNAME = "normalmodell"


def eingaben(root: Path = ROOT) -> dict:
    """Stundenreihen aus NB 00, Begehungstermine, Tagesmitteltemperatur."""
    from . import load_begehungen as lb
    from . import ternaer as tn
    serien = tn.lade_serien(Path(root) / "data" / "processed" / "real_meters")
    termine = {int(k): list(v) for k, v in lb.begehung_dates_by_meter().items()}
    starts = [s.index.min() for s in serien.values() if len(s)]
    enden = [s.index.max() for s in serien.values() if len(s)]
    temp = tm.lade_temperatur(min(starts).normalize(),
                              max(enden).normalize() + pd.Timedelta(hours=23))
    return {"serien": serien, "termine": termine, "temp": temp}


def _kennlinie_json(k: dict) -> dict:
    if k["form"] == "gerade":
        return {"form": "gerade", "a": float(k["a"]), "b": float(k["b"])}
    return {"form": "klassen", "stuetz_t": [float(v) for v in k["stuetz_t"]],
            "stuetz_y": [float(v) for v in k["stuetz_y"]]}


def _kennlinie_lesen(k: dict) -> dict:
    if k["form"] == "gerade":
        return k
    return {"form": "klassen", "stuetz_t": np.asarray(k["stuetz_t"]),
            "stuetz_y": np.asarray(k["stuetz_y"])}


def paket_bauen(serien: Optional[Mapping[int, pd.DataFrame]] = None,
                termine: Optional[Mapping[int, Sequence]] = None,
                temp: Optional[pd.Series] = None,
                kennzahlen: Optional[dict] = None,
                version: Optional[str] = None, wurzel: Path = mp.MODELS,
                aktuell: bool = True) -> mp.Paket:
    """Paket ``normalmodell``: Referenz und Kennlinien je Station und Kanal."""
    if serien is None or termine is None or temp is None:
        e = eingaben()
        serien = e["serien"] if serien is None else serien
        termine = e["termine"] if termine is None else termine
        temp = e["temp"] if temp is None else temp
    tage = tm.alle_tageswerte(serien, temp)
    mt = tm.modelltage(tage)
    ref = tm.referenz(mt, termine)
    mod, modtab = tm.modelle(mt, ref)
    kennlinien = [{"zaehler": int(m), "kanal": k,
                   "kennlinie": _kennlinie_json(v["kennlinie"]),
                   "s": float(v["s"]), "s_eff": float(v["s_eff"])}
                  for (m, k), v in mod.items()]
    ok = ref[ref["status"] == "ok"]
    kenn = {"stationen": int(len(ref)), "ueberwacht": int(len(ok))}
    kenn.update(kennzahlen or {})
    dateien = {
        "referenz.csv": lambda p: ref.to_csv(p, index_label="zaehler"),
        "kennlinien.json": lambda p: p.write_text(
            json.dumps(kennlinien, indent=1), encoding="utf-8"),
        "modelltabelle.csv": lambda p: modtab.to_csv(p, index=False),
    }
    return mp.schreibe_paket(
        PAKETNAME, "Alarm (Wächter)", dateien,
        parameter={"kanaele": list(tm.KANAELE), "form_je_kanal": tm.FORM_JE_KANAL,
                   "heizgrenze_c": tm.T_HEIZGRENZE, "cusum_k": tm.CUSUM_K,
                   "cusum_h": tm.CUSUM_H, "cusum_max": tm.CUSUM_MAX,
                   "phi_max": tm.PHI_MAX, "ref_kalendertage": tm.REF_KALENDERTAGE,
                   "abstand_begehung_tage": tm.ABSTAND_BEGEHUNG,
                   "min_ref_tage": tm.MIN_REF_TAGE},
        kennzahlen=kenn, datenstand=mt["datum"].max(),
        lernzeitraum="erstes Jahr je Station, spätestens 14 Tage vor der ersten Begehung",
        beschreibung=("Kennlinie je Station und Kanal gegen die Tagesmitteltemperatur "
                      "(Abkühlung kWh/m³, Tagesvolumen), CUSUM auf den Abweichungen"),
        quelle="notebooks/17_normalverhaltensmodell.ipynb, src/tagesmonitor.py",
        version=version, wurzel=wurzel, aktuell=aktuell)


def lade(version: Optional[str] = None, wurzel: Path = mp.MODELS) -> dict:
    paket = mp.lade_paket(PAKETNAME, version, wurzel)
    ref = paket.tabelle("referenz.csv", index_col="zaehler",
                        parse_dates=["ref_start", "ref_ende"])
    ref.index.name = "meter"
    mod = {(int(e["zaehler"]), e["kanal"]): {
        "kennlinie": _kennlinie_lesen(e["kennlinie"]), "s": e["s"],
        "s_eff": e["s_eff"]} for e in paket.json("kennlinien.json")}
    return {"paket": paket, "referenz": ref, "modelle": mod,
            "parameter": paket.parameter}


def anwenden(geladen: dict, serien: Mapping[int, pd.DataFrame],
             temp: pd.Series) -> dict:
    """Gespeicherte Kennlinien auf die Tageswerte anwenden.

    Rückgabe wie `tagesmonitor.monitor`: ``verlauf`` (je Station, Kanal und
    Heiztag nach der Referenz: Wert, Erwartung, Residuum, z, CUSUM-Konten)
    und ``alarme``. Dazu ``status`` je Zähler: überwacht, noch nicht
    eingelernt (nicht im Paket) oder der Grund aus der Referenz.
    """
    tage = tm.alle_tageswerte(serien, temp)
    mt = tm.modelltage(tage)
    ref = geladen["referenz"]
    mt_bekannt = mt[mt["meter"].isin(ref.index)]
    verlauf, alarme = tm.monitor(mt_bekannt, ref, geladen["modelle"])
    status = pd.Series({int(m): (ref.at[m, "status"] if m in ref.index
                                 else "noch nicht eingelernt")
                        for m in sorted(set(mt["meter"]) | set(ref.index))},
                       name="status")
    status = status.replace({"ok": "überwacht"})
    return {"verlauf": verlauf, "alarme": alarme, "status": status,
            "tage": tage}


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bauen", action="store_true")
    args = p.parse_args(argv)
    if args.bauen:
        paket = paket_bauen()
        print(f"Paket {paket.name} {paket.version} in {paket.ordner}: "
              f"{paket.meta['kennzahlen']}")


if __name__ == "__main__":
    main()
