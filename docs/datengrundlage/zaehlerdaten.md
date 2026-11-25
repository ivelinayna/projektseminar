# Zählerdaten

Für jede Hausanschlussstation (HAST) hat die ÜZ die Messwerte ihres Zählers als Export geliefert. Diese Zeitreihen
sind die Messgrundlage des Projekts. Notebook 00 lädt sie, prüft sie und führt sie je Zähler zu einer Stundenreihe
zusammen.

## Lieferungen

| Datei | Anzahl | Inhalt |
|---|---|---|
| `<Zählernummer>__n.csv` | 97 | Export 2024 |
| `<Zählernummer>_2025n.csv` | 96 | Export 2025, endet im Juli 2025 |
| `<Zählernummer>.ods` | 5 | Nachlieferung bis Juli 2026, ohne Zählerstände |

- Zusammen 198 Dateien für 101 Zählernummern. Die Exporte eines Zählers überlappen sich zeitlich.
- 8 Zähler sind laut ÜZ keine Hausstationen: das BHKW, die HHS-Kessel I bis IV, der Ölspitzenkessel und zwei
  Temperaturfühler im Heizhaus. Bei den Fühlern sind Energie, Durchfluss und Leistung durchgehend 0. Alle acht fallen
  heraus.
- Es bleiben **93 HAST**.

## Messgrößen

| Spalte im Export | Bedeutung | Art |
|---|---|---|
| `Timestamp` | Zeitpunkt, deutsche Lokalzeit | Pflicht |
| `Volume flow (l/h)` | Durchfluss | Pflicht |
| `Power (kW)` | Leistung | Pflicht |
| `Temperature difference (°C)` | Spreizung (Vorlauf minus Rücklauf) | Pflicht |
| `Flow temperature (°C)` | Vorlauftemperatur | Pflicht |
| `Return temperature (°C)` | Rücklauftemperatur | Pflicht |
| `Energy (kWh)` | Zählerstand Wärme | optional |
| `Volume (m³)` | Zählerstand Heizwasser | optional |

- Energie und Volumen sind Zählerstände. Sie zählen fortlaufend weiter.
- Optional heißt: In der Nachlieferung mit den Daten bis Juli 2026 fehlen diese beiden Spalten.
- `Flow temperature` ist die Vorlauftemperatur, nicht der Durchfluss.

## Zeitraum und Abdeckung

- Die Zähler kamen in zwei Wellen dazu: 43 im vierten Quartal 2021 (42 davon am 01.11.2021) und 43 im Herbst 2023.
  Dazwischen und danach gab es nur Einzelfälle.
- Der späteste Zähler beginnt am 17.12.2024. Ältere Stundenwerte hat laut ÜZ der Ringspeicher überschrieben.
- Alle CSV-Reihen enden im Juli 2025. Nur die fünf ODS-Zähler reichen bis Juli 2026.
- Bis etwa November 2022 liefern 45 Zähler nur einen Wert je Tag, immer um 23 Uhr (Tageswert-Phase).
- Die Dateien enthalten nur gemessene Stunden. Auf ein lückenloses Stundenraster gelegt, sind 80 % der Stunden
  gemessen (1.694.131 von 2.128.400). 84 % der übrigen Stunden fallen in die Tageswert-Phase. Echte Lücken sind also
  selten.

| Kennzahl | Wert |
|---|---|
| beobachteter Zeitraum je Zähler | gut ein halbes Jahr bis 4,7 Jahre |
| gemessene Stunden je Zähler | 4.939 bis 32.657, Median 16.123 |
| Abdeckung je Zähler | 46 % bis 100 %, Median 79 % |
| Zähler unter 70 % Abdeckung | 13 |
| Zähler unter 10.000 Messstunden | 7, für saisonale Kennzahlen eventuell zu kurz |

## Eigenheiten der Exporte

| Eigenheit | Behandlung in Notebook 00 |
|---|---|
| ODS-Werte 1000-fach zu groß (36000 statt 36,0 °C Vorlauf) | am Median des Vorlaufs erkannt und zurückgerechnet. Sonst ergäben sich 60.000 kW je HAST, das ganze Netz hat rund 2 MW |
| Zeitstempel minutenversetzt (13:00 im einen Export, 13:01 im anderen) | auf die volle Stunde abgerundet. Betraf 3 Zähler stark, dort waren 17 bis 47 % der Zeilen Dubletten |
| Exporte überlappen | bei gleichem Zeitstempel gilt der neuere Export. Die ODS ersetzt keine CSV-Stunden, sie verlängert die Reihe nur nach hinten |
| Zeilen nur mit Zählerstand: Stichtag 31.05. um 23:59, Monats- oder Jahresende, 0-kWh-Zeile bei Inbetriebnahme | 509 Zeilen verworfen. Sie hatten bei 49 Zählern den Beginn der Reihe nach vorn verschoben |
| eine Datei ohne Spreizung (81050517) | aus Vorlauf minus Rücklauf berechnet |
| Tippfehler im Dateinamen: `721354800__n.csv`, schon im ÜZ-Export | dem Zähler 72135480 zugeordnet. In der Überlappung sind alle Messspalten identisch |
| Lücken unsichtbar, weil die Dateien nur gemessene Stunden enthalten | lückenloses Stundenraster, eine Zeile ist eine Stunde |
| unmögliche Messwerte | Plausibilitätsgrenzen, z. B. Vor- und Rücklauf −20 bis 130 °C. Keine einzige Messzelle lag außerhalb |
| negative Leistung | bleibt erhalten. Bei 72167783 fließt nach der Abtrennung tatsächlich Wärme rückwärts (bis −14,7 kW). Das ist ein Befund, kein Messfehler |
| Zeitumstellung: Die doppelte Stunde im Oktober enthält nur eine Ablesung | keine Umrechnung nach UTC, sie hätte bis zu 405 Messstunden gekostet. Die Zeitstempel bleiben deutsche Lokalzeit |

Wie Notebook 00 daraus je Zähler eine Stundenreihe baut, steht unter
[Vorgehen → Daten aufbereiten](../aufbereitung/index.md).

## Stundenwerte sind Momentaufnahmen

- Durchfluss, Leistung und Temperaturen sind Momentaufnahmen zur vollen Stunde, keine Mittelwerte über die Stunde
  (Datencheck D2).
- Eine Tagessumme aus 24 Momentaufnahmen liegt im Winter um bis zu ±30 % neben dem echten Verbrauch.
- Tagesenergie und Tageswassermenge kommen deshalb aus den Zählerständen: Stand um Mitternacht minus Stand der
  Mitternacht davor. Das rechnet Notebook 10 (`notebooks/3_clustering/10_tagescluster.ipynb`, siehe
  [Tagescluster](../clustering/tagescluster.md)). Seine Tageswerte nutzen danach unter anderem die Notebooks 18 und 20.

## Wie die Messgrößen zusammenhängen

Die Spalten des Exports hängen physikalisch zusammen. Die folgenden Formeln stecken in fast allen Notebooks, auch
wenn sie dort selten ausgeschrieben sind.

### Spreizung

> Spreizung (K) = Vorlauf − Rücklauf

- Je größer die Spreizung, desto mehr Wärme hat die Station dem Wasser entnommen.
- Fehlt die Spalte in einer Datei, berechnet Notebook 00 sie so.

### Leistung

> Leistung (kW) = k × Durchfluss (l/h) × Spreizung (K)

- k ist Dichte mal Wärmekapazität des Wassers. Der übliche Nennwert ist 1,163 × 10⁻³ kW je l/h und Kelvin, also
  1,163 kWh je m³ und Kelvin.
- Aus den Daten bestimmt liegt k bei 1,152 × 10⁻³, im Median über alle Stationen. 90 % der Stationen liegen zwischen
  1,146 und 1,157 × 10⁻³ (Notebook 01). Dass der Wert etwas unter dem Nennwert liegt, passt dazu, dass warmes Wasser
  etwas weniger dicht ist.
- Notebook 01 nutzt die Formel, um einen fehlenden Kanal aus den beiden anderen zu ergänzen.

### Abkühlung je Kubikmeter

> Abkühlung (kWh/m³) = Tagesenergie ÷ Tageswassermenge ≈ 1,15 × mengengewichtete Spreizung

- Tagesenergie und Tageswassermenge kommen aus den Zählerständen (siehe oben).
- Die Kennzahl sagt, wie viel Wärme die Station aus jedem Kubikmeter Heizwasser holt. Hoch ist gut. Sie hängt nicht
  davon ab, wie groß das Haus ist, und lässt sich deshalb zwischen Stationen vergleichen.
- Es ist dieselbe Größe, die die ÜZ auf ihrer Folie „Performance“ nennt.
- Der Faktor ist das k aus der Leistungsformel. In den Notebooks steht er je nach Stelle als 1,15, 1,16 oder 1,163.
  Gemeint ist immer derselbe Zusammenhang.
- Auf Stundenebene ist die Abkühlung praktisch nur die Spreizung mal k. Ein Zusammenhang zwischen beiden ist deshalb
  kein Befund, sondern Rechnung (siehe [Stationsbilder und Befunde](../stationsbilder/index.md)).

### Mengengewichtete Temperatur

> mengengewichteter Vorlauf = Summe (Durchfluss × Vorlauf) ÷ Summe Durchfluss, über die Stunden eines Tages

- Jede Stunde zählt so viel, wie Wasser geflossen ist. Steht das Wasser, kühlt es in der Leitung aus. Solche Stunden
  zählen dann kaum.
- Für Rücklauf und Spreizung gilt dasselbe. Notebook 10 rechnet so, Notebook 18 und 39 nutzen den mengengewichteten
  Vorlauf.

### Kennlinie: Durchfluss gegen Leistung

> log Durchfluss = a + b × log Leistung, als Ausgleichsgerade über die Stunden einer Station

- Aus der Leistungsformel folgt, wie man die Steigung b liest:
    - b nahe 1: Der Durchfluss steigt mit der Last, die Spreizung bleibt gleich.
    - b nahe 0: Der Durchfluss bleibt gleich, egal wie viel Wärme gebraucht wird. Nur die Spreizung ändert sich. Das
      passt zu einem Ventil, das offen steht oder klemmt.
- Berechnet in `src/stationsbilder.py` (Funktion `kennlinienfit`) für Notebook 12. Notebook 38 nutzt die Steigung als
  Symptom „Kennlinie flach“.
- Nicht verwechseln: Notebook 18 nennt seine Erwartung gegen die Außentemperatur ebenfalls „Kennlinie“.
