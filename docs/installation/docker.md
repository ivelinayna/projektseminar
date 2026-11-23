# Start mit Docker

Mit Docker läuft das Projekt ohne eigene Python-Installation. Docker baut dafür einmalig ein sogenanntes **Image**: eine
fertig eingerichtete Umgebung mit Python, allen Paketen, den Notebooks und dem Code. Aus diesem Image startet Docker bei
Bedarf einen **Container**, in dem die Befehle und JupyterLab laufen. Die Daten bleiben außerhalb des Images im
Projektordner und werden beim Start in den Container eingebunden. Dadurch arbeiten alle Rechner mit denselben
Paketständen.

Vorausgesetzt sind die Schritte unter [Vorbereitung](vorbereitung.md): Repository herunterladen, Daten nach
`data/raw/` legen. Wie Befehle im Terminal eingegeben werden, steht dort unter
[Befehle im Terminal ausführen](vorbereitung.md#befehle-im-terminal-ausfuhren).

## 1 Docker installieren

- **Windows und macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installieren und starten.
  Docker Desktop muss laufen, solange mit dem Projekt gearbeitet wird.
- **Linux:** Docker Engine mit dem Compose-Plugin über die Paketquellen der Distribution installieren.
- **macOS ohne Administratorrechte:** Alternativ zu Docker Desktop lässt sich Colima verwenden
  (`brew install colima docker docker-compose`), siehe unten.

Colima wird gestartet mit

```bash
colima start --cpu 4 --memory 4 --mount "$HOME/projektseminar:w"
```

Der Pfad hinter `--mount` ist der eigene Projektordner. `colima stop` beendet die Umgebung.

Ob die Installation vollständig ist, zeigen die folgenden zwei Befehle im Terminal. Beide geben eine Versionsnummer aus:

```bash
docker --version
docker compose version
```

Das Image belegt ca. 5 GB Speicherplatz. Docker sollte mindestens 4 GB Arbeitsspeicher zur Verfügung haben, in
Docker Desktop einstellbar unter Settings → Resources.

## 2 Image bauen

Im Terminal im Projektordner ausführen:

```bash
docker compose build
```

- Der erste Bau dauert einige Minuten. Am Ende erscheint wieder die Eingabezeile.
- PyTorch wird ohne Unterstützung für Grafikkarten installiert. Das hält das Image deutlich kleiner.
- Ein neuer Bau ist nur nötig, wenn sich `requirements.txt` oder das `Dockerfile` ändern. Code und Notebooks werden
  aus dem Projektordner eingebunden, Änderungen daran wirken sofort.

## 3 Vorbereitende Befehle

Die folgenden vier Befehle nacheinander im Terminal ausführen und jeweils warten, bis die Eingabezeile wieder
erscheint:

```bash
docker compose run --rm jupyter python -m src.weather         #Außentemperatur vom DWD, braucht Internet
docker compose run --rm jupyter python -m src.main            #Netzgraph, Karten, Begehungstabelle
docker compose run --rm jupyter python -m src.meter_quality   #Datenqualität je Zähler (für Notebook 17)
docker compose run --rm jupyter python -m src.detect_real     #Winterkennzahlen je Zähler (für Notebook 17)
```

`docker compose run --rm jupyter` startet für jeden Befehl einen Container, führt den Befehl darin aus und entfernt
den Container danach wieder. Die Ergebnisse landen im Projektordner.

## 4 Notebooks ausführen

**JupyterLab starten:** Im Terminal ausführen:

```bash
docker compose up jupyter
```

Das Terminal zeigt danach fortlaufend Meldungen von JupyterLab. Dieses Fenster offen lassen. Solange JupyterLab läuft,
nimmt es keine weiteren Befehle an.

**JupyterLab öffnen:** Im Browser http://localhost:8888 aufrufen. Links erscheint der Projektordner.

**Ein Notebook ausführen:**

1. Links den Ordner `notebooks` und darin `1_daten` öffnen, dann `00_daten.ipynb` per Doppelklick öffnen.
2. Im Menü *Run → Run All Cells* wählen.
3. Warten, bis das Notebook durchgelaufen ist. Solange eine Zelle rechnet, steht links neben ihr `[*]`. Ist das
   Notebook fertig, steht neben jeder Zelle eine Zahl.

Danach die übrigen Notebooks auf dieselbe Weise öffnen und ausführen, in Nummernfolge. Die Notebooks starten sich nicht
gegenseitig. Welche Notebooks für das Dashboard nötig sind, steht unter [Ausführung bis zum Dashboard](ausfuehrung.md).

**JupyterLab beenden:** Im Terminalfenster `Strg+C` drücken.

## 5 Dashboard erzeugen

Voraussetzung: Die Notebooks 00 und 25 bis 29 sind ausgeführt. Läuft JupyterLab noch, die folgenden Befehle in einem
zweiten Terminalfenster ausführen. Dort zuerst mit `cd` in den Projektordner wechseln.

**Schritt 1:** Modellpakete bauen, die Befehle wieder einzeln nacheinander:

```bash
docker compose run --rm jupyter python -m src.prognose_waechter --bauen --gegenprobe
docker compose run --rm jupyter python -m src.normalmodell_waechter --bauen
docker compose run --rm jupyter python -m src.fehlerklassen --bauen --gegenprobe
```

**Schritt 2:** In JupyterLab Notebook 35 ausführen (empfohlen, siehe
[Ausführung](ausfuehrung.md#5-notebook-35-endmodell)).

**Schritt 3:** Daten für das Dashboard berechnen:

```bash
docker compose run --rm jupyter python -m src.dashboard_daten
```

**Schritt 4:** In JupyterLab Notebook 31 und danach Notebook 37 ausführen. Notebook 37 schreibt die Datei
`notebooks/fernwaerme_dashboard_final.html`.

**Schritt 5:** Dashboard ansehen. Die Datei lässt sich direkt per Doppelklick im Browser öffnen. Alternativ stellt
Docker sie bereit:

```bash
docker compose up dashboard
```

Das Dashboard ist danach unter http://localhost:8000/fernwaerme_dashboard_final.html erreichbar.

Die Modellpakete setzen die LSTM-Gewichte aus den Notebooks 27 und 28 in `notebooks/models/` voraus. Neu lernen
diese beiden Notebooks nur mit `SELBST_TRAINIEREN = True`, ohne Grafikkarte dauert das mehrere Stunden.

## 6 Aufräumen

```bash
docker compose down                  #Container stoppen
docker image rm fernwaerme-projekt   #Image löschen und Speicherplatz freigeben
```

Daten, Ergebnisse und Notebooks bleiben im Projektordner erhalten.

## Dienste

Docker stellt drei Dienste bereit. Jeder wird mit einem eigenen Befehl gestartet und läuft, bis er mit `Strg+C` oder
`docker compose down` beendet wird.

| Dienst | Befehl | Adresse im Browser | Zweck |
|---|---|---|---|
| `jupyter` | `docker compose up jupyter` | http://localhost:8888 | Notebooks ausführen |
| `dashboard` | `docker compose up dashboard` | http://localhost:8000/fernwaerme_dashboard_final.html | fertiges Dashboard aus Notebook 37 ansehen |
| `docs` | `docker compose up docs` | http://localhost:8001 | diese Dokumentation lokal |

## Eingebundene Ordner

| Ordner | Inhalt |
|---|---|
| `data/` | Rohdaten und aufbereitete Reihen |
| `outputs/` | Ergebnisse, Bilder, Dashboard-Daten |
| `models/` | Modellpakete |
| `notebooks/` | Notebooks und Dashboard-HTML |
| `src/`, `docs/` | Code und Dokumentation |

Alles, was die Container in diese Ordner schreiben, liegt danach auch im Projektordner auf dem eigenen Rechner.

## Einzelne Befehle im Container

Jeder Befehl aus dieser Dokumentation lässt sich in Docker ausführen, indem `docker compose run --rm jupyter`
vorangestellt wird, z. B.:

```bash
docker compose run --rm jupyter python -m src.aktualisieren
docker compose run --rm jupyter python -m pytest -q
```

## Hinweise

- Die Dashboard-HTML enthält Adressen. Sie wird nicht ins Repository übernommen und ist nur für den internen Gebrauch
  bestimmt.
- Die Adressen `localhost` sind nur auf dem eigenen Rechner erreichbar und sollten nicht im Netz freigegeben werden.
- Im Container rechnet PyTorch auf dem Prozessor. Die Notebooks 27 und 28 laden deshalb die Gewichte aus
  `notebooks/models/`. Mit `SELBST_TRAINIEREN = True` lernen sie neu, was im Container mehrere Stunden dauert.
