# GNN: Hilft das Netz?

**Notebook 39:** `notebooks/weitere_versuche/39_gnn.ipynb` · **Code:** im Notebook (numpy, ohne PyTorch und ohne
`src/`)

Das Normalverhaltensmodell aus Notebook 18 lernt für jede Station eine eigene Kennlinie gegen die Außentemperatur. Für
jeden Heiztag sagt es, was normal wäre, und meldet die Abweichung z in Streuungen. Jede Station steht dort für sich.
Dieses Notebook fragt:

> Wird die Erwartung besser, wenn ein Modell auch die Nachbarn im Leitungsnetz kennt, und zwar wegen des Netzes?

Ein **GNN** (Graph Neural Network) ist ein neuronales Netz, das auf einem Graphen rechnet: Jeder Knoten mischt seine
eigenen Werte mit denen seiner Nachbarn. Was das GNN an z erklären kann, käme von außen (Netz, Wetter, Vorlauf) und
wäre kein Fehler der Station.

Erwartet war wenig Gewinn: Schon in Notebook 18 (Abschnitt 15) weichen Nachbarn nicht gemeinsam ab. Hier wird das mit
einem echten Modell statt mit Korrelationen geprüft.

## Aufbau als Ablation

| Modell | Was es weiß |
|---|---|
| Notebook 18 allein | Kennlinie der Station gegen die Tagesmitteltemperatur |
| ohne Netz (MLP) | dazu Temperatur der zwei Vortage, Wochenende, Jahreszeit, eigener Vorlauf und die Lage im Netz als feste Zahlen |
| GNN (GraphSAGE) | dazu die Messwerte der Nachbarn vom selben Tag, über bis zu zwei Kanten |

„Ohne Netz“ und „GNN“ sind dasselbe Modell, einmal ohne und einmal mit Kanten. Der Unterschied zwischen beiden ist
genau der Beitrag des Netzes.

## Das Netz

- Die Kanten kommen aus `Nodes_Edges.ods` (über die Netztabellen aus Notebook 31), ohne Richtung. Die Pfeile in der
  Datei passen zu keiner Quelle: 51 zeigen von der angenommenen Quelle weg, 54 zu ihr hin.
- Wo die Heizzentrale liegt, ist nicht bekannt. Angenommen ist ein Standort, von dem laut Wärmenetzplan mehrere
  Hauptleitungen ausgehen. Er liegt nicht genau an dem Erzeuger-Knoten, den Notebook 32 später aus dem Vorlauf
  schätzt.
- Ein Knoten je Zähler. Adressen ohne Zähler bleiben als Zwischenknoten, damit die Stränge nicht zerfallen. Zusammen
  sind es 111 Knoten (84 Zähler, 27 Zwischenknoten) und 113 Kanten.
- Lage je Adresse: Kanten und Rohrweg bis zur Quelle, „Last dahinter“ (Anschlusswert, der über diese Adresse versorgt
  wird, groß heißt Hauptstrang), Randlage, Strangende und Rohrdimension am Hausanschluss.
- Lücken: 18 von 110 Adressen haben keine Koordinate, für 35 Kanten fehlt der Rohrweg (dort gilt der Median von
  55 m).

## Das Modell

- **GraphSAGE mit zwei Schichten:** Jeder Knoten verbindet seinen eigenen Zustand mit dem Mittel seiner Nachbarn.
  Zwei Schichten reichen zwei Kanten weit und überbrücken Zwischenknoten.
- **Ziel:** z für Abkühlung (kWh/m³) und Wassermenge aus Notebook 18, gekappt bei ±8.
- **Eingaben je Knoten und Tag:** 15 eigene Merkmale und 6 Messwerte (z beider Kanäle und Vorlauf, je mit einer
  Angabe, ob der Wert vorhanden ist).
- **Masken:** Die eigenen Messwerte einer Station sind für ihre Vorhersage immer verborgen. Sonst könnte das GNN sie
  über einen Nachbarn zurückbekommen und einfach abschreiben. Nur der eigene Vorlauf ist erlaubt, weil er von einem
  anderen Fühler kommt.
- Gelernt und bewertet wird nur vor der ersten Begehung einer Station. Ab 14 Tage davor gilt sie nicht mehr als
  normal.
- **Warum numpy:** Auf dem verwendeten Intel-Mac gab es PyTorch nur bis Version 2.2, und die passt nicht zu numpy 2.
  Das Modell ist klein, die Rückwärtsrechnung ist von Hand geschrieben und gegen numerische Ableitungen geprüft
  (größter relativer Fehler 3,3 · 10⁻⁸).

## Prüfung

- **Kreuzvalidierung über die vier Heizperioden** 2021/22 bis 2024/25: Jede ist einmal Prüfzeit, gelernt wird auf den
  anderen drei. Zufällig gezogene Tage gingen nicht, weil am selben Tag alle Stationen dasselbe Wetter haben. Das
  Modell sähe dann besser aus, als es ist.
- Abbruch über 15 % der Trainingswochen, drei Startwerte je Variante und Heizperiode, zusammen 24 Modelle.
- **Skill** ist der Anteil des Fehlers von Notebook 18, den ein Modell zusätzlich erklärt. **Beitrag des Netzes** =
  Skill GNN minus Skill ohne Netz.
- **Hauptfrage, vorab festgelegt:** Ist das GNN je Station besser als ohne Netz? Wilcoxon-Test gepaart über die
  Stationen, Schwelle 0,025 wegen der zwei Kanäle.
- Bewertet wird auf Tagen nach der Referenz von Notebook 18. Im Referenzjahr ist Notebook 18 künstlich gut, weil die
  Kennlinie dort angepasst wurde. Diese Wahl fiel erst nach dem ersten Blick auf die Ergebnisse, deshalb stehen
  beide Bewertungen in der Tabelle.

## Ergebnis

| Bewertung | Kanal | ohne Netz | GNN | Beitrag des Netzes |
|---|---|---|---|---|
| nach der Referenz (59 Stationen) | Abkühlung | 0,121 | 0,131 | +0,010 |
| | Wassermenge | 0,185 | 0,176 | −0,009 |
| alle Tage vor der Begehung (80 Stationen) | Abkühlung | −0,083 | −0,017 | +0,066 |
| | Wassermenge | −0,051 | 0,011 | +0,062 |

- **Das Netz bringt keinen messbaren Gewinn.** Je Station (58) ist das GNN zwar bei 60 % bzw. 62 % besser als ohne
  Netz, aber nicht signifikant (p = 0,172 und 0,423).
- Je Heizperiode wechselt die Reihenfolge: 2023/24 liegt das Modell ohne Netz vorn, 2022/23 und 2024/25 das GNN.
- Auf allen Tagen vor der Begehung liegt das GNN etwas vor dem Modell ohne Netz. Beide sind dort aber nicht besser als
  Notebook 18 allein.
- **Die neuen eigenen Merkmale helfen:** Ohne Netz erklärt das Modell nach der Referenz 12 % (Abkühlung) und 19 %
  (Wassermenge) des Fehlers von Notebook 18. Ein fester Versatz je Station schafft nur 5 % und −1 %. Welche Merkmale
  das tragen (Vortage, Vorlauf, Jahreszeit), ist offen.
- **Ventilfall 68956351:** Vor der Begehung ist das GNN schlechter als Notebook 18 allein, mit einem mittleren Fehler
  von 0,77 gegen 0,53 (Abkühlung) und 1,62 gegen 1,44 (Wassermenge). Ohne Netz liegt es bei 0,55 und 1,25.
- Der eigene Vorlauf ist kein ganz unabhängiges Signal. Er ist mengengewichtet und hängt damit am eigenen
  Durchfluss. Für einen Alarm müsste er heraus oder durch den Vorlauf der Nachbarn ersetzt werden.

## Warum es nicht weiterverfolgt wird

- Das Netz erklärt nichts, also lohnt auch kein Alarm (CUSUM) auf den korrigierten Abweichungen.
- Das Ergebnis passt zu den übrigen Prüfungen des Netzes: Nachbarn weichen nicht gemeinsam ab (Notebook 18,
  Abschnitt 15, und Notebooks 23 und 24), und im Modellvergleich verbessert das Netz weder Alarm noch Erkennung (siehe
  [Haus oder Netz](../modellvergleich.md#haus-oder-netz)). Die Fehler sitzen im einzelnen Haus.
- Nicht ausprobiert, weil es ohne Netz-Effekt nichts bringt oder Daten fehlen: Pfeilrichtung (gerichtetes GNN),
  Kantengewichte nach Rohrlänge und Dimension, Stundenwerte, PyTorch Geometric und Attention. Abschnitt 10 des
  Notebooks nennt für jeden Punkt, wann er sich lohnen würde.

## Was es zum Weitermachen bräuchte

| Was | Wofür |
|---|---|
| Lage der Heizzentrale und der Einspeisepunkte | Rohrweg und „Last dahinter“ genau statt angenommen |
| Bedeutung der Pfeile in `Nodes_Edges.ods` | gerichtetes GNN: Der Vorlauf fließt nur stromab |
| Koordinaten der 18 Adressen ohne Position | Rohrweg für die 35 Kanten ohne Länge |
| Vorlauftemperatur am Ausgang der Heizzentrale | netzweite Schwankungen direkt erklären statt über den Median der Flotte |
| Rohrdaten je Kante (Dimension, Länge, Baujahr) | Kantengewichte, hydraulischer Widerstand |

## Ausführen

- Vorher Notebook 10, 18 und 31 ausführen. Die Netztabellen aus Notebook 31 müssen in `notebooks/` liegen.
- Laufzeit rund 15 Minuten, fast alles im Training.
- Es schreibt nur mit `SPEICHERN = True`, dann die Datei `data/processed/gnn_vorhersagen.csv`.
