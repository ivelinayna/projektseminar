"""Nachbarn im Leitungsnetz: häufen sich auffällige Stationen?

Grundlage ist der logische Graph aus `build_graph.build_logical_graph`
(Nodes_Edges). Zwei Stationen sind Nachbarn, wenn höchstens
``max_kanten`` Kanten zwischen ihnen liegen; der Weg darf über
Knotenpunkte und über Hausstationen ohne Zähler führen.

Geprüft wird mit Permutationstests: die Merkmale (auffällig ja/nein bzw.
Score) werden zufällig auf die Stationen verteilt, der Graph bleibt
fest. Liegt die beobachtete Zahl auffälliger Nachbarpaare deutlich über
dem, was zufällige Verteilung ergibt, ist das ein Hinweis auf eine
netzseitige Gemeinsamkeit, kein Nachweis einer Ursache.

Statt über Kanten lassen sich Nachbarn auch über die Luftlinie bilden
(`radius_nachbarn`). Dafür braucht es Koordinaten je Haus; die
Nominatim-Positionen in `data/processed/hast_geocoded.csv` liegen fast
alle nur auf Straßenebene und taugen dafür nicht. `positionen_aus_handliste`
liest die von Hand gepflegte Liste aus NB 16 (Spalten ``adresse`` und
``koordinate``, optional ``zaehler``).

Knotennamen im Graph sind Adressen und werden nie ausgegeben.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

import networkx as nx
import numpy as np
import pandas as pd

from .load_data import _normalize_address

MAX_KANTEN = 2
KANTEN_SENSITIVITAET = (1, 2, 3)
RADIUS_SENSITIVITAET = (50, 100, 200)
ERDRADIUS_M = 6_371_000
N_PERMUTATIONEN = 10_000
TABELLEN_SPALTEN = ["meter", "fehlerbild", "im_graph", "n_nachbarn",
                    "n_mit_score", "n_auffaellig", "n_gleiches_bild",
                    "nachbarn"]


def _als_meter(wert) -> Optional[int]:
    try:
        f = float(wert)
    except (TypeError, ValueError):
        return None
    return int(f) if np.isfinite(f) else None


def meter_knoten(g: nx.Graph) -> Dict[int, object]:
    """Zählernummer -> Knoten für alle Hausstationen mit Zähler."""
    out: Dict[int, object] = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") != "HAST":
            continue
        m = _als_meter(d.get("zaehlernummer"))
        if m is not None and m not in out:
            out[m] = n
    return out


def nachbarn(g: nx.Graph, max_kanten: int = MAX_KANTEN) -> Dict[int, Set[int]]:
    """Zählernummer -> Zählernummern in höchstens ``max_kanten`` Kanten."""
    knoten = meter_knoten(g)
    zu_meter = {n: m for m, n in knoten.items()}
    out = {}
    for m, n in knoten.items():
        weit = nx.single_source_shortest_path_length(g, n, cutoff=max_kanten)
        out[m] = {zu_meter[x] for x in weit if x in zu_meter and x != n}
    return out


def paare(nb: Mapping[int, Set[int]]) -> List[Tuple[int, int]]:
    """Ungeordnete Nachbarpaare, jedes einmal, sortiert."""
    return sorted({(min(a, b), max(a, b)) for a, s in nb.items() for b in s})


def _koordinate(text) -> Tuple[float, float]:
    zahlen = re.findall(r"-?\d+(?:\.\d+)?", str(text))
    if len(zahlen) != 2:
        return np.nan, np.nan
    lat, lon = float(zahlen[0]), float(zahlen[1])
    #in der Handliste sind Breite und Länge manchmal vertauscht
    if lat < 20 and lon > 40:
        lat, lon = lon, lat
    return lat, lon


def positionen_aus_handliste(pfad, adressen: Mapping[int, str]) -> pd.DataFrame:
    """Zählernummer, lat, lon aus der Koordinatenliste von NB 16.

    ``adressen`` ist Zählernummer -> Adresse (``load_begehungen.meter_to_address``).
    Steht in der Liste eine Spalte ``zaehler``, gilt die Koordinate direkt
    für diese Zähler. Die Ausgabe enthält keine Adressen.
    """
    pfad = Path(pfad)
    if pfad.suffix.lower() == ".csv":
        roh = pd.read_csv(pfad, dtype=str)
    else:
        roh = pd.read_excel(pfad, dtype=str,
                            engine="odf" if pfad.suffix.lower() == ".ods" else None)
    lat, lon = zip(*[_koordinate(k) for k in roh["koordinate"].fillna("")]) \
        if len(roh) else ((), ())
    roh = roh.assign(lat=list(lat), lon=list(lon)).dropna(subset=["lat", "lon"])
    je_adresse = {_normalize_address(a): (la, lo) for a, la, lo in
                  zip(roh["adresse"], roh["lat"], roh["lon"])}
    pos = {int(m): je_adresse[_normalize_address(a)]
           for m, a in adressen.items() if _normalize_address(a) in je_adresse}
    if "zaehler" in roh.columns:
        for z, la, lo in zip(roh["zaehler"].fillna(""), roh["lat"], roh["lon"]):
            for m in re.findall(r"\d+", z):
                pos[int(m)] = (la, lo)
    return pd.DataFrame([{"meter": m, "lat": la, "lon": lo}
                         for m, (la, lo) in sorted(pos.items())],
                        columns=["meter", "lat", "lon"])


def radius_nachbarn(pos: pd.DataFrame, radius_m: float) -> Dict[int, Set[int]]:
    """Zählernummer -> Zählernummern höchstens ``radius_m`` Luftlinie entfernt."""
    m = pos["meter"].astype(int).to_numpy()
    la = np.radians(pos["lat"].to_numpy(float))
    lo = np.radians(pos["lon"].to_numpy(float))
    h = (np.sin((la[:, None] - la[None, :]) / 2) ** 2
         + np.cos(la[:, None]) * np.cos(la[None, :])
         * np.sin((lo[:, None] - lo[None, :]) / 2) ** 2)
    d = 2 * ERDRADIUS_M * np.arcsin(np.sqrt(h))
    return {int(m[i]): {int(m[j]) for j in np.flatnonzero(d[i] <= radius_m)
                        if j != i}
            for i in range(len(m))}


def _indizes(paar_liste, werte: Mapping[int, object],
             stationen: Optional[Iterable[int]] = None):
    if stationen is not None:
        erlaubt = {int(m) for m in stationen}
        werte = {m: v for m, v in werte.items() if m in erlaubt}
    stationen = sorted(werte)
    pos = {m: i for i, m in enumerate(stationen)}
    p = [(pos[a], pos[b]) for a, b in paar_liste if a in pos and b in pos]
    i = np.array([x for x, _ in p], dtype=int)
    j = np.array([y for _, y in p], dtype=int)
    return stationen, i, j


def join_test(paar_liste, flags: Mapping[int, bool],
              n: int = N_PERMUTATIONEN, seed: int = 0,
              stationen: Optional[Iterable[int]] = None) -> dict:
    """Paare mit zwei auffälligen Stationen gegen zufällige Verteilung.

    Nur Stationen mit einem Wert in ``flags`` und Paare zwischen ihnen
    zählen. ``stationen`` beschränkt die Permutation auf die Stationen im
    Graph; sonst würden Stationen ohne Knoten auffällige Labels schlucken
    und die Zufallserwartung senken. ``p`` ist einseitig: Anteil der
    Permutationen mit mindestens so vielen auffälligen Paaren wie beobachtet.
    """
    stationen, i, j = _indizes(paar_liste, flags, stationen)
    f = np.array([bool(flags[m]) for m in stationen])
    beob = int(np.sum(f[i] & f[j]))
    rng = np.random.default_rng(seed)
    perm = rng.permuted(np.tile(f, (int(n), 1)), axis=1)
    zufall = (perm[:, i] & perm[:, j]).sum(axis=1)
    return {"n_stationen": len(stationen), "n_auffaellig": int(f.sum()),
            "paare": int(len(i)), "beobachtet": beob,
            "erwartet": float(zufall.mean()),
            "p": float((1 + np.sum(zufall >= beob)) / (n + 1))}


def _paar_korrelation(x: np.ndarray, i: np.ndarray, j: np.ndarray) -> np.ndarray:
    #x hat Form (Permutationen, Stationen); jedes Paar zählt in beide Richtungen
    a = np.concatenate([x[:, i], x[:, j]], axis=1)
    b = np.concatenate([x[:, j], x[:, i]], axis=1)
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    nenner = np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1))
    return (a * b).sum(axis=1) / np.where(nenner > 0, nenner, np.nan)


def score_test(paar_liste, score: Mapping[int, float],
               n: int = N_PERMUTATIONEN, seed: int = 0,
               stationen: Optional[Iterable[int]] = None) -> dict:
    """Rangkorrelation der Scores benachbarter Stationen mit Permutation.

    Ränge statt Rohwerte, damit einzelne extreme Stationen den Wert nicht
    tragen. ``stationen`` wie bei `join_test`. ``p`` ist einseitig
    (Nachbarn ähnlicher als zufällig).
    """
    gueltig = {m: float(s) for m, s in score.items() if np.isfinite(s)}
    stationen, i, j = _indizes(paar_liste, gueltig, stationen)
    r = pd.Series([gueltig[m] for m in stationen]).rank().to_numpy()
    beob = float(_paar_korrelation(r[None, :], i, j)[0])
    rng = np.random.default_rng(seed)
    zufall = _paar_korrelation(rng.permuted(np.tile(r, (int(n), 1)), axis=1),
                               i, j)
    return {"n_stationen": len(stationen), "paare": int(len(i)),
            "beobachtet": beob, "erwartet": float(np.nanmean(zufall)),
            "p": float((1 + np.sum(zufall >= beob)) / (n + 1))}


def nachbartabelle(nb: Mapping[int, Set[int]], markiert: pd.DataFrame,
                   fehlerbild: Optional[Mapping[int, str]] = None
                   ) -> pd.DataFrame:
    """Je auffälliger Station: Nachbarn, davon bewertet, auffällig, gleiches Bild.

    ``markiert`` ist eine Tabelle eines Winters (oder eine Stationsübersicht)
    mit ``meter`` und ``auffaellig``.
    """
    fehlerbild = dict(fehlerbild or {})
    status = dict(zip(markiert["meter"].astype(int),
                      markiert["auffaellig"].astype(bool)))
    zeilen = []
    for m in sorted(k for k, v in status.items() if v):
        bild = fehlerbild.get(m, "")
        if m not in nb:
            zeilen.append({"meter": m, "fehlerbild": bild, "im_graph": False,
                           "n_nachbarn": np.nan, "n_mit_score": np.nan,
                           "n_auffaellig": np.nan, "n_gleiches_bild": np.nan,
                           "nachbarn": ""})
            continue
        s = sorted(nb[m])
        bewertet = [x for x in s if x in status]
        auff = [x for x in bewertet if status[x]]
        gleich = [x for x in auff if bild and fehlerbild.get(x) == bild]
        zeilen.append({"meter": m, "fehlerbild": bild, "im_graph": True,
                       "n_nachbarn": len(s), "n_mit_score": len(bewertet),
                       "n_auffaellig": len(auff), "n_gleiches_bild": len(gleich),
                       "nachbarn": ", ".join(str(x) for x in s)})
    return pd.DataFrame(zeilen, columns=TABELLEN_SPALTEN)
