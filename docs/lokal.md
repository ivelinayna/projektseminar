# Lokaler Start ohne Docker

Lokal läuft das Projekt in einer eigenen Python-Umgebung. Dieser Weg bietet sich an, wenn eine Grafikkarte vorhanden ist,
weil die LSTMs dann in Minuten statt Stunden lernen, oder wenn am Code gearbeitet wird. Vorausgesetzt sind die Schritte
unter [Vorbereitung](vorbereitung.md): Projekt holen, Daten nach `data/raw/` legen.

## 1 Python einrichten

Empfohlen ist Python 3.11. Auf dieser Version wurde das Projekt entwickelt, und auf ihr baut auch das Docker-Image auf.

```bash
python -m venv .venv
.venv\Scripts\activate          #Windows
source .venv/bin/activate       #Linux, macOS
```

- Die Umgebung liegt danach im Projektordner unter `.venv/` und ist gitignored.
- In jedem neuen Terminal muss die Umgebung erneut aktiviert werden, sonst fehlen die Pakete.

## 2 Pakete installieren

```bash
pip install -r requirements.txt
pip install jupyterlab pytest
```

- `requirements.txt` enthält alle Pakete für Code und Notebooks, auch `torch` und `xgboost`. Diese beiden werden nur
  von den Notebooks 27 bis 29, 34 und 35 und von den Befehlen für die Modellpakete gebraucht.
- PyTorch nutzt eine vorhandene Grafikkarte automatisch. Ohne Grafikkarte rechnet es auf dem Prozessor.
- `pyarrow` ist auf Versionen unter 25 beschränkt. Mit Version 25 brachen die Modell-Notebooks ab.
- Für die Dokumentation kommt `pip install -r docs/requirements.txt` hinzu (siehe unten).

## 3 Installation prüfen

```bash
python -m pytest -q
```

- Die meisten Tests arbeiten mit kleinen künstlichen Daten und laufen ohne Rohdaten. Laufen sie durch, ist die
  Umgebung vollständig.
- Tests, die Begehungen oder echte Reihen brauchen, werden ohne diese Daten übersprungen.

## 4 JupyterLab starten

```bash
jupyter lab
```

- JupyterLab im Projektordner starten. Der Dateibaum zeigt dann Notebooks, Daten und Ergebnisse.
- Die Notebooks liegen in Unterordnern von `notebooks/` und müssen dort bleiben. Die erste Zelle jedes Notebooks sucht
  den Projektordner und wechselt nach `notebooks/`. Von dort aus sind alle Pfade angegeben.
- Die Reihenfolge der Notebooks beschreibt [Ausführung bis zum Dashboard](ausfuehrung.md).

## 5 Dokumentation lokal ansehen

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

Die Dokumentation ist danach unter `http://127.0.0.1:8000` erreichbar. Änderungen an den Seiten in `docs/` erscheinen
sofort. Read the Docs baut dieselbe Seite aus `mkdocs.yml` und `.readthedocs.yaml`.

## Häufige Fehler

| Meldung oder Verhalten | Ursache und Lösung |
|---|---|
| `ModuleNotFoundError: No module named 'src'` bei `python -m src...` | Der Befehl wurde nicht im Projektordner gestartet. In den Projektordner wechseln. |
| `ModuleNotFoundError` für ein Paket wie `pandas` | Die Umgebung ist nicht aktiviert (Schritt 1). |
| `keine Zählerreihen in data/processed/real_meters, erst NB 00` | Notebook 00 wurde noch nicht ausgeführt. |
| Abbruch beim Lesen einer Parquet-Datei | `pyarrow` 25 oder neuer ist installiert. `pip install "pyarrow<25"` |
| Karte im Dashboard ohne Hintergrund | Kein Internetzugang. Kartenkacheln und Leaflet werden aus dem Netz geladen. |
