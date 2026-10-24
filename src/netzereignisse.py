"""Gleichzeitige Alarme: Netzereignis oder Problem der einzelnen Station?

Der Tagesmonitor (`tagesmonitor.py`) meldet Alarme je Station. Starten an
vielen Stationen zur selben Zeit Alarme, spricht das eher für etwas
Netzseitiges (Vorlaufabsenkung, Kälteeinbruch, den die Kennlinie nicht ganz
abfängt, oder eine Begehungswelle) als für einen Fehler im einzelnen Haus.
Dasselbe im Kleinen: starten benachbarte Stationen im Leitungsnetz
gemeinsam, ist das ein Hinweis auf den Strang.

Als Zeitpunkt zählt der geschätzte Beginn der Änderung (``beginn``), nicht
der Alarmtag, weil der CUSUM je nach Stärke der Änderung unterschiedlich
lange bis zur Schwelle braucht.

Beide Tests arbeiten mit Permutation. Für Netztage wird jede Station in
sich zeitlich verschoben (Anzahl und Überwachungstage bleiben, nur der
Zeitpunkt ist zufällig), für Nachbarn werden die Stationen auf die Knoten
des Graphen zufällig verteilt. Ein Treffer ist ein Hinweis, kein Nachweis
einer Ursache.
"""
from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import alarmbewertung as ab

FENSTER_TAGE = 3
FENSTER_SENSITIVITAET = (1, 3, 7)
N_PERMUTATIONEN = 1000
N_PERMUTATIONEN_PAARE = 10_000
ALPHA = 0.05
STATUS_SPALTEN = ["meter", "winter", "prioritaet", "auffaellig", "score",
                  "rang", "fehlerbild", "chronisch", "alarme_schlechter",
                  "alarme_besser", "alarme_netzereignis", "alarme_nachbar"]


def einsaetze(alarme: pd.DataFrame) -> pd.DataFrame:
    """Alarme mit Bewertung (schlechter/besser) und Beginn als Kalendertag."""
    a = ab.bewerte_richtung(alarme)
    return pd.DataFrame({
        "meter": a["meter"].astype(int).to_numpy(),
        "kanal": a["kanal"].to_numpy(),
        "datum": pd.to_datetime(a["datum"]).dt.normalize().to_numpy(),
        "beginn": pd.to_datetime(a["beginn"]).dt.normalize().to_numpy(),
        "bewertung": a["bewertung"].to_numpy(),
    })


def _matrix(einsatz: pd.DataFrame, beobachtet: Mapping[int, pd.DatetimeIndex]):
    meters = sorted(int(m) for m, t in beobachtet.items() if len(t))
    alle = pd.DatetimeIndex(np.concatenate(
        [pd.DatetimeIndex(beobachtet[m]).normalize().to_numpy() for m in meters]))
    tage = pd.date_range(alle.min(), alle.max(), freq="D")
    pos = {m: i for i, m in enumerate(meters)}
    A = np.zeros((len(meters), len(tage)), dtype=bool)
    for m in meters:
        A[pos[m], tage.get_indexer(pd.DatetimeIndex(beobachtet[m]).normalize())] = True
    E = np.zeros_like(A)
    for m, b in zip(einsatz["meter"], pd.to_datetime(einsatz["beginn"])):
        if m not in pos:
            continue
        aktiv = np.flatnonzero(A[pos[m]])
        d = (b - tage[0]).days
        #Beginn auf den nächsten überwachten Tag legen, sonst ginge er beim Verschieben verloren
        E[pos[m], aktiv[np.argmin(np.abs(aktiv - d))]] = True
    return meters, tage, A, E


def verschiebe(E: np.ndarray, A: np.ndarray, rng) -> np.ndarray:
    """Jede Zeile zufällig zyklisch über ihre aktiven Tage verschieben."""
    V = np.zeros_like(E)
    for i in range(E.shape[0]):
        idx = np.flatnonzero(A[i])
        if len(idx):
            V[i, idx] = np.roll(E[i, idx], int(rng.integers(len(idx))))
    return V


def _dilatiere(E: np.ndarray, fenster: int) -> np.ndarray:
    cs = np.pad(np.cumsum(E, axis=1), ((0, 0), (fenster + 1, fenster)), mode="edge")
    cs[:, :fenster + 1] = 0
    n = E.shape[1]
    return (cs[:, 2 * fenster + 1:2 * fenster + 1 + n] - cs[:, :n]) > 0


def _paarsumme(c: np.ndarray) -> float:
    return float(np.sum(c * (c - 1) / 2))


def netztage(einsatz: pd.DataFrame, beobachtet: Mapping[int, pd.DatetimeIndex],
             fenster: int = FENSTER_TAGE, n: int = N_PERMUTATIONEN,
             seed: int = 0, alpha: float = ALPHA) -> dict:
    """Tage, an denen ungewöhnlich viele Stationen gleichzeitig starten.

    Je Tag zählt, wie viele Stationen innerhalb von ``fenster`` Tagen davor
    oder danach einen Alarmbeginn haben. Die Schwelle ist das
    ``1 - alpha``-Quantil des größten Tageswerts unter Permutation, damit
    gilt das Niveau für den ganzen Zeitraum und nicht je Tag.
    ``p_global`` prüft die zeitliche Häufung insgesamt (Paare von
    Stationen, die im selben Fenster starten).
    """
    meters, tage, A, E = _matrix(einsatz, beobachtet)
    c = _dilatiere(E, fenster).sum(axis=0)
    rng = np.random.default_rng(seed)
    maxima = np.empty(n)
    summen = np.empty(n)
    for k in range(n):
        cp = _dilatiere(verschiebe(E, A, rng), fenster).sum(axis=0)
        maxima[k] = cp.max()
        summen[k] = _paarsumme(cp)
    schwelle = float(np.quantile(maxima, 1 - alpha))
    beob = _paarsumme(c)
    tab = pd.DataFrame({"datum": tage, "n_aktiv": A.sum(axis=0),
                        "n_gleichzeitig": c, "netzereignis": c > schwelle})

    episoden = []
    ev = np.flatnonzero(tab["netzereignis"].to_numpy())
    if len(ev):
        bruch = np.flatnonzero(np.diff(ev) > 1)
        for teil in np.split(ev, bruch + 1):
            lo, hi = teil[0], teil[-1]
            zeilen = np.flatnonzero(E[:, max(lo - fenster, 0):hi + fenster + 1]
                                    .any(axis=1))
            episoden.append({
                "von": tage[lo], "bis": tage[hi],
                "n_stationen": len(zeilen),
                "n_aktiv": int(A[:, lo:hi + 1].any(axis=1).sum()),
                "max_gleichzeitig": int(c[lo:hi + 1].max()),
                "meter": ", ".join(str(meters[i]) for i in zeilen)})
    return {"tage": tab, "schwelle": schwelle,
            "episoden": pd.DataFrame(episoden, columns=[
                "von", "bis", "n_stationen", "n_aktiv", "max_gleichzeitig",
                "meter"]),
            "n_stationen": len(meters), "n_einsaetze": int(E.sum()),
            "paare_beobachtet": beob, "paare_erwartet": float(summen.mean()),
            "p_global": float((1 + np.sum(summen >= beob)) / (n + 1))}


def _tage_je_meter(einsatz: pd.DataFrame) -> Dict[int, np.ndarray]:
    b = pd.to_datetime(einsatz["beginn"]).to_numpy().astype("datetime64[D]")
    t = pd.DataFrame({"meter": einsatz["meter"].astype(int).to_numpy(),
                      "tag": b.astype(np.int64)})
    return {int(m): np.unique(g["tag"].to_numpy()) for m, g in t.groupby("meter")}


def _naechster_abstand(a: np.ndarray, b: np.ndarray):
    if not len(a) or not len(b):
        return None
    d = np.abs(a[:, None] - b[None, :])
    i, j = np.unravel_index(np.argmin(d), d.shape)
    return int(a[i]), int(b[j]), int(d[i, j])


def nachbar_gleichzeitig(einsatz: pd.DataFrame, paar_liste,
                         fenster: int = FENSTER_TAGE,
                         n: int = N_PERMUTATIONEN_PAARE, seed: int = 0,
                         stationen: Optional[Iterable[int]] = None) -> dict:
    """Nachbarpaare, deren Alarme innerhalb von ``fenster`` Tagen beginnen.

    ``stationen`` sind die Stationen, die im Graph hängen und überwacht
    werden; nur zwischen ihnen wird permutiert. Stationen ohne Alarm
    gehören dazu, sie können nie gleichzeitig sein. ``p`` ist einseitig.
    """
    tage = _tage_je_meter(einsatz)
    if stationen is None:
        stationen = {m for p in paar_liste for m in p}
    st = sorted({int(m) for m in stationen})
    pos = {m: i for i, m in enumerate(st)}
    K = np.zeros((len(st), len(st)), dtype=bool)
    for a in st:
        for b in st:
            if a < b:
                r = _naechster_abstand(tage.get(a, np.array([])),
                                       tage.get(b, np.array([])))
                K[pos[a], pos[b]] = K[pos[b], pos[a]] = (
                    r is not None and r[2] <= fenster)
    p = [(pos[a], pos[b]) for a, b in paar_liste if a in pos and b in pos]
    i = np.array([x for x, _ in p], dtype=int)
    j = np.array([y for _, y in p], dtype=int)
    beob = int(K[i, j].sum())
    rng = np.random.default_rng(seed)
    P = rng.permuted(np.tile(np.arange(len(st)), (int(n), 1)), axis=1)
    zufall = K[P[:, i], P[:, j]].sum(axis=1)

    treffer = []
    for a, b in ((st[x], st[y]) for x, y in zip(i, j) if K[x, y]):
        ta, tb, d = _naechster_abstand(tage[a], tage[b])
        treffer.append({"meter_a": a, "meter_b": b,
                        "beginn_a": pd.Timestamp(np.datetime64(ta, "D")),
                        "beginn_b": pd.Timestamp(np.datetime64(tb, "D")),
                        "abstand_tage": d})
    return {"n_stationen": len(st), "paare": int(len(i)), "beobachtet": beob,
            "erwartet": float(zufall.mean()),
            "p": float((1 + np.sum(zufall >= beob)) / (n + 1)),
            "treffer": pd.DataFrame(treffer, columns=[
                "meter_a", "meter_b", "beginn_a", "beginn_b", "abstand_tage"])}


def markiere(einsatz: pd.DataFrame, ereignistage: Sequence, paar_liste,
             fenster: int = FENSTER_TAGE) -> pd.DataFrame:
    """Flags je Alarm: ``netzereignis`` und ``nachbar_gleichzeitig``.

    Netzereignis: Beginn liegt höchstens ``fenster`` Tage neben einem
    Ereignistag aus `netztage`. Nachbar: ein Nachbar hat einen Alarm
    derselben Bewertung, der höchstens ``fenster`` Tage daneben beginnt.
    """
    e = einsatz.copy()
    b = pd.to_datetime(e["beginn"]).to_numpy().astype("datetime64[D]").astype(np.int64)
    ev = (pd.DatetimeIndex(ereignistage).to_numpy().astype("datetime64[D]")
          .astype(np.int64))
    e["netzereignis"] = (np.abs(b[:, None] - ev[None, :]) <= fenster).any(axis=1) \
        if len(ev) else False
    nb: Dict[int, set] = {}
    for a, c in paar_liste:
        nb.setdefault(int(a), set()).add(int(c))
        nb.setdefault(int(c), set()).add(int(a))
    tage = {(m, w): g for (m, w), g in
            pd.DataFrame({"m": e["meter"].astype(int), "w": e["bewertung"],
                          "t": b}).groupby(["m", "w"])["t"]}
    flags = []
    for m, w, t in zip(e["meter"].astype(int), e["bewertung"], b):
        andere = [tage[(x, w)].to_numpy() for x in nb.get(m, ()) if (x, w) in tage]
        flags.append(any(np.any(np.abs(o - t) <= fenster) for o in andere))
    e["nachbar_gleichzeitig"] = flags
    return e


def monitor_status(prioritaet: pd.DataFrame, markiert: pd.DataFrame,
                   fehlerbild: pd.DataFrame, uebersicht: pd.DataFrame,
                   alarme: pd.DataFrame) -> pd.DataFrame:
    """Eine Zeile je Station und Kernwinter für Karten und Dashboards.

    Enthält nur Zählernummern, keine Adressen. Alarme werden wie in
    `alarmbewertung.prioritaet_je_winter` über den Alarmtag der
    Heizperiode zugeordnet.
    """
    s = prioritaet[["meter", "winter", "prioritaet", "auffaellig",
                    "alarme_schlechter", "alarme_besser"]].copy()
    s = s.merge(markiert[["meter", "winter", "score", "rang"]],
                on=["meter", "winter"], how="left")
    s = s.merge(fehlerbild[["meter", "winter", "fehlerbild"]],
                on=["meter", "winter"], how="left")
    s["fehlerbild"] = s["fehlerbild"].fillna("")
    s = s.merge(uebersicht[["meter", "chronisch"]], on="meter", how="left")
    s["chronisch"] = s["chronisch"].fillna(False).astype(bool)
    a = alarme.assign(meter=alarme["meter"].astype(int),
                      datum=pd.to_datetime(alarme["datum"]))
    netz, nachbar = [], []
    for r in s.itertuples(index=False):
        lo, hi = ab.heizperiode(r.winter)
        eigen = a[(a["meter"] == int(r.meter)) & (a["datum"] >= lo)
                  & (a["datum"] <= hi)]
        netz.append(int(eigen["netzereignis"].sum()))
        nachbar.append(int(eigen["nachbar_gleichzeitig"].sum()))
    s["alarme_netzereignis"] = netz
    s["alarme_nachbar"] = nachbar
    return s[STATUS_SPALTEN]
