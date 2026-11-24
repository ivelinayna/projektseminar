# Änderungen 1: Rohdaten lesbar machen

Die ersten Änderungen machen die Exporte überhaupt erst nutzbar. Die Zahlen zeigen den Stand von damals, als noch
96 Zähler als HAST galten.

## ODS-Werte 1000-fach zu groß

- Problem: In den ODS-Dateien steht zum Beispiel 36000 für 36,0 °C Vorlauf.
- Ohne Korrektur kämen 60.000 kW je HAST heraus. Das ganze Netz hat rund 2 MW.
- Lösung: am Median der Vorlauftemperatur erkennen und zurückrechnen.

## Zeitstempel auf die volle Stunde abrunden

- Problem: 13:00 und 13:01 überleben beide die Duplikatentfernung. Dieselbe Stunde steht doppelt in der Reihe.
- Das verfälscht vor allem die FFT, die „ein Wert ist eine Stunde“ annimmt.
- Lösung: abrunden und die beiden Arten von Dubletten getrennt zählen, damit sichtbar bleibt, welche normal sind.

## Lückenloses Stundenraster

- Problem: Lücken waren unsichtbar, „eine Zeile ist eine Stunde“ galt nicht.
- Lösung: Raster über den ganzen Zeitraum, Abdeckung je Zähler in der Übersicht.
- Damals ergab sich: 2.398.470 Rasterstunden, davon nur 1.744.941 gemessen (73 %). Über ein Viertel aller Stunden
  fehlte, und das war vorher nicht zu sehen.

## Plausibilitätsgrenzen

- Lösung: Werte außerhalb der Grenzen auf leer setzen, nach dem Zurückrechnen der ODS.
- Ergebnis: keine einzige der damals 1,74 Mio. Messzellen maskiert. Nach der Skalierungskorrektur sind die Daten
  physikalisch sauber.

## Keine Umrechnung nach UTC

- Getestet, weil die Zeitachse in Lokalzeit nicht eindeutig ist (im Oktober gibt es 02:00 zweimal, im März gar
  nicht).
- Verworfen: Die doppelte Stunde im Oktober enthält in den Exporten nur eine Ablesung, es gibt also keine zweite
  Stunde zu retten. Jede Variante hat Messstunden gekostet:

| Variante | Ergebnis |
|---|---|
| Doppelte Stunde automatisch erkennen | scheitert bei 166 von 198 Dateien |
| Doppelte Stunde als leer setzen | 405 Messstunden verloren |
| Doppelte Stunde als Winterzeit lesen | 240 Messstunden verloren, weil durch die Verschiebung mehr Zeilen der Exporte in dieselbe Stunde fallen |

## Erzeuger und Kessel ausschließen

- Laut ÜZ-Meeting sind 6 Zähler Erzeuger oder Kessel, keine Hausstationen: BHKW, HHS-Kessel I bis IV,
  Ölspitzenkessel.
- Sie stehen in einer festen Liste im Code und kommen nicht mehr in `real_meters/`.
