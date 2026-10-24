"""Fehler erkennen und unterteilen nach Folie 5, als Modellpaket für den Betrieb.

Die Kette stammt aus den Notebooks 18 bis 22 (Dominik):

1. **Kennzahlen** je Zähler aus einem Winter und dem folgenden Sommer
   (Notebook 18): Sommernächte, Rücklauf, Spreizung, Regelverhalten,
   Auslastung.
2. **LSTM-Embedding** (Notebook 20): ein Netz, das aus einem Tag den nächsten
   vorhersagt, übersetzt jeden Tag in acht Zahlen; je Zähler und Zeitraum
   der Mittelwert.
3. **Ventil-Modell** (Notebook 22): logistische Regression auf Kennzahlen
   und Embedding, Grenze fest 0,5 (AUC 0,89 aus der Kreuzvalidierung).
4. **Optimum oder schlechter** (Notebook 19): K-Means mit k = 2 auf drei
   Regelungs-Kennzahlen, die Gruppe mit dem kälteren Rücklauf ist das
   Optimum.
5. **Klasse nach Folie 5** in dieser Reihenfolge: Regelventil tauschen
   (Reparatur), sonst Regelparameter optimieren (Regelungsoptimierung),
   sonst kein Handlungsbedarf. Dazu Hinweise auf Dämmung und auf einen zu
   großen Anschluss (Kapazitätsanpassung).

In den Notebooks lag das gelernte Modell nur im Speicher; gespeichert
wurde nur die Ergebnistabelle `fehlerklassen_je_hast.csv`. Hier wird alles,
was zum erneuten Anwenden gebraucht wird, als Paket ``fehlerklassen``
abgelegt, und `saison_bewerten` rechnet die Klassen für eine beliebige
Heizperiode neu, z. B. für Winter 24/25 nach den Begehungen.

    python -m src.fehlerklassen --bauen       # Paket bauen und gegenprüfen
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import modellpaket as mp

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
NB_MODELLE = ROOT / "notebooks" / "models"
PAKETNAME = "fehlerklassen"
SEED = 0
STICHTAG = pd.Timestamp("2024-09-01")

#Zeiträume der Notebooks 18 und 20 (vor den Begehungen)
WINTER = ("2023-10-01", "2024-04-01")
SOMMER = ("2024-06-01", "2024-09-01")

KENNZAHLEN = ["sommer_nachtfluss_lph", "sommer_durchlauf_anteil",
              "sommer_nacht_spreizung_k", "winter_ruecklauf_bei_0c",
              "winter_spreizung_last_k", "winter_ruecklauf_p90", "winter_fluss_cv",
              "winter_nacht_tag_fluss", "sommerlast_anteil", "anteil_volumenstrom",
              "streubreite_betriebspunkte", "ruecklauf_lastgewichtet", "auslastung"]
EMB_WINTER = [f"lstm_w2324_z{i}" for i in range(8)]
EMB_SOMMER = [f"lstm_s2024_z{i}" for i in range(8)]
MERKMALE = KENNZAHLEN + EMB_WINTER + EMB_SOMMER
KMEANS_MERKMALE = ["anteil_volumenstrom", "streubreite_betriebspunkte",
                   "ruecklauf_lastgewichtet"]
VENTIL_GRENZE = 0.5
MIN_LASTSTUNDEN = 200
EMB_KANAELE = ["leistung", "durchfluss", "spreizung", "vorlauf", "ruecklauf", "aussen"]
EMB_MIN_TAGE = 30
KLASSEN = {"ventil": "Regelventil tauschen",
           "schlechter": "Regelparameter optimieren",
           "optimum": "kein Handlungsbedarf",
           "unklar": "nicht einstufbar"}
#Folie 5 und die Begriffe der Aufgabenstellung
HANDLUNG = {"Regelventil tauschen": "Reparatur",
            "Regelparameter optimieren": "Regelungsoptimierung",
            "kein Handlungsbedarf": "keine", "nicht einstufbar": "Daten prüfen"}


# --- Kennzahlen (Notebook 18) -------------------------------------------------

def _kennzahlen_eines_zaehlers(g: pd.DataFrame, winter, sommer) -> pd.Series:
    """Wie `kennzahlen` in Notebook 18, Zelle 35, mit Zeiträumen als Parameter."""
    w = g[(g["timestamp"] >= winter[0]) & (g["timestamp"] < winter[1])]
    s = g[(g["timestamp"] >= sommer[0]) & (g["timestamp"] < sommer[1])]
    k = {"stunden_winter": int(w["durchfluss"].notna().sum()),
         "stunden_sommer": int(s["durchfluss"].notna().sum())}
    nacht = s[s["timestamp"].dt.hour <= 5].dropna(subset=["durchfluss"])
    fliesst = nacht[nacht["durchfluss"] >= 5]
    k["sommer_nachtfluss_lph"] = nacht["durchfluss"].median()
    k["sommer_durchlauf_anteil"] = (nacht["durchfluss"] >= 5).mean() if len(nacht) else np.nan
    k["sommer_nacht_spreizung_k"] = fliesst["spreizung"].median() if len(fliesst) >= 20 else np.nan
    tag = w.groupby(w["timestamp"].dt.floor("D"))[["ruecklauf", "aussen"]].mean().dropna()
    tag = tag[tag["aussen"] <= 15]
    k["winter_ruecklauf_bei_0c"] = (np.polyfit(tag["aussen"], tag["ruecklauf"], 1)[1]
                                    if len(tag) >= 30 else np.nan)
    last = w[(w["leistung"] > 0.5) & (w["durchfluss"] > 1)
             & (w["spreizung"] > 1)].dropna(subset=["ruecklauf"])
    k["winter_spreizung_last_k"] = last["spreizung"].mean()
    k["winter_ruecklauf_p90"] = w["ruecklauf"].quantile(0.9)
    k["winter_fluss_cv"] = (last["durchfluss"].std() / last["durchfluss"].mean()
                            if len(last) else np.nan)
    tags = w.loc[w["timestamp"].dt.hour.between(8, 20), "durchfluss"].median()
    nachts = w.loc[w["timestamp"].dt.hour <= 5, "durchfluss"].median()
    k["winter_nacht_tag_fluss"] = nachts / tags if tags > 0 else np.nan
    k["winter_spitzenlast_kw"] = w["leistung"].quantile(0.99)
    ende = pd.Timestamp(sommer[1])
    jahr = g[(g["timestamp"] >= ende - pd.DateOffset(years=1)) & (g["timestamp"] < ende)]
    k["sommerlast_anteil"] = (s["leistung"].mean() / jahr["leistung"].mean()
                              if jahr["leistung"].mean() > 0 else np.nan)
    k["anteil_volumenstrom"] = k["streubreite_betriebspunkte"] = np.nan
    k["ruecklauf_lastgewichtet"] = np.nan
    if len(last) >= MIN_LASTSTUNDEN:
        log_p, log_v = np.log(last["leistung"]), np.log(last["durchfluss"])
        log_d = np.log(last["spreizung"])
        k["anteil_volumenstrom"] = np.cov(log_p, log_v, bias=True)[0, 1] / np.var(log_p)
        k["streubreite_betriebspunkte"] = np.sqrt(np.var(log_v) + np.var(log_d))
        k["ruecklauf_lastgewichtet"] = np.average(last["ruecklauf"], weights=last["leistung"])
    return pd.Series(k)


def kennzahlen(stunden: pd.DataFrame, winter=WINTER, sommer=SOMMER,
               grenze: Optional[pd.Series] = None,
               anschluss: Optional[pd.Series] = None,
               vertrag: Optional[pd.Series] = None) -> pd.DataFrame:
    """Kennzahlen je Zähler für einen Winter und den folgenden Sommer.

    ``grenze`` schneidet je Zähler alles ab diesem Datum ab (Notebook 18:
    erste Begehung, spätestens Stichtag). ``anschluss`` ist der
    Anschlusswert in kW (Auslastung = Spitzenlast / Anschlusswert),
    ``vertrag`` der Vertrag vor der Begehung (``auslastung_vertrag``).
    """
    s = stunden
    if grenze is not None:
        s = s[s["timestamp"] < s["zaehler"].map(grenze)]
    kz = s.groupby("zaehler").apply(_kennzahlen_eines_zaehlers, winter=winter,
                                    sommer=sommer)
    if anschluss is not None:
        kz["auslastung"] = kz["winter_spitzenlast_kw"] / anschluss.reindex(kz.index)
    else:
        kz["auslastung"] = np.nan
    if vertrag is not None:
        kz["auslastung_vertrag"] = kz["winter_spitzenlast_kw"] / vertrag.reindex(kz.index)
    return kz.drop(columns="winter_spitzenlast_kw")


def lade_anschlusswerte(pfad: Path = PROCESSED / "hast_features.csv") -> pd.Series:
    """Anschlusswert je Zähler aus Notebook 00 (ohne die Adressspalte)."""
    t = pd.read_csv(pfad, usecols=["Zählernummer", "anschlusswert_kw"])
    return t.set_index("Zählernummer")["anschlusswert_kw"]


def grenze_vor_begehung(labels: pd.DataFrame, zaehler: Sequence[int],
                        stichtag: pd.Timestamp = STICHTAG) -> pd.Series:
    """Erste Begehung, spätestens Stichtag; ohne Begehung der Stichtag."""
    return (labels["erste_begehung"].clip(upper=stichtag)
            .reindex(sorted(zaehler)).fillna(stichtag))


# --- LSTM-Embedding (Notebook 20) --------------------------------------------

def _torch():
    import torch
    return torch


def embedding_netz():
    """Netz aus Notebook 20, Abschnitt 3 (gleiche Namen der Gewichte)."""
    torch = _torch()
    nn = torch.nn

    class LSTMEmbedding(nn.Module):
        def __init__(self, n_ein=6, n_aus=5, versteckt=96, kern=8):
            super().__init__()
            self.encoder = nn.LSTM(n_ein, versteckt, batch_first=True)
            self.zum_kern = nn.Linear(versteckt, kern)
            self.vom_kern = nn.Linear(kern, versteckt)
            self.decoder = nn.LSTM(versteckt + 1, versteckt, batch_first=True)
            self.ausgang = nn.Linear(versteckt, n_aus)

        def einbetten(self, tag):
            _, (zustand, _) = self.encoder(tag)
            return self.zum_kern(zustand[-1])

        def forward(self, tag, aussen_ziel):
            kern = self.einbetten(tag)
            je_stunde = self.vom_kern(kern).unsqueeze(1).repeat(1, aussen_ziel.shape[1], 1)
            y, _ = self.decoder(torch.cat([je_stunde, aussen_ziel], dim=2))
            return self.ausgang(y)

    return LSTMEmbedding()


def _tagesfeld(stunden: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    s = stunden.dropna(subset=EMB_KANAELE).copy()
    s["tag"] = s["timestamp"].dt.floor("D")
    voll = s.groupby(["zaehler", "tag"])["timestamp"].transform("size") == 24
    s = s[voll].sort_values(["zaehler", "timestamp"])
    werte = s[EMB_KANAELE].to_numpy(dtype=np.float32).reshape(-1, 24, len(EMB_KANAELE))
    tage = s[["zaehler", "tag"]].iloc[::24].reset_index(drop=True)
    return werte, tage, s


def embedding_skalierung(stunden: pd.DataFrame, grenze: pd.Series) -> dict:
    """Skalen aus den Tagen vor der Begehung (Notebook 20, Abschnitt 2)."""
    werte, tage, s = _tagesfeld(stunden)
    vorher = (tage["tag"] < tage["zaehler"].map(grenze).fillna(STICHTAG)).to_numpy()
    stunde_vorher = np.repeat(vorher, 24)
    skal = {"teiler": {}, "mittel": {}, "streuung": {}}
    for i, kanal in enumerate(EMB_KANAELE):
        if kanal in ("leistung", "durchfluss"):
            skal["teiler"][kanal] = (s[stunde_vorher].groupby("zaehler")[kanal]
                                     .quantile(0.95).clip(lower=1e-3))
        else:
            skal["mittel"][kanal] = float(werte[vorher, :, i].mean())
            skal["streuung"][kanal] = float(werte[vorher, :, i].std())
    return skal


def embeddings(modell, skal: dict, stunden: pd.DataFrame,
               zeitraeume: Dict[str, Tuple[str, str]],
               grenze: Optional[pd.Series] = None, min_tage: int = EMB_MIN_TAGE,
               geraet: Optional[str] = None) -> pd.DataFrame:
    """Mittleres Embedding je Zähler und Zeitraum (Spalten lstm_<name>_z0..7).

    Mit ``grenze`` zählen nur Tage davor (Notebook 20). Zähler ohne Teiler
    im Paket bekommen ihr eigenes 95-%-Quantil aus den übergebenen Daten.
    """
    torch = _torch()
    geraet = geraet or ("cuda" if torch.cuda.is_available() else "cpu")
    werte, tage, s = _tagesfeld(stunden)
    x = werte.copy()
    for i, kanal in enumerate(EMB_KANAELE):
        if kanal in ("leistung", "durchfluss"):
            teiler = skal["teiler"][kanal]
            eigene = s.groupby("zaehler")[kanal].quantile(0.95).clip(lower=1e-3)
            teiler = teiler.combine_first(eigene)
            je_tag = tage["zaehler"].map(teiler).fillna(1.0).to_numpy(dtype=np.float32)
            x[:, :, i] = werte[:, :, i] / je_tag[:, None]
        else:
            x[:, :, i] = ((werte[:, :, i] - np.float32(skal["mittel"][kanal]))
                          / np.float32(skal["streuung"][kanal]))
    modell = modell.to(geraet).eval()
    with torch.no_grad():
        kerne = torch.cat([modell.einbetten(torch.tensor(x[i:i + 4096]).to(geraet)).cpu()
                           for i in range(0, len(x), 4096)]).numpy() if len(x) else np.zeros((0, 8))
    kern_tab = pd.concat([tage, pd.DataFrame(kerne, columns=[f"z{i}" for i in range(8)])], axis=1)
    if grenze is not None:
        kern_tab = kern_tab[kern_tab["tag"] < kern_tab["zaehler"].map(grenze).fillna(STICHTAG)]
    teile = []
    for name, (von, bis) in zeitraeume.items():
        t = kern_tab[(kern_tab["tag"] >= von) & (kern_tab["tag"] < bis)]
        m = t.groupby("zaehler")[[f"z{i}" for i in range(8)]].mean()
        teile.append(m[t.groupby("zaehler").size() >= min_tage].add_prefix(f"lstm_{name}_"))
    return pd.concat(teile, axis=1)


# --- Modelle (Notebook 19 und 22) ---------------------------------------------

def _lr_suche():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(class_weight="balanced", max_iter=5000))
    return GridSearchCV(pipe, {"logisticregression__C": [0.03, 0.1, 0.3, 1.0]},
                        cv=StratifiedKFold(4, shuffle=True, random_state=SEED),
                        scoring="roc_auc")


def kreuzvalidiert(X: pd.DataFrame, y: np.ndarray) -> np.ndarray:
    """Verschachtelte Leave-one-out-Werte wie Notebook 20 und 22."""
    from sklearn.model_selection import LeaveOneOut, cross_val_predict
    return cross_val_predict(_lr_suche(), X, y, cv=LeaveOneOut(),
                             method="predict_proba", n_jobs=-1)[:, 1]


def youden(y: np.ndarray, score: np.ndarray) -> float:
    from sklearn.metrics import roc_curve
    fpr, tpr, schwellen = roc_curve(y, score)
    return float(schwellen[np.argmax(tpr - fpr)])


def kmeans_lernen(kz: pd.DataFrame) -> dict:
    """K-Means k = 2 auf drei Regelungs-Kennzahlen (Notebook 19)."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    daten = kz[KMEANS_MERKMALE].dropna()
    skal = StandardScaler().fit(daten)
    km = KMeans(n_clusters=2, n_init=25, random_state=0).fit(skal.transform(daten))
    zentren = skal.inverse_transform(km.cluster_centers_)
    optimum = int(np.argmin(zentren[:, KMEANS_MERKMALE.index("ruecklauf_lastgewichtet")]))
    return {"merkmale": KMEANS_MERKMALE, "mittel": skal.mean_.tolist(),
            "skala": skal.scale_.tolist(), "zentren": km.cluster_centers_.tolist(),
            "optimum": optimum, "zentren_echt": zentren.tolist()}


def kmeans_einstufen(km: dict, kz: pd.DataFrame) -> pd.Series:
    """Optimum / schlechter je Zähler, leer ohne alle drei Kennzahlen."""
    d = kz.reindex(columns=km["merkmale"]).dropna()
    x = (d.to_numpy() - np.asarray(km["mittel"])) / np.asarray(km["skala"])
    abstand = ((x[:, None, :] - np.asarray(km["zentren"])[None]) ** 2).sum(axis=2)
    cluster = abstand.argmin(axis=1)
    return pd.Series(np.where(cluster == km["optimum"], "Optimum", "schlechter"),
                     index=d.index).reindex(kz.index)


def trainingsdaten(kz: pd.DataFrame, emb: pd.DataFrame,
                   labels: pd.DataFrame) -> pd.DataFrame:
    """Prüfbasis von Notebook 22: begangene mit Winter-Embedding und Sommerwerten."""
    merkmale = kz.join(emb[EMB_WINTER + EMB_SOMMER])
    daten = labels.join(merkmale, how="inner")
    return daten.dropna(subset=EMB_WINTER + ["sommer_durchlauf_anteil"])


def lernen(kz: pd.DataFrame, emb: pd.DataFrame, labels: pd.DataFrame) -> dict:
    """Ventil- und Dämmungsmodell, Vertragsregel, K-Means; dazu die Werte aus der Kreuzvalidierung."""
    from .pruefstand import auc_mit_intervall
    daten = trainingsdaten(kz, emb, labels)
    aus = {"daten_index": daten.index.tolist()}
    oof = pd.DataFrame(index=daten.index)
    for ziel in ("ventil", "daemmung"):
        d = daten.dropna(subset=[ziel])
        y = d[ziel].astype(int).to_numpy()
        oof[ziel] = pd.Series(kreuzvalidiert(d[MERKMALE], y), index=d.index)
        aus[f"{ziel}_modell"] = _lr_suche().fit(d[MERKMALE], y).best_estimator_
        aus[f"{ziel}_auc"] = auc_mit_intervall(y, oof.loc[d.index, ziel].to_numpy())
        aus[f"{ziel}_youden"] = youden(y, oof.loc[d.index, ziel].to_numpy())
    #Überdimensionierung: Regel niedrige Auslastung zum Vertrag vor der Begehung
    d = daten.dropna(subset=["ueberdimensioniert"])
    median = float(daten["auslastung_vertrag"].median())
    s = -d["auslastung_vertrag"].fillna(median)
    y = d["ueberdimensioniert"].astype(int).to_numpy()
    aus["vertrag_median"] = median
    aus["vertrag_auc"] = auc_mit_intervall(y, s.to_numpy())
    aus["vertrag_grenze"] = -youden(y, s.to_numpy())     # Auslastung höchstens
    oof["vertrag"] = (-daten["auslastung_vertrag"].fillna(median)).where(
        daten["ueberdimensioniert"].notna())
    aus["oof"] = oof
    aus["kmeans"] = kmeans_lernen(kz)
    aus["lernbereich"] = {"min": daten[KENNZAHLEN].min().to_dict(),
                          "max": daten[KENNZAHLEN].max().to_dict()}
    return aus


def bewerten(teile: dict, kz: pd.DataFrame, emb: pd.DataFrame,
             oof: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Klasse nach Folie 5 und Hinweise je Zähler.

    ``teile`` kommt aus `lernen` oder `lade`. Mit ``oof`` werden für
    begangene Zähler die Werte aus der Kreuzvalidierung eingesetzt (wie
    Notebook 22), sonst gilt für alle das fertige Modell.
    """
    par = teile["parameter"]
    merkmale = kz.join(emb.reindex(columns=EMB_WINTER + EMB_SOMMER))
    X = merkmale.reindex(columns=MERKMALE)
    k = pd.DataFrame(index=merkmale.index)
    k["p_ventil"] = teile["ventil_modell"].predict_proba(X)[:, 1]
    k["p_daemmung"] = teile["daemmung_modell"].predict_proba(X)[:, 1]
    bezug = (merkmale["auslastung_vertrag"].fillna(merkmale["auslastung"])
             if "auslastung_vertrag" in merkmale else merkmale["auslastung"])
    k["auslastung"] = bezug.fillna(par["vertrag_median"])
    if oof is not None:
        for ziel, spalte in (("ventil", "p_ventil"), ("daemmung", "p_daemmung")):
            o = oof[ziel].dropna()
            k.loc[o.index.intersection(k.index), spalte] = o
        o = oof["vertrag"].dropna()
        k.loc[o.index.intersection(k.index), "auslastung"] = -o
    k["kmeans"] = kmeans_einstufen(teile["kmeans"], kz)
    k["klasse"] = np.select(
        [k["p_ventil"] >= par["ventil_grenze"], k["kmeans"] == "schlechter",
         k["kmeans"] == "Optimum"],
        [KLASSEN["ventil"], KLASSEN["schlechter"], KLASSEN["optimum"]], KLASSEN["unklar"])
    k["handlung"] = k["klasse"].map(HANDLUNG)
    k["hinweis_daemmung"] = k["p_daemmung"] >= par["daemmung_grenze"]
    k["hinweis_vertrag"] = k["auslastung"] <= par["vertrag_grenze"]
    lb = teile["lernbereich"]
    lo, hi = pd.Series(lb["min"]), pd.Series(lb["max"])
    km = merkmale.reindex(columns=KENNZAHLEN)
    k["kennzahlen_ausserhalb"] = ((km > hi) | (km < lo)).sum(axis=1)
    return k


def paket_bauen(stunden: Optional[pd.DataFrame] = None,
                labels: Optional[pd.DataFrame] = None,
                kz: Optional[pd.DataFrame] = None, emb: Optional[pd.DataFrame] = None,
                gewichte: Path = NB_MODELLE / "lstm_embedding_begangen.pt",
                version: Optional[str] = None, wurzel: Path = mp.MODELS,
                aktuell: bool = True) -> mp.Paket:
    """Paket ``fehlerklassen`` aus den Ausgaben der Notebooks 18 bis 20.

    Ohne Argumente liest es `modell_stunden.parquet`, `modell_labels.csv`,
    `modell_kennzahlen.csv` und `lstm_embedding.csv`, also genau das, woraus
    Notebook 22 gelernt hat.
    """
    import joblib
    torch = _torch()
    if stunden is None:
        stunden = pd.read_parquet(PROCESSED / "modell_stunden.parquet")
    if labels is None:
        labels = pd.read_csv(PROCESSED / "modell_labels.csv", index_col="zaehler",
                             parse_dates=["erste_begehung"])
    if kz is None:
        kz = pd.read_csv(PROCESSED / "modell_kennzahlen.csv", index_col="zaehler")
    if emb is None:
        emb = pd.read_csv(PROCESSED / "lstm_embedding.csv", index_col="zaehler")
    gelernt = lernen(kz, emb, labels)
    grenze = grenze_vor_begehung(labels, stunden["zaehler"].unique())
    skal = embedding_skalierung(stunden, grenze)
    gespeichert = torch.load(gewichte, map_location="cpu")
    par = {"ventil_grenze": VENTIL_GRENZE,
           "daemmung_grenze": gelernt["daemmung_youden"],
           "vertrag_grenze": gelernt["vertrag_grenze"],
           "vertrag_median": gelernt["vertrag_median"],
           "merkmale": MERKMALE, "kennzahlen": KENNZAHLEN,
           "winter": list(WINTER), "sommer": list(SOMMER),
           "emb_min_tage": EMB_MIN_TAGE, "stichtag": STICHTAG,
           "klassen": KLASSEN, "handlung": HANDLUNG}
    auc = {f"{z}_auc": [round(v, 3) for v in gelernt[f"{z}_auc"]]
           for z in ("ventil", "daemmung", "vertrag")}
    teiler = pd.DataFrame(skal["teiler"])
    dateien = {
        "embedding_gewichte.pt": lambda p: torch.save(gespeichert["gewichte"], p),
        "embedding_skalierung.json": lambda p: p.write_text(json.dumps(
            {"mittel": skal["mittel"], "streuung": skal["streuung"]}, indent=2),
            encoding="utf-8"),
        "embedding_teiler.csv": lambda p: teiler.to_csv(p, index_label="zaehler"),
        "ventil_modell.joblib": lambda p: joblib.dump(gelernt["ventil_modell"], p),
        "daemmung_modell.joblib": lambda p: joblib.dump(gelernt["daemmung_modell"], p),
        "kmeans.json": lambda p: p.write_text(json.dumps(gelernt["kmeans"], indent=2),
                                              encoding="utf-8"),
        "lernbereich.json": lambda p: p.write_text(json.dumps(gelernt["lernbereich"],
                                                              indent=2), encoding="utf-8"),
        "kreuzvalidierung.csv": lambda p: gelernt["oof"].to_csv(p, index_label="zaehler"),
    }
    return mp.schreibe_paket(
        PAKETNAME, "Fehler erkennen und unterteilen (Folie 5)", dateien,
        parameter=par, kennzahlen={**auc, "lernstationen": len(gelernt["daten_index"])},
        datenstand=stunden["timestamp"].max(),
        lernzeitraum=f"Winter {WINTER[0]}–{WINTER[1]}, Sommer {SOMMER[0]}–{SOMMER[1]}, vor der ersten Begehung",
        beschreibung=("Kennzahlen + LSTM-Embedding → logistische Regression (Ventil, Dämmung), "
                      "Auslastungsregel (Vertrag), K-Means Optimum/schlechter → Klasse nach Folie 5"),
        quelle="notebooks/18 bis 22", version=version, wurzel=wurzel, aktuell=aktuell)


def lade(version: Optional[str] = None, wurzel: Path = mp.MODELS) -> dict:
    import joblib
    torch = _torch()
    paket = mp.lade_paket(PAKETNAME, version, wurzel)
    netz = embedding_netz()
    netz.load_state_dict(torch.load(paket.pfad("embedding_gewichte.pt"), map_location="cpu"))
    sk = paket.json("embedding_skalierung.json")
    teiler = paket.tabelle("embedding_teiler.csv", index_col="zaehler")
    return {"paket": paket, "parameter": paket.parameter, "netz": netz.eval(),
            "skalierung": {"mittel": sk["mittel"], "streuung": sk["streuung"],
                           "teiler": {k: teiler[k].dropna() for k in teiler.columns}},
            "ventil_modell": joblib.load(paket.pfad("ventil_modell.joblib")),
            "daemmung_modell": joblib.load(paket.pfad("daemmung_modell.joblib")),
            "kmeans": paket.json("kmeans.json"),
            "lernbereich": paket.json("lernbereich.json"),
            "kreuzvalidierung": paket.tabelle("kreuzvalidierung.csv", index_col="zaehler")}


def saison_bewerten(geladen: dict, stunden: pd.DataFrame, winter: Tuple[str, str],
                    sommer: Tuple[str, str], anschluss: Optional[pd.Series] = None,
                    geraet: Optional[str] = None) -> pd.DataFrame:
    """Klassen für eine Heizperiode mit dem gespeicherten Modell.

    Kennzahlen und Embedding kommen aus ``winter`` und ``sommer`` ohne
    Begehungsgrenze (der Zustand in dieser Zeit). Die Auslastung bezieht
    sich auf den Anschlusswert, der dann der aktuelle Vertrag ist.
    """
    anschluss = lade_anschlusswerte() if anschluss is None else anschluss
    kz = kennzahlen(stunden, winter, sommer, anschluss=anschluss)
    emb = embeddings(geladen["netz"], geladen["skalierung"], stunden,
                     {"w2324": winter, "s2024": sommer},
                     min_tage=geladen["parameter"].get("emb_min_tage", EMB_MIN_TAGE),
                     geraet=geraet)
    k = bewerten(geladen, kz, emb)
    k["stunden_winter"] = kz["stunden_winter"]
    k["stunden_sommer"] = kz["stunden_sommer"]
    return k


def gegenprobe(geladen: dict) -> dict:
    """Paket gegen `fehlerklassen_je_hast.csv` aus Notebook 22 halten."""
    kz = pd.read_csv(PROCESSED / "modell_kennzahlen.csv", index_col="zaehler")
    emb = pd.read_csv(PROCESSED / "lstm_embedding.csv", index_col="zaehler")
    neu = bewerten(geladen, kz, emb, oof=geladen["kreuzvalidierung"])
    alt = pd.read_csv(PROCESSED / "fehlerklassen_je_hast.csv", index_col="zaehler")
    m = alt.join(neu, rsuffix="_paket", how="inner")
    return {"zaehler": len(m),
            "max_abw_p_ventil": float((m["p_ventil"] - m["p_ventil_paket"]).abs().max()),
            "klasse_gleich": float((m["klasse"] == m["klasse_paket"]).mean()),
            "kmeans_gleich": float((m["kmeans"].fillna("-") == m["kmeans_paket"].fillna("-")).mean()),
            "hinweis_daemmung_gleich": float((m["hinweis_daemmung"].astype(bool)
                                              == m["hinweis_daemmung_paket"]).mean()),
            "hinweis_vertrag_gleich": float((m["hinweis_vertrag"].astype(bool)
                                             == m["hinweis_vertrag_paket"]).mean()),
            "klassen_paket": neu["klasse"].value_counts().to_dict()}


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--bauen", action="store_true")
    p.add_argument("--gegenprobe", action="store_true")
    args = p.parse_args(argv)
    if args.bauen:
        paket = paket_bauen()
        print(f"Paket {paket.name} {paket.version}: {paket.meta['kennzahlen']}")
    if args.gegenprobe:
        for k, v in gegenprobe(lade()).items():
            print(f"{k:26s} {v}")


if __name__ == "__main__":
    main()
