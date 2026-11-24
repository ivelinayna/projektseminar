# Vom Haus-Graph zum Rohrbaum

Die Kantendatei der ÜZ war der erste Netzgraph des Projekts. Warum der Rohrbaum sie ersetzt hat wird auf
dieser Seite der Reihe nach begründet: was die Kantendatei kann, was die Messdaten dazu sagen, wie aus dem Leitungsplan ein
Rohrnetz wird und wie der Baum geprüft wurde. Den Code enthalten die Notebooks 31 und 32.

## 1 Ausgangspunkt: die Kantendatei

- `Nodes_Edges.ods` enthält 110 Kanten zwischen Adressen. Sie verbinden Häuser direkt miteinander.
- In einem Fernwärmenetz fließt das Wasser aber von der Straßenleitung ins Haus und zurück, nicht von Haus zu Haus. Die Karte legt aber nahe, dass
  Kanten die Anschlussreihenfolge der Häuser entlang einer Straße abbilden, nicht den Rohrverlauf.
- Jede Kante hat eine Richtung (gerichtete Kante). Es gibt aber 7 Nodes ohne Zufluss und 6 mit mehreren Zuflüssen, also
  keinen einzelnen Startpunkt.

Die Datei sagt damit, welche Stationen im Netz nah beieinander hängen. In welche Richtung das
Wasser fließt, sagt sie nicht.

## 2 Einspeisung gegenprüfen

Die Lage des Erzeugers hat die ÜZ nachgeliefert. Ob sie zu den Messdaten passt, prüft Notebook 32 mit dem Vorlauf: Er
kühlt entlang der Rohre ab, Häuser nahe der Einspeisung bekommen im Mittel wärmeres Wasser.

- Je Haus die mittlere Abweichung des Vorlaufs vom Netzmittel, nur Dezember bis Februar und nur Stunden mit Durchfluss.
- Je Punkt im Rohrnetz die Rangkorrelation (Spearman) zwischen dieser Abweichung und dem Rohrweg zum Punkt. An der
  echten Einspeisung ist sie stark negativ.
- Zufallsvergleich: Die Häuser werden 300-mal vertauscht. Ein Signal gibt es nur, wenn der echte Wert klar unter der
  5-%-Grenze liegt.

| Ergebnis | Wert |
|---|---|
| beste Rangkorrelation | −0,70 |
| 5-%-Grenze bei vertauschten Häusern | −0,28 |
| die 5 besten Punkte | −0,68 bis −0,70 |
| Vorlaufverlust an diesen Punkten | 0,77 bis 1,36 K je 100 m Rohr |
| Lage des Erzeuger-Knotens aus Notebook 31 | Rang 2 und 3 |

- Das Signal ist deutlich. Die Lage der ÜZ passt zur Schätzung.
- Die fünf besten Punkte liegen dicht beieinander. Die Schätzung trennt sie kaum.
- Gefunden wird der Punkt, an dem die gemessenen Häuser „anfangen“, nicht zwingend die Heizzentrale. Mehrere
  Einspeisepunkte lassen sich nicht trennen, und Stichleitungen mit wenig Durchfluss kühlen aus und verzerren. Das
  Ergebnis ist eine Schätzung, kein Messwert. Sie prüft die Angabe der ÜZ und ersetzt sie nicht.
- Im Januar und Februar sinkt der Vorlauf um 1,21 K je 100 m Rohrweg.

## 3 Gerichtete Kanten gegen Messdaten

Der Erzeuger wird zur Quelle des Netzes. Danach zeigt jede Kante vom näheren zum weiter entfernten Knoten (gezählt in
Kanten bis zum Erzeuger, bei Gleichstand entscheidet der Name). Dabei werden 54 von 111 Kanten umgedreht. Alle Knoten
sind vom Erzeuger aus erreichbar.

Je Kante mit Messungen an beiden Enden: Sinkt der Vorlauf in Kantenrichtung? Gewertet werden Durchfluss ab 20 l/h,
November bis März und mindestens 100 gemeinsame Stunden. Unter 0,5 K gilt als unklar.

| Richtung | Vorlauf sinkt | Vorlauf steigt |
|---|---|---|
| wie in der Datei | 22 | 26 |
| vom Erzeuger weg | 26 | 22 |

- Es sind 56 Kanten bewertbar, 8 davon unklar. Die Richtung vom Erzeuger weg passt etwas besser, der Unterschied ist
  klein.
- Auf Ebene der Hauskanten bleibt die Richtung damit unsicher. Das spricht für den Wechsel auf die Rohrebene.

## 4 Rohrnetz aus dem Leitungsplan

Die Kantendatei verbindet Häuser, der Leitungsplan zeigt die Rohre. Notebook 32 baut daraus ein physisches Netz.

- Der Leitungsplan wird in Stücke von etwa 2 m zerlegt. Lücken bis 2,5 m werden überbrückt, damit getrennte
  Linienstücke zusammenhängen.
- Vor- und Rücklauf liegen als parallele Linien im Plan. Das erzeugt etwa 2000 Ringe, die keine echten Schleifen sind.
  Sie stören nicht, solange alle Häuser angeschlossen sind.

## 5 Erzeuger und Häuser anbinden

- Der Erzeuger liegt 6 m neben dem nächsten Rohrpunkt und kommt auf diesen Punkt.
- Jedes Haus hängt am nächsten Rohrpunkt (höchstens 40 m entfernt). Alle 109 Häuser sind mit dem Erzeuger verbunden.
  Der Anschlussabstand liegt im Median bei 6 m, höchstens bei 36 m. 9 Häuser teilen sich eine Anschlussstelle.

## 6 Der Baum

- Für jedes Haus mit Zähler wird der kürzeste Rohrweg vom Erzeuger genommen. Zusammen ergeben die Wege einen Baum.
- Aus den kürzesten Wegen bleiben als Schlüsselpunkte der Erzeuger, die Anschlussstellen der Häuser und die Knoten, an
  denen sich der Baum verzweigt. Die Abschnitte dazwischen haben eine Länge und eine Zahl der Häuser dahinter.

| Rohrbaum | Wert |
|---|---|
| Häuser mit Zähler | 79 |
| Abzweige | 72 |
| genutzte Rohrlänge | 3804 m von 9577 m im Plan |

## 7 Prüfung gegen die Messdaten

Test „oberes Haus wärmer“: Das nächste Haus flussaufwärts sollte wärmeren Vorlauf haben.

| Test | Kantendatei | Rohrbaum |
|---|---|---|
| Vorlauf sinkt in Kantenrichtung (Kanten) | 22 von 56 (Richtung wie in der Datei), 26 von 56 (vom Erzeuger weg) | – |
| oberes Haus hat wärmeren Vorlauf (Paare) | – | 36 von 38, bei einem kälter, bei einem unklar |

Die beiden Tests messen nicht dasselbe. Sie zeigen aber, dass der Rohrbaum zum Vorlaufgefälle passt und die Hauskanten
nicht.

## 8 Grenzen

- Der Baum ist ein Kürzeste-Wege-Baum, kein hydraulisches Modell. Durchmesser, Drücke und Ringschlüsse fehlen. Die
  Richtungen bleiben Annahmen.
- Ein Teil der Abzweige ist unecht: Wo Vor- und Rücklauf nah beieinander liegen, wechselt der kürzeste Weg manchmal
  zwischen beiden Leitungen.
- Von den Nodes der Kantendatei haben 79 einen Zähler. Die 30 ohne Zähler fehlen im Baum und in den Tests.

