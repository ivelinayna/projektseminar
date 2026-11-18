# Docker

Mit Docker läuft das Projekt ohne eigene Python-Installation. Ein Image enthält Python, alle Pakete, die Notebooks und
den Code. Die Daten bleiben außerhalb des Images und werden beim Start eingehängt.

## Voraussetzungen

- Docker Desktop (Windows, macOS) oder Docker Engine mit Compose (Linux). Auf dem Mac geht auch Colima statt Docker
  Desktop (`colima start --cpu 4 --memory 4`), dann den Projektordner beim Start einhängen.
- Die Rohdaten der ÜZ liegen lokal unter `data/raw/` (siehe [Daten](daten.md)). Sie sind nicht im Repo, ohne sie
  läuft kein Notebook.
- Rund 5 GB frei für das Image, mindestens 4 GB Arbeitsspeicher für den Container.

## Image bauen

```bash
docker compose build
```

- Der erste Bau dauert einige Minuten. PyTorch wird ohne Grafikkarten-Unterstützung installiert, das hält das Image
  kleiner.
- Danach muss nur neu gebaut werden, wenn sich `requirements.txt` ändert. Code und Notebooks werden eingehängt.

## Dienste

| Dienst | Befehl | Adresse | Wofür |
|---|---|---|---|
| `jupyter` | `docker compose up jupyter` | http://localhost:8888 | Notebooks ausführen |
| `dashboard` | `docker compose up dashboard` | http://localhost:8000/fernwaerme_dashboard_final.html | fertiges Dashboard aus Notebook 37 ansehen |
| `docs` | `docker compose up docs` | http://localhost:8001 | diese Doku lokal |
| `app` | `docker compose --profile extra up app` | http://localhost:8501 | ältere Streamlit-App (Rücklauf-Ampel) |

Beenden mit `Strg+C` oder `docker compose down`.

## Eingehängte Ordner

| Ordner | Inhalt |
|---|---|
| `data/` | Rohdaten und aufbereitete Reihen |
| `outputs/` | Ergebnisse, Bilder, Dashboard-Daten |
| `models/` | Modellpakete |
| `notebooks/` | Notebooks und Dashboard-HTML |
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

## Typischer Ablauf

1. `docker compose build`
2. `docker compose up jupyter`, im Browser Notebook 00 und danach die gewünschten Notebooks ausführen.
3. Für das Dashboard die Modellpakete bauen (Notebook 35 oder die Befehle unter [Schnellstart](schnellstart.md)),
   dann Notebook 31 und Notebook 37 ausführen.
4. `docker compose up dashboard` und die angezeigte Adresse öffnen.

## Hinweise

- Die Dashboard-HTML enthält Adressen. Sie ist gitignored und nur für den internen Gebrauch.
- JupyterLab startet ohne Passwort. Die Ports sind deshalb nur auf dem eigenen Rechner erreichbar (`127.0.0.1`). Das
  so lassen und nicht ins Netz freigeben.
- Das Image wurde für Linux gebaut. Auf Windows und macOS läuft es über Docker Desktop.
- Im Container rechnet PyTorch nur auf der CPU. Die Notebooks 27 und 28 trainieren die LSTMs neu, wenn keine Gewichte
  in `notebooks/models/` liegen. Das dauert auf der CPU mehrere Stunden.
- Getestet am 18.11.2026 auf einem Mac (Apple Silicon) mit Colima: Bau rund 3,5 Minuten, Tests grün bis auf
  `test_dashboard_app` (braucht `data/processed/priority_scores.csv` aus `python -m src.priority`), Notebooks 00, 01,
  07, 21 und 37 und `src.dashboard_daten` laufen durch und liefern dieselben Zahlen wie lokal.
