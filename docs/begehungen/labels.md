# Label aus Messdaten

**Notebook 03:** `notebooks/2_begehungen/03_labels.ipynb` · **Code:** Begehungs-Loader in `src/load_begehungen.py`

Dieses Notebook baut **kein** Modell. Es beantwortet die Frage, die vor jedem Modell steht: Was genau soll ein Modell
erkennen? Es schlägt eine Definition von „auffällig“ vor, die sich allein aus den Messdaten ergibt, und prüft dann,
ob sie hält.

## Warum ein eigenes Label nötig ist

- **Cluster taugen nicht als Label.** Die Stationen bilden keine natürlichen Gruppen (Notebook 07).
- **Die Begehungstabelle liefert kein Zustandslabel.** Die Änderungskategorie misst, wie viel der Monteur verstellt
  hat, nicht wie schlecht die Station lief ([Notebook 02](wirkung.md)).
- **`n_actions > 0` ist bei 76 % der Stationen wahr.** Ein Label, das fast immer zutrifft, trennt nichts.

**Die Idee:** Eine Hausübergabestation soll dem heißen Wasser Wärme entziehen und es kalt zurückschicken. Fließt viel
Wasser, kommt es aber fast genauso heiß zurück, wurde keine Wärme übertragen. Das ist messbar und braucht keine
Begehung.

## Monatswerte je Station

- Je Station und Monat ein typischer Wert für Durchfluss, Spreizung, Rücklauf und Leistung, jeweils als Median über
  die Stunden. Einzelne Ausreißer wie eine kurze heiße Zapfung verziehen ihn nicht.
- Monate mit weniger als **400 Messstunden** fallen heraus. Die Abdeckung schwankt je Station stark (siehe
  [Daten aufbereiten](../aufbereitung/index.md)), ein Monatswert aus 30 Stunden wäre wertlos.
- Ergebnis: **2.300 Station-Monate** an 93 Stationen, November 2022 bis Juli 2026.
- Die Spalten werden über ihren Namen umbenannt, nicht über ihre Position. Beim Vorbereiten waren Spreizung und
  Leistung über die Position vertauscht, das hat das Ergebnis vervierfacht.

## Die Regel

**Durchfluss über 50 l/h und gleichzeitig Spreizung unter 8 K** heißt auffällig: Es fließt ordentlich Wasser, aber es
kommt fast so heiß zurück, wie es angekommen ist. Die Station wälzt um, ohne Wärme abzugeben.

- Das Urteil gilt **je Station und Monat**, nicht je Station. Eine Station kann jahrelang auffällig und danach in
  Ordnung sein.
- **266 von 2.300** Station-Monaten sind auffällig (11,6 %), an **24 von 93** Stationen.
- Die beiden Schwellen sind eine Setzung, kein Messergebnis. Ob sie tragen, prüfen die nächsten Abschnitte.

**Gegenprobe am bekannten Reparaturfall:** Bei Zähler 68956351 wurde am 09.09.2024 ein Ventil geschlossen
([Notebook 02](wirkung.md#einzelfall-68956351)). Die Regel weiß davon nichts, sie sieht nur Zahlen. Trotzdem kippt sie
genau in diesem Monat:

| Monat | Durchfluss | Spreizung | auffällig |
|---|---|---|---|
| Juni 2024 | 671 l/h | 0,1 K | ja |
| Juli 2024 | 507 l/h | 0,1 K | ja |
| August 2024 | 494 l/h | 0,1 K | ja |
| September 2024 | 3 l/h | 0,4 K | nein |
| Oktober 2024 | 3 l/h | 18,0 K | nein |
| November 2024 | 44,5 l/h | 32,8 K | nein |
| Dezember 2024 | 73 l/h | 35,5 K | nein |

## Sind die Schwellen robust?

Eine Definition, die bei leicht anderen Zahlen völlig andere Stationen trifft, wäre willkürlich. Deshalb wird die
Regel mit neun Schwellenpaaren durchgerechnet. Zahl der betroffenen Stationen:

| Durchfluss ↓ / Spreizung → | unter 6 K | unter 8 K | unter 10 K |
|---|---|---|---|
| über 40 l/h | 22 | 25 | 30 |
| über 50 l/h | 22 | **24** | 29 |
| über 60 l/h | 21 | 24 | 26 |

- Die Zahl der auffälligen Monate liegt über alle neun Varianten zwischen 234 und 322.
- Entscheidend ist, **welche** Stationen getroffen werden: Die 21 der strengsten Variante (60 l/h, 6 K) stecken alle in
  der Menge der Regel, die lockerste Variante (40 l/h, 10 K) enthält alle 24 und fügt 6 hinzu.
- Es gibt also einen stabilen Kern, der unabhängig von der genauen Schwelle auffällt. Das ist der Unterschied zur
  frühen Regel in `src/fault_detection.py`, deren Schwellen auf synthetischen Daten kalibriert wurden und bei fast
  allen echten Zählern anschlagen.

## Wann wechselt der Zustand?

- Ein auffälliger Zustand **beginnt 36-mal** (bei 21 Stationen) und **endet 37-mal** (bei 22 Stationen).
- 7 Stationen sind schon im ersten Messmonat auffällig, ihr Beginn lässt sich nie beobachten.
- Der Zustand ändert sich selten. Ein Modell, das stur „wie im Vormonat“ sagt, liegt zu **96,7 %** richtig, „immer
  unauffällig“ zu 88,3 %, ohne etwas verstanden zu haben.
- **Folge für jedes spätere Modell:** Es muss auf den wenigen Wechseln bewertet werden, nicht auf allen Monaten. Auf
  allen Zeilen gewinnt immer das triviale Modell.

## Passt das Label zu den Begehungen?

Bisher prüft sich die Regel nur an sich selbst. Die einzige unabhängige Quelle sind die Notizen der Monteure.

**Stichwortsuche in den Freitexten:** Nennt eine Notiz ein hydraulisches Thema (Ventil, Zirkulation, Schmutzfänger),
ist die Station in 29 % der Fälle auffällig (n = 21), sonst in 18 % (n = 45). Der Unterschied ist nicht gesichert
(Fisher-Test p = 0,35).

**Lösen Begehungen die Wechsel aus?** Fast nie. Nur 2 von 36 Beginnen und 2 von 37 Enden fallen in einen Monat mit
Begehung. Die wenigen Fälle passen aber zu [Notebook 02](wirkung.md): Zustände, die in einem Begehungsmonat enden,
gehören zu den Stationen mit der stärksten gemessenen Verbesserung, darunter der Ventilfall. Ein Beginn fällt auf
72167783, deren Rücklauf nach der Begehung von 18,6 auf 71,0 °C stieg. Beide Notebooks kommen unabhängig voneinander
auf dieselben Einzelfälle.

Die Stationen ändern ihren Zustand also überwiegend **ohne** erkennbaren äußeren Anlass. Das ist ein eigener Befund und
passt dazu, dass Notebook 02 keinen gesicherten Effekt der Begehungen nachweisen konnte.

## Abgleich mit der Handkodierung

Die Stichwortsuche ist grob. Deshalb wurden alle 57 Freitextnotizen zusätzlich **von Hand** eingeordnet, im
**Kodierbogen** (`data/processed/kodierbogen_freitexte.xlsx`). Das geschah blind, ohne zu sehen, welche Station die
Regel als auffällig einstuft. Je Notiz steht dort, ob sie zur Regel passt (ja, nein, unklar), welche Art von Befund sie
beschreibt und eine Anmerkung.

| Notiz passt zur Regel | Notizen | Stationen mit Monatswerten | davon laut Regel auffällig |
|---|---|---|---|
| ja | 14 | 12 | 4 (33 %) |
| nein | 13 | 12 | 1 (8 %) |
| unklar | 30 | 28 | 8 (29 %) |

**Insgesamt stimmt nur die Richtung.** Die Regel findet bei „ja“ deutlich mehr als bei „nein“, gesichert ist das bei
so wenigen Fällen nicht (Fisher-Test p = 0,32). Über die Hälfte der Notizen sagt zur Frage nichts.

**Die Regel übersieht viele dokumentierte Mängel.** 8 der 14 mit „ja“ kodierten Stationen haben keinen einzigen
auffälligen Monat. Zwei Erklärungen liegen nahe:

- **Zeitweise Fehler** verschwinden im Monatsmedian, etwa ein Ventil, das nur hin und wieder hängt.
- **Fehler auf der Hausseite**, etwa an der Heizkreispumpe, zeigen sich auf der Netzseite nicht zwangsläufig als
  Dauerdurchfluss.

**Bei den schweren Fällen passt es.** 6 Stationen haben mindestens zehn auffällige Monate. Keine davon ist mit „nein“
kodiert. Von den vier mit über 20 auffälligen Monaten sind drei mit „ja“ kodiert, eine mit „unklar“. Dazu passt die
Aufschlüsselung nach Befundart: Notizen zu Zirkulation (2 von 3) und Ventil oder Hydraulik (6 von 14) treffen
häufiger auf auffällige Stationen als Notizen zu Regelung oder Konfiguration (keine).

Der Kodierbogen liegt nicht im Repository, weil er die Freitexte der ÜZ enthält. Ohne ihn überspringt das Notebook
diesen Abschnitt, die Zahlen hier stammen aus einem Lauf mit Kodierbogen. Er ist nicht dieselbe Tabelle wie die
Prüfliste, die Notebook 38 braucht.

## Einordnung

| Prüfung | Ergebnis | Bewertung |
|---|---|---|
| Gegenprobe am bekannten Reparaturfall | Label kippt genau im Reparaturmonat | bestanden |
| Robustheit der Schwellen | stabiler Kern über neun Schwellenpaare | bestanden |
| Zeitliches Verhalten | wenige, klar erkennbare Wechsel | bestanden |
| Freitext, Stichwortsuche | kein gesicherter Zusammenhang | nicht bestanden |
| Handkodierung, alle Fälle | Richtung stimmt, nicht gesichert | teilweise |
| Handkodierung, schwere Fälle | keine einzige mit „nein“ kodiert | bestanden |

Das Label ist ein **Detektor für schwere, monatelang anhaltende Zustände**, kein allgemeiner Defektdetektor. In dieser
engeren Rolle ist es belastbar, und so sollte es auch benannt werden. Ließe es sich gar nicht bestätigen, wäre auch
das ein Ergebnis: „defekt“ wäre aus diesen Daten nicht eindeutig zu definieren. Das würde erklären, warum das
Clustering und die frühen Klassifikationsversuche kein Signal fanden.

## Was als Nächstes sinnvoll ist

- Die Schwellen in `src/fault_detection.py` nachjustieren. Die Label-Tabelle liefert dafür erstmals einen Maßstab aus
  echten Daten.
- Die auffälligen Stationen mit ihrem Zeitraum als Wartungsliste an die ÜZ geben.
- Die Wechsel einzeln ansehen: Gibt es in den Monaten davor ein Vorzeichen, etwa einen langsam steigenden Rücklauf?
  Ohne Vorzeichen gibt es nichts vorherzusagen.

## Ausgabe

- `data/processed/station_monat_label.csv`: eine Zeile je Station und Monat mit allen Messwerten und dem Urteil,
  2.300 Zeilen. Enthält Zählernummern, bleibt lokal.
- `data/processed/station_monat_label.json`: Regel, Schwellen und die wichtigsten Zahlen des Laufs.
