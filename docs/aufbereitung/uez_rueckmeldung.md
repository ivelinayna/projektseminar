# Änderungen 3: Rückmeldung der ÜZ

Die ÜZ hat Fragen zu den Daten beantwortet. Die Antworten und das, was beim Nachprüfen auffiel, sind
in mehreren Änderungen eingeflossen.

## Temperaturfühler im Heizhaus ausschließen

- Problem: 41704231 und 41704232 liefen bisher als HAST mit. Laut ÜZ sind es Temperaturfühler im Heizhaus, die Vor-
  und Rücklauf überwachen.
- Energie, Durchfluss und Leistung sind in beiden Reihen durchgehend 0, nur die Temperaturen sind echt. Sie verzerrten
  die Kennzahlen über alle Stationen und das Clustering.
- Lösung: in die Liste der Nicht-HAST aufgenommen. Es sind jetzt 8, es bleiben 94 statt 96 HAST.
- Wirkung: Der Anschlusswert fehlt nur noch bei 9 statt 11 Zählern, `dt_mean_loaded` nur noch bei 1 statt 3
  Stationen. Die Lücken in `flow_short_cycle_power` und `rt_above_50_share_loaded` waren genau diese beiden Fühler
  (Durchfluss immer 0, keine FFT möglich).

## Falschen Dateinamen korrigieren

- Problem: Aus `721354800__n.csv` entstanden zwei „Zähler“: 721354800 (11/2021 bis 05/2024, ohne Anschlusswert) und
  72135480 (erst ab 31.05.2022, 50 % Abdeckung).
- Nachweis, dass es derselbe Zähler ist:
    - In der Überlappung (01.01.2023 bis 13.05.2024, 3.339 Stunden) sind alle 7 Messspalten identisch.
    - Der Zählerstand läuft an der Naht nahtlos weiter (62.990 kWh um 14 Uhr, 62.994 kWh um 15 Uhr).
    - Der Monatsverbrauch Januar bis April 2024 aus der Datei stimmt auf die kWh genau mit der Abrechnung in
      `Zuordnung.xlsx` überein.
- Lösung: Die Datei wird direkt beim Einsammeln dem richtigen Zähler zugeordnet. 101 statt 102 Zählernummern,
  93 statt 94 HAST.
- Wirkung: 72135480 reicht jetzt von 01.11.2021 bis 11.07.2025 mit 73 % Abdeckung, wie die übrigen Zähler ab 2021.
  In zwei späteren Notebooks war der Zähler vorher doppelt als Durchlauf-Fall gezählt.

## Adresskorrektur für zwei Zähler

- Problem: 80912175 und 80912177 standen in `Nodes_Edges.ods` und im Blatt 2024 von `Zuordnung.xlsx` unter der
  falschen Adresse (gleicher Eigentümer). Ab dem Blatt 2025 stimmt es.
- Lösung: feste Korrektur im Code, die Rohdaten bleiben unverändert.
- Wirkung: In Notebook 00 ändert sich nur die Adresse. In den Notebooks, die den Anschlusswert über die Adresse
  suchen, bekommt 80912166 dadurch eindeutig 19 kW statt „mehrdeutig“ (10 oder 19 kW).

## Zeilen ohne Messwerte verwerfen

- Problem: Die CSV-Exporte enthalten neben den Stundenwerten Zeilen, in denen nur ein Zählerstand steht: den
  Stichtagsstand jedes Jahr am 31.05. um 23:59, eine 0-kWh-Zeile bei Inbetriebnahme und bei einzelnen Zählern Monats-
  oder Jahresendstände. Sie liefen wie Messungen mit und richteten drei Fehler an:
    - Das Raster begann am frühesten Zählerstand statt an der ersten Messung, zum Beispiel bei 81019433 am 31.05.2024
      statt am 17.12.2024. Lange leere Strecken drückten die Abdeckung.
    - Der Stichtag 31.05.2022 um 23:59 gewann in seiner Stunde gegen die echte Messung um 23:00. Bei 42 Zählern fehlten
      in dieser Stunde die Temperaturen.
    - Bei 80912174 steckte eine 0-kWh-Zeile mitten in der Reihe. Der Zählerstand sprang von 168 auf 0 und dann auf
      170 kWh.
- Lösung: Eine Zeile fliegt nur heraus, wenn alle fünf Messgrößen leer sind.
- Wirkung:
    - 509 Zeilen in 134 Dateien verworfen (404 Stichtage, 86 mit 0 kWh, 19 Monats- oder Jahresendstände), keine davon
      mit Messwert.
    - 49 Zähler beginnen später, alle um mehr als 30 Tage.
    - Rasterstunden 2.316.682 → 2.128.400, Abdeckung im Netz 73 % → 80 %, je Zähler mindestens 17 % → 46 %,
      Median 73 % → 79 %, unter 70 % Abdeckung 18 → 13 Zähler.
    - Vom Minutenversatz betroffene Zähler 89 → 3. Fast alle bisherigen Treffer waren Stichtagszeilen, die mit der
      Messung um 23:00 in dieselbe Stunde fielen.
    - Gemessene Stunden 1.694.229 → 1.694.131: 98 Stunden, in denen nur ein Zählerstand stand, zählten vorher als
      gemessen. Kein Messwert geht verloren.
    - Dabei gefunden: 84 % der Rasterstunden ohne Messung liegen in der Tageswert-Phase, nicht in echten Lücken.
- Die Tageswert-Phase selbst bleibt drin. Sie ist echte Messung, nur seltener.

## Filtertrend nur aus Monaten mit genug Stundenwerten

- Problem: 45 Zähler haben bis etwa November 2022 nur einen Wert je Tag, immer um 23 Uhr. Das obere Monatsquantil
  des Durchflusses beruht dort auf rund 30 Nachtwerten statt rund 720 Stundenwerten.
- Nachweis, dass die Uhrzeit den Unterschied macht und nicht die Station (Januar, Median über 40 Zähler):

| Januar | oberer Durchfluss |
|---|---|
| 2022, nur 23-Uhr-Werte | 213 l/h |
| 2023, alle Stunden | 325 l/h |
| 2023, nur 23-Uhr-Werte | 218 l/h |

- Folge: Die frühen Monate lagen rund 100 l/h zu niedrig. Die Gerade stieg künstlich, ein zusetzender Filter wurde
  verdeckt.
- Lösung: Ein Monat zählt nur mit mindestens 200 gemessenen Stunden (etwa 8 volle Tage). Monate der Tageswert-Phase
  und angebrochene Monate am Rand fallen damit heraus.
- Wirkung:
    - Nur diese eine Kennzahl ändert sich, alle anderen bleiben exakt gleich. Keine Station verliert den Wert.
    - 45 Zähler mit Tageswert-Phase: Median +0,63 → −1,59 l/h je Monat, bei 20 kippt das Vorzeichen.
    - 48 Zähler ohne Tageswert-Phase: 44 unverändert, 4 ändern sich wegen angebrochener Randmonate.
    - Alle Stationen: Median +0,10 → −1,40 l/h je Monat.
- `real_meters/` bleibt dabei unverändert, die Tageswerte bleiben drin.

## Anschlusswert auch über die Adresse

- Problem: Nach einem Zählertausch steht in `Nodes_Edges.ods` noch die alte Nummer. Der neue Zähler fand keinen
  Anschlusswert, obwohl der Wert des Hauses bekannt ist.
- Lösung: zweite Stufe über die Adresse, mit der 1:1-Regel aus [Schritt 5](schritte.md#5-adresse-und-anschlusswert-zuordnen).
- Warum die 1:1-Regel: An einer Adresse steht ein alter Zähler (66417929) mit 500 kW, heute sind dort aber zwei
  Stationen (81050517 und 81062289). Zusammen erreichen sie höchstens 565 kW, in 95 % der Stunden unter 318 kW. Die
  500 kW gelten also für beide zusammen, nicht für jede.
- Wirkung: Der Anschlusswert fehlt bei 6 statt 8 HAST. 80912166 bekommt 19 kW, 72167784 bekommt 16 kW, jeweils vom
  alten Zähler an derselben Adresse. Die Lastquoten dieser beiden sind damit gerechnet statt in Notebook 01
  geschätzt.

## Notebooks neu ausgeführt

- Jede Änderung wurde zuerst als Probelauf gerechnet und dann mit einem Neulauf bestätigt (zuletzt mit
  93 HAST). Die Notizen im Notebook sind an diesen Lauf angepasst.
- Notebook 01 musste danach neu laufen, weil sich mit dem Filtertrend ein Merkmal des Clusterings geändert hat.
