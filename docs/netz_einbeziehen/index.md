# Netz einbeziehen

Die Modelle der übrigen Abschnitte sehen jede Station für sich. Dieser Abschnitt fragt, was das Netz dazu beiträgt:
Wo hängt eine Station, woher kommt ihr Wasser, und lässt sich eine Abweichung dem Haus oder dem Netz zuordnen? Er
beschreibt, wie aus Kantendatei und Leitungsplan ein Netzmodell entsteht, wie es geprüft wurde und warum das Ergebnis
für die Fehlererkennung ein Negativbefund ist. Den Code enthalten die Notebooks 31 bis 33 und 39. Wie die Datengrundlage 
aussieht und wie die Zuordnung funktioniert, steht unter [Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md).

## Die Fragen

| Frage | Antwort | Seite | Notebook |
|---|---|---|---|
| Welche Station hängt wo im Netz? | Netzmodell aus der Kantendatei, Zähler auf Nodes und Karte | [Vom Haus-Graph zum Rohrbaum](rohrbaum.md) | 31 |
| Wo speist das Netz ein, und in welche Richtung fließt es? | Schätzung aus dem Vorlauf, Kanten vom Erzeuger aus ausgerichtet | [Vom Haus-Graph zum Rohrbaum](rohrbaum.md) | 32 |
| Welchen Weg nimmt das Wasser wirklich? | Rohrbaum: kürzester Rohrweg vom Erzeuger zu jedem Haus | [Vom Haus-Graph zum Rohrbaum](rohrbaum.md) | 32 |
| Liegt eine Abweichung am Haus oder am Netz? | Vergleich eines Hauses mit seinen Nachbarn im Rohrbaum | [Haus oder Netz](haus_oder_netz.md) | 32 |
| Hilft das Netz bei der Fehlererkennung? | Basislinie mit und ohne Netz-Merkmale, aus den Daten gelernter Graph, GNN-Entwurf | [Fehlererkennung](fehlererkennung.md) | 32, 39 |

## Ergebnis in Kürze

- Der Rohrbaum aus dem Leitungsplan passt zum Vorlaufgefälle: Das obere Haus ist bei 36 von 38 Paaren wärmer.
- Das Netz wirkt auf alle Häuser gemeinsam. Ein Effekt je Strang ist nicht nachweisbar, weder im Rohrbaum noch in der
  Kantendatei noch in einem aus den Daten gelernten Graphen.
- Für die Fehlererkennung trägt der Sommernacht-Durchfluss beim Ventil (AUC 0,84 bis 0,87). Netz-Merkmale verbessern die
  Basislinie nicht.
- Ein GNN lohnt sich damit nicht. Das Ergebnis steht unter [GNN: Hilft das Netz?](../weitere_versuche/gnn.md).

## Der Weg

1. **Netzmodell aus allen zur Verfügung stehenden Dateien (Notebook 31):** Die Zähler und Adressen aus
   Zuordnung werden mit denen der Kantendatei abgeglichen, anschließend wird geprüft, welche davon über eine Zeitreihe
   verfügen. Über die Koordinatentabelle werden die konkreten Punkte auf die Karte gebracht und über den Leitungsplan
   mit den Rohren (106 von 111 Kanten, mit der Kante zum Erzeuger, liegen auf Rohren) verknüpft.
   Der Erzeuger kommt mit der Lage dazu, die die ÜZ nachgeliefert hat.
2. **Einspeisung gegenprüfen (Notebook 32):** Der Vorlauf kühlt entlang der Rohre ab. Für jeden Punkt im Rohrnetz wird
   geprüft, wie gut der Rohrweg zu ihm die Vorlaufunterschiede der Häuser erklärt. Das Ergebnis passt zur Lage, die die
   ÜZ genannt hat.
3. **Kanten ausrichten:** Mit dem Erzeuger als Quelle zeigt jede Kante vom näheren zum weiter entfernten Knoten. Die
   Messdaten entscheiden, ob das besser ist als die gerichteten Kanten der Datei.
4. **Rohrbaum bauen:** Auf Ebene der Rohre ist klar, wie ein Haus an den Straßenleitungen hängt. Für jedes Haus wird der
   kürzeste Rohrweg vom Erzeuger genommen, die Wege ergeben einen Baum.
5. **Haus oder Netz:** Ein Haus wird mit seinen Nachbarn im Baum und mit zufälligen Häusern verglichen.
6. **Fehlererkennung mit Netz-Merkmalen:** Sommernacht-Durchfluss, andere Zielgrößen und eine Basislinie, jeweils gegen
   die Begehungslabels geprüft.
7. **Graph aus den Daten lernen:** Umgekehrte Frage: Welche Häuser hängen laut Stundenwerten zusammen, und passt das
   zum Rohrbaum?
8. **GNN-Entwurf (Notebook 39):** Ein Graph-Modell, das die Messwerte der Nachbarn nutzt, gegen dasselbe Modell ohne
   Netz. Die Seite dazu ist [GNN: Hilft das Netz?](../weitere_versuche/gnn.md).

## Wie es zusammenläuft

```
Notebook 00   saubere Stundenreihen je Zähler
     │
Notebook 31   Kantendatei + Leitungsplan + Zuordnung + Koordinaten  ──►  Netz-Cache (daten_cache/paket.pkl)
     │
     ├──► Notebook 32   Einspeisung, Rohrbaum, Nachbarvergleich, Basislinie, gelernter Graph
     │         │
     │         ├──► daten_cache/gnn_daten.npz  ──►  Notebook 39   GNN-Entwurf
     │         └──► Rohrbaum für das Dashboard  ──►  Notebook 37
     │
     └──► Notebook 33   Netzkarte mit Monitorstatus
```

Ausgaben und Dateien dieser Notebooks enthalten Adressen. Sie bleiben intern.

## Annahmen und Grenzen

| Annahme oder Grenze | Folge |
|---|---|
| Lage des Erzeugers von der ÜZ nachgeliefert, die Vorlauf-Schätzung passt dazu | Die Schätzung findet den Punkt, an dem die gemessenen Häuser „anfangen“, und trennt mehrere Einspeisepunkte nicht |
| Richtungen der Kanten | der Rohrbaum ist ein Kürzeste-Wege-Baum und kein hydraulisches Modell; Durchmesser, Drücke und Ringschlüsse fehlen |
| unechte Abzweige durch parallele Vor- und Rücklaufleitungen | die Zahl der Abzweige ist zu hoch; Tests je Abzweig sind davon betroffen |
| 30 Nodes ohne Zähler | sie fehlen im Rohrbaum und in den Tests |
| wenige positive Fälle (9 bis 30 je Label) | Unterschiede unter etwa 0,1 AUC sind Rauschen; das Ventil-Ergebnis beruht auf 10 Fällen |
| Beobachtungszeit vor dem Stichtag etwa acht Monate | nur ein Teil des Winters |


