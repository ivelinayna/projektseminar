# Ausführung bis zum Dashboard

Diese Seite beschreibt den Weg von den Rohdaten bis zur fertigen Dashboard-Datei. Vorausgesetzt ist, dass die Daten
der ÜZ in `data/raw/` liegen (siehe [Vorbereitung](vorbereitung.md)) und die Umgebung läuft, mit Docker oder lokal.

Die Befehle stehen hier für den lokalen Start. Mit Docker gilt:

- Befehle bekommen `docker compose run --rm jupyter` davor, also z. B.
  `docker compose run --rm jupyter python -m src.weather`.
- Notebooks laufen im JupyterLab aus `docker compose up jupyter` (http://localhost:8888).

## Überblick

```text
1  Vorbereitende Befehle     Außentemperatur, Netz, Begehungstabelle, Kennzahlen je Zähler
        |
2  Notebook 00                Stundenreihe je Zähler (Grundlage für alles)
        |
3  Notebooks 25 bis 29        Labels, Kennzahlen, LSTM-Fingerabdruck, Prognose-LSTM, Fehlerklassen
        |
4  Modellpakete               drei Pakete in models/
        |
5  Notebook 35                strenger Vergleich, Endmodell als Pakete (empfohlen)
        |
6  python -m src.dashboard_daten   Pakete auf die aktuellen Daten anwenden
        |
7  Notebook 31                Netz-Cache mit der Lage der Häuser
        |
8  Notebook 37                Dashboard als HTML-Datei
```

Für das Dashboard reichen diese Schritte. Die übrigen Notebooks zeigen den Weg dorthin und sind unter
[Die übrigen Notebooks](#die-ubrigen-notebooks) beschrieben.

## 1 Vorbereitende Befehle

```bash
python -m src.weather        #Außentemperatur vom DWD, braucht Internet
python -m src.main           #Netzgraph, Karten, Begehungstabelle
python -m src.meter_quality  #Datenqualität je Zähler
python -m src.detect_real    #Winterkennzahlen je Zähler
```

| Befehl | schreibt | gebraucht von |
|---|---|---|
| `src.weather` | Stundenwerte in `data/raw/weather/`, Tageswerte in `data/raw/weather/tageswerte/` | fast alle Notebooks, Dashboard |
| `src.main` | `inspections_tidy.csv`, Netzbilder und Karten | Notebook 08 |
| `src.meter_quality` | `meter_quality.csv` | Notebook 17 |
| `src.detect_real` | `features_real.csv` | Notebook 17 |

- `src.weather` lädt nur beim ersten Mal. Danach liest das Projekt aus dem Cache.
- Für das Dashboard allein genügt `src.weather`. Die anderen drei Befehle werden für die Notebooks 08 und 17
  gebraucht.

## 2 Notebook 00

`notebooks/1_daten/00_daten.ipynb` immer zuerst ausführen.

- Es liest alle Zählerexporte, korrigiert die bekannten Exportfehler und schreibt je Zähler eine Stundenreihe nach
  `data/processed/real_meters/`.
- Alle anderen Notebooks und Befehle lesen nur diese Reihen, nie die Rohdateien direkt.
- Dauer: unter 1 Minute.

## 3 Notebooks 25 bis 29

Die lernenden Modelle bauen aufeinander auf und laufen der Reihe nach:

| Notebook | schreibt |
|---|---|
| 25 Modelldaten | `modell_stunden.parquet`, `modell_labels.csv`, `modell_kennzahlen.csv` |
| 26 Einstufung | `kmeans_einstufung.csv` |
| 27 LSTM-Fingerabdruck | `lstm_embedding.csv`, `lstm_scores.csv`, Gewichte nach `notebooks/models/` |
| 28 Prognose-LSTM | `prognose_tage.csv`, Gewichte nach `notebooks/models/` |
| 29 XGBoost und Klassen | `fehlerklassen_je_hast.csv` |

- Die meisten Schritte dauern wenige Minuten. Ohne Grafikkarte, etwa in Docker, benötigen die Notebooks 27 und 28
  beim Neulernen rund 4,5 bzw. 3,5 Stunden, Notebook 35 rund 5 Stunden.
- Liegen die Gewichte bereits in `notebooks/models/`, laden 27 und 28 sie, und das Neulernen entfällt. Da alle Seeds
  fest gesetzt sind, liefern neu gelernte Gewichte auf demselben Rechner dieselben Zahlen.
- Auf anderer Hardware können die Zahlen in den letzten Stellen abweichen. Die Aussagen bleiben gleich.

## 4 Modellpakete bauen

```bash
python -m src.prognose_waechter --bauen --gegenprobe
python -m src.normalmodell_waechter --bauen
python -m src.fehlerklassen --bauen --gegenprobe
python -m src.modellpaket       #listet die vorhandenen Pakete
```

| Paket | Inhalt | aus |
|---|---|---|
| `normalmodell` | Tagesmonitor: Kennlinie je Station mit CUSUM | Stundenreihen aus Notebook 00 |
| `prognose_lstm` | Prognose-LSTM als Wächter für warme Tage | Notebooks 25 und 28 |
| `fehlerklassen` | Ventil-Modell und Klasse nach Folie 5 | Notebooks 25 bis 27 |

- Ein Paket enthält das gelernte Modell und alles zum Anwenden: Skalierung, Schwellen, Zeiträume, Version.
- `--gegenprobe` wendet das fertige Paket noch einmal an und gibt den Vergleich mit den Zahlen aus Notebook 28 bzw. 29
  aus, z. B. den Anteil gleicher Klassen. Alle Werte sollten übereinstimmen.
- Jedes Paket liegt als eigene Version unter `models/<name>/`. Die Datei `AKTUELL` sagt, welche Version das Dashboard
  nimmt.

## 5 Notebook 35: Endmodell

`notebooks/8_modellvergleich/35_endmodell.ipynb` lernt Monitoring-Modell und LSTM-Modell auf einer gemeinsamen
Zeitachse neu, prüft beide streng und speichert das Ergebnis als drei neue Pakete (Version `nb34_<Datum>`). Am Ende
setzt es diese Pakete als aktuelle Version.

- Empfohlen, weil das Dashboard dann genau die Modelle zeigt, die in Notebook 35 am besten abgeschnitten haben (siehe
  [Strenger Vergleich](vergleich/endmodell.md)).
- Braucht die Pakete aus Schritt 4, weil es das alte Prognose-LSTM zum Vergleich lädt.
- Dauert deutlich länger als die anderen Notebooks, weil es alle Netze je Prüfteil neu lernt.
- Ohne Notebook 35 nutzt das Dashboard die Pakete aus Schritt 4. Die Anzeige ist dieselbe, die Modelle stammen dann
  aus den Notebooks 26 bis 29.

## 6 Daten für das Dashboard

```bash
python -m src.dashboard_daten
```

- Wendet die aktuellen Pakete auf die Stundenreihen an, ohne neu zu lernen.
- Schreibt Wächter-Meldungen, Fehlerklassen, Netzvergleich, Empfehlung und Netzeffizienz nach `outputs/dashboard/`.
- Nur Zählernummern, keine Adressen. Dauer: wenige Minuten.

## 7 Notebook 31: Netz

`notebooks/7_netz/31_netz.ipynb` baut aus Leitungsplan, Kantendatei, Zuordnung und der Handliste mit Koordinaten das
Netzmodell und speichert es als Cache unter `notebooks/daten_cache/`.

- Braucht die Netzdateien in `data/raw/` und `adressen_koordinaten.ods` (siehe [Vorbereitung](vorbereitung.md)).
- Fehlen Koordinaten, schreibt das Notebook eine Liste `fehlende_koordinaten_<Zeit>.ods`. Dort die Spalte
  `koordinate` ergänzen und das Notebook noch einmal ausführen.

## 8 Notebook 37: Dashboard

`notebooks/9_dashboard/37_dashboard.ipynb` verbindet `outputs/dashboard/` mit dem Netz-Cache und schreibt
`notebooks/fernwaerme_dashboard_final.html`.

Ansehen:

- Datei per Doppelklick im Browser öffnen, oder
- mit Docker: `docker compose up dashboard`, dann
  http://localhost:8000/fernwaerme_dashboard_final.html.

Die Karte lädt Kartenkacheln und Leaflet aus dem Internet. Ohne Netz bleibt der Hintergrund leer. Wie das Dashboard
aufgebaut ist und was es zeigt, steht unter [Dashboard](ergebnisse_dashboard.md).

## Die übrigen Notebooks

Alle Notebooks lassen sich in Nummernfolge von 00 bis 39 ausführen. Ein vollständiger Lauf ohne Grafikkarte
und mit neu lernenden Netzen dauert rund 15 Stunden, überwiegend in den Notebooks 27, 28 und 35. Werden nur einzelne Notebooks
ausgeführt, sind folgende Abhängigkeiten zu beachten:

| Notebook | braucht vorher |
|---|---|
| alle | Notebook 00, `python -m src.weather` |
| 08 | `python -m src.main` |
| 17 | `python -m src.meter_quality`, `python -m src.detect_real` |
| 18, 30, 34, 39 | Notebook 10 (Tageswerte `hast_tage`) |
| 30, 34, 39 | Notebook 18 (Normalverhaltensmodell) |
| 30 | Notebook 28 (Prognose-LSTM) |
| 32, 33, 39 | Notebook 31 (Netz-Cache) |
| 33 | Notebook 24 (Monitorstatus); die Stationsblätter erzeugt es selbst, wenn sie fehlen |
| 34, 35 | Notebooks 25 bis 29 |
| 36 | Notebook 35 (Vorhersagen in `outputs/finalvergleich/`) |
| 38 | zwei Handtabellen in `data/manual/` (siehe [Vorbereitung](vorbereitung.md)) |

Was jedes Notebook macht und herausfindet, steht unter [Überblick der Notebooks](notebooks.md).

## Neue Zählerdaten einspielen

Für den Betrieb nach dem Projekt gibt es einen Befehl, der die Überwachung in einem Schritt auf den neuesten Stand
bringt:

```bash
python -m src.aktualisieren
```

1. Neue Exporte der ÜZ nach `data/raw/` legen.
2. Der Befehl führt Notebook 00 neu aus, holt die Außentemperatur nach und rechnet Netzvergleich, Tagesmonitor und
   Priorität.
3. Ergebnis unter `outputs/`: Stationsblätter, `status.csv` und ein Kurzbericht `bericht.txt` mit Priorität, frischen
   Alarmen und Änderungen seit dem letzten Lauf.

Das Dashboard wird dabei nicht neu gebaut. Dafür danach die Schritte 6 bis 8 wiederholen. Die Modellpakete bleiben
dieselben, sie werden nur auf die neuen Daten angewendet.

## Tests

```bash
python -m pytest -q
```

- Eine Testdatei je Modul in `tests/`. Die meisten Tests laufen ohne Rohdaten.
- Tests, die Begehungen oder echte Reihen brauchen, werden ohne diese Daten übersprungen.
- Welche Befehle und Module es gibt, steht unter [Befehle und Module](pipeline.md).
