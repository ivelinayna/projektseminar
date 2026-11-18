# Schnellstart

Zwei Wege: lokal mit Python oder mit Docker ([Docker](docker.md)). Beide brauchen die Rohdaten der ÜZ. Sie liegen nicht
im Repo.

## 1 Rohdaten ablegen

- Die Dateien der ÜZ nach `data/raw/` kopieren. Welche Dateien das sind, steht unter [Daten](daten.md).
- Handgepflegte Listen mit Adressen gehören nach `data/manual/`.
- Beide Ordner sind gitignored. Nichts davon committen.

## 2 Lokal einrichten

Python 3.11 wird empfohlen.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux, macOS
pip install -r requirements.txt
pip install jupyterlab
```

- `torch` und `xgboost` brauchen nur die Notebooks 27 bis 29, 34 und 35 und die Modellpakete.
- Ohne Grafikkarte läuft alles auf der CPU, nur langsamer.

## 3 Vorbereitende Befehle

Aus dem Projektordner:

```bash
python -m src.weather        # Außentemperatur vom DWD holen (einmal, danach Cache)
python -m src.main           # Graphen, Karten, Begehungstabelle (inspections_tidy.csv)
```

## 4 Notebooks ausführen

- Jupyter im Projektordner starten: `jupyter lab`.
- Die Notebooks liegen in `notebooks/` und müssen dort bleiben. Viele Zellen suchen den Projektordner relativ dazu.
- Immer zuerst Notebook 00 ausführen. Es bereitet die Stundenreihen auf. Alle anderen Notebooks lesen dieses Ergebnis.
- Danach in Nummernfolge. Welche Notebooks voneinander abhängen, steht unter [Notebooks](notebooks.md).

## 5 Modelle und Dashboard

```bash
python -m src.prognose_waechter --bauen --gegenprobe
python -m src.normalmodell_waechter --bauen
python -m src.fehlerklassen --bauen --gegenprobe
python -m src.dashboard_daten     # Modellergebnisse nach outputs/dashboard/
```

- Die Modellpakete landen in `models/` (gitignored). Notebook 35 baut sie ebenfalls.
- Danach Notebook 31 (Netz-Cache) und Notebook 37 (Dashboard) ausführen. Mehr unter [Dashboard](dashboard.md).

## 6 Neue Zählerdaten einspielen

```bash
python -m src.aktualisieren
```

- Führt Notebook 00 neu aus, holt die Außentemperatur und rechnet Netzvergleich, Tagesmonitor und Priorität.
- Ergebnis: Stationsblätter, `status.csv` und ein Kurzbericht unter `outputs/`.

## 7 Tests

```bash
python -m pytest -q
```

- Die meisten Tests laufen ohne Rohdaten.
- Einige Tests brauchen die Begehungstabelle und werden sonst übersprungen.

## 8 Doku lokal ansehen

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

Dann im Browser `http://127.0.0.1:8000` öffnen. Read the Docs baut dieselbe Seite aus `mkdocs.yml` und
`.readthedocs.yaml`.
