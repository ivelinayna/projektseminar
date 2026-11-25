# Vier Verfahren im Vergleich

**Notebook 08:** `notebooks/3_clustering/08_clusterbenchmark.ipynb` · **Code:** Adressabgleich über
`_normalize_address` in `src/load_data.py`

[Notebook 07](stationscluster.md) findet mit K-Means keine klare Struktur. Dieses Notebook prüft, ob es am Verfahren
liegt. Vier Verfahren laufen auf denselben 93 Stationen, denselben 10 Merkmalen und derselben Vorverarbeitung:

- **K-Means:** teilt in k Gruppen um je ein Zentrum.
- **Ward:** fügt schrittweise die ähnlichsten Gruppen zusammen (hierarchisch).
- **GMM:** beschreibt die Daten als Mischung mehrerer Normalverteilungen.
- **HDBSCAN:** sucht dichte Bereiche und lässt den Rest als Rauschen stehen.

Bewertet wird mit der Silhouette, immer zusammen mit den Clustergrößen, und mit der **Stabilität**: 25-mal werden die
Stationen mit Zurücklegen neu gezogen und neu geclustert, dann wird die Aufteilung mit der auf allen Daten verglichen
(Bootstrap-ARI, 1 = immer dieselbe Aufteilung, 0 = Zufall). Die Silhouette misst die Form der Wolke, nicht, ob ein
Ergebnis stabil ist.

## Ergebnis

| Verfahren | k | Silhouette | Clustergrößen | Stabilität (ARI) |
|---|---|---|---|---|
| K-Means | 2 | 0,237 | 31/62 | **0,67** |
| K-Means | 3 | 0,219 | 30/60/3 | 0,45 |
| Ward | 2 | 0,179 | 36/57 | 0,28 |
| Ward | 3 | 0,164 | 4/57/32 | 0,31 |
| GMM | 2 | 0,312 | 76/17 | 0,43 |
| GMM | 3 | 0,156 | 16/20/57 | 0,36 |
| HDBSCAN (mindestens 3 je Cluster) | – | 0,217 | 44/4, dazu 45 Rauschen | 0,06 |
| HDBSCAN (mindestens 5 oder 8) | – | – | alles Rauschen | – |

- **Keine belastbare Struktur.** Nur GMM mit k = 2 liegt knapp über 0,25, bei einer sehr ungleichen Aufteilung.
- **K-Means ist am stabilsten**, aber deutlich unter dem Wert 0,90 aus dem früheren K-Means-Notebook. Der hatte K-Means
  als stabil ausgewiesen, obwohl die Struktur fachlich schwach war.
- Mehr als drei Cluster zerlegen bei allen Verfahren nur die Masse weiter, ohne bessere Silhouette als bei k = 2.
- **HDBSCAN trägt nicht:** Ab 5 Stationen Mindestgröße ist alles Rauschen, bei 3 bleibt rund die Hälfte unzugeordnet.

## Worin sich die Verfahren einig sind

- **Nur über die Ausreißer, und auch das nur K-Means und Ward.** 58202380 und 66761022 sind der robusteste
  Einzelbefund: K-Means und Ward trennen sie bei k = 3 als Kleinst-Cluster ab (Winterrücklauf über 60 °C,
  Sommer-Durchfluss über 2.000 l/h, kaum Leerlauf). GMM sieht sie nicht als eigene Gruppe.
- Paarweise stimmen die Verfahren nur mäßig überein (ARI 0,35 bis 0,48). Wie die Masse aufgeteilt wird, hängt vom
  Verfahren ab.
- Die Trennachse ist fachlich richtig: Rücklauf, Leerlauf und Spreizung. Die schwach gespreizte Gruppe (30 Stationen,
  Rücklauf 53,6 °C bei 16,2 K Spreizung) ist die fachlich interessante.

## Abgleich mit den Begehungen

- Kein Cluster ist signifikant maßnahmenreicher als die anderen (Fisher-Test p ≥ 0,33, Mann-Whitney p ≥ 0,08).
- Die Basisrate liegt bei 77 % (56 Stationen im Abgleich): Fast jede begangene Station hat eine Maßnahme. Damit lässt
  sich nichts trennen (siehe [Wirkung im 21-Tage-Fenster](../begehungen/wirkung.md#ereignis-statt-label)).
- Der Ausreißer-Cluster fehlt in den Begehungsdaten ganz und lässt sich nicht testen.

## Ausgabe

- `data/processed/cluster_benchmark.csv`: eine Zeile je HAST mit der Clusterzuordnung aller vier Verfahren.
  HDBSCAN-Rauschen steht als −1 in der Datei.
- `data/processed/cluster_benchmark.json`: Silhouette, Clustergrößen und Bootstrap-ARI je Verfahren und k, dazu Seed
  und die in Notebook 00 entfernten Zähler.
