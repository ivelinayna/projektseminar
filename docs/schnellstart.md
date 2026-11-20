# Schnellstart

Diese Seite fasst alle Befehle in der Reihenfolge der Ausführung zusammen. Die Schritte im Einzelnen erläutern
[Vorbereitung](vorbereitung.md), [Start mit Docker](docker.md), [Lokaler Start ohne Docker](lokal.md) und
[Ausführung bis zum Dashboard](ausfuehrung.md).

Für beide Wege muss das Projekt geholt sein, die Daten der ÜZ müssen in `data/raw/` und die Handliste mit Koordinaten
in `data/manual/` liegen (siehe [Vorbereitung](vorbereitung.md)).

## Mit Docker

```bash
docker compose build
docker compose run --rm jupyter python -m src.weather
docker compose run --rm jupyter python -m src.main
docker compose run --rm jupyter python -m src.meter_quality
docker compose run --rm jupyter python -m src.detect_real
docker compose up jupyter        #http://localhost:8888, dann Notebook 00, danach der Reihe nach
```

Dashboard, nachdem die Notebooks 00 und 25 bis 29 gelaufen sind:

```bash
docker compose run --rm jupyter python -m src.prognose_waechter --bauen --gegenprobe
docker compose run --rm jupyter python -m src.normalmodell_waechter --bauen
docker compose run --rm jupyter python -m src.fehlerklassen --bauen --gegenprobe
#in Jupyter: Notebook 35 (empfohlen)
docker compose run --rm jupyter python -m src.dashboard_daten
#in Jupyter: Notebook 31, dann Notebook 37
docker compose up dashboard      #http://localhost:8000/fernwaerme_dashboard_final.html
```

## Lokal

```bash
python -m venv .venv
.venv\Scripts\activate           #Windows
source .venv/bin/activate        #Linux, macOS
pip install -r requirements.txt
pip install jupyterlab pytest

python -m src.weather
python -m src.main
python -m src.meter_quality
python -m src.detect_real
jupyter lab                      #Notebook 00, danach der Reihe nach
```

Dashboard, nachdem die Notebooks 00 und 25 bis 29 gelaufen sind:

```bash
python -m src.prognose_waechter --bauen --gegenprobe
python -m src.normalmodell_waechter --bauen
python -m src.fehlerklassen --bauen --gegenprobe
#in Jupyter: Notebook 35 (empfohlen)
python -m src.dashboard_daten
#in Jupyter: Notebook 31, dann Notebook 37
```

Ergebnis: `notebooks/fernwaerme_dashboard_final.html`, per Doppelklick im Browser öffnen.

## Weitere Befehle

| Zweck | Befehl |
|---|---|
| Tests | `python -m pytest -q` |
| neue Zählerdaten einspielen | `python -m src.aktualisieren` |
| Doku lokal | `pip install -r docs/requirements.txt`, dann `mkdocs serve` |
| Doku mit Docker | `docker compose up docs`, dann http://localhost:8001 |
