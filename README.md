# Fehlererkennung im Fernwärmenetz

Projektseminar der Julius-Maximilians-Universität Würzburg mit der ÜZ Mainfranken, SS 2026 und WS 2026.

Ziel: Fehler an Hausanschlussstationen (HAST) aus den stündlichen Zählerdaten erkennen und eine Maßnahme vorschlagen.
Grundlage sind etwa 100 Zähler eines Teilnetzes, 66 Begehungen durch Monteure und das Leitungsnetz.

Ausführliche Doku: Ordner `docs/`, als Webseite mit Read the Docs (`mkdocs.yml`).

## Ergebnis in Kürze

- Überwachtes Lernen auf den Begehungen scheitert an zu wenigen und unsauberen Labels.
- Stationen lassen sich nicht in klare Typen clustern. Betriebsstunden schon (5 Zustände).
- Für die Überwachung trägt ein Tagesmonitor: wetterbereinigte Kennlinie je Station mit CUSUM-Alarm.
- Für die Einstufung nach den Handlungsklassen der ÜZ dient eine logistische Regression auf einem LSTM-Embedding.
- Viele Ansätze haben nicht getragen. Sie sind unter „Negativbefunde“ dokumentiert.
- Ergebnis für die ÜZ: ein Dashboard als HTML-Datei mit Karte und Handlungsliste.

## Ordner

| Ordner | Inhalt |
|---|---|
| `notebooks/` | 40 Notebooks (00 bis 39) in neun Teilen und einem Anhang, je ein Ordner, siehe unten |
| `src/` | wiederverwendbarer Code, eine Datei je Aufgabe |
| `tests/` | Tests mit pytest |
| `docs/` | Doku für Read the Docs |
| `data/` | Rohdaten und aufbereitete Daten, gitignored (siehe `data/README.md`) |
| `outputs/` | Ergebnisse und Bilder, gitignored |
| `models/` | Modellpakete, gitignored (siehe `models/README.md`) |
| `archiv/` | alter Stand und Entwürfe, nur lokal, gitignored |

## Notebooks

| Teil | Ordner | Notebooks | Thema |
|---|---|---|---|
| 1 | `1_daten/` | 00 bis 01 | Daten laden und Lücken füllen |
| 2 | `2_begehungen/` | 02 bis 06 | Begehungen und ihre Wirkung |
| 3 | `3_clustering/` | 07 bis 10 | Clustering |
| 4 | `4_stationsbilder/` | 11 bis 15 | Stationsbilder und Befunde |
| 5 | `5_monitoring/` | 16 bis 24 | Anomalien und Monitoring |
| 6 | `6_lernende_modelle/` | 25 bis 30 | Lernende Modelle |
| 7 | `7_netz/` | 31 bis 33 | Netz und Karte |
| 8 | `8_modellvergleich/` | 34 bis 36 | Modellvergleich, Endmodell, Merkmale und Erklärbarkeit |
| 9 | `9_dashboard/` | 37 | Dashboard |
| Anhang | `weitere_versuche/` | 38 bis 39 | Weitere Versuche (Bayes-Diagnose, GNN) |

Notebook 00 immer zuerst ausführen. Alle anderen lesen dessen Ergebnis. Details in `docs/notebooks.md`.

## Schnellstart lokal

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows, sonst: source .venv/bin/activate
pip install -r requirements.txt jupyterlab

#Rohdaten der ÜZ nach data/raw/ kopieren
python -m src.weather             # Außentemperatur
python -m src.main                # Netz, Karten, Begehungstabelle
python -m src.meter_quality       # Datenqualität je Zähler
python -m src.detect_real         # Winterkennzahlen je Zähler
jupyter lab                       # dann Notebook 00, danach der Reihe nach
python -m pytest -q               # Tests
```

## Schnellstart mit Docker

```bash
docker compose build
docker compose up jupyter         # http://localhost:8888
docker compose up dashboard       # http://localhost:8000/fernwaerme_dashboard_final.html
docker compose up docs            # http://localhost:8001
```

Schritt-für-Schritt-Anleitung (Docker installieren, Projekt holen, Daten ablegen, ausführen) in `docs/docker.md`.

## Doku

```bash
pip install -r docs/requirements.txt
mkdocs serve                      # http://127.0.0.1:8000
```

Read the Docs baut die Seite aus `.readthedocs.yaml` und `mkdocs.yml`.

## Datenschutz

- Rohdaten, Ergebnisse und Modellpakete werden nie committet.
- Die Doku nennt Stationen nur über die Zählernummer, nie über die Adresse.
- Die Dashboard-HTML und die Netz-Notebooks 31 bis 33 zeigen Adressen. Sie sind nur für den internen Gebrauch.