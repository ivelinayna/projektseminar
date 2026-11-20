# Start mit Docker

Mit Docker läuft das Projekt ohne eigene Python-Installation. Ein Image enthält Python, alle Pakete, die Notebooks und
den Code. Die Daten bleiben außerhalb des Images und werden beim Start als Ordner eingehängt. Dadurch arbeiten alle
Rechner mit denselben Paketständen. Vorher die Schritte unter [Vorbereitung](vorbereitung.md) erledigen: Projekt
holen, Daten nach `data/raw/` legen.

## 1 Docker installieren

- **Windows und macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installieren und starten.
  Docker Desktop muss laufen, solange mit dem Projekt gearbeitet wird.
- **Linux:** Docker Engine mit dem Compose-Plugin über die Paketquellen der Distribution installieren.
- **macOS ohne Administratorrechte:** Alternativ zu Docker Desktop lässt sich Colima verwenden
  (`brew install colima docker docker-compose`). Gestartet wird es mit

  ```bash
  colima start --cpu 4 --memory 4 --mount "$HOME/projektseminar:w"
  ```

  Der Pfad hinter `--mount` ist der eigene Projektordner. `colima stop` beendet die Umgebung.

Ob die Installation vollständig ist, zeigen

```bash
docker --version
docker compose version
```

Das Image belegt rund 5 GB Speicherplatz. Docker sollte mindestens 4 GB Arbeitsspeicher zur Verfügung haben, in
Docker Desktop einstellbar unter Settings → Resources.

## 2 Image bauen

```bash
docker compose build
```

- Der erste Bau dauert einige Minuten.
- PyTorch wird ohne Unterstützung für Grafikkarten installiert. Das hält das Image deutlich kleiner.
- Ein neuer Bau ist nur nötig, wenn sich `requirements.txt` oder das `Dockerfile` ändern. Code und Notebooks werden
  eingehängt, Änderungen daran wirken sofort.

## 3 Vorbereiten und Notebooks ausführen

```bash
docker compose run --rm jupyter python -m src.weather         #Außentemperatur vom DWD, braucht Internet
docker compose run --rm jupyter python -m src.main            #Netzgraph, Karten, Begehungstabelle
docker compose run --rm jupyter python -m src.meter_quality   #Datenqualität je Zähler (für Notebook 17)
docker compose run --rm jupyter python -m src.detect_real     #Winterkennzahlen je Zähler (für Notebook 17)
docker compose up jupyter
```

- JupyterLab ist danach unter http://localhost:8888 erreichbar.
- Zuerst `notebooks/1_daten/00_daten.ipynb` ausführen, danach die übrigen Notebooks in Nummernfolge (siehe
  [Ausführung bis zum Dashboard](ausfuehrung.md)).
- `Strg+C` im Terminal beendet JupyterLab.

## 4 Dashboard

```bash
docker compose run --rm jupyter python -m src.prognose_waechter --bauen --gegenprobe
docker compose run --rm jupyter python -m src.normalmodell_waechter --bauen
docker compose run --rm jupyter python -m src.fehlerklassen --bauen --gegenprobe
docker compose run --rm jupyter python -m src.dashboard_daten
```

- Die Modellpakete setzen die Ausgaben der Notebooks 25 bis 29 voraus, darunter die LSTM-Gewichte aus den Notebooks
  27 und 28 in `notebooks/models/`. Ohne Grafikkarte lernen diese beiden Notebooks mehrere Stunden.
- Danach in JupyterLab Notebook 31 (Netz) und Notebook 37 (Dashboard) ausführen. Die vollständige Reihenfolge mit
  Notebook 35 steht unter [Ausführung bis zum Dashboard](ausfuehrung.md).
- `docker compose up dashboard` stellt das Ergebnis unter http://localhost:8000/fernwaerme_dashboard_final.html bereit.

## 5 Aufräumen

```bash
docker compose down                  #Container stoppen
docker image rm fernwaerme-projekt   #Image löschen und Speicherplatz freigeben
```

Daten, Ergebnisse und Notebooks bleiben im Projektordner erhalten.

## Dienste

| Dienst | Befehl | Adresse | Zweck |
|---|---|---|---|
| `jupyter` | `docker compose up jupyter` | http://localhost:8888 | Notebooks ausführen |
| `dashboard` | `docker compose up dashboard` | http://localhost:8000/fernwaerme_dashboard_final.html | fertiges Dashboard aus Notebook 37 ansehen |
| `docs` | `docker compose up docs` | http://localhost:8001 | diese Dokumentation lokal |

Beendet werden die Dienste mit `Strg+C` oder `docker compose down`.

## Eingehängte Ordner

| Ordner | Inhalt |
|---|---|
| `data/` | Rohdaten und aufbereitete Reihen |
| `outputs/` | Ergebnisse, Bilder, Dashboard-Daten |
| `models/` | Modellpakete |
| `notebooks/` | Notebooks und Dashboard-HTML |
| `src/`, `docs/` | Code und Dokumentation |

Alles, was die Container in diese Ordner schreiben, liegt danach auch im Projektordner auf dem eigenen Rechner.

## Einzelne Befehle im Container

```bash
docker compose run --rm jupyter python -m src.weather
docker compose run --rm jupyter python -m src.main
docker compose run --rm jupyter python -m src.aktualisieren
docker compose run --rm jupyter python -m src.dashboard_daten
docker compose run --rm jupyter python -m pytest -q
```

## Hinweise

- Die Dashboard-HTML enthält Adressen. Sie ist gitignored und nur für den internen Gebrauch bestimmt.
- Die Ports sind nur auf dem eigenen Rechner erreichbar (`127.0.0.1`) und sollten nicht im Netz freigegeben werden.
- Im Container rechnet PyTorch auf dem Prozessor. Liegen keine Gewichte in `notebooks/models/`, lernen die Notebooks
  27 und 28 neu, was mehrere Stunden dauert.
