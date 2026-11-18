# Änderungen 2: Kennzahlen ans Raster anpassen

Seit dem Stundenraster gibt es leere Zeilen für nicht gemessene Stunden. Die Kennzahlen je Station mussten darauf
angepasst werden.

## Anteile nur über gemessene Stunden

- Problem: Seit dem Raster gibt es leere Zeilen. Ein Vergleich mit einem leeren Wert ergibt immer „falsch“. Ein
  einfacher Mittelwert hätte die Lücken als „Bedingung nicht erfüllt“ mitgezählt.
- Der Anteil wäre genau *richtiger Wert mal Abdeckung* gewesen. Beim Zähler mit damals 17 % Abdeckung also nur noch
  17 % des richtigen Werts.
- Lösung: eine Hilfsfunktion teilt nur durch die gemessenen Stunden. Gilt für `idle_share`, `summer_flow_share` und
  `rt_above_50_share_loaded`.

## Abdeckung in die Kennzahlentabelle

- Gemessene Stunden, Rasterlänge und Abdeckung stehen jetzt in `hast_features.csv`, 20 statt 17 Spalten.
- So ist für jede Station sichtbar, auf wie vielen echten Messstunden ihre Kennzahlen beruhen.

## Wirkung auf die Regelhysterese

- `flow_short_cycle_power` ist im Clustering der drittstärkste Treiber. Mit Raster sinkt ihr Median über alle HAST
  von 0,1866 auf 0,1742 (−4,3 %).
- 8 Stationen lagen vorher um 20 bis 34 % daneben, am stärksten 80912182 (0,182 → 0,120).
- Überraschend: Die Verzerrung hängt kaum an der Menge der Lücken (Korrelation nur +0,23), sondern an ihrer
  Verteilung. Viele kleine, verstreute Lücken stauchen die Zeitachse durchgehend, wenige große Blöcke verschieben sie
  nur einmal.

## Jahreswerte normiert

- Problem: `energy_kwh_year` hieß „Jahr“, summierte aber über die ganze Messreihe. Lang beobachtete Zähler sahen
  dadurch größer aus.
- Lösung: Die Jahreswerte sind jetzt auf 8.760 Stunden je Jahr normiert.
