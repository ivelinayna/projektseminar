# Ausführung bis zum Dashboard

Diese Seite beschreibt den Weg von den Rohdaten bis zur fertigen Dashboard-Datei. Vorausgesetzt ist, dass die Daten
der ÜZ in `data/raw/` liegen (siehe [Vorbereitung](vorbereitung.md)) und die Umgebung läuft, mit Docker oder lokal.

- **Befehle** werden im Terminal im Projektordner eingegeben, einzeln und nacheinander (siehe
  [Befehle im Terminal ausführen](vorbereitung.md#befehle-im-terminal-ausfuhren)). Sie stehen hier für den lokalen
  Start. Mit Docker wird jedem Befehl `docker compose run --rm jupyter` vorangestellt, z. B.
  `docker compose run --rm jupyter python -m src.weather`.
- **Notebooks** werden in JupyterLab einzeln geöffnet und über *Run → Run All Cells* ausgeführt. Sie starten sich nicht
  gegenseitig. Wie JupyterLab gestartet wird, beschreiben [Start mit Docker](docker.md#4-notebooks-ausfuhren) und
  [Lokaler Start ohne Docker](lokal.md#4-notebooks-ausfuhren).

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
  [Modellvergleich](../modellvergleich.md)).
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
- Die Tabellen enthalten nur Zählernummern, keine Adressen.

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
aufgebaut ist und was es zeigt, steht unter [Dashboard](../ergebnisse_dashboard.md).

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

Fragestellung und Ergebnis der einzelnen Notebooks beschreibt der [Überblick der Notebooks](../notebooks.md).

## Neue Zählerdaten einspielen

Liefert die ÜZ neue Zählerexporte, bringt ein einziger Befehl Überwachung und Dashboard auf den neuen Stand. Die
Modelle lernen dabei nicht neu, die vorhandenen Modellpakete werden auf die neuen Daten angewendet.

**Schritt 1:** Die neuen Exporte nach `data/raw/` kopieren, zusätzlich zu den vorhandenen Dateien.

**Schritt 2:** Im Terminal im Projektordner ausführen:

```bash
python -m src.aktualisieren
```

Der Befehl arbeitet nacheinander folgende Schritte ab und zeigt im Terminal an, bei welchem er gerade ist:

| Schritt | was passiert |
|---|---|
| 1 | Notebook 00 bereitet die Stundenreihen neu auf |
| 2 | die Außentemperatur wird vom DWD nachgeladen |
| 3 | Netzvergleich, Tagesmonitor und Priorität werden berechnet, die Stationsblätter und `status.csv` geschrieben |
| 4 | ein Kurzbericht `bericht.txt` fasst Priorität, aktuelle Alarme und Änderungen seit dem letzten Lauf zusammen |
| 5 | die Modellpakete werden auf die neuen Daten angewendet (`src.dashboard_daten`), die Handlungsliste wird mit Datum gesichert |
| 6 | Notebook 31 aktualisiert den Netz-Cache mit den neuen Stundenreihen |
| 7 | Notebook 37 schreibt das Dashboard `notebooks/fernwaerme_dashboard_final.html` neu |

- Die Notebooks laufen dabei im Hintergrund, JupyterLab muss nicht geöffnet sein. Die Notebooks selbst werden nicht
  verändert, ihre Ausgaben stehen in `outputs/aktualisierung/`.
- Der Zeitraum der Karte reicht bis zum Ende der Messdaten, sobald die Mehrheit der Zähler neuere Daten hat.
- Voraussetzung für die Schritte 5 bis 7 sind die Modellpakete in `models/` (siehe Abschnitte 4 und 5
  oben) und die Handliste mit Koordinaten. Fehlen die Pakete, bricht der Befehl nach Schritt 4 mit einem Hinweis ab. Bericht und
  Stationsblätter sind dann bereits geschrieben.
- Mit `python -m src.aktualisieren --ohne-dashboard` laufen nur die Schritte 1 bis 4.
- Wie Begehungen zurückgemeldet und die Modelle im Betrieb geprüft werden, beschreibt
  [Betrieb bei der ÜZ](betrieb.md).

## Tests

```bash
python -m pytest -q
```

- Eine Testdatei je Modul in `tests/`. Die meisten Tests laufen ohne Rohdaten.
- Tests, die Begehungen oder echte Reihen brauchen, werden ohne diese Daten übersprungen.
- Welche Befehle und Module es gibt, steht unter [Befehle und Module](pipeline.md).
