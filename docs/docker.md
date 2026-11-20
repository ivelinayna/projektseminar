# Docker

Mit Docker läuft das Projekt ohne eigene Python-Installation. Ein Image enthält Python, alle Pakete, die Notebooks und
den Code. Die Daten bleiben außerhalb des Images und werden beim Start eingehängt.

## Schritt für Schritt auf dem eigenen Rechner

### 1 Docker installieren

- **Windows und macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) installieren und einmal
  starten. Es muss laufen (Wal-Symbol in der Taskleiste bzw. Menüleiste), sonst findet `docker` keinen Dienst.
- **Linux:** Docker Engine mit dem Compose-Plugin über die Paketquellen der Distribution.
- **macOS ohne Docker Desktop:** Colima geht auch, ohne Admin-Rechte. `colima`, `docker` und `docker compose`
  installieren (z. B. `brew install colima docker docker-compose`), dann:

  ```bash
  colima start --cpu 4 --memory 4 --mount "$HOME/projektseminar:w"
  ```

  Den Pfad hinter `--mount` auf den eigenen Projektordner setzen. `colima stop` beendet es wieder.
- Prüfen, ob alles da ist:

  ```bash
  docker --version
  docker compose version
  ```

Bedarf: rund 5 GB Platte für das Image, mindestens 4 GB Arbeitsspeicher für Docker (in Docker Desktop unter
Settings → Resources einstellbar).

### 2 Projekt holen

```bash
git clone https://github.com/ivelinayna/projektseminar.git
cd projektseminar
```

Ohne Git geht auch der ZIP-Download auf GitHub (Code → Download ZIP), dann entpacken und in den Ordner wechseln. Alle
folgenden Befehle laufen in diesem Ordner.

### 3 Rohdaten ablegen

- Die Daten der ÜZ sind vertraulich und nicht im Repo. Ohne sie läuft kein Notebook.
- Die Dateien nach `data/raw/` kopieren. Welche Dateien es sind, steht in `data/README.md` und unter
  [Daten](daten.md).

### 4 Image bauen

```bash
docker compose build
```

- Beim ersten Mal einige Minuten (auf einem aktuellen Mac rund 3,5 Minuten). PyTorch wird ohne Grafikkarte installiert,
  das hält das Image kleiner.
- Neu bauen nur, wenn sich `requirements.txt` oder das `Dockerfile` ändert. Code und Notebooks werden eingehängt.

### 5 Vorbereiten und Notebooks ausführen

```bash
docker compose run --rm jupyter python -m src.weather         # Außentemperatur vom DWD, braucht Internet
docker compose run --rm jupyter python -m src.main            # Graphen, Karten, Begehungstabelle
docker compose run --rm jupyter python -m src.meter_quality   # Datenqualität je Zähler (für Notebook 17)
docker compose run --rm jupyter python -m src.detect_real     # Winterkennzahlen je Zähler (für Notebook 17)
docker compose up jupyter
```

- Im Browser http://localhost:8888 öffnen, ein Passwort gibt es nicht.
- Zuerst `notebooks/1_daten/00_daten.ipynb` ausführen, danach in Nummernfolge (siehe [Notebooks](notebooks.md)).
- Beenden mit `Strg+C` im Terminal.

### 6 Dashboard

```bash
docker compose run --rm jupyter python -m src.prognose_waechter --bauen --gegenprobe
docker compose run --rm jupyter python -m src.normalmodell_waechter --bauen
docker compose run --rm jupyter python -m src.fehlerklassen --bauen --gegenprobe
docker compose run --rm jupyter python -m src.dashboard_daten
```

- Danach in Jupyter Notebook 31 (Netz) und Notebook 37 (Dashboard) ausführen.
- `docker compose up dashboard` und http://localhost:8000 öffnen.
- Die Modellpakete brauchen die LSTM-Gewichte aus den Notebooks 27 und 28 in `notebooks/models/`. Fehlen sie, die
  beiden Notebooks vorher ausführen (auf der CPU mehrere Stunden).

### 7 Aufräumen

```bash
docker compose down          # Container stoppen
docker image rm fernwaerme-projekt   # Image löschen, gibt die 4 GB wieder frei
```

Daten, Ergebnisse und Notebooks bleiben im Projektordner erhalten.

## Dienste

| Dienst | Befehl | Adresse | Wofür |
|---|---|---|---|
| `jupyter` | `docker compose up jupyter` | http://localhost:8888 | Notebooks ausführen |
| `dashboard` | `docker compose up dashboard` | http://localhost:8000 | Dashboard (Streamlit) mit den Daten aus Notebook 37 |
| `docs` | `docker compose up docs` | http://localhost:8001 | diese Doku lokal |

Beenden mit `Strg+C` oder `docker compose down`.

## Eingehängte Ordner

| Ordner | Inhalt |
|---|---|
| `data/` | Rohdaten und aufbereitete Reihen |
| `outputs/` | Ergebnisse, Bilder, Dashboard-Daten |
| `models/` | Modellpakete |
| `notebooks/` | Notebooks |
| `src/`, `docs/` | Code und Doku, damit Änderungen sofort wirken |

Alles, was in den Containern in diese Ordner geschrieben wird, liegt danach auch lokal.

## Befehle im Container

Einzelne Pipeline-Befehle laufen mit `docker compose run`:

```bash
docker compose run --rm jupyter python -m src.weather
docker compose run --rm jupyter python -m src.main
docker compose run --rm jupyter python -m src.aktualisieren
docker compose run --rm jupyter python -m src.dashboard_daten
docker compose run --rm jupyter python -m pytest -q
```

## Hinweise

- Die Dashboard-Daten in `outputs/dashboard/app/` enthalten Adressen. Sie sind gitignored und nur für den internen Gebrauch.
- JupyterLab startet ohne Passwort. Die Ports sind deshalb nur auf dem eigenen Rechner erreichbar (`127.0.0.1`). Das
  so lassen und nicht ins Netz freigeben.
- Das Image wurde für Linux gebaut. Auf Windows und macOS läuft es über Docker Desktop.
- Im Container rechnet PyTorch nur auf der CPU. Die Notebooks 27 und 28 trainieren die LSTMs neu, wenn keine Gewichte
  in `notebooks/models/` liegen. Das dauert auf der CPU mehrere Stunden.
- Getestet am 18.11.2026 auf einem Mac (Apple Silicon) mit Colima: Bau rund 3,5 Minuten, alle Tests grün, Notebooks 00, 01, 07, 21
  und 37 und `src.dashboard_daten` laufen durch und liefern dieselben Zahlen wie lokal.
