# Netz und Zuordnung

Die Quellen des Projekts haben verschiedene Schlüssel. Das heißt die Zählerdaten kennen nur die Zählernummer, die
Begehungstabelle nur die Adresse und der Leitungsplan nur die Linien auf der Karte. Um eine Begehung mit den Messwerten
ihrer Station zu verbinden oder eine Station im Netz zu verorten, braucht es Zuordnungstabellen. Diese Seite
beschreibt sie und zeigt, wie weit die Verknüpfung reicht.

## Welche Quelle welchen Schlüssel hat

| Quelle | Zählernummer | Adresse | Lage im Netz |
|---|---|---|---|
| Zählerdaten | ja | – | – |
| Begehungen | – | ja | – |
| `Zuordnung.xlsx` | ja | ja | – |
| `Nodes_Edges.ods` | ja | ja | Kanten zwischen Adressen |
| Koordinatentabelle (von Hand) | – | ja | Koordinate |
| Leitungsplan (Shapefiles, KML) | – | – | Rohrverlauf als Geometrie |

- Die Adresse verbindet alles: Über sie hängen Zähler, Begehungen, Anschlusswert und Lage zusammen.
- Adressen dienen nur zum Verknüpfen. In der Doku und in den Ergebnissen stehen nur Zählernummern.

## Zähler und Adresse: `Zuordnung.xlsx`

Die ÜZ führt je Jahr ein Blatt, welcher Zähler an welcher Abnahmestelle hängt.

| Blatt | Spalten | Zähler |
|---|---|---|
| 2024 | Zählernummer, V-PIN, Abnahmestelle, zwölf Monatswerte | 99 |
| 2025 | wie 2024 | 99 |
| 2026 | Zählernummer, Straße und Hausnummer getrennt, Januar und Februar | 100 |

- Zusammen 102 Zähler an 100 Adressen. Es ist die vollständigste Liste: 88 der 93 HAST stehen darin.
- 14 Zähler der Liste haben keine Zählerdaten, darunter ausgetauschte Zähler.
- Die Monatswerte stammen aus der Abrechnung. Sie dienen nur zur Gegenprobe, etwa bei Zähler 72167783, der seit
  April 2025 keine Wärme mehr abnimmt.
- Steht ein Zähler in den Jahren unter verschiedenen Adressen, gilt das neueste Blatt.

### Zählertausch und doppelte Einträge

- **Tausch:** An 2 Adressen steht in verschiedenen Jahren ein anderer Zähler. Das Tauschdatum fehlt. Eine
  Vorher-Nachher-Auswertung über den Tausch hinweg würde zwei Geräte vergleichen, nicht zwei Zustände einer Station.
  Eine Begehung liegt an einer solchen Adresse.
- **Zwei Zähler im selben Jahr:** An 3 Adressen. Laut ÜZ kommt beides vor: zwei Stationen auf einem Grundstück oder
  ein Zähler unter der falschen Adresse.
- **Falsche Adresse:** Zwei Zähler standen im Blatt 2024 und in `Nodes_Edges.ods` unter der Hausnummer eines anderen
  Hauses desselben Eigentümers. Ab Blatt 2025 stimmt es. Notebook 00 korrigiert das, die Rohdaten bleiben unverändert.
- **Begehung zu Zähler:** Hat eine Adresse mehrere Zähler, wird der Zähler mit Zeitreihe genommen.
- **Mehrere Zähler an einem Haus:** Für die Netzauswertung zählt das Haus. Durchfluss und Leistung werden addiert,
  Temperaturen gemittelt (nur ab 5 l/h).

### Adressen vergleichbar machen

Dieselbe Adresse ist in den Quellen verschieden geschrieben: „Str.“, „Straße“ oder „Strasse“, Umlaute
ausgeschrieben oder nicht, Hausnummerzusätze mit oder ohne Leerzeichen, Bereiche wie „6 - 8“. Ein einfacher
Textvergleich würde viele Paare verfehlen. Alle Notebooks bringen Adressen deshalb vor jedem Vergleich in dieselbe
Form: klein geschrieben, „straße“ ausgeschrieben, Umlaute ersetzt, Zusätze zusammengezogen.

## Anschlusswert und Kantendatei: `Nodes_Edges.ods`

| Blatt | Inhalt | Umfang |
|---|---|---|
| Nodes | Zählernummer, Kundennummer, Anschlusswert in kW, Adresse | 99 Zähler an 94 Adressen |
| Edges | eine Kante als Paar zweier Adressen (`Node From`, `Node To`) | 110 Kanten |
| Straßen | V-PIN und Abnahmestelle | 99 Zeilen |

Kundennummer und V-PIN werden für die Auswertung nicht gebraucht.

### Anschlusswert

- Der Anschlusswert ist die vertraglich vereinbarte Leistung der Station in kW. Es gibt ihn nur in dieser Datei.
- Median 10 kW, kleinster Wert 5 kW, größter 500 kW.
- Er macht Stationen verschiedener Größe vergleichbar, z. B. als Auslastung (Spitzenlast geteilt durch Anschlusswert)
  im Clustering oder als Größenklasse im Netzvergleich.

Herkunft des Anschlusswerts bei den 93 HAST (Notebook 00):

| Herkunft | HAST |
|---|---|
| direkt über die Zählernummer | 85 |
| über die Adresse (Zähler fehlt in Nodes, die Adresse steht darin) | 2 |
| zwei Stationen teilen sich einen Vertrag, kein eigener Wert | 2 |
| Zähler steht in keiner Tabelle | 4 |

- 6 HAST bleiben damit ohne Anschlusswert. Kennzahlen, die ihn brauchen, fehlen dort.

### Kantendatei

- 110 Kanten verbinden 99 Nodes zu einem zusammenhängenden Netz mit genau einem Ring.
- Die Nodes sind Adressen. 17 davon finden keine Station mit Zähler: Heizwerk, Abzweige, Schächte oder Adressen in
  abweichender Schreibweise.
- Die Kanten verbinden Häuser direkt miteinander. Das Wasser fließt aber von der Straßenleitung ins Haus und zurück,
  nicht von Haus zu Haus. Die Kantendatei sagt also, welche Stationen im Netz nah beieinander hängen, nicht, wo die
  Rohre liegen.
- **Gerichtete Kanten:** Jede Kante hat eine Richtung. Es gibt aber 7 Nodes ohne Zufluss und 6 mit mehreren Zuflüssen, also
  keinen einzelnen Startpunkt. Etwa die Hälfte der gerichteten Kanten zeigt zum Erzeuger hin statt von ihm weg (Notebook 31 und
  32). Auch der Vorlauf sinkt in Kantenrichtung nicht häufiger, als er steigt: An 22 von 56 bewertbaren Kanten sinkt
  er, an 26 steigt er, 8 sind unklar. Nur ein Blick auf die Karte gibt einen Hinweis zu Bedeutung der Richtung der Kanten.
  Es sieht so aus, als geben die Kanten nur die Anschlussreihenfolge der Häuser entlang einer Straße an. Eine hunderprozentige Erklärung bleibt jedoch offen. 

## Leitungsplan

### Shapefiles

- Drei Ebenen: Linien, Punkte und Mehrfachpunkte, in ETRS89 / UTM 32N.
- 1308 Linien mit zusammen 18,6 km. Jede Linie hat einen Linientyp als Zahl, aber keine Legende. Die Bedeutung ist
  nur aus dem Kartenbild erschlossen: vermutlich Typ 1 und 2 Vor- und Rücklauf, Typ 3 Doppelrohr.
- Als Rohre zählen die Typen 1, 2, 3 und 5: 438 Rohre mit 9,4 km. Ihre Beschriftung enthält Material, Bauart und
  Dimension.
- Typ 6 sind 837 kurze Linien (Median 8,1 m). Fast alle enden mehr als 25 m vom nächsten Rohr entfernt und passen
  damit schlecht zu Hausanschlüssen. Ihre Bedeutung ist offen.

### KML

- `Leitungsverlauf.kml` enthält mehr Linien: 1289 mit 18,4 km. Jedes Rohr aus den Shapefiles ist darin enthalten.
- Wo eine KML-Linie ein Shapefile-Rohr überdeckt, bekommt sie dessen Rohrdaten. Das gelingt bei 424 Linien. 865
  Linien mit zusammen 8,6 km bleiben ohne Rohrart.
- Die KML ist die Grundlage für den Rohrweg zwischen Stationen und für die Netzkarten (Notebooks 31 bis 33).

### Wärmenetzplan

- `Wärmenetzplan[38].pdf` ist ein Übersichtsplan. Er zeigt ungefähr, wo der Erzeuger liegt und wo Hauptleitungen
  abgehen.
- Welcher Knoten der Erzeuger ist, hat die ÜZ bestätigt (Notebook 32). Eine Schätzung aus den Vorlauftemperaturen
  landet ebenfalls dort. Ob es weitere Einspeisepunkte gibt, ist offen.
- Nennweite, Länge und Baujahr je Kante gibt es nur teilweise. Das Netz bleibt damit ein logisches Modell, kein
  hydraulisches.

## Koordinaten der Adressen (Handtabelle)

Um Stationen auf die Karte und an das Rohrnetz zu bringen, braucht jede Adresse eine Koordinate. Die automatische
Adresssuche über OpenStreetMap (Nominatim) fand meist nur die Straße, nicht das Haus. Im Neubaugebiet kennt
OpenStreetMap zu wenige Hausnummern. Die Koordinaten wurden deshalb von Hand in Google Maps herausgesucht, durch klicken auf das Haus erfasst und anschließend in die Tabelle übertragen.

| | |
|---|---|
| Datei | `data/manual/adressen_koordinaten.ods`, nicht im Repository |
| Zeilen | eine je Adresse, rund 100 |
| `adresse` | Straße und Hausnummer |
| `koordinate` | Breite und Länge als Text, z. B. `49.81, 10.34` |
| `quelle` | Hinweis, nur in 4 Zeilen gefüllt |

- Die Koordinaten stammen fast alle aus Google Maps. In 2 Zeilen stammt die Koordinate aus Nominatim und wurden auf der
  Karte geprüft. In 2 weiteren zeigt die Karte für zwei Hausnummern dasselbe Haus.
- Jeder Zähler der Zuordnung mit Zeitreihe hat eine Koordinate. Ohne Koordinate sind vor allem Nodes der
  Kantendatei ohne Zähler, etwa Abzweige und Schächte. Ihre Lage wird aus den Nachbarn im Netz geschätzt.
- Adressen ohne Koordinate schreibt Notebook 31 in eine Liste zum Nachtragen
  (`fehlende_koordinaten_<Zeitpunkt>.ods`).
- Die Tabelle enthält Adressen und bleibt deshalb lokal.


## Was die Verknüpfung ergibt

| Stand der 93 HAST | HAST |
|---|---|
| Adresse bekannt und an einer Kante der Kantendatei | 84 |
| Adresse in der Zuordnung, aber an keiner Kante | 5 |
| in keiner Tabelle, also ohne Adresse | 4 |

- Die 4 Zähler ohne Adresse lassen sich weder im Netz verorten noch einer Begehung zuordnen. Sie haben auch keinen
  Anschlusswert.
- Netzauswertungen arbeiten deshalb mit gut 80 Stationen.
- Jede Begehung findet über ihre Adresse einen Zähler. Von den 58 datierten Begehungen landen 53 an einem Zähler mit
  Zeitreihe (51 Zähler). Die übrigen 5 liegen an Stationen, für die keine Zählerdaten geliefert wurden.

Was an Netz und Zuordnung unsicher ist und welche Angaben noch fehlen, steht unter
[Qualität und Einschränkungen](qualitaet.md#netz-und-zuordnung).
Wie aus Kantendatei und Leitungsplan ein Netzmodell entsteht, zeigen die Notebooks 31 bis 33 (siehe
[Überblick der Notebooks, Teil 7: Netz](../notebooks.md#teil-7-netz)).
