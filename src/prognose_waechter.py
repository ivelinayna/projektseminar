"""Prognose-LSTM als Wächter im Betrieb (gelernt in Notebook 21).

Notebook 21 lernt das Netz und prüft es. Was nach dem Lernen zum Anwenden
gebraucht wird, lag dort nur im Notebook-Speicher: die Skalierung, die
normale Schwankung je Station, der Faktor je Jahreszeit und die Schwelle.
Dieses Modul

- rechnet diese Teile genau wie Notebook 21 nach und legt sie mit den
  Gewichten als Modellpaket ab (`paket_bauen`),
- wendet ein Paket auf beliebige Stundenwerte an, ohne neu zu lernen
  (`anwenden`),
- prüft, dass das Paket dieselben z-Werte, Warnungen und Alarme liefert
  wie Notebook 21 (`gegenprobe`).

Zwei Alarmregeln stehen auf denselben z-Werten zur Wahl:

- ``schwelle``: |z| ≥ Schwelle an zwei Tagen hintereinander, ein Alarm je
  Veränderung (mindestens ``ruhe`` Tage ohne Warnung dazwischen). Das ist
  die Regel aus Notebook 21.
- ``cusum``: zweiseitiger CUSUM wie im Normalverhaltensmodell (Notebook 17,
  `tagesmonitor.cusum`), je Kanal, mit der Streuung für die Ähnlichkeit
  aufeinanderfolgender Tage vergrößert. Notebook 23 hat gezeigt, dass die
  Alarmregel und nicht das Netz den Unterschied zum Normalverhaltensmodell
  macht; diese Regel macht das prüfbar (Notebook 32).

Als Vergleich ohne Lernen gibt es dieselbe Kette mit ``erwartung =
"wochenmittel"``: Jede Stunde des Zieltags ist der Mittelwert dieser Stunde
über die sieben Vortage (der Vergleich „Mittel der Woche“ aus Notebook 21).

    python -m src.prognose_waechter --bauen      # Paket aus Notebook 21 bauen
    python -m src.prognose_waechter --gegenprobe # Paket gegen NB 21 prüfen
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import modellpaket as mp
from . import tagesmonitor as tm

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
NB_MODELLE = ROOT / "notebooks" / "models"
PAKETNAME = "prognose_lstm"

#Festlegungen aus Notebook 21, Abschnitt 1
STICHTAG = pd.Timestamp("2024-09-01")
LERNEN_BIS = pd.Timestamp("2024-06-01")
VORGESCHICHTE = 7
HEIZGRENZE_C = 15.0
SEED = 0
KANAELE = ["ruecklauf", "durchfluss", "vorlauf", "aussen"]
RL, FL, VL, AT = range(4)
NACHT_STUNDEN = 6                 # 0 bis 5 Uhr
VERSTECKT = 64
#Kalibrierung (Notebook 21, Abschnitt 6)
MIN_VAL_TAGE = 10
MIN_RL_MAD = 0.5
MIN_FL_MAD = 5.0
MIN_FAKTOR = 0.5
#Warnregel (Abschnitt 7 und 8): z ≥ 4 an zwei Tagen, ein Alarm je Veränderung
SCHWELLE = 4.0
RUHE = 7
#CUSUM wie im Normalverhaltensmodell
CUSUM_K = tm.CUSUM_K
CUSUM_H = tm.CUSUM_H
PHI_MAX = tm.PHI_MAX
MIN_PHI_PAARE = 8
Z_SPALTEN = {"ruecklauf": "z_rl", "nachtdurchfluss": "z_fluss"}

TAGES_SPALTEN = ["zaehler", "tag", "heiztag", "rl_gemessen", "rl_erwartet",
                 "fluss_nacht_gemessen", "fluss_nacht_erwartet", "res_rl",
                 "res_fluss_nacht"]


def _torch():
    import torch
    return torch


def netz(versteckt: int = VERSTECKT):
    """Encoder–Decoder aus Notebook 21, Abschnitt 3 (gleiche Namen der Gewichte)."""
    torch = _torch()
    nn = torch.nn

    class Prognose(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = nn.LSTM(len(KANAELE), versteckt, batch_first=True)
            self.decoder = nn.LSTM(2, versteckt, batch_first=True)
            self.ausgang = nn.Linear(versteckt, 2)

        def forward(self, vergangenheit, zieltag):
            _, zustand = self.encoder(vergangenheit)
            y, _ = self.decoder(zieltag, zustand)
            return self.ausgang(y)

    return Prognose()


# --- Daten ------------------------------------------------------------------

def stundenwerte(meter_dir: Path = PROCESSED / "real_meters",
                 wetter: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Stundenwerte wie `modell_stunden.parquet` (Notebook 18, Zelle 6 und 15).

    Liest die Zählerreihen aus Notebook 00 und hängt die DWD-Außentemperatur
    an. Für den Betrieb, wenn neue Exporte da sind und NB 18 nicht neu
    laufen soll.
    """
    from .weather import load_outdoor_temperature

    spalten = {"Timestamp": "timestamp", "Flow temperature (°C)": "vorlauf",
               "Return temperature (°C)": "ruecklauf",
               "Temperature difference (°C)": "spreizung",
               "Volume flow (l/h)": "durchfluss", "Power (kW)": "leistung"}
    teile = []
    for pfad in sorted(Path(meter_dir).glob("*.csv")):
        df = pd.read_csv(pfad, usecols=list(spalten), parse_dates=["Timestamp"])
        df = df.rename(columns=spalten)
        df.insert(0, "zaehler", int(pfad.stem))
        teile.append(df)
    if not teile:
        raise FileNotFoundError(f"keine Zählerreihen in {meter_dir}, erst NB 00")
    stunden = pd.concat(teile, ignore_index=True)
    if wetter is None:
        wetter = load_outdoor_temperature(stunden["timestamp"].min(),
                                          stunden["timestamp"].max())
    wetter = wetter.rename(columns={"t_out": "aussen"})[["timestamp", "aussen"]]
    return stunden.merge(wetter, on="timestamp", how="left")


def tagesfeld(stunden: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
    """Vollständige Tage als Feld Tage × 24 × 4 (Notebook 21, Abschnitt 2).

    Ein Tag zählt nur mit 24 Stunden, in denen alle vier Größen gemessen
    sind. ``tage`` trägt je Eintrag Zähler, Datum, Heiztag und ob die sieben
    Vortage lückenlos davor liegen.
    """
    s = stunden.dropna(subset=KANAELE).copy()
    s["tag"] = s["timestamp"].dt.floor("D")
    voll = s.groupby(["zaehler", "tag"])["timestamp"].transform("size") == 24
    s = s[voll].sort_values(["zaehler", "timestamp"])
    werte = s[KANAELE].to_numpy(dtype=np.float32).reshape(-1, 24, len(KANAELE))
    tage = s[["zaehler", "tag"]].iloc[::24].reset_index(drop=True)
    mit = pd.Series(True, index=tage.index)
    for k in range(1, VORGESCHICHTE + 1):
        mit &= ((tage["zaehler"].shift(k) == tage["zaehler"])
                & (tage["tag"].shift(k) == tage["tag"] - pd.Timedelta(days=k)))
    tage["mit_vorgeschichte"] = mit.to_numpy()
    tage["heiztag"] = werte[:, :, AT].mean(axis=1) < HEIZGRENZE_C
    return werte, tage


def abschnitte(tage: pd.DataFrame, erste_begehung: pd.Series,
               lernen_bis: pd.Timestamp = LERNEN_BIS,
               stichtag: pd.Timestamp = STICHTAG,
               seed: int = SEED) -> Tuple[pd.Series, np.ndarray]:
    """Training, Validierung, Test und „nach der Begehung“ wie Notebook 21.

    ``erste_begehung`` ist je begangenem Zähler das Datum der ersten
    Begehung (NaT erlaubt). Rückgabe: Abschnitt je Tag und die gezogenen
    Validierungswochen.
    """
    grenze = tage["zaehler"].map(erste_begehung.clip(upper=stichtag)).fillna(stichtag)
    woche = tage["tag"].dt.to_period("W").astype(str)
    lernwochen = woche[tage["tag"] < lernen_bis].unique()
    val_wochen = np.random.default_rng(seed).choice(
        lernwochen, size=int(0.1 * len(lernwochen)), replace=False)
    abschnitt = np.select(
        [tage["tag"] >= grenze, tage["tag"] >= lernen_bis, woche.isin(val_wochen)],
        ["nach der Begehung", "Test (Sommer 2024)", "Validierung"], "Training")
    return pd.Series(abschnitt, index=tage.index), val_wochen


def skalierung_lernen(werte: np.ndarray, tage: pd.DataFrame,
                      lernzeit: np.ndarray) -> dict:
    """Skalen nur aus den Lerntagen: Durchfluss je Zähler, Temperaturen für alle."""
    fluss = pd.DataFrame({"zaehler": np.repeat(tage["zaehler"].to_numpy(), 24),
                          "durchfluss": werte[:, :, FL].ravel()})
    fl_teiler = (fluss[np.repeat(lernzeit, 24)].groupby("zaehler")["durchfluss"]
                 .quantile(0.95).clip(lower=1.0))
    mittel = {k: float(werte[lernzeit, :, i].mean())
              for i, k in enumerate(KANAELE) if k != "durchfluss"}
    streuung = {k: float(werte[lernzeit, :, i].std())
                for i, k in enumerate(KANAELE) if k != "durchfluss"}
    return {"fl_teiler": fl_teiler, "mittel": mittel, "streuung": streuung}


def skalieren(werte: np.ndarray, tage: pd.DataFrame, skal: dict) -> np.ndarray:
    x = werte.copy()
    for i, k in enumerate(KANAELE):
        if k == "durchfluss":
            teiler = tage["zaehler"].map(skal["fl_teiler"]).fillna(1.0)
            x[:, :, i] /= teiler.to_numpy(dtype=np.float32)[:, None]
        else:
            x[:, :, i] = ((x[:, :, i] - np.float32(skal["mittel"][k]))
                          / np.float32(skal["streuung"][k]))
    return x


def eingaenge(x: np.ndarray, idx: np.ndarray):
    """Vergangenheit (7 × 24 × 4), Zieltag bekannt (24 × 2), Ziel (24 × 2)."""
    torch = _torch()
    verg = x[idx[:, None] + np.arange(-VORGESCHICHTE, 0)].reshape(
        len(idx), VORGESCHICHTE * 24, len(KANAELE))
    return (torch.tensor(verg), torch.tensor(x[idx][:, :, [AT, VL]]),
            torch.tensor(x[idx][:, :, [RL, FL]]))


def _geraet(geraet: Optional[str] = None) -> str:
    if geraet:
        return geraet
    return "cuda" if _torch().cuda.is_available() else "cpu"


def vorhersagen(modell, x: np.ndarray, tage: pd.DataFrame, idx: np.ndarray,
                skal: dict, geraet: Optional[str] = None,
                stapel: int = 4096) -> Tuple[np.ndarray, np.ndarray]:
    """Rücklauf [°C] und Durchfluss [l/h] je Stunde der Zieltage."""
    torch = _torch()
    geraet = _geraet(geraet)
    modell = modell.to(geraet).eval()
    teile = []
    with torch.no_grad():
        for start in range(0, len(idx), stapel):
            v, z, _ = eingaenge(x, idx[start:start + stapel])
            teile.append(modell(v.to(geraet), z.to(geraet)).cpu().numpy())
    p = np.concatenate(teile) if teile else np.zeros((0, 24, 2), np.float32)
    rl = p[:, :, 0] * np.float32(skal["streuung"]["ruecklauf"]) + np.float32(skal["mittel"]["ruecklauf"])
    teiler = tage.loc[idx, "zaehler"].map(skal["fl_teiler"]).to_numpy()
    fl = p[:, :, 1] * teiler[:, None]
    return rl, fl


def wochenmittel(werte: np.ndarray, idx: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Vergleich ohne Lernen: jede Stunde = Mittel dieser Stunde über 7 Vortage."""
    w = werte[idx[:, None] + np.arange(-VORGESCHICHTE, 0)].mean(axis=1)
    return w[:, :, RL], w[:, :, FL]


def abweichungen(werte: np.ndarray, tage: pd.DataFrame, idx: np.ndarray,
                 rl: np.ndarray, fl: np.ndarray) -> pd.DataFrame:
    """Tagesmittel gemessen und erwartet, Abweichung gemessen minus erwartet."""
    gem_rl = werte[idx][:, :, RL]
    gem_fl = werte[idx][:, :NACHT_STUNDEN, FL]
    return pd.DataFrame({
        "zaehler": tage.loc[idx, "zaehler"].to_numpy(),
        "tag": tage.loc[idx, "tag"].to_numpy(),
        "heiztag": tage.loc[idx, "heiztag"].to_numpy(),
        "rl_gemessen": gem_rl.mean(axis=1),
        "rl_erwartet": rl.mean(axis=1),
        "fluss_nacht_gemessen": gem_fl.mean(axis=1),
        "fluss_nacht_erwartet": fl[:, :NACHT_STUNDEN].mean(axis=1),
        "res_rl": (gem_rl - rl).mean(axis=1),
        "res_fluss_nacht": (gem_fl - fl[:, :NACHT_STUNDEN]).mean(axis=1),
    }, index=idx)


# --- Kalibrierung und Alarmregeln ---------------------------------------------

def mad(s: pd.Series) -> float:
    return 1.4826 * (s - s.median()).abs().median()


def z_werte(abw: pd.DataFrame, kal: pd.DataFrame,
            faktor: Optional[pd.DataFrame]) -> pd.DataFrame:
    k = kal.reindex(abw["zaehler"])
    abw = abw.copy()
    abw["z_rl"] = ((abw["res_rl"].to_numpy() - k["rl_mitte"].to_numpy())
                   / k["rl_mad"].to_numpy())
    abw["z_fluss"] = ((abw["res_fluss_nacht"].to_numpy() - k["fl_mitte"].to_numpy())
                      / k["fl_mad"].to_numpy())
    if faktor is not None:
        for spalte in ("z_rl", "z_fluss"):
            abw[spalte] = abw[spalte] / abw["heiztag"].map(faktor[spalte]).to_numpy()
    return abw


def _phi(g: pd.DataFrame, spalte: str) -> Tuple[float, int]:
    """Korrelation eines z-Werts mit dem des Vortags, nur direkte Folgetage."""
    g = g.sort_values("tag")
    folge = g["tag"].diff().eq(pd.Timedelta(days=1)).to_numpy()
    z = g[spalte].to_numpy(dtype=float)
    a, b = z[1:][folge[1:]], z[:-1][folge[1:]]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan, int(ok.sum())
    return float(np.corrcoef(a[ok], b[ok])[0, 1]), int(ok.sum())


def kalibrieren(val: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normale Lage und Schwankung je Station, Faktor je Jahreszeit.

    Genau wie Notebook 21 (`kalibrieren`), aus Tagen, die das Netz nicht
    zum Lernen benutzt hat. Zusätzlich je Station die Ähnlichkeit
    aufeinanderfolgender Tage (``phi_rl``, ``phi_fluss``) für die
    CUSUM-Regel; bei zu wenigen Paaren gilt der Median der Stationen.
    """
    kal = val.groupby("zaehler").agg(
        tage=("res_rl", "size"), rl_mitte=("res_rl", "median"),
        rl_mad=("res_rl", mad), fl_mitte=("res_fluss_nacht", "median"),
        fl_mad=("res_fluss_nacht", mad))
    kal = kal[kal["tage"] >= MIN_VAL_TAGE].copy()
    kal["rl_mad"] = kal["rl_mad"].clip(lower=MIN_RL_MAD)
    kal["fl_mad"] = kal["fl_mad"].clip(lower=MIN_FL_MAD)
    roh = z_werte(val, kal, None)
    faktor = pd.DataFrame({k: roh.groupby("heiztag")[k].apply(mad)
                           for k in ("z_rl", "z_fluss")}).clip(lower=MIN_FAKTOR)
    z = z_werte(val[val["zaehler"].isin(kal.index)], kal, faktor)
    for spalte, name in (("z_rl", "phi_rl"), ("z_fluss", "phi_fluss")):
        werte = {m: _phi(g, spalte) for m, g in z.groupby("zaehler")}
        phi = pd.Series({m: p if n >= MIN_PHI_PAARE else np.nan
                         for m, (p, n) in werte.items()})
        phi = phi.reindex(kal.index)
        kal[name] = phi.fillna(phi.median()).clip(0.0, PHI_MAX)
    return kal, faktor


def warnungen(abw: pd.DataFrame, schwelle: float) -> pd.Series:
    """Auffällig an zwei direkt aufeinanderfolgenden Tagen (Notebook 21)."""
    auff = (abw["z_rl"].abs() >= schwelle) | (abw["z_fluss"].abs() >= schwelle)
    vortag_auff = auff.groupby(abw["zaehler"]).shift(1, fill_value=False)
    vortag_direkt = abw.groupby("zaehler")["tag"].diff().eq(pd.Timedelta(days=1))
    return auff & vortag_auff & vortag_direkt


def alarme_aus_warnungen(abw: pd.DataFrame, warnung: pd.Series,
                         ruhe: int = RUHE) -> pd.Series:
    """Erster Warntag nach mindestens ``ruhe`` Tagen ohne Warnung."""
    vorige = (abw["tag"].where(warnung).groupby(abw["zaehler"])
              .transform(lambda s: s.ffill().shift(1)))
    abstand = (abw["tag"] - vorige).dt.days
    return warnung & (abstand.isna() | (abstand > ruhe))


def cusum_alarme(abw: pd.DataFrame, kal: pd.DataFrame, k: float = CUSUM_K,
                 h: float = CUSUM_H) -> pd.DataFrame:
    """CUSUM je Station und Kanal auf den z-Werten des Wächters.

    Die z-Werte werden wie im Normalverhaltensmodell für die Ähnlichkeit
    aufeinanderfolgender Tage durch √((1 + φ) / (1 − φ)) geteilt. Rückgabe:
    je Tag die beiden Konten je Kanal und je Alarm eine Zeile in der Spalte
    ``cusum_alarm`` (Kanal und Richtung in ``cusum_kanal``). Der Deckel
    der Konten liegt bei mindestens 2 h, damit auch h über 5 erreichbar ist.
    """
    aus = abw[["zaehler", "tag"]].copy()
    for name in Z_SPALTEN:
        aus[f"s_plus_{name}"] = np.nan
        aus[f"s_minus_{name}"] = np.nan
    aus["cusum_alarm"] = False
    aus["cusum_kanal"] = ""
    for meter, g in abw.groupby("zaehler", sort=False):
        if meter not in kal.index:
            continue
        g = g.sort_values("tag")
        for name, spalte in Z_SPALTEN.items():
            phi = float(kal.at[meter, "phi_rl" if spalte == "z_rl" else "phi_fluss"])
            z = g[spalte].to_numpy(dtype=float) / np.sqrt((1 + phi) / (1 - phi))
            gueltig = np.isfinite(z)
            sp, sm, al = tm.cusum(z[gueltig], k=k, h=h,
                                  deckel=max(tm.CUSUM_MAX, 2 * h))
            zeilen = g.index[gueltig]
            aus.loc[zeilen, f"s_plus_{name}"] = sp
            aus.loc[zeilen, f"s_minus_{name}"] = sm
            for i, richtung, _ in al:
                zeile = zeilen[i]
                aus.loc[zeile, "cusum_alarm"] = True
                text = f"{name} {'höher' if richtung > 0 else 'niedriger'}"
                alt = aus.at[zeile, "cusum_kanal"]
                aus.at[zeile, "cusum_kanal"] = f"{alt}, {text}" if alt else text
    return aus


# --- Paket bauen und anwenden -----------------------------------------------

def _lade_gewichte(pfad: Path, geraet: Optional[str] = None):
    torch = _torch()
    modell = netz()
    gespeichert = torch.load(pfad, map_location=_geraet(geraet))
    modell.load_state_dict(gespeichert["gewichte"])
    return modell.eval(), gespeichert


def nachrechnen(stunden: pd.DataFrame, labels: pd.DataFrame,
                gewichte: Path = NB_MODELLE / "prognose_lstm_begangen.pt",
                geraet: Optional[str] = None) -> dict:
    """Notebook 21 bis zur Kalibrierung nachrechnen, mit gespeicherten Gewichten."""
    werte, tage = tagesfeld(stunden)
    abschnitt, val_wochen = abschnitte(tage, labels["erste_begehung"])
    tage["abschnitt"] = abschnitt
    tage["begangen"] = tage["zaehler"].isin(labels.index)
    lernzeit = (abschnitt == "Training").to_numpy()
    skal = skalierung_lernen(werte, tage, lernzeit)
    ziel = np.flatnonzero(tage["mit_vorgeschichte"].to_numpy())
    ziel = ziel[tage.loc[ziel, "zaehler"].isin(skal["fl_teiler"].index).to_numpy()]
    modell, gespeichert = _lade_gewichte(gewichte, geraet)
    x = skalieren(werte, tage, skal)
    rl, fl = vorhersagen(modell, x, tage, ziel, skal, geraet)
    abw = abweichungen(werte, tage, ziel, rl, fl)
    abw["abschnitt"] = tage.loc[ziel, "abschnitt"].to_numpy()
    kal, faktor = kalibrieren(abw[abw["abschnitt"] == "Validierung"])
    verlauf = pd.DataFrame(gespeichert.get("verlauf", {}))
    return {"werte": werte, "tage": tage, "skalierung": skal, "modell": modell,
            "abweichungen": abw, "kalibrierung": kal, "faktor": faktor,
            "val_wochen": val_wochen, "verlauf": verlauf,
            "lernzaehler": sorted(labels.index)}


def paket_bauen(stunden: Optional[pd.DataFrame] = None,
                labels: Optional[pd.DataFrame] = None,
                gewichte: Path = NB_MODELLE / "prognose_lstm_begangen.pt",
                schwelle: float = SCHWELLE, ruhe: int = RUHE,
                alarmregel: str = "schwelle", cusum_h: float = CUSUM_H,
                kennzahlen: Optional[dict] = None, version: Optional[str] = None,
                wurzel: Path = mp.MODELS, aktuell: bool = True) -> mp.Paket:
    """Modellpaket ``prognose_lstm`` aus den Gewichten von Notebook 21.

    Ohne Argumente liest es `modell_stunden.parquet` und `modell_labels.csv`
    (Notebook 18). Die Gewichte müssen zu diesen Daten passen: Nach einer
    Änderung von NB 00 erst NB 21 neu trainieren (docs/pipeline.md).
    """
    if alarmregel not in ("schwelle", "cusum"):
        raise ValueError("alarmregel muss 'schwelle' oder 'cusum' sein")
    torch = _torch()
    if stunden is None:
        stunden = pd.read_parquet(PROCESSED / "modell_stunden.parquet")
    if labels is None:
        labels = pd.read_csv(PROCESSED / "modell_labels.csv", index_col="zaehler",
                             parse_dates=["erste_begehung"])
    r = nachrechnen(stunden, labels, gewichte)
    skal = r["skalierung"]
    verlauf = r["verlauf"]
    lern = r["tage"][r["tage"]["abschnitt"] == "Training"]
    kenn = {"kalibrierte_stationen": len(r["kalibrierung"]),
            "bester_validierungsfehler": (float(verlauf["validierung"].min())
                                          if len(verlauf) else None),
            "runden": int(len(verlauf))}
    kenn.update(kennzahlen or {})
    dateien = {
        "gewichte.pt": lambda p: torch.save(
            {k: v.cpu() for k, v in r["modell"].state_dict().items()}, p),
        "durchfluss_teiler.csv": lambda p: skal["fl_teiler"].rename("teiler_lph")
        .to_csv(p, index_label="zaehler"),
        "skalierung.json": lambda p: p.write_text(pd.Series({
            "mittel": skal["mittel"], "streuung": skal["streuung"]}).to_json(
                indent=2), encoding="utf-8"),
        "kalibrierung.csv": lambda p: r["kalibrierung"].to_csv(p),
        "faktor_jahreszeit.csv": lambda p: r["faktor"].rename(
            index={True: "heiztag", False: "warmer_tag"}).to_csv(
                p, index_label="tagesart"),
        "lernkurve.csv": lambda p: verlauf.to_csv(p, index=False),
    }
    return mp.schreibe_paket(
        PAKETNAME, "Alarm (Wächter)", dateien,
        parameter={"kanaele": KANAELE, "vorgeschichte_tage": VORGESCHICHTE,
                   "versteckt": VERSTECKT, "nacht_stunden": NACHT_STUNDEN,
                   "heizgrenze_c": HEIZGRENZE_C, "schwelle": schwelle,
                   "ruhe_tage": ruhe, "cusum_k": CUSUM_K, "cusum_h": cusum_h,
                   "alarmregel": alarmregel, "seed": SEED,
                   "lernen_bis": LERNEN_BIS, "stichtag": STICHTAG,
                   "validierungswochen": sorted(map(str, r["val_wochen"])),
                   "lernzaehler": r["lernzaehler"]},
        kennzahlen=kenn,
        datenstand=stunden["timestamp"].max(),
        lernzeitraum=(lern["tag"].min(), lern["tag"].max()),
        beschreibung=("Encoder–Decoder-LSTM: sagt aus 7 Vortagen, Wetter und "
                      "Vorlauf Rücklauf und Durchfluss des Tages voraus; "
                      "z-Werte je Station, Alarm nach Regel"),
        quelle="notebooks/21_prognose_lstm_waechter.ipynb", version=version,
        wurzel=wurzel, aktuell=aktuell)


def lade(version: Optional[str] = None, wurzel: Path = mp.MODELS,
         geraet: Optional[str] = None) -> dict:
    """Paket laden: Netz, Skalierung, Kalibrierung, Parameter."""
    torch = _torch()
    paket = mp.lade_paket(PAKETNAME, version, wurzel)
    par = paket.parameter
    modell = netz(par.get("versteckt", VERSTECKT))
    modell.load_state_dict(torch.load(paket.pfad("gewichte.pt"),
                                      map_location=_geraet(geraet)))
    teiler = paket.tabelle("durchfluss_teiler.csv", index_col="zaehler")["teiler_lph"]
    sk = paket.json("skalierung.json")
    kal = paket.tabelle("kalibrierung.csv", index_col="zaehler")
    faktor = paket.tabelle("faktor_jahreszeit.csv", index_col="tagesart")
    faktor.index = faktor.index.map({"heiztag": True, "warmer_tag": False})
    return {"paket": paket, "modell": modell.eval(),
            "skalierung": {"fl_teiler": teiler, "mittel": sk["mittel"],
                           "streuung": sk["streuung"]},
            "kalibrierung": kal, "faktor": faktor, "parameter": par}


def anwenden(geladen: dict, stunden: pd.DataFrame,
             erwartung: str = "lstm", ab: Optional[pd.Timestamp] = None,
             geraet: Optional[str] = None,
             kalibrierung: Optional[pd.DataFrame] = None,
             faktor: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Wächter auf Stundenwerte anwenden, ohne neu zu lernen.

    Rückgabe: eine Zeile je Zähler und vorhergesagtem Tag mit gemessenen und
    erwarteten Tagesmitteln, z-Werten, Warnung, Alarm nach der
    Schwellenregel (``alarm_schwelle``), CUSUM-Konten und -Alarmen
    (``alarm_cusum``) und ``alarm`` nach der Regel im Paket. Zähler ohne
    Skala im Paket werden nicht vorhergesagt, Zähler ohne Kalibrierung
    bekommen keine z-Werte (``status``).

    ``erwartung="wochenmittel"`` ersetzt das Netz durch das Mittel der
    sieben Vortage (Vergleich ohne Lernen). Dann sollten ``kalibrierung``
    und ``faktor`` aus denselben Tagen mit dieser Erwartung kommen
    (`kalibrieren`), sonst passen die Schwankungen nicht.
    """
    par = geladen["parameter"]
    skal = geladen["skalierung"]
    kal = geladen["kalibrierung"] if kalibrierung is None else kalibrierung
    fak = geladen["faktor"] if faktor is None else faktor
    werte, tage = tagesfeld(stunden)
    ziel = np.flatnonzero(tage["mit_vorgeschichte"].to_numpy())
    bekannt = tage.loc[ziel, "zaehler"].isin(skal["fl_teiler"].index).to_numpy()
    ziel = ziel[bekannt]
    if ab is not None:
        ziel = ziel[(tage.loc[ziel, "tag"] >= pd.Timestamp(ab)).to_numpy()]
    if erwartung == "lstm":
        x = skalieren(werte, tage, skal)
        rl, fl = vorhersagen(geladen["modell"], x, tage, ziel, skal, geraet)
    elif erwartung == "wochenmittel":
        rl, fl = wochenmittel(werte, ziel)
    else:
        raise ValueError("erwartung muss 'lstm' oder 'wochenmittel' sein")
    abw = abweichungen(werte, tage, ziel, rl, fl)
    abw = z_werte(abw, kal, fak)
    abw["status"] = np.where(abw["zaehler"].isin(kal.index), "überwacht",
                             "nicht kalibriert")
    abw = abw.sort_values(["zaehler", "tag"])
    schwelle = float(par.get("schwelle", SCHWELLE))
    abw["warnung"] = warnungen(abw, schwelle)
    abw["alarm_schwelle"] = alarme_aus_warnungen(abw, abw["warnung"],
                                                 int(par.get("ruhe_tage", RUHE)))
    cs = cusum_alarme(abw, kal, float(par.get("cusum_k", CUSUM_K)),
                      float(par.get("cusum_h", CUSUM_H)))
    abw = abw.join(cs.drop(columns=["zaehler", "tag"]).rename(
        columns={"cusum_alarm": "alarm_cusum"}))
    regel = par.get("alarmregel", "schwelle")
    abw["alarm"] = abw["alarm_cusum"] if regel == "cusum" else abw["alarm_schwelle"]
    return abw.reset_index(drop=True)


def gegenprobe(tab: pd.DataFrame,
               nb21: Path = PROCESSED / "prognose_tage.csv") -> dict:
    """Paket gegen die Ausgabe von Notebook 21 halten.

    Vergleicht je Zähler und Tag z-Werte, Warnung und Alarm. Kleine
    Abweichungen bei den z-Werten kommen von Grafikkarte gegen CPU.
    """
    alt = pd.read_csv(nb21, parse_dates=["tag"])
    m = alt.merge(tab, on=["zaehler", "tag"], suffixes=("_nb21", "_paket"))
    return {
        "zeilen_nb21": len(alt), "zeilen_paket": int(tab["status"].eq("überwacht").sum()),
        "gemeinsam": len(m),
        "max_abw_z_rl": float((m["z_rl_nb21"] - m["z_rl_paket"]).abs().max()),
        "max_abw_z_fluss": float((m["z_fluss_nb21"] - m["z_fluss_paket"]).abs().max()),
        "warnung_gleich": float((m["warnung_nb21"] == m["warnung_paket"]).mean()),
        "alarm_gleich": float((m["alarm_nb21"] == m["alarm_schwelle"]).mean()),
        "alarme_nb21": int(m["alarm_nb21"].sum()),
        "alarme_paket": int(m["alarm_schwelle"].sum()),
    }


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bauen", action="store_true", help="Paket aus NB 21 bauen")
    p.add_argument("--gegenprobe", action="store_true",
                   help="Betriebspaket gegen prognose_tage.csv prüfen")
    p.add_argument("--alarmregel", choices=("schwelle", "cusum"), default="schwelle")
    p.add_argument("--cusum-h", type=float, default=CUSUM_H)
    args = p.parse_args(argv)
    if args.bauen:
        paket = paket_bauen(alarmregel=args.alarmregel, cusum_h=args.cusum_h)
        print(f"Paket {paket.name} {paket.version} in {paket.ordner}")
    if args.gegenprobe:
        geladen = lade()
        stunden = pd.read_parquet(PROCESSED / "modell_stunden.parquet")
        erg = gegenprobe(anwenden(geladen, stunden))
        for k, v in erg.items():
            print(f"{k:22s} {v}")


if __name__ == "__main__":
    main()
