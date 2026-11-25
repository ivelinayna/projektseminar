# Schnellstart

Diese Seite fasst alle Schritte in der Reihenfolge der Ausführung zusammen. Ausführlich erläutert werden sie unter
[Vorbereitung](vorbereitung.md), [Start mit Docker](docker.md), [Lokaler Start ohne Docker](lokal.md) und
[Ausführung bis zum Dashboard](ausfuehrung.md).

## Voraussetzungen

Für beide Wege gilt (siehe [Vorbereitung](vorbereitung.md)):

- Das Repository ist mit `git clone https://github.com/ivelinayna/projektseminar.git` heruntergeladen, und alle Befehle
  werden im Ordner `projektseminar` ausgeführt.
- Die Daten der ÜZ liegen in `data/raw/`, die Handliste mit Koordinaten in `data/manual/`.

Befehle werden im Terminal (Windows: PowerShell) im Projektordner eingegeben, eine Zeile nach der anderen. Jede Zeile
erst ausführen, wenn die vorige fertig ist (siehe
[Befehle im Terminal ausführen](vorbereitung.md#befehle-im-terminal-ausfuhren)).

Die Notebooks werden in JupyterLab einzeln geöffnet und über *Run → Run All Cells* ausgeführt, zuerst Notebook 00,
danach die übrigen in Nummernfolge. Sie starten sich nicht gegenseitig.

## Mit Docker

### 1 Image bauen und vorbereiten

```bash
docker compose build
docker compose run --rm jupyter python -m src.weather
docker compose run --rm jupyter python -m src.main
docker compose run --rm jupyter python -m src.meter_quality
docker compose run --rm jupyter python -m src.detect_real
```

### 2 Notebooks ausführen

```bash
docker compose up jupyter
```

JupyterLab ist danach im Browser unter http://localhost:8888 erreichbar. Das Terminalfenster offen lassen, JupyterLab
läuft nur, solange es geöffnet ist. Für die folgenden Befehle ein zweites Terminalfenster öffnen und dort mit `cd` in
den Projektordner wechseln.

### 3 Dashboard erzeugen

Voraussetzung: Die Notebooks 00 und 25 bis 29 sind ausgeführt. Liegen die Modellpakete vom Projektteam schon in
`models/`, reichen die Notebooks 00 und 25, und die Schritte 1 und 2 entfallen.

**Schritt 1:** Modellpakete bauen:

```bash
docker compose run --rm jupyter python -m src.prognose_waechter --bauen --gegenprobe
docker compose run --rm jupyter python -m src.normalmodell_waechter --bauen
docker compose run --rm jupyter python -m src.fehlerklassen --bauen --gegenprobe
```

**Schritt 2:** In JupyterLab Notebook 35 ausführen (empfohlen, siehe [Ausführung](ausfuehrung.md#5-notebook-35-endmodell)).

**Schritt 3:** Daten für das Dashboard berechnen:

```bash
docker compose run --rm jupyter python -m src.dashboard_daten
```

**Schritt 4:** In JupyterLab Notebook 31 und danach Notebook 37 ausführen.

**Schritt 5:** Dashboard ansehen:

```bash
docker compose up dashboard
```

Das Dashboard ist danach unter http://localhost:8000/fernwaerme_dashboard_final.html erreichbar.

## Lokal

### 1 Umgebung einrichten

Umgebung anlegen:

```bash
python -m venv .venv
```

Umgebung aktivieren, je nach Betriebssystem mit genau einem der beiden Befehle:

| Betriebssystem | Befehl |
|---|---|
| Windows | `.venv\Scripts\activate` |
| macOS, Linux | `source .venv/bin/activate` |

Pakete installieren:

```bash
pip install -r requirements.txt
pip install jupyterlab pytest
```

### 2 Vorbereiten

```bash
python -m src.weather
python -m src.main
python -m src.meter_quality
python -m src.detect_real
```

### 3 Notebooks ausführen

```bash
jupyter lab
```

JupyterLab öffnet sich im Browser. Das Terminalfenster offen lassen, JupyterLab läuft nur, solange es geöffnet ist.
Für die folgenden Befehle ein zweites Terminalfenster öffnen, mit `cd` in den Projektordner wechseln und die Umgebung
aktivieren.

### 4 Dashboard erzeugen

Voraussetzung: Die Notebooks 00 und 25 bis 29 sind ausgeführt. Liegen die Modellpakete vom Projektteam schon in
`models/`, reichen die Notebooks 00 und 25, und die Schritte 1 und 2 entfallen.

**Schritt 1:** Modellpakete bauen:

```bash
python -m src.prognose_waechter --bauen --gegenprobe
python -m src.normalmodell_waechter --bauen
python -m src.fehlerklassen --bauen --gegenprobe
```

**Schritt 2:** In JupyterLab Notebook 35 ausführen (empfohlen, siehe [Ausführung](ausfuehrung.md#5-notebook-35-endmodell)).

**Schritt 3:** Daten für das Dashboard berechnen:

```bash
python -m src.dashboard_daten
```

**Schritt 4:** In JupyterLab Notebook 31 und danach Notebook 37 ausführen.

**Schritt 5:** Die Datei `notebooks/fernwaerme_dashboard_final.html` per Doppelklick im Browser öffnen.

## Weitere Befehle

| Zweck | Befehl |
|---|---|
| Tests | `python -m pytest -q` |
| neue Zählerdaten einspielen | `python -m src.aktualisieren` |
| Dokumentation lokal | `pip install -r docs/requirements.txt`, dann `mkdocs serve` |
| Dokumentation mit Docker | `docker compose up docs`, dann http://localhost:8001 |
