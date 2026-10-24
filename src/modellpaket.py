"""Modellpakete: ein gelerntes Modell mit allem, was zum Anwenden gehört.

Warum es das braucht
--------------------
Die Notebooks speichern bisher nur Gewichte (`notebooks/models/*.pt`). Zum
Anwenden auf neue Tage braucht ein Modell aber mehr:

- die Skalierung (z. B. das 95-%-Quantil des Durchflusses je Zähler),
- die Kalibrierung (normale Schwankung je Station, Faktor je Jahreszeit),
- die Schwelle und die Alarmregel,
- und das Wissen, woraus es gelernt wurde (Datenstand, Lernzeitraum,
  Code-Stand), damit später klar ist, was man vor sich hat.

Fehlt eines davon, rechnet man im Betrieb mit einer anderen Skalierung
oder Schwelle als im Notebook, und die geprüften Zahlen gelten nicht mehr.

Aufbau eines Pakets
-------------------
Ein Paket ist ein Ordner ``models/<name>/<version>/``:

    paket.json      Metadaten: Name, Aufgabe, Version, erstellt am,
                    Datenstand, Lernzeitraum, Code-Stand (git), Versionen
                    der Bibliotheken, Parameter, Prüfkennzahlen und je
                    Datei eine SHA-256-Prüfsumme
    <dateien>       was das Modell braucht, z. B. ``gewichte.pt``,
                    ``kalibrierung.csv``, ``modell.joblib``

``models/<name>/AKTUELL`` enthält die Version, die der Betrieb benutzt.
Ältere Versionen bleiben liegen; zurück geht es mit `setze_aktuell`.

``models/`` ist gitignored: Die Pakete enthalten Zählernummern und sind
aus Firmendaten gelernt.

    python -m src.modellpaket            # Übersicht aller Pakete
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
META = "paket.json"
AKTUELL = "AKTUELL"
#Bibliotheken, deren Version im Paket steht (nur wenn installiert)
BIBLIOTHEKEN = ("numpy", "pandas", "scikit-learn", "torch", "xgboost")


class PaketFehler(RuntimeError):
    """Paket fehlt, ist unvollständig oder wurde nach dem Speichern verändert."""


def _sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_stand(root: Path = ROOT) -> Dict[str, Any]:
    """Commit und ob es ungesicherte Änderungen gibt; leer ohne git."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                capture_output=True, text=True, timeout=10)
        status = subprocess.run(["git", "status", "--porcelain", "src"],
                                cwd=root, capture_output=True, text=True,
                                timeout=10)
    except (OSError, subprocess.SubprocessError):
        return {}
    if commit.returncode != 0:
        return {}
    return {"commit": commit.stdout.strip(),
            "src_geaendert": bool(status.stdout.strip())}


def bibliotheken() -> Dict[str, str]:
    from importlib import metadata
    aus = {"python": platform.python_version()}
    for name in BIBLIOTHEKEN:
        try:
            aus[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return aus


def _json_wert(wert: Any) -> Any:
    """Zeitstempel, numpy-Zahlen und Pfade JSON-tauglich machen."""
    if isinstance(wert, (pd.Timestamp, datetime)):
        return wert.isoformat()
    if isinstance(wert, Path):
        return str(wert)
    if hasattr(wert, "item"):
        return wert.item()
    if isinstance(wert, dict):
        return {str(k): _json_wert(v) for k, v in wert.items()}
    if isinstance(wert, (list, tuple)):
        return [_json_wert(v) for v in wert]
    return wert


@dataclass
class Paket:
    """Ein geladenes Paket: Ordner und Metadaten, Dateien auf Abruf."""

    ordner: Path
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.meta["name"]

    @property
    def version(self) -> str:
        return self.meta["version"]

    @property
    def parameter(self) -> Dict[str, Any]:
        return self.meta.get("parameter", {})

    def pfad(self, datei: str) -> Path:
        if datei not in self.meta.get("dateien", {}):
            raise PaketFehler(f"{self.name} {self.version}: keine Datei {datei}")
        return self.ordner / datei

    def tabelle(self, datei: str, **kw) -> pd.DataFrame:
        return pd.read_csv(self.pfad(datei), **kw)

    def json(self, datei: str) -> Any:
        return json.loads(self.pfad(datei).read_text(encoding="utf-8"))

    def pruefe(self) -> None:
        """Bricht ab, wenn eine Datei fehlt oder sich verändert hat."""
        for datei, soll in self.meta.get("dateien", {}).items():
            p = self.ordner / datei
            if not p.exists():
                raise PaketFehler(f"{self.name} {self.version}: {datei} fehlt")
            if _sha256(p) != soll:
                raise PaketFehler(
                    f"{self.name} {self.version}: {datei} wurde nach dem "
                    "Speichern verändert (Prüfsumme passt nicht)")


def schreibe_paket(name: str, aufgabe: str,
                   dateien: Mapping[str, Callable[[Path], None]],
                   parameter: Optional[Mapping[str, Any]] = None,
                   kennzahlen: Optional[Mapping[str, Any]] = None,
                   datenstand: Any = None, lernzeitraum: Any = None,
                   beschreibung: str = "", quelle: str = "",
                   version: Optional[str] = None, wurzel: Path = MODELS,
                   aktuell: bool = True) -> Paket:
    """Paket anlegen.

    ``dateien`` bildet Dateinamen auf Funktionen ab, die die Datei an den
    übergebenen Pfad schreiben, z. B.
    ``{"kalibrierung.csv": lambda p: kal.to_csv(p)}``. So bleibt dieses
    Modul frei von torch oder scikit-learn.

    ``datenstand`` ist der letzte Zeitstempel der Daten, aus denen gelernt
    oder kalibriert wurde, ``lernzeitraum`` ein Paar (von, bis) oder ein
    Text. ``kennzahlen`` sind die Prüfergebnisse, mit denen das Modell
    freigegeben wurde. Mit ``aktuell=True`` wird die neue Version gleich
    zur Betriebsversion.
    """
    version = version or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ordner = Path(wurzel) / name / version
    if ordner.exists():
        raise PaketFehler(f"{ordner} gibt es schon")
    ordner.mkdir(parents=True)
    pruefsummen = {}
    for datei, schreiber in dateien.items():
        schreiber(ordner / datei)
        pruefsummen[datei] = _sha256(ordner / datei)
    meta = {
        "name": name, "aufgabe": aufgabe, "version": version,
        "erstellt": datetime.now().isoformat(timespec="seconds"),
        "beschreibung": beschreibung, "quelle": quelle,
        "datenstand": _json_wert(datenstand),
        "lernzeitraum": _json_wert(lernzeitraum),
        "parameter": _json_wert(dict(parameter or {})),
        "kennzahlen": _json_wert(dict(kennzahlen or {})),
        "code": git_stand(), "bibliotheken": bibliotheken(),
        "dateien": pruefsummen,
    }
    (ordner / META).write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    if aktuell:
        setze_aktuell(name, version, wurzel)
    return Paket(ordner, meta)


def versionen(name: str, wurzel: Path = MODELS) -> list:
    ordner = Path(wurzel) / name
    if not ordner.is_dir():
        return []
    return sorted(p.name for p in ordner.iterdir()
                  if p.is_dir() and (p / META).exists())


def aktuelle_version(name: str, wurzel: Path = MODELS) -> Optional[str]:
    zeiger = Path(wurzel) / name / AKTUELL
    if zeiger.exists():
        return zeiger.read_text(encoding="utf-8").strip() or None
    alle = versionen(name, wurzel)
    return alle[-1] if alle else None


def setze_aktuell(name: str, version: str, wurzel: Path = MODELS) -> None:
    if version not in versionen(name, wurzel):
        raise PaketFehler(f"{name}: keine Version {version}")
    (Path(wurzel) / name / AKTUELL).write_text(version + "\n", encoding="utf-8")


def lade_paket(name: str, version: Optional[str] = None,
               wurzel: Path = MODELS, pruefen: bool = True) -> Paket:
    """Paket laden, ohne Version die Betriebsversion (``AKTUELL``)."""
    version = version or aktuelle_version(name, wurzel)
    if version is None:
        raise PaketFehler(
            f"kein Paket {name} unter {Path(wurzel) / name}. Erst bauen, "
            "mit python -m src.prognose_waechter --bauen, src.normalmodell_waechter "
            "--bauen bzw. src.fehlerklassen --bauen")
    ordner = Path(wurzel) / name / version
    if not (ordner / META).exists():
        raise PaketFehler(f"{ordner / META} fehlt")
    paket = Paket(ordner, json.loads((ordner / META).read_text(encoding="utf-8")))
    if pruefen:
        paket.pruefe()
    return paket


def uebersicht(wurzel: Path = MODELS) -> pd.DataFrame:
    """Eine Zeile je Paketversion, die Betriebsversion markiert."""
    zeilen = []
    wurzel = Path(wurzel)
    if wurzel.is_dir():
        for ordner in sorted(p for p in wurzel.iterdir() if p.is_dir()):
            aktiv = aktuelle_version(ordner.name, wurzel)
            for v in versionen(ordner.name, wurzel):
                m = json.loads((ordner / v / META).read_text(encoding="utf-8"))
                lz = m.get("lernzeitraum", "")
                if isinstance(lz, (list, tuple)):
                    lz = " bis ".join(str(x)[:10] for x in lz)
                zeilen.append({
                    "name": m["name"], "version": v, "aktuell": v == aktiv,
                    "aufgabe": m.get("aufgabe", ""),
                    "erstellt": m.get("erstellt", ""),
                    "datenstand": m.get("datenstand", ""),
                    "lernzeitraum": lz,
                    "commit": (m.get("code") or {}).get("commit", "")[:8],
                    "beschreibung": m.get("beschreibung", "")})
    return pd.DataFrame(zeilen, columns=[
        "name", "version", "aktuell", "aufgabe", "erstellt", "datenstand",
        "lernzeitraum", "commit", "beschreibung"])


def main() -> None:
    tab = uebersicht()
    if tab.empty:
        print(f"Keine Pakete unter {MODELS}.")
        return
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(tab.drop(columns=["beschreibung"]).to_string(index=False))


if __name__ == "__main__":
    main()
