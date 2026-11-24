# Daten aufbereiten

Notebook 00 macht aus den 198 Exportdateien der ÜZ je Zähler eine saubere Stundenreihe und daraus eine Tabelle mit
einer Zeile je Station. Alle weiteren Notebooks bauen darauf auf.

Was in den Rohdaten steckt, steht unter [Zählerdaten](../datengrundlage/zaehlerdaten.md). Dieser Abschnitt beschreibt den
Ablauf und vor allem, warum die einzelnen Schritte nötig wurden. Viele davon kamen erst im Lauf des Projekts dazu,
meist weil ein Ergebnis nicht plausibel aussah oder die ÜZ eine Frage beantwortet hat.

## Ablauf auf einen Blick

1. **Dateien einsammeln:** alle CSV- und ODS-Exporte unter `data/raw/` nach Zählernummer gruppieren, den falschen
   Dateinamen korrigieren und die Zähler entfernen, die keine Hausstation sind.
2. **Jede Datei lesen und prüfen:** fehlende Spreizung ergänzen, Zeilen ohne Messwert verwerfen, ODS-Werte
   zurückrechnen, unmögliche Werte maskieren.
3. **Je Zähler zusammenführen:** Zeitstempel auf die volle Stunde abrunden, sortieren, doppelte Stunden entfernen.
4. **Lückenloses Stundenraster:** für jede Stunde eine Zeile, nicht gemessene Stunden bleiben leer.
5. **Adresse und Anschlusswert zuordnen:** aus `Zuordnung.xlsx` und `Nodes_Edges.ods`.
6. **Kennzahlen je Station:** 14 Kennzahlen aus der Stundenreihe, dazu Zählernummer, Adresse, Anschlusswert und
   Abdeckung.

Jeder Schritt steht genauer unter [Die Schritte im Einzelnen](schritte.md).

Ergebnis sind zwei Ablagen unter `data/processed/`:

| Ablage | Inhalt | Wer sie nutzt |
|---|---|---|
| `real_meters/` | eine CSV je Zähler, 93 Dateien, Stundenraster in deutscher Lokalzeit, Zählerstände bleiben drin | alle Notebooks, die mit Zeitreihen arbeiten |
| `hast_features.csv` | 93 Zeilen, 20 Spalten | Clustering in Notebook 07 |

Die Rohdaten bleiben unverändert. Jede Korrektur steht im Code und wird bei jedem Lauf neu angewendet.

### Was der letzte Lauf ausgibt

| Schritt | Ergebnis |
|---|---|
| Dateien gefunden | 198 Dateien für 101 Zählernummern |
| Dateiname korrigiert | 1 (`721354800` → `72135480`) |
| keine Hausstation, ausgeschlossen | 8 |
| zusammengeführt | 93 Zähler |
| ODS-Dateien zurückgerechnet | 5 |
| Spreizung berechnet | 1 Datei |
| Zeilen ohne Messwert verworfen | 509 |
| Messzellen als unmöglich maskiert | 0 |
| Zeilen aus der Exportüberlappung entfernt | 367.298 |
| Zeilen aus dem Minutenversatz entfernt | 29.945, bei 3 Zählern |
| Stundenraster | 2.128.400 Stunden, davon 1.694.131 gemessen (80 %) |

## Wie die Aufbereitung gewachsen ist

Notebook 00 führt jede Änderung mit Grund und Wirkung in seinen Notizen. Viele Schritte kamen erst im Lauf des
Projekts dazu, in drei Runden:

1. **[Rohdaten lesbar machen](rohdaten.md):** ODS-Werte zurückrechnen, Zeitstempel abrunden, lückenloses
   Stundenraster, Plausibilitätsgrenzen, keine Umrechnung nach UTC, Erzeuger und Kessel ausschließen.
2. **[Kennzahlen ans Raster anpassen](kennzahlen.md):** Anteile nur über gemessene Stunden, Abdeckung in der
   Kennzahlentabelle, Wirkung auf die Regelhysterese, Jahreswerte normiert.
3. **[Rückmeldung der ÜZ](uez_rueckmeldung.md):** Temperaturfühler im Heizhaus, falscher Dateiname,
   Adresskorrektur, Zeilen ohne Messwerte, Filtertrend, Anschlusswert über die Adresse.
