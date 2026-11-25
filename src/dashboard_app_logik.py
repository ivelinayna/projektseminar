"""Logik des Fernwärme-Dashboards für die Streamlit-App (``src/dashboard_app.py``).

Nachbau des JavaScript-Teils aus ``notebooks/dashboard_final.py`` (HTML-Fassung) in Python.
Jede Funktion hier hat dort ein Gegenstück mit demselben Namen (``meldKlasse`` -> ``meld_klasse``,
``updateStats`` -> ``stats_html`` usw.). Rundung, Texte, Farben und Reihenfolgen sind gleich,
``tests/test_dashboard_app.py`` vergleicht beide Fassungen.

Gelesen wird die fertige HTML-Datei aus Notebook 37 (``notebooks/fernwaerme_dashboard_final.html``).
Die App nimmt die dort eingebetteten Daten, Notebook 37 und ``dashboard_final.py`` bleiben
unverändert. Hier wird nichts gelernt oder neu gerechnet, nur angezeigt.
"""

from __future__ import annotations

import base64
import json
import math
import unicodedata
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "notebooks" / "fernwaerme_dashboard_final.html"

NA = -32768
QN = ["Tagesmonitor", "Prognose-LSTM"]
DR_NAME = ["keine Maßnahme erkannt", "niedrig", "mittel", "hoch"]
DR_FARBE = ["#1a9850", "#fee08b", "#fc8d59", "#d73027"]
MA = {"reparatur": ("Reparatur (Regelventil)", "#d73027"),
      "kapazitaet": ("Kapazitätsanpassung prüfen", "#8b5cf6"),
      "daemmung": ("Dämmung prüfen (Hinweis)", "#2563eb"),
      "daten": ("Daten prüfen", "#6b7280"),
      "keine": ("keine Maßnahme erkannt", "#1a9850")}
PO = {3: ("hoch", "#d73027"), 2: ("mittel", "#fc8d59"), 1: ("gering", "#1a9850")}
ME = {"schl": ("Verschlechterung", "#d73027"),
      "netz": ("Verschlechterung, viele Stationen zugleich", "#f59e0b"),
      "bess": ("nur Verbesserung", "#2563eb"),
      "ruhig": ("überwacht, keine Meldung", "#a6d96a"),
      "aus": ("nicht überwacht", "#bbbbbb")}
GRAU = "#bbbbbb"
WD = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]

#Färbungen wie im Auswahlfeld der HTML-Fassung, in derselben Reihenfolge
FAERBUNGEN = {"dring": "Dringlichkeit der Empfehlung", "mass": "Maßnahme und Verdacht auf Fehlerart",
              "meld": "Meldungen der Wächter", "pot": "Potenzial im Netzvergleich",
              "spr": "Spreizung", "vor": "Vorlauf", "rueck": "Rücklauf", "fluss": "Durchfluss",
              "leist": "Leistung"}
MODELL_FAERBUNGEN = ("dring", "mass", "meld", "pot")
#Messwerte: Name, Einheit, Farbverlauf; Feld 0 bis 3 = Vorlauf, Rücklauf, Durchfluss, Leistung
MET = {"spr": ("Spreizung", "K", ["#d73027", "#fee08b", "#1a9850"]),
       "vor": ("Vorlauf", "°C", ["#fff3b0", "#f59e0b", "#b91c1c"]),
       "rueck": ("Rücklauf", "°C", ["#e0f2fe", "#38bdf8", "#1e3a8a"]),
       "fluss": ("Durchfluss", "l/h", ["#f3e8ff", "#a855f7", "#4c1d95"]),
       "leist": ("Leistung", "kW", ["#f3e8ff", "#a855f7", "#4c1d95"])}
STAENDE = {"auto": "Saison wie Zeitregler", "vor": "vor den Begehungen", "heute": "Stand heute"}
MASS_FILTER = {"": "alle Maßnahmen", "reparatur": "Reparatur (Regelventil)",
               "kapazitaet": "Kapazitätsanpassung prüfen", "daemmung": "Dämmung prüfen", "daten": "Daten prüfen"}
FENSTER = {72: "Fenster: 3 Tage", 336: "Fenster: 14 Tage", 1440: "Fenster: 60 Tage"}
SCHRITTE = {1: "1 h / Schritt", 6: "6 h / Schritt", 24: "1 Tag / Schritt"}

#Farben wie die CSS-Variablen der HTML-Fassung, hell und dunkel
FARBEN = {"light": {"bg": "#f2f5f8", "panel": "#fff", "ink": "#1b2631", "muted": "#5d6b79", "line": "#d5dce3",
                    "vor": "#d6402d", "rueck": "#2e6db3", "sel": "#0a7d6b", "btn": "#f6f8fa", "accent": "#c2410c"},
          "dark": {"bg": "#12171d", "panel": "#1a222b", "ink": "#e6ebf1", "muted": "#98a5b3", "line": "#2c3743",
                   "vor": "#ff6b57", "rueck": "#5aa2ee", "sel": "#3ed1b8", "btn": "#222c36", "accent": "#fb923c"}}


# --- JavaScript-Verhalten -------------------------------------------------------------------
# Damit Zahlen und Texte Zeichen für Zeichen gleich herauskommen wie im Browser.

class _Undef:
    """Steht für ``undefined`` in JavaScript: ein Feld, das es im Eintrag nicht gibt."""

    def __repr__(self):
        return "undefined"


UNDEF = _Undef()


def wahr(x) -> bool:
    """Wahrheitswert wie in JavaScript: leere Listen und Objekte sind wahr, 0, '', NaN falsch."""
    if x is None or x is UNDEF or x is False:
        return False
    if isinstance(x, (int, float)):
        return not (x == 0 or (isinstance(x, float) and math.isnan(x)))
    if isinstance(x, str):
        return x != ""
    return True


def js_str(x) -> str:
    """``String(x)`` in JavaScript."""
    if x is None:
        return "null"
    if x is UNDEF:
        return "undefined"
    if x is True:
        return "true"
    if x is False:
        return "false"
    if isinstance(x, float):
        if math.isnan(x):
            return "NaN"
        if x.is_integer() and abs(x) < 1e21:
            return str(int(x))
        return repr(x)
    return str(x)


def keine_zahl(x) -> bool:
    """``isNaN(x)`` für die Fälle, die hier vorkommen (Zahl, null, undefined)."""
    if x is UNDEF:
        return True
    if x is None:
        return False
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def to_fixed(x, d: int) -> str:
    """``Number(x).toFixed(d)``: rundet die exakte Binärzahl, bei Gleichstand weg von null."""
    x = float(x)
    if x == 0:
        x = 0.0     #-0 schreibt JavaScript ohne Vorzeichen
    q = Decimal(x).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    return format(q, "f")


def js_round(x: float) -> int:
    """``Math.round``: bei ,5 immer aufwärts."""
    r = math.floor(x)
    return r + 1 if x - r >= 0.5 else r


def esc(s) -> str:
    return "".join({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}.get(c, c)
                   for c in js_str(s))


def de(x, d: int = 2) -> str:
    if x is None or x is UNDEF or keine_zahl(x):
        return "–"
    return to_fixed(x, d).replace(".", ",")


def pz(x) -> str:
    if x is None or x is UNDEF or keine_zahl(x):
        return "–"
    return f"{js_round(100 * x)} %"


def f1(v, d: int = 1) -> str:
    return "–" if keine_zahl(v) else to_fixed(v, d)


def _feld(s: dict, k: str):
    return s[k] if k in s else UNDEF


def row(a, b) -> str:
    return f'<div class="kv"><span>{a}</span><b>{b}</b></div>'


def blk(titel, inhalt) -> str:
    return f'<div class="blk"><span>{titel}</span>{inhalt}</div>'


def _hex_rgb(c: str) -> list:
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def color_at(stops: list, t: float) -> str:
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    x = t * n
    i = min(math.floor(x), n - 1)
    u = x - i
    a, b = _hex_rgb(stops[i]), _hex_rgb(stops[i + 1])
    return "rgb(" + ",".join(str(js_round(v + (b[k] - v) * u)) for k, v in enumerate(a)) + ")"


def sortierschluessel(name: str):
    """Ungefähr ``localeCompare(…, 'de')``: Umlaute wie Grundbuchstaben, Kleinschreibung zuerst."""
    basis = "".join(c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c))
    return (basis.casefold(), name.swapcase())


# --- Daten ----------------------------------------------------------------------------------

def lade(html: Path = HTML) -> tuple:
    """Daten und Messwerte aus der HTML-Datei von Notebook 37 (``const D = {...}`` im Skript)."""
    html = Path(html)
    if not html.exists():
        raise FileNotFoundError(f"{html.name} fehlt in {html.parent}. Notebook 37 ausführen, es schreibt die Datei.")
    text = html.read_text(encoding="utf-8")
    marke = "const D = "
    if marke not in text:
        raise ValueError(f"In {html.name} stehen keine Dashboard-Daten ({marke!r} fehlt).")
    daten, _ = json.JSONDecoder().raw_decode(text, text.index(marke) + len(marke))
    roh = np.frombuffer(base64.b64decode(daten.pop("b64")), dtype="<i2").reshape(daten["M"], 4, daten["H"])
    return daten, roh


def _datum(s: str) -> datetime:
    return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]) if len(s) > 11 else 0)


class Dashboard:
    """Alles, was nicht vom Zustand abhängt, einmal beim Laden berechnet (wie oben im JavaScript)."""

    def __init__(self, daten: dict, messwerte: np.ndarray):
        D = self.D = daten
        self.H, self.M, self.FMIN, self.MT = D["H"], D["M"], D["fluss_min"], D["mt"]
        roh = np.asarray(messwerte).reshape(self.M, 4, self.H)
        sc = np.asarray(D["scale"], dtype=float).reshape(1, 4, 1)
        #val(m, f, h) = I16 / SC[f], fehlende Werte NaN
        self.werte = np.where(roh == NA, np.nan, roh / sc)
        v, r, f = self.werte[:, 0], self.werte[:, 1], self.werte[:, 2]
        with np.errstate(invalid="ignore"):
            self.spreizung = np.where((f > self.FMIN) & ~np.isnan(v) & ~np.isnan(r), v - r, np.nan)

        self.MD = MD = D["modell"]
        self.MST, self.MEL, self.UEB = MD["stationen"], MD["meldungen"], MD["ueberwacht"]
        self.G_ = MD["meta"]["grenzen"]
        self.VOR = MD["meta"].get("vor") or None
        self.WECHSEL = _datum(self.VOR["wechsel"]) if self.VOR else None
        self.LEER_VOR = {"dr": 0, "ma": [], "rang": None, "empfehlung": "keine",
                         "warum": "Für die Zeit vor den Begehungen gibt es zu wenige Daten.",
                         "ventil": "", "p_ventil": None, "sommernacht": None, "daemmung": False,
                         "p_daemmung": None, "kapazitaet": False, "auslastung": None, "fehlerbild": "",
                         "sonderfall": ""}
        self.T0 = _datum(D["t0"])
        self.TAG0 = _datum(MD["tag0"])
        self._tag_versatz_h = int((self.T0 - self.TAG0).total_seconds() // 3600)
        self.EFF = {e["m"]: e for e in MD["effizienz"]}

        #Netzreihen über den ganzen Zeitraum (sumP als Float32Array wie im Browser)
        p = self.werte[:, 3]
        gueltig = ~np.isnan(p)
        summe = np.where(gueltig, p, 0.0).sum(axis=0)
        self.sumP = np.where(gueltig.any(axis=0), summe, np.nan).astype(np.float32).astype(float)
        self.nVal = (~np.isnan(self.werte[:, 0])).sum(axis=0)
        sv = np.sort(self.sumP[~np.isnan(self.sumP)])
        self.maxP = max(float(sv[math.floor(len(sv) * 0.99)]), 1.0) if len(sv) else 1.0

        #Farbskalen der Messwerte: 2 bis 98 % über jede fünfte Stunde
        self.bereich = {k: self._qrange(self._reihe(k)) for k in MET}

        self.N, self.E = D["nodes"], D["edges"]
        for e in self.E:
            a, b = self.N[e["a"]], self.N[e["b"]]
            e["P"] = e["p"] if e.get("p") and len(e["p"]) > 1 else [[a["lat"], a["lon"]], [b["lat"], b["lon"]]]
        self.haeuser = [i for i, n in enumerate(self.N) if n["m"] >= 0]
        self.auswahl = sorted(self.haeuser, key=lambda i: sortierschluessel(self.N[i]["name"]))

    # --- Messwerte
    def _reihe(self, k: str) -> np.ndarray:
        return self.spreizung if k == "spr" else self.werte[:, ["vor", "rueck", "fluss", "leist"].index(k)]

    @staticmethod
    def _qrange(arr: np.ndarray) -> list:
        a = arr[:, ::5].ravel()
        a = np.sort(a[~np.isnan(a)])
        if not len(a):
            return [0, 1]
        lo, hi = float(a[math.floor(len(a) * 0.02)]), float(a[math.floor(len(a) * 0.98)])
        return [lo, hi] if hi > lo else [lo, lo + 1]

    def val(self, m: int, f: int, h: int) -> float:
        return float(self.werte[m, f, h])

    def spr(self, m: int, h: int) -> float:
        return float(self.spreizung[m, h])

    def met_wert(self, k: str, m: int, h: int) -> float:
        return float(self._reihe(k)[m, h])

    # --- Zeit
    def zeit(self, h: int) -> datetime:
        return self.T0 + timedelta(hours=h)

    def fmt(self, h: int) -> str:
        d = self.zeit(h)
        return f"{WD[(d.weekday() + 1) % 7]}, {d:%d.%m.%Y}, {d:%H}:00"

    def fmt_date(self, h: int) -> str:
        return f"{self.zeit(h):%d.%m.%y}"

    def fmt_tag(self, t: int) -> str:
        return f"{self.TAG0 + timedelta(days=t):%d.%m.%y}"

    def tag_at(self, h: int) -> int:
        return (self._tag_versatz_h + h) // 24

    def monat_at(self, h: int) -> str:
        return f"{self.zeit(h):%Y-%m}"

    def h_von(self, zeitpunkt: datetime) -> float:
        return (zeitpunkt - self.T0).total_seconds() / 3600

    def set_h(self, v: float) -> int:
        """``setH``: auf ganze Stunden runden und auf den Zeitraum begrenzen."""
        return max(0, min(self.H - 1, js_round(v)))

    def h_vor_begehungen(self) -> int:
        """Knopf „Stand vor den Begehungen“: 14 Tage vor dem Wechseltag."""
        return min(self.H - 1, max(0, self.h_von(self.WECHSEL - timedelta(days=14))))

    def start_h(self) -> int:
        return max(0, min(self.H - 1, self.D["start"]))

    # --- Stand der Bewertung
    def stand(self, h: int, wahl: str) -> str:
        if not self.VOR:
            return "heute"
        if wahl != "auto":
            return wahl
        return "vor" if self.zeit(h) < self.WECHSEL else "heute"

    def stand_text(self, st: str) -> str:
        if st == "vor":
            return "vor den Begehungen (Winter " + js_str(self.VOR["winter_name"]) + " und Sommer 2024)"
        return "heute (Winter " + js_str(self.MD["meta"]["winter"]) + " mit dem Sommer danach)"

    def S(self, z: str, st: str) -> Optional[dict]:
        s = self.MST.get(z)
        if not s or st != "vor":
            return s
        v = s.get("vor")
        return {**s, **(v if wahr(v) else self.LEER_VOR)}

    @staticmethod
    def HS(n: dict, st: str):
        return n.get("hs_vor") if st == "vor" else n.get("hs")

    # --- Färbungen aus den Modellen
    def meld_klasse(self, n: dict, h: int) -> Optional[str]:
        if not n.get("st"):
            return None
        t = self.tag_at(h)
        schl = schl_netz = bess = 0
        ueb = False
        for z in n["st"]:
            for a in self.MEL.get(z) or []:
                if not wahr(a[4]) or a[0] > t or a[0] <= t - self.MT:
                    continue
                if a[1] > 0:
                    schl += 1
                    if wahr(a[3]):
                        schl_netz += 1
                else:
                    bess += 1
            u = self.UEB.get(z)
            if u and 0 <= t < len(u) and u[t] == "1":
                ueb = True
        if schl:
            return "netz" if schl == schl_netz else "schl"
        if bess:
            return "bess"
        return "ruhig" if ueb else "aus"

    def kat_klassen(self, k: str) -> list:
        if k == "dring":
            return [(i, DR_NAME[i], DR_FARBE[i]) for i in (3, 2, 1, 0)]
        if k == "mass":
            return [(c, *MA[c]) for c in MA]
        if k == "meld":
            return [(c, *ME[c]) for c in ME]
        return [(i, *PO[i]) for i in (3, 2, 1)]

    def kat_key(self, k: str, n: dict, h: int, st: str):
        if k == "dring":
            hs = self.HS(n, st)
            return hs.get("dr") if wahr(hs) else None
        if k == "mass":
            hs = self.HS(n, st)
            return hs.get("ma") if wahr(hs) else None
        if k == "meld":
            return self.meld_klasse(n, h)
        hs = n.get("hs")
        return hs["po"] if wahr(hs) and wahr(hs.get("po")) else None

    def kat_name(self, k: str) -> str:
        return {"dring": "Dringlichkeit der Empfehlung", "mass": "Maßnahme und Verdacht",
                "meld": "Meldungen der Wächter", "pot": "Potenzial im Netzvergleich"}[k]

    def kat_l2(self, k: str, h: int, wahl: str) -> str:
        st = self.stand(h, wahl)
        if k == "dring":
            zusatz = "" if not self.VOR else (" Wechselt mit dem Zeitregler am 01.09.2024." if wahl == "auto"
                                              else " Saison fest gewählt.")
            return "Stand " + self.stand_text(st) + "." + zusatz
        if k == "mass":
            return "Bei mehreren Maßnahmen zählt die vorderste. Stand " + self.stand_text(st) + "."
        if k == "meld":
            return (f"Meldungen der letzten {self.MT} Tage bis {self.fmt_date(h)}. "
                    "Heiztage: Tagesmonitor, sonst Prognose-LSTM.")
        return "Abstand zum besten Viertel, Winter " + js_str(self.MD["meta"]["winter"]) + "."

    def kat_farbe(self, k: str, key) -> Optional[str]:
        if key is None or isinstance(key, bool):
            return None
        return next((f for c, _, f in self.kat_klassen(k) if c == key and type(c) is type(key)), None)

    def zaehle(self, k: str, h: int, st: str) -> tuple:
        c, ohne = {}, 0
        for i in self.haeuser:
            key = self.kat_key(k, self.N[i], h, st)
            if key is None:
                ohne += 1
            else:
                c[key] = c.get(key, 0) + 1
        return c, ohne

    # --- Karte
    def haus_stil(self, i: int, h: int, wahl: str, metric: str, sel: int) -> dict:
        """``updateNodes`` für ein Haus: Füllfarbe, Deckkraft, Rand."""
        n = self.N[i]
        if n["m"] < 0:
            r = 7 if n.get("src") else (3.5 if self.D["punkte"] else 0)
            return {"radius": r, "fill": "#aaaaaa", "op": 0.8 if (self.D["punkte"] and not n.get("src")) else 0.95,
                    "weight": 3 if n.get("src") else (1 if self.D["punkte"] else 0),
                    "color": "#e11d48" if n.get("src") else "#222222"}
        if metric in MODELL_FAERBUNGEN:
            c = self.kat_farbe(metric, self.kat_key(metric, n, h, self.stand(h, wahl)))
            fill, op = (c or GRAU), (0.95 if c else 0.45)
        else:
            v = self.met_wert(metric, n["m"], h)
            lo, hi = self.bereich[metric]
            fill = GRAU if math.isnan(v) else color_at(MET[metric][2], (v - lo) / (hi - lo))
            op = 0.45 if math.isnan(v) else 0.95
        return {"radius": 6 + 2 * min((n.get("k") or 1) - 1, 3), "fill": fill, "op": op,
                "weight": 4 if i == sel else 1, "color": None if i == sel else "#222222"}

    def kante(self, e: dict, h: int) -> dict:
        """``updateEdges`` für eine Leitung: Last, Breite, Deckkraft, Tempo der Fließpunkte."""
        load, miss, tot = 0.0, 0, 0
        for m, c in e["c"]:
            tot += 1
            p = self.val(m, 3, h)
            if math.isnan(p):
                miss += 1
            else:
                load += p * c
        rel = min(load / self.maxP, 1)
        #negative Leistung (Messfehler): Math.sqrt gibt NaN, der Browser zeichnet dann 1 px
        w = 2 + 5 * math.sqrt(rel) if rel >= 0 else math.nan
        op = 0.25 if tot == 0 else (0.45 if miss > 0 else 0.95)
        dw = math.nan if math.isnan(w) else max(w * 0.45, 1.5)
        dur = 4 / (0.4 + 3 * rel)
        return {"load": load, "miss": miss, "tot": tot, "w": w, "op": op, "dw": dw,
                "aktiv": load > 0.05, "dur": to_fixed(dur, 2) + "s" if math.isfinite(dur) and dur > 0 else None}

    def node_tip(self, n: dict, h: int, wahl: str, metric: str) -> str:
        if n.get("src"):
            return "<b>" + esc(n["name"]) + "</b><br>Erzeuger (Einspeisung)"
        if n["m"] < 0:
            return "<b>" + esc(n["name"]) + "</b><br>Abzweig oder Punkt ohne Zähler"
        m = n["m"]
        mod = ""
        hs = self.HS(n, self.stand(h, wahl))
        if wahr(hs):
            mod = f"<br><b>{esc(MA[hs['ma']][0])}</b> · Dringlichkeit {esc(DR_NAME[hs['dr']])}"
        if metric == "meld":
            k = self.meld_klasse(n, h)
            if k:
                mod += "<br>Meldungen: " + esc(ME[k][0])
        return (f"<b>{esc(n['name'])}</b>{mod}<br>Vorlauf {f1(self.val(m, 0, h))} °C · Rücklauf "
                f"{f1(self.val(m, 1, h))} °C<br>Spreizung {f1(self.spr(m, h))} K<br>Durchfluss "
                f"{f1(self.val(m, 2, h), 0)} l/h · Leistung {f1(self.val(m, 3, h))} kW"
                + ("<br><i>Position geschätzt</i>" if n.get("est") else ""))

    def edge_tip(self, e: dict, k: dict) -> str:
        if k["tot"] == 0:
            miss = "Keine Zähler stromabwärts"
        elif k["miss"] > 0:
            miss = f"{k['miss']} von {k['tot']} Häusern stromabwärts ohne Daten, Wert zu niedrig"
        else:
            miss = "Alle Häuser stromabwärts mit Daten"
        return (f"<b>{esc(self.N[e['a']]['name'])} → {esc(self.N[e['b']]['name'])}</b><br>Leistung "
                f"{f1(k['load'])} kW<br><span style=\"opacity:.8\">{miss}</span>")

    def legende_html(self, metric: str, h: int, wahl: str) -> str:
        if metric in MODELL_FAERBUNGEN:
            c, ohne = self.zaehle(metric, h, self.stand(h, wahl))
            return (f"<b>{esc(self.kat_name(metric))}</b>"
                    + "".join(f'<div class="kat"><i style="background:{farbe}"></i>{esc(name)}<b>{c.get(k, 0)}</b></div>'
                              for k, name, farbe in self.kat_klassen(metric))
                    + (f'<div class="kat"><i style="background:{GRAU};opacity:.5"></i>keine Modellergebnisse<b>{ohne}</b></div>'
                       if ohne else "")
                    + f'<div class="l2">Zahl = Häuser auf der Karte. {esc(self.kat_l2(metric, h, wahl))}</div>')
        name, unit, stops = MET[metric]
        lo, hi = self.bereich[metric]
        return (f'<b>{name} in {unit}</b><div class="grad" style="background:linear-gradient(90deg,{",".join(stops)})"></div>'
                f'<div class="row"><span>{to_fixed(lo, 1)}</span><span>{to_fixed(hi, 1)}</span></div>'
                '<div class="l2">Grau: keine Daten oder kein Durchfluss</div>')

    # --- Seitenleiste „Netz“
    def netz_werte(self, h: int) -> tuple:
        n, wf, sv_, sr = 0, 0.0, 0.0, 0.0
        for m in range(self.M):
            v, r, f = self.val(m, 0, h), self.val(m, 1, h), self.val(m, 2, h)
            if not math.isnan(v):
                n += 1
            if f > self.FMIN and not math.isnan(v) and not math.isnan(r):
                wf += f
                sv_ += v * f
                sr += r * f
        return n, wf, sv_, sr

    def stats_html(self, h: int, wahl: str) -> str:
        n, wf, sv_, sr = self.netz_werte(h)
        st = self.stand(h, wahl)
        e = self.EFF.get(self.monat_at(h))
        cm, _ = self.zaehle("meld", h, st)
        cd, _ = self.zaehle("dring", h, st)
        cp, _ = self.zaehle("pot", h, st)
        if e:
            eff = (row("Wärme je m³ Heizwasser", de(e["kwh_m3"], 1) + " kWh/m³")
                   + row("Rücklauf / Spreizung", de(e["rl"], 1) + " °C / " + de(e["spr"], 1) + " K")
                   + ("" if e["ok"] else f'<div class="muted klein">Nur {js_str(e["n"])} Stationen mit Daten, '
                                         'mit anderen Monaten nicht vergleichbar.</div>'))
        else:
            eff = '<div class="muted klein">kein Wert für diesen Monat</div>'
        netz = cm.get("netz", 0)
        winter = self.VOR["winter_name"] if st == "vor" else self.MD["meta"]["winter"]
        return (row("Gesamtleistung", f1(self.sumP[h]) + " kW")
                + row("Vorlauf / Rücklauf (gewichtet)",
                      to_fixed(sv_ / wf, 1) + " / " + to_fixed(sr / wf, 1) + " °C" if wf else "–")
                + row("Spreizung (gewichtet)", to_fixed((sv_ - sr) / wf, 1) + " K" if wf else "–")
                + row("Häuser mit Messwerten", f"{n} von {self.M}")
                + "<h3>Netzeffizienz im Monat</h3>" + eff
                + f"<h3>Meldungen der letzten {self.MT} Tage</h3>"
                + row("Häuser mit Verschlechterung", str(cm.get("schl", 0) + netz)
                      + (f" (davon {netz} zugleich mit vielen)" if netz else ""))
                + row("Häuser nur mit Verbesserung", cm.get("bess", 0))
                + f"<h3>Handlungsbedarf, Winter {esc(winter)}</h3>"
                + row("Dringlichkeit hoch / mittel / niedrig", f"{cd.get(3, 0)} / {cd.get(2, 0)} / {cd.get(1, 0)}")
                + row("Potenzial hoch", f"{cp.get(3, 0)} Häuser"))

    def zeit_label(self, h: int) -> str:
        return self.fmt(h) + (" (keine Daten)" if self.netz_werte(h)[0] == 0 else "")

    # --- Hausfenster
    def verdacht(self, s: dict) -> str:
        z = []
        sn = _feld(s, "sommernacht")
        z.append("Ventil: " + (f"{esc(s['ventil'])} (Score {de(_feld(s, 'p_ventil'))}, Grenze {de(self.G_['ventil'], 1)})"
                               if wahr(_feld(s, "ventil")) else "–")
                 + (f" · Durchfluss in {pz(sn)} der Sommernächte" if sn is not None else "")
                 + (" · Fehlerbild „ventil“ im Netzvergleich" if _feld(s, "fehlerbild") == "ventil" else ""))
        z.append("Dämmung: " + (f"Hinweis (Score {de(_feld(s, 'p_daemmung'))})" if wahr(_feld(s, "daemmung"))
                                else "kein Hinweis"))
        ausl = _feld(s, "auslastung")
        z.append("Kapazität: " + ("–" if ausl is None else f"Spitzenlast {pz(ausl)} des Anschlusswerts"
                                  + (", Anschluss vermutlich zu groß" if wahr(_feld(s, "kapazitaet")) else "")))
        if wahr(_feld(s, "sonderfall")):
            z.append("Sonderfall: " + esc(s["sonderfall"]) + ", erst Messdaten prüfen")
        return "<br>".join(z)

    def letzte_meldungen(self, z: str, h: int) -> str:
        t = self.tag_at(h)
        a = [x for x in (self.MEL.get(z) or []) if x[0] <= t][-4:][::-1]
        if not a:
            return '<span class="muted">keine bis zum gewählten Zeitpunkt</span>'
        return "<br>".join(f"{self.fmt_tag(x[0])} · {QN[x[2]]}: {esc(x[5])}"
                           + (" (schlechter)" if x[1] > 0 else " (besser)")
                           + ("" if wahr(x[4]) else " · <i>nur Hinweis</i>")
                           + (" · viele Stationen zugleich" if wahr(x[3]) else "") for x in a)

    def modell_block(self, z: str, h: int, wahl: str) -> str:
        st = self.stand(h, wahl)
        s = self.S(z, st)
        if not s:
            return f'<div class="zaehler"><p class="muted">Zähler {esc(z)}: keine Modellergebnisse.</p></div>'
        ma = s["ma"][0] if len(s["ma"]) else "keine"
        dr = s["dr"]
        rang = _feld(s, "rang")
        von = len(self.MD["liste_vor"]) if st == "vor" else self.MD["meta"]["stationen"]
        netz_rang = _feld(s, "netz_rang")
        if wahr(netz_rang):
            netz = (f"Rang {js_str(netz_rang)} von {js_str(_feld(s, 'netz_n'))} · Potenzial "
                    f"{esc(s['potenzial'] if wahr(_feld(s, 'potenzial')) else '–')}"
                    + (f'<br><span class="klein">{esc(s["luecke"])}</span>' if wahr(_feld(s, "luecke")) else ""))
        else:
            netz = '<span class="muted">kein Netzvergleich (zu wenige Winterdaten)</span>'
        nw = _feld(s, "netz_winter")
        return ('<div class="zaehler">'
                + f'<div class="emp" style="border-color:{MA[ma][1]}"><div class="kopf"><span class="badge" '
                  f'style="background:{DR_FARBE[dr]}">'
                + ("Dringlichkeit " + DR_NAME[dr] if dr else DR_NAME[0]) + "</span>"
                + f'<span class="muted klein">Zähler {esc(z)}'
                + (f" · Platz {js_str(rang)} von {js_str(von)}" if wahr(rang) else "") + "</span></div>"
                + f'<div class="muted klein">Stand {esc(self.stand_text(st))}</div>'
                + f"<b>{esc('Keine Maßnahme empfohlen' if s['empfehlung'] == 'keine' else s['empfehlung'])}</b>"
                + (f'<div class="muted klein">{esc(s["warum"])}</div>' if wahr(_feld(s, "warum")) else "") + "</div>"
                + blk("Leistung im Netz (Winter " + esc(nw if wahr(nw) else self.MD["meta"]["winter"]) + ")", netz)
                + blk("Verdacht auf Fehlerart", self.verdacht(s))
                + blk("Veränderung, letzte Heizperiode", esc(_feld(s, "veraenderung")))
                + blk("Meldungen bis zum gewählten Zeitpunkt", self.letzte_meldungen(z, h))
                + blk("Befund bei der Begehung", esc(_feld(s, "befund")))
                + "</div>")

    def node_info_html(self, sel: int, h: int, wahl: str) -> str:
        if sel < 0:
            return '<p class="muted">Haus auf der Karte oder in der Liste auswählen.</p>'
        n = self.N[sel]
        m = n["m"]
        zs = n["z"].split(", ") if n.get("z") else []
        return (('<p class="muted klein">Position geschätzt</p>' if n.get("est") else "")
                + "".join(self.modell_block(z, h, wahl) for z in zs)
                + "<h3>Messwerte zur gewählten Stunde</h3>"
                + row("Vorlauf / Rücklauf", f1(self.val(m, 0, h)) + " / " + f1(self.val(m, 1, h)) + " °C")
                + row("Spreizung", f1(self.spr(m, h)) + " K") + row("Durchfluss", f1(self.val(m, 2, h), 0) + " l/h")
                + row("Leistung", f1(self.val(m, 3, h)) + " kW"))

    # --- Diagramme
    def win_range(self, h: int, win: int) -> tuple:
        n = min(win, self.H)
        i0 = max(0, min(self.H - n, h - n // 2))
        return i0, i0 + n - 1

    @staticmethod
    def diagramm(reihen: list, i0: int, i1: int, zero: bool, iw: float) -> dict:
        """Rechenteil von ``drawChart``: Wertebereich, fünf Gitterlinien, Mittel je Bildpunkt-Gruppe.

        ``reihen`` sind ganze Zeitreihen (numpy), ``iw`` die Breite der Zeichenfläche in Pixeln.
        """
        n = i1 - i0 + 1
        lo, hi = math.inf, -math.inf
        for s in reihen:
            a = s[i0:i1 + 1]
            a = a[~np.isnan(a)]
            if len(a):
                lo, hi = min(lo, float(a.min())), max(hi, float(a.max()))
        if not math.isfinite(lo):
            lo, hi = 0.0, 1.0
        if zero:
            lo = min(lo, 0)
        if hi - lo < 1e-6:
            hi = lo + 1
        pad = (hi - lo) * 0.06
        hi += pad
        if not zero or lo < 0:
            lo -= pad
        ticks = [lo + (hi - lo) * k / 4 for k in range(5)]
        labels = [to_fixed(v, 0) if (hi - lo) > 20 else to_fixed(v, 1) for v in ticks]
        step = max(1, math.floor(n / (iw * 1.5)))
        linien = []
        for s in reihen:
            xs, ys = [], []
            for i in range(i0, i1 + 1, step):
                a = s[i:min(i + step, i1 + 1)]
                a = a[~np.isnan(a)]
                if not len(a):
                    xs.append(i + (step - 1) / 2)
                    ys.append(None)     #Lücke: Linie absetzen
                    continue
                xs.append(i + (step - 1) / 2)
                ys.append(float(a.sum() / len(a)))
            linien.append((xs, ys))
        return {"lo": lo, "hi": hi, "ticks": ticks, "labels": labels, "linien": linien}

    # --- Handlungsliste
    def liste(self, h: int, wahl: str, fm: str, alle: bool) -> list:
        """``renderListe``: [(zähler, index auf der Karte oder -1, eintrag), …]."""
        st = self.stand(h, wahl)
        zeilen = []
        for z, k in (self.MD["liste_vor"] if st == "vor" else self.MD["liste"]):
            s = self.S(z, st)
            if not alle and s["dr"] == 0:
                continue
            if fm and fm not in s["ma"]:
                continue
            zeilen.append((z, k, s))
        return zeilen

    def liste_zeile_html(self, z: str, k: int, s: dict) -> str:
        """Eine Zeile wie in der HTML-Tabelle (für den Abgleich in den Tests)."""
        knopf = (f'<button data-k="{k}">Karte</button>' if k >= 0
                 else '<span class="muted klein">nicht auf der Karte</span>')
        rang = _feld(s, "rang")
        return (f"<tr><td>{js_str(rang) if wahr(rang) else ''}</td><td>{esc(z)}</td>"
                f'<td><span class="badge" style="background:{DR_FARBE[s["dr"]]}">{esc(DR_NAME[s["dr"]])}</span></td>'
                f'<td>{esc(s["empfehlung"])}</td><td class="klein">{esc(s["warum"])}</td>'
                f'<td class="klein">{esc(_feld(s, "befund"))}</td><td>{knopf}</td></tr>')

    # --- Texte mit Werten aus den Paketen (Reiter „So funktioniert's“)
    def info_werte(self) -> dict:
        pk = self.MD["meta"].get("pakete") or {}
        return {"winter": js_str(self.MD["meta"]["winter"]), "daemmung": de(self.G_["daemmung"], 1),
                "vertrag": pz(self.G_["vertrag"]),
                "punkte": "Graue Punkte sind Abzweige und Anschlussstellen am Rohr. " if self.D["punkte"] else "",
                "stand": ("Stand: Modellpakete " + ", ".join(f"{k} {v}" for k, v in pk.items())
                          + "; angewendet am " + js_str(self.MD["meta"]["erstellt"])[:10] + "; Messdaten bis "
                          + js_str(self.MD["meta"]["datenende"]) + ". Zahlen zur Güte aus Notebook 35.")}
