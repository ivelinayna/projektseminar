# Lokaler Start ohne Docker

Lokal läuft das Projekt in einer eigenen Python-Umgebung auf dem Rechner. Dieser Weg bietet sich an, wenn eine
Grafikkarte vorhanden ist, weil die LSTMs dann in Minuten statt Stunden lernen, oder wenn am Code gearbeitet wird.

Vorausgesetzt sind die Schritte unter [Vorbereitung](vorbereitung.md): Repository herunterladen, Daten nach
`data/raw/` legen. Wie Befehle im Terminal eingegeben werden, steht dort unter
[Befehle im Terminal ausführen](vorbereitung.md#befehle-im-terminal-ausfuhren).

## 1 Python einrichten

Empfohlen ist Python 3.11 ([python.org](https://www.python.org/downloads/)). Auf dieser Version wurde das Projekt
entwickelt, und auf ihr baut auch das Docker-Image auf.

Im Terminal im Projektordner eine Umgebung anlegen:

```bash
python -m venv .venv
```

Eine Umgebung ist ein eigener Ordner `.venv/` im Projektordner, in den alle Pakete des Projekts installiert werden.
Andere Python-Projekte auf dem Rechner bleiben davon unberührt.

Danach die Umgebung aktivieren, je nach Betriebssystem mit genau einem der beiden Befehle:

| Betriebssystem | Befehl |
|---|---|
| Windows | `.venv\Scripts\activate` |
| macOS, Linux | `source .venv/bin/activate` |

- Ist die Umgebung aktiv, steht `(.venv)` am Anfang der Eingabezeile.
- In jedem neuen Terminalfenster muss die Umgebung erneut aktiviert werden, sonst fehlen die Pakete.
- Der Ordner `.venv/` wird nicht ins Repository übernommen.

## 2 Pakete installieren

Bei aktiver Umgebung nacheinander ausführen:

```bash
pip install -r requirements.txt
pip install jupyterlab pytest
```

- `requirements.txt` enthält alle Pakete für Code und Notebooks, auch `torch` und `xgboost`. Diese beiden werden nur
  von den Notebooks 27 bis 29, 34 und 35 und von den Befehlen für die Modellpakete gebraucht.
- PyTorch nutzt eine vorhandene Grafikkarte automatisch. Ohne Grafikkarte rechnet es auf dem Prozessor.
- `pyarrow` ist auf Versionen unter 25 beschränkt. Mit Version 25 brachen die Modell-Notebooks ab.

## 3 Installation prüfen

```bash
python -m pytest -q
```

- Die meisten Tests arbeiten mit kleinen künstlichen Daten und laufen ohne Rohdaten. Laufen sie ohne Fehler durch, ist
  die Umgebung vollständig.
- Tests, die Begehungen oder echte Reihen brauchen, werden ohne diese Daten übersprungen.

## 4 Notebooks ausführen

**JupyterLab starten:** Im Terminal im Projektordner, bei aktiver Umgebung:

```bash
jupyter lab
```

JupyterLab öffnet sich im Browser, links erscheint der Projektordner. Das Terminal zeigt fortlaufend Meldungen von
JupyterLab. Dieses Fenster offen lassen. Solange JupyterLab läuft, nimmt es keine weiteren Befehle an.

**Ein Notebook ausführen:**

1. Links den Ordner `notebooks` und darin `1_daten` öffnen, dann `00_daten.ipynb` per Doppelklick öffnen.
2. Im Menü *Run → Run All Cells* wählen.
3. Warten, bis das Notebook durchgelaufen ist. Solange eine Zelle rechnet, steht links neben ihr `[*]`. Ist das
   Notebook fertig, steht neben jeder Zelle eine Zahl.

Danach die übrigen Notebooks auf dieselbe Weise öffnen und ausführen, in Nummernfolge. Die Notebooks starten sich nicht
gegenseitig. Welche Notebooks für das Dashboard nötig sind, steht unter [Ausführung bis zum Dashboard](ausfuehrung.md).

**Weitere Befehle, während JupyterLab läuft:** Ein zweites Terminalfenster öffnen, mit `cd` in den Projektordner
wechseln und die Umgebung aktivieren (Schritt 1). Dort lassen sich dann alle übrigen Befehle ausführen.

**JupyterLab beenden:** Im ersten Terminalfenster `Strg+C` drücken.

Die Notebooks liegen in Unterordnern von `notebooks/` und müssen dort bleiben. Die erste Zelle jedes Notebooks sucht
den Projektordner und rechnet alle Pfade von dort aus.

## 5 Dokumentation lokal ansehen

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

Die Dokumentation ist danach im Browser unter http://127.0.0.1:8000 erreichbar. Änderungen an den Seiten in `docs/`
erscheinen sofort. Read the Docs baut dieselbe Seite aus `mkdocs.yml` und `.readthedocs.yaml`.

## Häufige Fehler

| Meldung oder Verhalten | Ursache und Lösung |
|---|---|
| `ModuleNotFoundError: No module named 'src'` bei `python -m src...` | Der Befehl wurde nicht im Projektordner gestartet. Mit `cd` in den Projektordner wechseln. |
| `ModuleNotFoundError` für ein Paket wie `pandas` | Die Umgebung ist nicht aktiviert (Schritt 1). |
| `keine Zählerreihen in data/processed/real_meters, erst NB 00` | Notebook 00 wurde noch nicht ausgeführt. |
| Abbruch beim Lesen einer Parquet-Datei | `pyarrow` 25 oder neuer ist installiert. `pip install "pyarrow<25"` |
| Karte im Dashboard ohne Hintergrund | Kein Internetzugang. Kartenkacheln und Leaflet werden aus dem Netz geladen. |
