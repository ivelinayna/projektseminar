# Performance 

**Notebook 05:** `notebooks/2_begehungen/05_performance.ipynb` · **Code:** `src/performance.py`, Tests in
`tests/test_performance.py`

Die ÜZ hat auf der Folie „Vergleich Gesamteffizienz vor und nach der Optimierung von HAST“ gezeigt, dass optimierte
Stationen bei 8,8 °C Außentemperatur **2,12 kWh/m³ bzw. 13,4 %** mehr Energie je m³ Heizwasser umsetzen, gerechnet mit
rund 60 optimierten Stationen im ganzen Versorgungsgebiet. Dieses Notebook rechnet die Folie mit unseren Zählerdaten
nach.

**Die Kennzahl:** Energie durch Volumen in kWh/m³ entspricht der durchflussgewichteten Spreizung, 1 kWh/m³ ≈ 0,86 K.
Hoch ist gut, das Wasser kühlt in der Station stärker ab.

## Kennzahl und Auswertung (Abschnitte 1 bis 9)

- **Tageswerte aus den Zählerständen:** Differenzen der Energie- und Volumenstände. Verworfen werden Tage unter 0,5 m³,
  mit weniger als 20 gültigen Stunden oder außerhalb von −2 bis 70 kWh/m³. Gültig sind 59.483 von 85.986
  Stationstagen (69 %).
- **Gegenprobe:** Die Kennzahl in Kelvin stimmt im Median auf 0,5 K mit der gemessenen Spreizung überein. 10 von 93
  Zählern weichen um mehr als 3 K ab, einer um mehr als 15 K (58202380). Sie sind Kandidaten für eine Prüfung.
- **Zwei Varianten:** A mit dem festen Stichtag der Folie (30.09.2024), B mit dem eigenen Begehungsdatum je Station
  und ±7 Tagen Puffer. Beide nur mit den 51 Stationen, die eine Begehung haben.
- **Je Gruppe eine Gerade** gegen die Außentemperatur, Abstand am Bezugspunkt, clusterrobuste Fehler je Zähler.

| | Variante A | Variante B | Folie |
|---|---|---|---|
| Abstand am Bezugspunkt | +1,29 kWh/m³ (5,8 %) | +1,17 kWh/m³ (5,2 %) | +2,12 kWh/m³ (13,4 %) |
| p | 0,13 | 0,21 | – |
| Bezugspunkt | 9,7 °C | 9,6 °C | 8,8 °C |
| Stationen, Tage | 51, 32.116 | 51, 31.632 | rund 60, unbekannt |

- Gleiche Richtung wie auf der Folie, aber kleiner und nicht von null unterscheidbar.
- Die flachere Gerade der optimierten Stationen ist nur angedeutet (p 0,16 bis 0,26).
- Der Bezugspunkt ist in beiden Gruppen dicht belegt, es wird nichts extrapoliert. „Optimiert“ ist im Mittel 2,3 bis
  2,7 K kälter.
- Das absolute Niveau liegt rund 6 kWh/m³ über der Folie, die Ursache ist nicht geklärt.
- **Nachlieferung (Abschnitt 9):** Ab dem vierten Quartal 2025 tragen nur noch drei bis vier Nachlieferungszähler die
  Nachher-Phase,
  mit Zählerständen, die aus Leistung und Durchfluss hochgerechnet sind. Das trifft das Niveau über Monate, einzelne
  Tage weichen ab. Vier Stationen, eine davon dominiert: keine Aussage zur Wirkung.

## Wie belastbar ist der Abstand? (Abschnitt 10)

Der Abstand aus Abschnitt 5 hängt an drei Entscheidungen, die Abschnitt 10 einzeln prüft. Gerechnet wird wie oben mit
Variante A, denselben gültigen Tagen und clusterrobusten Fehlern.

### Zeitraum

Nach dem 11.07.2025 liefern nur noch die fünf Nachlieferungszähler Daten. Bis dahin sind ihre Zählerstände gemessen,
danach ist praktisch jede Stunde hochgerechnet (rund 8.950 Stunden je Zähler). In Abschnitt 5 sind diese Tage
enthalten, obwohl Abschnitt 9 sie als nicht aussagekräftig einstuft.

| Fassung | Abstand | p |
|---|---|---|
| bis Juli 2026, alle Tage (wie Abschnitt 5) | +1,29 kWh/m³ (5,8 %) | 0,13 |
| bis 31.12.2025 | +1,62 kWh/m³ (7,3 %) | 0,06 |
| **bis 11.07.2025, gemeinsames Exportende** | **+1,95 kWh/m³ (8,8 %)** | **0,04** |
| ohne die fünf Nachlieferungszähler | +1,44 kWh/m³ (6,3 %) | 0,12 |

- Je weniger Nachlieferungstage, desto größer der Abstand. Die späten Tage von vier Stationen liegen niedrig und
  ziehen die Nachher-Gerade nach unten.
- Nur die Fassung bis zum Exportende ist knapp signifikant. Sie ist die sauberste Form der ÜZ-Methode: alle
  Stationen im selben Zeitraum, nur gemessene Zählerstände.

### Bezugspunkt der Folie

- Die Folie liest den Abstand bei 8,8 °C ab, Abschnitt 5 beim Mittelwert unserer Tage (9,7 °C).
- Bei uns ändert das fast nichts (0,05 bis 0,1 kWh/m³), weil die beiden Geraden nahezu parallel laufen. Bei der Folie
  ändert es viel: Ihre Geraden schneiden sich bei −4,1 °C, der Abstand wächst mit der Temperatur.
- **Am gleichen Bezugspunkt 8,8 °C:** Folie 13,4 % gegen 5,4 bis 8,3 % hier.
- Widerlegt sind die 13,4 % damit nicht. Sie liegen im Konfidenzintervall der Fassung bis zum Exportende (bis 16,4 %).

### Jede Station nur mit sich selbst

- Abschnitt 5 vergleicht alle Stationstage vorher mit allen nachher. Die Stationen tragen aber sehr unterschiedlich
  viele Tage bei: vorher 0 bis 688 (Median 335), nachher 0 bis 284 (Median 269).
- Mit **Stationseffekten** werden Kennzahl und Außentemperatur je Zähler um ihren Mittelwert bereinigt. Unterschiede
  im Niveau zwischen den Stationen fallen heraus, es zählt nur die Veränderung innerhalb einer Station.
- **Ergebnis: +0,8 bis +1,0 kWh/m³ (3,7 bis 4,6 %)**, in keinem Zeitraum signifikant (p 0,21 bis 0,26), aber stabil:
  Der Zeitraum verschiebt den Wert kaum.
- Der kleinere Wert liegt nicht an anderen Stationen vorher und nachher. 46 der 51 Stationen haben Tage in beiden
  Phasen, und nur mit diesen 46 steigt der Abstand nach der Rechnung oben sogar auf 9,1 % (p ≈ 0,03).
- Er liegt an der Gewichtung: Stationen, die schon vor der Begehung überdurchschnittlich gut waren, haben anteilig
  mehr Nachher-Tage (Rangkorrelation +0,48). Sie heben die Nachher-Gerade an, ohne dass sich eine Station verändert
  hat.

## Einordnung

- **Die Richtung ist stabil, die Höhe unsicher.** Je nach Rechnung sind es 4 bis 9 %, deutlich weniger als die
  13,4 % der Folie.
- Am ehesten vergleichbar mit der Folie ist die Fassung bis zum Exportende bei 8,8 °C: **8,3 %**, knapp signifikant.
- Station für Station bleiben rund 4,5 %, nicht signifikant. Ein Teil des Abstands kommt aus der Zusammensetzung der
  Stationstage, nicht aus einer Veränderung der Stationen.
- Eine Kontrollgruppe ohne Begehung fehlt hier. Die hat erst der [Wintervergleich](wintervergleich.md).

## Ausgaben

Grafiken der beiden Varianten unter `outputs/`: `performance_variante_a.png`, `performance_variante_b.png` und die
Tagesansichten `performance_variante_a_tage.png`, `performance_variante_b_tage.png`.
