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

Alle Notebooks liegen unter `notebooks/3_clustering/` und laufen nach Notebook 00.

## Die Notebooks

| Notebook | Frage | Ergebnis in einem Satz |
|---|---|---|
| [07 Stationscluster](stationscluster.md)<br>`07_stationscluster.ipynb` | Lassen sich die HAST mit K-Means in Betriebsprofile gruppieren? | Keine klare Struktur, aber eine fachlich lesbare Trennung nach Rücklauf, Spreizung und Sommer-Durchfluss. |
| [08 Vier Verfahren im Vergleich](benchmark.md)<br>`08_clusterbenchmark.ipynb` | Findet ein anderes Verfahren mehr Struktur? | Nein. K-Means ist am stabilsten, einig sind sich die Verfahren nur über zwei Ausreißer. |
| [09 Stundencluster und Validierung](validierung.md)<br>`09_clustervalidierung.ipynb` | Trägt ein Clustering der einzelnen Stunden, oder bildet es nur die Jahreszeit ab? | Fünf stabile Betriebszustände, darunter ein Verdacht auf hydraulischen Kurzschluss in 13 % der Stunden. |
| [10 Tagescluster](tagescluster.md)<br>`10_tagescluster.ipynb` | Welche Tagestypen gibt es, und liegen die Tage einer HAST zusammen? | Vier Typen an Heiztagen, drei im Sommer. Dauerdurchfluss grenzt sich klar ab, und die Station prägt ihre Tage. |

## Wie die Notebooks aufeinander aufbauen

- **07 ist der Ausgangspunkt.** K-Means auf der Kennzahlentabelle `hast_features.csv` aus Notebook 00, eine Zeile je
  Station. Die Silhouette bleibt unter 0,25, die Flotte ist eher ein Kontinuum als eine Menge klarer Typen.
- **08 prüft, ob es am Verfahren liegt.** Ward, GMM und HDBSCAN auf denselben Merkmalen, dazu die Stabilität über
  Bootstrap. Keins findet mehr.
- **09 prüft die Merkmale und geht auf die Stunde.** Auf Stationsebene ändert auch eine andere Gewichtung der
  Merkmale nichts. Werden dagegen die einzelnen Betriebsstunden geclustert, entstehen stabile Zustände.
- **10 geht auf den Tag.** Es nutzt die Zeitachse, die in einer Zeile je Station verloren geht, und vergleicht nur
  Tage mit ähnlichem Wetter.

## Gesamtbild

- **Je Station gibt es keine klaren Gruppen.** Über alle Verfahren und Gewichtungen bleibt die Silhouette auf
  Stationsebene unter 0,25 (Ausnahme GMM mit 0,31 bei einer 76/17-Aufteilung). Robust sind nur zwei Ausreißer,
  58202380 und 66761022.
- **Feiner aufgelöst wird es klarer.** Die Stundencluster sind stabil (Silhouette 0,40), im Sommer und in der
  Übergangszeit trennen sich die Tage deutlich (Silhouette 0,74).
- **Auf allen Ebenen taucht dasselbe Muster auf:** viel Wasser, kaum Abkühlung, hoher Rücklauf, auch nachts. Auf
  Stationsebene ist das Cluster 0 in Notebook 07, bei den Stunden der Kurzschlussverdacht, bei den Tagen der Typ
  „Dauerdurchfluss“. Es ist dasselbe Bild, das die Label-Regel aus [Notebook 03](../begehungen/labels.md) beschreibt.
- **Die Station prägt ihre Tage.** Die Tage einer HAST landen deutlich häufiger im selben Cluster als bei Zufall.
  Stationsprofile sind also sinnvoll, auch wenn sich die Stationen nicht in klare Gruppen teilen.
- **Die Begehungen trennen die Cluster nicht.** Kein Cluster ist signifikant maßnahmenreicher (08), der Abgleich der
  Stundenzustände bleibt ohne p < 0,05 (09). Das Problem ist das Label, nicht die Methode.

## Ausgaben

Alle Tabellen landen unter `data/processed/` und bleiben lokal.

| Notebook | Datei | Inhalt |
|---|---|---|
| 07 | `hast_clusters.csv`, `.json` | Cluster je Station mit den 10 Merkmalen und der Abdeckung, **enthält Adressen** |
| 08 | `cluster_benchmark.csv`, `.json` | Ergebnisse je Verfahren und k |
| 09 | `clustervalidierung.csv`, `.json` | Stundenzustände und Prüfergebnisse |
| 10 | `hast_tage.csv`, `hast_tage_clusteranteile.csv`, `hast_tage.json` | eine Zeile je HAST und Tag mit Merkmalen, Markierungen und Tagestyp |

Die Tageszeilen aus Notebook 10 sind die Grundlage für spätere Notebooks, unter anderem das Normalverhaltensmodell
(Notebook 18) und die Notebooks 30, 34 und 39.
