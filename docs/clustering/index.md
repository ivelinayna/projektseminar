# Merkmale und Clustering

Die Begehungen liefern kein brauchbares Label (siehe [Label aus Messdaten](../begehungen/labels.md)). Clustering
braucht keines: Es sucht in den Messdaten selbst nach Gruppen. Dieser Teil fragt deshalb, ob sich die Stationen nach
ihrem Betriebsverhalten gruppieren lassen und ob sich dabei gesunde von auffälligen trennen.

Gerechnet wird auf drei Ebenen, die immer feiner werden:

| Ebene | Eine Zeile ist | Notebooks |
|---|---|---|
| Station | eine HAST mit ihren Kennzahlen über die ganze Historie | 07, 08 |
| Stunde | eine Betriebsstunde einer HAST | 09 |
| Tag | eine HAST an einem Tag, getrennt nach Außentemperatur | 10 |

Alle Notebooks liegen unter `notebooks/3_clustering/` und laufen nach Notebook 00. 08 und 09 brauchen zusätzlich
`inspections_tidy.csv` aus `python -m src.main`.

## Die Notebooks

| Notebook | Frage | Ergebnis in einem Satz |
|---|---|---|
| [07 Stationscluster](stationscluster.md)<br>`07_stationscluster.ipynb` | Lassen sich die HAST mit K-Means in Betriebsprofile gruppieren? | Keine klare Struktur, aber eine fachlich lesbare Trennung nach Rücklauf, Spreizung und Sommer-Durchfluss. |
| [08 Vier Verfahren im Vergleich](benchmark.md)<br>`08_clusterbenchmark.ipynb` | Findet ein anderes Verfahren mehr Struktur? | Nein. K-Means ist am stabilsten. K-Means und Ward trennen dieselben zwei Ausreißer ab, sonst sind sich die Verfahren kaum einig. |
| [09 Stundencluster und Validierung](validierung.md)<br>`09_clustervalidierung.ipynb` | Trägt ein Clustering der einzelnen Stunden, oder bildet es nur die Jahreszeit ab? | Fünf stabile Betriebszustände, darunter ein Verdacht auf hydraulischen Kurzschluss in 13 % der Stunden. |
| [10 Tagescluster](tagescluster.md)<br>`10_tagescluster.ipynb` | Welche Tagestypen gibt es, und liegen die Tage einer HAST zusammen? | Vier Typen an Heiztagen, drei im Sommer. Dauerdurchfluss grenzt sich klar ab, und die Station prägt ihre Tage. |

## Wie die Notebooks aufeinander aufbauen

- **07 ist der Ausgangspunkt.** K-Means auf der Kennzahlentabelle `hast_features.csv` aus Notebook 00. Darin ist jede
  Station auf eine Zeile verdichtet: 14 Kennzahlen über die ganze Historie, etwa Winterrücklauf, Spreizung unter Last,
  Sommer-Durchfluss und Leerlaufanteil, dazu Zählernummer, Adresse, Anschlusswert und Abdeckung (siehe
  [Daten aufbereiten, Schritt 6](../aufbereitung/schritte.md#6-kennzahlen-je-station)). 07 nutzt 10 der 14 Kennzahlen
  (siehe [Merkmale](stationscluster.md#merkmale)). Die Silhouette bleibt unter 0,25, die Flotte ist eher ein
  Kontinuum als eine Menge klarer Typen.
- **08 prüft, ob es am Verfahren liegt.** Ward, GMM und HDBSCAN auf denselben Merkmalen, dazu die Stabilität über
  Bootstrap. Keins findet mehr. K-Means und Ward trennen dieselben zwei Ausreißer ab, sonst sind sich die Verfahren
  kaum einig (paarweiser ARI 0,35 bis 0,48).
- **09 prüft die Merkmale und geht auf die Stunde.** Auf Stationsebene ändert auch eine andere Gewichtung der
  Merkmale nichts. Werden dagegen die einzelnen Betriebsstunden geclustert, entstehen stabile Zustände.
- **10 geht auf den Tag.** Es nutzt die Zeitachse, die in einer Zeile je Station verloren geht, und vergleicht nur
  Tage mit ähnlichem Wetter.

## Gesamtbild

- **Je Station gibt es keine klaren Gruppen.** Mit den 10 Merkmalen aus 07 und 08 bleibt die Silhouette unter 0,25
  (Ausnahme GMM mit 0,31 bei einer 76/17-Aufteilung), mit allen 21 Merkmalen aus 09 bei k = 3 zwischen 0,26 und 0,31.
  Höhere Werte gibt es nur, wenn vier extreme Stationen abgetrennt werden (89/4, Silhouette 0,61). Robust sind nur
  zwei Ausreißer, 58202380 und 66761022.
- **Feiner aufgelöst wird es teilweise klarer.** Die Stundencluster sind stabil (Silhouette 0,40, Bootstrap-ARI
  0,85). Im Sommer und in der Übergangszeit trennen sich die Tage deutlich (Silhouette 0,74 bei zwei Typen, 0,50 bei
  den gewählten drei), an Heiztagen nur schwach (0,27 bis 0,30).
- **Auf allen Ebenen taucht dasselbe Muster auf:** viel Wasser, kaum Abkühlung, hoher Rücklauf, auch nachts. Am
  deutlichsten ist es bei den Stunden (Kurzschlussverdacht, 4,2 K Spreizung, 71 °C Rücklauf) und bei den Tagen (Typ
  „Dauerdurchfluss“, rund 3,5 K und 72 °C). Auf Stationsebene zeigt es sich in abgeschwächter Form als Cluster 0 in
  Notebook 07 (15,9 K, 55 °C). Es ist dasselbe Bild, das die Label-Regel aus
  [Notebook 03](../begehungen/labels.md) beschreibt.
- **Die Station prägt ihre Tage.** Die Tage einer HAST landen deutlich häufiger im selben Cluster als bei Zufall
  (Median der Konzentration 0,68 bis 0,88, bei Zufall 0,35 bis 0,54). Stationsprofile sind also sinnvoll, auch wenn
  sich die Stationen nicht in klare Gruppen teilen.
- **Die Begehungen trennen die Cluster nicht.** Kein Cluster ist signifikant maßnahmenreicher (08), der Abgleich der
  Stundenzustände bleibt ohne p < 0,05 (09). Das Problem ist das Label, nicht die Methode.

## Ausgaben

Alle Tabellen landen unter `data/processed/` und bleiben lokal.

| Notebook | Datei | Inhalt |
|---|---|---|
| 07 | `hast_clusters.csv`, `.json` | Cluster je Station mit den 10 Merkmalen und der Abdeckung, **enthält Adressen** |
| 08 | `cluster_benchmark.csv`, `.json` | Clusterzuordnung je HAST für alle vier Verfahren; im JSON Silhouette, Größen und Bootstrap-ARI je Verfahren und k |
| 09 | `clustervalidierung.csv`, `.json` | je Station der Anteil ihrer Stunden in den fünf Zuständen, keine Stundenreihe |
| 10 | `hast_tage.csv`, `hast_tage_clusteranteile.csv`, `hast_tage.json` | eine Zeile je HAST und Tag mit Merkmalen, Markierungen und Tagestyp |

Die Tageszeilen aus Notebook 10 sind die Grundlage für spätere Notebooks, unter anderem das Normalverhaltensmodell
(Notebook 18) und die Notebooks 30, 34 und 39.
