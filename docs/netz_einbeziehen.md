# Netz einbeziehen

Die Modelle der übrigen Abschnitte sehen jede Station für sich. Dieser Abschnitt fragt, was das Netz dazu beiträgt:
Wo hängt eine Station, woher kommt ihr Wasser, und lässt sich eine Abweichung dem Haus oder dem Netz zuordnen? Er
beschreibt, wie aus Kantendatei und Leitungsplan ein Netzmodell entsteht, wie es geprüft wurde und warum das Ergebnis
für die Fehlererkennung ein Negativbefund ist. Den Code enthalten die Notebooks 31 bis 33 und 39. Welche Quellen es gibt und wie
weit die Zuordnung reicht, steht unter [Netz und Zuordnung](datengrundlage/netz_und_zuordnung.md).

## Die Fragen

| Frage | Antwort in diesem Abschnitt | Notebook |
|---|---|---|
| Welche Station hängt wo im Netz? | Netzmodell aus der Kantendatei, Zähler auf Nodes und Karte | 34 |
| Wo speist das Netz ein, und in welche Richtung fließt es? | Schätzung aus dem Vorlauf, Leitungen vom Erzeuger aus ausgerichtet | 35 |
| Welchen Weg nimmt das Wasser wirklich? | Rohrbaum: kürzester Rohrweg vom Erzeuger zu jedem Haus | 35 |
| Liegt eine Abweichung am Haus oder am Netz? | Vergleich eines Hauses mit seinen Nachbarn im Rohrbaum | 35 |
| Hilft das Netz bei der Fehlererkennung? | Basislinie mit und ohne Netz-Merkmale, aus den Daten gelernter Graph, GNN-Entwurf | 35, 37 |

## Der Weg

1. **Netzmodell aus der Kantendatei (Notebook 31):** Die 110 Kanten von `Nodes_Edges.ods` ergeben ein zusammenhängendes
   Netz. Die Zähler mit Zeitreihe werden über Zählernummer und Adresse auf Nodes gelegt, über die Koordinatentabelle auf
   die Karte und über den Leitungsplan auf Rohre (106 von 111 Kanten, mit der Kante zum Erzeuger, liegen auf Rohren). Der Erzeuger kommt mit der Lage dazu,
   die die ÜZ nachgeliefert hat.
2. **Einspeisung gegenprüfen (Notebook 32):** Der Vorlauf kühlt entlang der Rohre ab. Für jeden Punkt im Rohrnetz wird
   geprüft, wie gut der Rohrweg zu ihm die Vorlaufunterschiede der Häuser erklärt. Das Ergebnis passt zur Lage, die die ÜZ genannt hat.
3. **Leitungen ausrichten:** Mit dem Erzeuger als Quelle zeigt jede Kante vom näheren zum weiter entfernten Knoten. Die
   Messdaten entscheiden, ob das besser ist als die Pfeile der Datei.
4. **Rohrbaum bauen:** Auf Ebene der Rohre ist klar, wie ein Haus an den Straßenleitungen hängt. Für jedes Haus wird der
   kürzeste Rohrweg vom Erzeuger genommen, die Wege ergeben einen Baum.
5. **Haus oder Netz:** Ein Haus wird mit seinen Nachbarn im Baum und mit zufälligen Häusern verglichen.
6. **Fehlererkennung mit Netz-Merkmalen:** Sommernacht-Durchfluss, andere Zielgrößen und eine Basislinie, jeweils gegen
   die Begehungslabels geprüft.
7. **Graph aus den Daten lernen:** Umgekehrte Frage: Welche Häuser hängen laut Stundenwerten zusammen, und passt das
   zum Rohrbaum?
8. **GNN-Entwurf (Notebook 39):** Ein Graph-Modell, das die Messwerte der Nachbarn nutzt, gegen dasselbe Modell ohne
   Netz.

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

## Warum der Rohrbaum und nicht die Kantendatei

Die Kantendatei verbindet Häuser direkt miteinander. Das Wasser fließt aber von der Straßenleitung ins Haus und zurück,
nicht von Haus zu Haus. Dazu kommt, dass die Pfeile der Datei keine Fließrichtung ergeben: Es gibt mehrere Nodes ohne
Zufluss und mehrere mit mehreren Zuflüssen, und der Vorlauf sinkt in Pfeilrichtung nicht häufiger, als er steigt.
Der Rohrbaum schneidet dagegen besser ab, wenn man ihn gegen die Messdaten hält.

| Test | Kantendatei | Rohrbaum |
|---|---|---|
| Vorlauf sinkt in Pfeilrichtung (Kanten) | 22 von 56 (Pfeile wie in der Datei), 26 von 56 (vom Erzeuger weg) | – |
| oberes Haus hat wärmeren Vorlauf (Paare) | – | 36 von 38, bei einem kälter, bei einem unklar |

Die beiden Tests messen nicht dasselbe. Sie zeigen aber, dass der Rohrbaum zum Vorlaufgefälle passt und die Hauskanten
nicht.

### Aufbau des Rohrnetzes

- Der Leitungsplan wird in Stücke von etwa 2 m zerlegt. Lücken bis 2,5 m werden überbrückt, damit getrennte
  Linienstücke zusammenhängen.
- Jedes Haus hängt am nächsten Rohrpunkt (höchstens 40 m entfernt). Der Erzeuger kommt auf den nächsten Rohrpunkt.
- Vor- und Rücklauf liegen als parallele Linien im Plan. Das erzeugt etwa 2000 Ringe, die keine echten Schleifen sind.
  Sie stören nicht, solange alle Häuser angeschlossen sind.
- Aus den kürzesten Wegen bleiben als Schlüsselpunkte der Erzeuger, die Anschlussstellen der Häuser und die Knoten, an
  denen sich der Baum verzweigt. Ein Teil dieser Abzweige ist unecht: Wo Vor- und Rücklauf nah beieinander liegen,
  wechselt der kürzeste Weg manchmal zwischen beiden Leitungen.

## Haus oder Netz

Bis zu diesem Abschnitt blieb offen, ob eine Abweichung am einzelnen Haus oder am Netz liegt: Es gab kein Netz-Merkmal in
den Daten. Der Rohrbaum erlaubt den Vergleich eines Hauses mit seinen Nachbarn. Weichen alle gemeinsam ab, spricht das
für das Netz. Weicht nur ein Haus ab, spricht es für das Haus.

**Vorgehen**

1. Je Haus ein Normalwert der Spreizung aus Außentemperatur, deren Quadrat, Uhrzeit und Wochentag (Ridge-Regression, nur
   Stunden mit Durchfluss, nur Daten vor dem 1.9.2024, damit keine Messung nach einer Begehung eingeht).
2. Die Abweichung wird zu Tageswerten gemittelt und je Haus robust standardisiert (Median und MAD, begrenzt auf ±6).
3. Nachbarn sind die 4 Häuser mit dem kürzesten Rohrweg im Baum.
4. Verglichen wird die mittlere Korrelation der Tageswerte mit den Nachbarn gegen 200 Ziehungen mit zufälligen Häusern.
5. Danach wird das Netzsignal herausgerechnet: je Tag der Median aller anderen Häuser. Mit dem Rest wird der Test
   wiederholt.

**Ergebnis**

| Prüfung | Korrelation |
|---|---|
| alle Häuser untereinander | etwa 0,22 |
| Rohrbaum-Nachbarn gegen zufällige Häuser | 0,231 gegen 0,223 (95-%-Grenze 0,238) |
| nach Abzug des Netzsignals | 0,015 gegen −0,001 (95-%-Grenze 0,014) |

- Die Häuser schwanken gemeinsam. Nachbarn im Baum teilen nicht mehr als zufällige Häuser. Ein Effekt je Strang ist
  nicht nachweisbar.
- Nach dem Abzug bleibt ein winziger Rest. 0,015 erklärt rechnerisch etwa 0,02 % der Streuung.
- Die Korrelation ist keine Prozentzahl, sondern eine Zahl zwischen −1 und 1. Erst ihr Quadrat gibt den erklärten
  Anteil an.

**Gegenproben.** Weil ein Negativbefund immer auch an der Messung liegen kann, wurde auf mehreren Wegen nachgeprüft:

| Gegenprobe | Ergebnis |
|---|---|
| Nachbarn aus der Kantendatei (2, 3 und 4 Kanten Abstand) statt aus dem Rohrbaum | nach Netzabzug 0,034, 0,014, 0,004 gegen etwa 0: verschwindet mit dem Abstand |
| Häuser unter demselben Abzweig (11 Gruppen, meist Paare) | 0,122 gegen 0,002 (95-%-Grenze 0,072); die Korrelationen der Paare streuen von −0,11 bis 0,45, der Rest kommt von wenigen Paaren |
| Richtung: folgt das untere Haus dem oberen mit 1 bis 3 Stunden Versatz | 33 Paare, 52 % positiv bei 50 % Zufall, p = 0,66 |
| kurze Ereignisse (mindestens 3 Stunden in Folge mit \|z\| > 3) | keine Netztage, Nachbarn haben am selben Tag etwas häufiger ein Ereignis (3,0 % gegen 2,1 %), auf sehr kleinem Niveau |

Die Zahl „Netzanteil“ aus dem ersten Versuch (im Mittel gut 70 % der Abweichung) ist nicht aussagekräftig. Der Betrag des
Nachbarmittels bleibt auch bei unabhängigen Nachbarn über null. Aussagekräftig ist nur der Vergleich mit zufälligen
Häusern. Der Ereignistest kann außerdem Netzereignisse nicht sehen, weil das Netzsignal vorher herausgerechnet wurde.
Dass er keine Netztage findet, ist deshalb kein Befund.

## Fehlererkennung mit Netz-Merkmalen

Die Begehungen liefern Labels je Zähler. Geprüft wird mit der AUC (0,5 = Zufall, 1 = perfekte Trennung) und einem
90-%-Bereich aus 400 Bootstrap-Ziehungen. Bei 9 bis 30 positiven Fällen je Label sind Unterschiede unter etwa 0,1
Rauschen.

- **Sommernacht-Durchfluss:** Fließt im Sommer nachts (Juni bis August 2024, 0 bis 4 Uhr) Wasser, passt das zu einem
  Ventil, das nicht schließt. Das trennt Ventil gut (AUC 0,84 bis 0,87), für die anderen Labels gibt es kein Signal.
- **Andere Zielgrößen:** Vorlauf, Rücklauf und Spreizung, jeweils als Abweichung, nach Netzabzug und mit Vorzeichen
  (dauerhaft über oder unter dem Netz). Am besten schneidet bei Ventil die Spreizung dauerhaft über dem Netz ab (0,88).
  Sonst liegen die Werte zwischen 0,5 und 0,66 mit breitem Bereich.
- **Vorlauf-Defizit:** Der Vorlauf sinkt im Januar und Februar um 1,21 K je 100 m Rohrweg. Wer weniger bekommt als für
  seine Lage erwartet, liegt unter der Geraden. Dieses Merkmal trennt kein Label in der erwarteten Richtung. Bei Ventil
  liegt es sogar bei 0,13, das heißt, Ventil-Häuser haben eher einen zu warmen Vorlauf.

**Basislinie.** Eine logistische Regression mit stark gebremsten Gewichten, geprüft mit Kreuzvalidierung nach Straßen
(eine Straße nie zugleich in Training und Test), 20-mal wiederholt. Nur Labels mit mindestens 8 positiven und 8
negativen Fällen. Vier Varianten:

| Variante | Merkmale |
|---|---|
| Nachtdurchfluss allein | keine, nur eine Schwelle |
| Nachtdurchfluss | Median und Anteil aktiver Nachtstunden |
| Haus-Merkmale | Nachtdurchfluss, Spreizung, Vorlauf und Rücklauf gegen das Netz, Vorlauf-Defizit |
| Haus- und Graph-Merkmale | zusätzlich dieselben Werte der 4 Nachbarn und die Differenz Haus minus Nachbarn |

- Bei Ventil erreicht der Nachtdurchfluss allein 0,87, mit allen Haus-Merkmalen 0,89, mit Graph-Merkmalen 0,85. Die
  Graph-Merkmale bringen nichts dazu.
- Bei den anderen Labels liegt die AUC höchstens bei 0,68 (Dämmung), teils deutlich unter 0,5. Werte unter 0,5 in der
  Kreuzvalidierung sind Überanpassung ohne Signal und kein Signal in Gegenrichtung.
- Die Koeffizienten bei Ventil zeigen in die erwartete Richtung: mehr Nachtdurchfluss spricht für Ventil.

Gerechnet wurden mehrere Zielgrößen gegen mehrere Labels. Die jeweils besten zu zeigen überschätzt. Bei Ventil spricht
für ein echtes Signal, dass mehrere unabhängige Größen in dieselbe Richtung zeigen.

## Graph aus den Daten lernen

Bisher wurde geprüft, ob Rohrbaum-Nachbarn ähnliche Messwerte haben. Hier wird umgekehrt aus den Stundenwerten gelernt,
welche Häuser zusammenhängen.

- Vom Stundenrest der Spreizung werden Netz-Median, die 3 stärksten gemeinsamen Muster (SVD) und die Trägheit jeder Reihe
  abgezogen.
- Folgt Haus b dem Haus a mit 1 bis 3 Stunden Versatz, entsteht eine Kante a → b. Als Kante gilt nur, was stärker ist als
  99,5 % von 200 um ganze Tage verschobenen Reihen.
- Abgleich: Verbinden die gelernten Kanten Rohrbaum-Nachbarn öfter als Zufall? Zeigen sie im Baum abwärts?

| Ergebnis | Wert |
|---|---|
| gelernte Kanten | 131, zufällig erwartet etwa 29 |
| davon zwischen Rohrbaum-Nachbarn | 9 % (Zufall 6 %) |
| davon zwischen Nachbarn der Kantendatei | 9 % (Zufall 4 %) |
| Kanten mit bekanntem Oben und Unten | 3, die Richtung ist nicht prüfbar |
| meiste Kanten an einem Haus | 24 |

Die Daten enthalten also zeitversetzte Zusammenhänge. Sie sind aber überwiegend nicht das Rohrnetz. Wenige Häuser
tragen sehr viele Kanten, eher ein Störer oder ein Messproblem als ein Strang. Als Grundlage für ein Graph-Modell taugt
der gelernte Graph nicht.

Eine Vorsichtsmaßnahme dabei: Die Zufallsgrenze verschiebt die Reihen nur um ganze Tage. Würden sie um beliebig viele
Stunden verschoben, ginge der gemeinsame Tagesrhythmus in der Zufallsvariante verloren, und die Grenze wäre zu locker.

## GNN-Entwurf

Notebook 39 prüft die Frage mit einem echten Modell: Verbessert ein Graph-Modell (GraphSAGE, in numpy gerechnet) das
Normalverhaltensmodell aus Notebook 18, und zwar wegen des Netzes? Die Variante „ohne Netz“ ist dasselbe Modell ohne den
Nachbarteil, so dass ein Unterschied dem Netz zugerechnet werden kann.

- Vier Heizperioden, jede einmal als Prüfzeit. Keine zufälligen Tage, weil aufeinanderfolgende Tage ähnlich sind und am
  selben Tag alle Stationen dasselbe Wetter teilen.
- Der eigene Messwert einer Station wird verborgen, damit das Modell ihn nicht über die Nachbarn zurückbekommt.
- Nach der Referenz erklärt das Modell ohne Netz 12,1 % (Abkühlung) und 18,5 % (Wassermenge) des Fehlers von Notebook 18.
  Der Beitrag des Netzes beträgt +0,010 und −0,009 und ist je Station nicht signifikant (p = 0,172 und 0,423, Schwelle
  0,025).
- Beim Ventilfall 68956351 ist das Modell mit Netz schlechter als Notebook 18 allein.

Die Daten für ein weiteres Graph-Modell stehen in `daten_cache/gnn_daten.npz`: 79 Häuser und 152 Streckenknoten, zusammen
231 Knoten und 460 gerichtete Kanten, dazu stündliche Messreihen und feste Merkmale je Haus (Rohrweg zum Erzeuger,
Abzweige bis zum Erzeuger, Häuser dahinter, Spitzenleistung, Länge der Anschlussleitung). Sinnvoll ist ein GNN erst, wenn
eine Größe mit Strang-Signal gefunden wird.

## Annahmen und Grenzen

| Annahme oder Grenze | Folge |
|---|---|
| Lage des Erzeugers von der ÜZ nachgeliefert, die Vorlauf-Schätzung passt dazu | offen bleibt, ob es weitere Einspeisepunkte gibt: Die Schätzung findet den Punkt, an dem die gemessenen Häuser „anfangen“, und trennt mehrere Einspeisepunkte nicht |
| Richtungen der Kanten | der Rohrbaum ist ein Kürzeste-Wege-Baum und kein hydraulisches Modell; Durchmesser, Drücke und Ringschlüsse fehlen |
| unechte Abzweige durch parallele Vor- und Rücklaufleitungen | die Zahl der Abzweige ist zu hoch; Tests je Abzweig sind davon betroffen |
| 30 Nodes ohne Zähler | sie fehlen im Rohrbaum und in den Tests |
| Begehungen zu zufälligen Terminen | „nicht begangen“ heißt nicht „fehlerfrei“; die Labels sind positiv oder unbekannt |
| wenige positive Fälle (9 bis 30 je Label) | Unterschiede unter etwa 0,1 AUC sind Rauschen; das Ventil-Ergebnis beruht auf 10 Fällen |
| Beobachtungszeit vor dem Stichtag etwa acht Monate | nur ein Teil des Winters |

Die Tests gelten für Tagesmittel der Spreizung und die genannten Nachbarschaften. Sie sagen nichts über die Idee
insgesamt.

## Offen

- Andere Größen mit möglichem Strang-Signal: Rücklauf, Vorlauf, Wärmeverlust pro 100 m, kurze Ereignisse in
  Stundenwerten ohne vorherigen Netzabzug.
- Unechte Abzweige durch parallele Vor- und Rücklaufleitungen zusammenführen und die Tests je Abzweig wiederholen.
- Die Hubs des gelernten Graphen gegen die Begehungslabels prüfen.
- Bedeutung der Pfeile in der Kantendatei und mögliche weitere Einspeisepunkte mit der ÜZ klären.
- Mehr Begehungen als Labels, damit kleine Unterschiede sichtbar werden.
