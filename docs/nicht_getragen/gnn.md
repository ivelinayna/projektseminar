# GNN: Hilft das Netz?

**Notebook 39:** `notebooks/weitere_versuche/39_gnn.ipynb`

## Die Idee

Das Normalverhaltensmodell (Notebook 18) lernt für jede Station, wie viel Wasser sie bei welcher Außentemperatur
normalerweise braucht und wie stark sie es abkühlt. Weicht ein Tag davon ab, kann das ein Fehler in der Station sein.
Es kann aber auch von außen kommen, zum Beispiel vom Netz: Der Vorlauf kommt kälter an, oder ein Strang zieht gerade
viel Wärme.

Alle Stationen hängen am selben Leitungsnetz. Kommt ein Teil der Abweichung vom Netz, müssten ihn die Nachbarn auch
sehen. Ein **GNN** (Graph Neural Network) ist ein neuronales Netz, das genau dafür gebaut ist: Es rechnet auf dem
Leitungsnetz und liest für jede Station die Messwerte ihrer Nachbarn mit. Die Idee war, damit den Teil der Abweichung
herauszurechnen, der vom Netz kommt. Übrig bliebe, was wirklich in der Station passiert, also ein saubereres
Fehlersignal.

## Umsetzung und Hürden

- **Das Netz zusammensetzen.** Welche Station neben welcher hängt, steht in der Kantendatei der ÜZ
  (`Nodes_Edges.ods`). Sie verbindet Häuser direkt miteinander, nicht über die echten Leitungen. Ihre Richtungen passen zu
  keiner einzelnen Quelle, was sie bedeuten, ist unklar. Das GNN nutzt die Verbindungen deshalb ohne Richtung.
- **Lücken im Netz.** 27 von 111 Knoten haben keinen Zähler, etwa Abzweige, Schächte oder Häuser ohne Fernauslesung.
  Sie bleiben als leere Zwischenstücke drin, damit die Stränge nicht zerfallen. 18 Adressen haben keine Koordinate,
  35 Verbindungen keine Rohrlänge.
- **Die Einspeisung.** Das Notebook setzt die Quelle auf einen Punkt aus dem Wärmenetzplan. Parallel dazu hat die ÜZ
  bestätigt, welcher Knoten der Erzeuger ist (Notebook 32). Der Punkt im GNN liegt rund 50 m daneben, der bestätigte
  Knoten wurde nicht mehr eingebaut.
- **Kein fertiges Werkzeug.** Für den verwendeten Intel-Mac gab es keine passende PyTorch-Version. Das Modell ist
  deshalb von Hand in numpy geschrieben, sein Rechenweg ist gegen Zahlenableitungen geprüft.
- **Ehrlich prüfen.**
    - Dasselbe Modell läuft einmal mit und einmal ohne Netz. Der Unterschied ist genau der Beitrag des Netzes.
    - Gelernt wird auf drei Heizperioden, geprüft auf der vierten. So kennt das Modell die Prüftage nicht.
    - Die eigenen Messwerte einer Station bleiben für ihre Vorhersage verborgen. Sonst könnte das Modell sie über die
      Nachbarn einfach abschreiben.
    - Gelernt und geprüft wird nur vor der ersten Begehung einer Station, damit Eingriffe vor Ort nicht als normal
      gelten.

## Ergebnis

- **Das Netz bringt nichts Messbares.** Mit Netz erklärt das Modell bei der Abkühlung 1 Prozentpunkt mehr von der
  Abweichung als ohne, bei der Wassermenge 1 Prozentpunkt weniger. Je Station ist der Unterschied nicht signifikant
  (p = 0,17 und 0,42).
- **Geholfen haben die neuen eigenen Merkmale,** etwa die Temperatur der Vortage, der eigene Vorlauf und die
  Jahreszeit. Schon ohne Netz erklärt das Modell 12,1 % (Abkühlung) und 18,5 % (Wassermenge) der Abweichung, die
  Notebook 18 übrig lässt. Das wäre eher eine Verbesserung für Notebook 18 selbst.
- **Im Ventilfall 68956351** ist das GNN sogar schlechter als Notebook 18 allein.

## Warum das Netz nichts gebracht hat

1. **Fehler sitzen im Haus, nicht im Netz.** Ein offenes Ventil oder eine falsche Einstellung betrifft eine einzelne
   Station, ihre Nachbarn merken davon nichts. Das zeigen auch andere Prüfungen: Nachbarn im Rohrbaum weichen nicht
   stärker gemeinsam ab als zufällig gewählte Häuser (Notebook 32), und im Modellvergleich verbessert das Netz weder
   Alarm noch Erkennung (siehe [Haus oder Netz](../modellvergleich.md#haus-oder-netz)).
2. **Nur der Vorlauf verbindet die Häuser.** Das Wasser fließt vom Erzeuger über die Straßenleitung ins Haus und über
   den Rücklauf zurück zum Erzeuger, nicht zum Nachbarn. Was Nachbarn teilen, ist der Vorlauf. Der fällt tatsächlich
   entlang der Leitung ab: Das Haus weiter oben im Strang ist bei 36 von 38 Paaren wärmer (Notebook 32). Den Vorlauf
   misst aber jede Station selbst, er steckt schon im Modell ohne Netz. Abkühlung und Wassermenge, an denen man
   Fehler sieht, hängen am Rücklauf und am Durchfluss im Haus, und die kommen beim Nachbarn nicht an.
   Die Vortests in Notebook 18 (Abschnitte 15 und 16) zeigen genau das: Beim Vorlauf hängen direkte Nachbarn
   zusammen (Korrelation 0,13 gegen 0,04 bei Zufallspaaren), bei Abkühlung und Wassermenge nicht (0,01 und −0,01,
   wie bei Zufallspaaren).
3. **Das Netz ist klein und dünn verbunden.** Es gibt 84 Stationen mit Zähler, die meisten haben nur ein bis drei
   Nachbarn, und die haben oft selbst keinen Zähler. Das Netz ist fast ein Baum mit nur einem Ring. Selbst ein kleiner
   Netz-Effekt ließe sich damit kaum vom Zufall trennen.

## Was es gebraucht hätte

- **Messgrößen, die wirklich durchs Netz laufen:** Vorlauftemperatur und Druck am Ausgang der Heizzentrale und an
  den Abzweigen. Dann ließe sich sehen, wann das Netz selbst schwankt.
- **Ein echtes Leitungsmodell:** Leitungen mit Länge und Durchmesser, der bestätigte Erzeuger als Quelle und die
  Fließrichtung, statt einer Liste, die Häuser direkt verbindet.
- **Mehr Stationen mit Fernauslesung,** damit die Nachbarn auch Messwerte haben.
- **Eine Frage, bei der das Netz zählt,** etwa ob Häuser am Ende eines Strangs zu kaltes Wasser oder zu wenig Druck
  bekommen. Für Fehler im einzelnen Haus reicht es, jede Station mit sich selbst zu vergleichen.

## Ausführen

- Vorher die Notebooks 10, 18 und 31 ausführen. Die Netztabellen aus Notebook 31 müssen in `notebooks/` liegen.
- Laufzeit rund 15 Minuten. Die technischen Einzelheiten (Merkmale, Masken, Bewertung) stehen im Notebook.
