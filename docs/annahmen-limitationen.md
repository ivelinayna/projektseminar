# Annahmen und Limitationen

Ehrliche Einordnung dessen, was die aktuellen Ergebnisse tragen — und
was nicht. Stand 2026-07-08.

## Annahmen (markiert, nicht validiert)

1. **Synthetisches Datenmodell.** `synth_data.py` modelliert
   Wärmebedarf, Vorlaufkurve und Fehlerbilder mit plausiblen, aber
   angenommenen Parametern (Heizgrenze 15 °C, Auslegungs-ΔT 30 K,
   Spitzenlast ~70 % des Anschlusswerts, DHW-Burstiness). Diese
   Parameter stammen nicht aus ÜZ-Messdaten.
2. **Schwellenwerte der Baseline.** Die Regeln in `fault_detection.py`
   (z. B. Winter-RT > 48 °C, Sommer-Medianfluss > 25 l/h) sind auf die
   synthetischen Daten kalibriert und müssen an echten Daten mit der
   Begehungs-Ground-Truth neu kalibriert werden.
3. **Fehlerbilder.** Die 5 Fehlerfamilien decken die im Begehungs-Excel
   dokumentierten Maßnahmen ab, sind aber eine Vereinfachung; reale
   Fehler können kombiniert oder anders ausgeprägt auftreten.
4. **Ortsname.** Das Teilnetz ist Wiesentheid (frühere Doku sagte
   fälschlich Prichsenstadt; eine Adresse „Prichsenstädter Straße"
   erklärt die Verwechslung vermutlich).

## Limitationen

1. **100 % Accuracy ist Pipeline-Validierung, kein Ergebnis.** Die
   Baseline erkennt exakt die Fehler, die derselbe Code injiziert hat.
   Auf echten Daten ist deutlich schlechtere Trennschärfe zu erwarten.
2. **Echte Zeitreihen sind noch nicht angeschlossen.** Die CSVs liegen
   vor und `load_timeseries.py` liest sie, aber Features/Detection
   laufen noch auf synthetischen Daten. Offene Entscheidungen:
   Analysefenster (Features erwarten ~1 Jahr), Umgang mit Zählertausch,
   Umgang mit Messrauschen (negative Flüsse) und Lücken.
3. **Geocoding-Lücke ist ein Datenproblem, kein Codeproblem.** OSM hat
   für das Neubaugebiet keine ausreichenden Hausnummern; mehrere HAST
   fallen auf Straßenmittelpunkte zusammen. Karten-Positionen einzelner
   HAST sind daher nicht belastbar, bis ÜZ-Koordinaten oder
   BKG-Geocoding vorliegen.
4. **Logischer und räumlicher Graph sind unverbunden.** Das geplante
   Snapping HAST → Rohrknoten hängt an verlässlichen Koordinaten
   (siehe Punkt 3).
5. **8 Waisen-HAST** ohne Kanten in der Topologie — vermutlich
   Datenqualität bei ÜZ, bis zur Klärung fehlen sie in Netzanalysen,
   die Konnektivität voraussetzen.
6. **Begehungsabdeckung 63 %.** 35 der 94 HAST-Adressen haben keine
   Ground Truth; für sie kann kein Label-basiertes Training/Scoring
   erfolgen.
7. **Kein ML/GNN.** Bewusst zurückgestellt, bis echte Zeitreihen
   integriert, Labels gejoint und die Baseline als Benchmark gemessen
   ist (Anforderung aus CLAUDE.md).

## Verworfene / begrenzte Ansätze

- **Nominatim-only-Geocoding** wurde gebaut, liefert aber wegen der
  OSM-Hausnummernlücke Straßenmittelpunkte — als alleinige Quelle
  verworfen; Cache + `address_overrides.csv` bleiben als Übergang.
- **Direkter Join Shapefile-Punkte ↔ Adressen** ist unmöglich (nur 16
  unbeschriftete Punkte im Shapefile).
