# Handlungsempfehlungen

Die Aufgabenstellung verlangt je Station eine Handlungsempfehlung: Reparatur, Regelungsoptimierung oder
Kapazitätsanpassung. Diese Seite beschreibt, wie aus den Ausgaben des [Endmodells](endmodell.md) eine
Empfehlung wird, was beim aktuellen Datenstand herauskommt und wie verlässlich das ist. Gerechnet wird mit den Paketen
aus Notebook 35, angewendet vom Programm dashboard_daten. Angezeigt wird die Empfehlung in der Handlungsliste des
[Dashboards](dashboard.md).

## Von der Klasse zur Handlung

Jede Station bekommt zuerst eine der drei Klassen (siehe [Fehlerart und Klasse je Station](../modelle/klassen.md)).
Daraus wird die Handlung:

| Klasse | wann | Handlung |
|---|---|---|
| Regelventil tauschen | Ventil-Score ab 0,5 | Reparatur: Regelventil tauschen |
| Regelparameter optimieren | sonst K-Means „schlechter“ | keine eigene Handlung, siehe unten |
| kein Handlungsbedarf | sonst K-Means „Optimum“ | keine |
| nicht einstufbar | weder Ventil-Score ab 0,5 noch eine Einstufung durch K-Means, weil Kennzahlen fehlen | Daten prüfen |

Unabhängig von der Klasse kommen zwei Hinweise dazu:

- **Dämmung prüfen:** Dämmungs-Score ab 0,5.
- **Kapazitätsanpassung prüfen:** Die Spitzenlast liegt bei höchstens 69 % der Vertragsleistung. Die Grenze ist über
  den Youden-Index auf den begangenen Stationen gewählt.

## Dringlichkeit

| Dringlichkeit | wann |
|---|---|
| hoch | Reparatur, bestätigt durch das Fehlerbild „ventil“ des Monitoring-Modells |
| mittel | Reparatur nur nach dem Ventil-Score |
| niedrig | nur Hinweise: Kapazität prüfen, Dämmung prüfen, Daten prüfen |
| keine | weder Handlung noch Hinweis |

- Innerhalb einer Stufe wird nach dem Ventil-Score sortiert. Das ist der Teil der Reihenfolge, den Notebook 35 belegt.
- **Sonderfälle** bekommen nur „Daten prüfen“, keine Reparatur. Sonderfall heißt: Mindestens zwei Kennzahlen liegen
  außerhalb dessen, woraus das Modell gelernt hat, oder die Station hat mehr als 10 % des Wintervolumens im Netz und
  ist damit keine typische Hausstation. Für solche Werte ist der Score nicht geprüft.
- Die Stufen sind festgelegt, nicht gelernt.
- Die Dringlichkeit ist nicht die Priorität des Monitoring-Modells (siehe
  [Alarme](../monitoring/alarme.md#prioritat-aus-netzvergleich-und-verschlechterungsalarm)). Priorität „hoch“ heißt:
  im Netzvergleich auffällig und ein Verschlechterungsalarm in der Heizperiode, das trifft aktuell auf 8 Stationen zu.
  Dringlichkeit „hoch“ verlangt einen Reparaturverdacht, den das Fehlerbild „ventil“ bestätigt, das sind aktuell 2.

## Stand der Empfehlungen

Gerechnet mit den Paketen aus Notebook 35 auf den Messdaten bis 20.07.2026. Klasse und Empfehlung gelten für den
letzten Winter mit genug Daten, das ist 2024/25, und den Sommer 2025. Für den Winter 2025/26 fehlen die Daten der
meisten Zähler. Die Zahlen gibt `python -m src.dashboard_daten` am Ende aus, die Tabelle je Station steht danach in
`outputs/dashboard/stationen.parquet` (Spalten `dringlichkeit` und `handlung`).

| Dringlichkeit | Stationen |
|---|---|
| hoch | 2 |
| mittel | 7 |
| niedrig | 53 |
| keine | 31 |
| zusammen | 93 |

| Handlung | Stationen |
|---|---|
| Reparatur: Regelventil tauschen | 9 |
| Dämmung prüfen | 37 |
| Kapazitätsanpassung prüfen | 14 |
| Daten prüfen | 15, davon 6 Sonderfälle und 9 nicht einstufbar |
| keine | 31 |

Eine Station kann mehrere Handlungen haben, zum Beispiel eine Reparatur und den Hinweis auf die Dämmung.

- Die Klasse „Regelventil tauschen“ haben 11 Stationen. 9 davon bekommen die Reparatur, 2 sind Sonderfälle und bekommen
  nur „Daten prüfen“.
- Die Klasse „Regelparameter optimieren“ haben 14 Stationen. Sie bekommen dafür keine Handlung, nur die Hinweise, die
  unabhängig von der Klasse gelten.

**Vorher und jetzt.** Zum Vergleich rechnet das Programm auch den Stand vor den Begehungen, aus dem Winter 2023/24 und
dem Sommer 2024 mit Tagen vor der ersten Begehung. Damals hatten 19 Stationen einen Reparaturverdacht (6 hoch, 13
mittel), heute sind es 9. Das passt dazu, dass bei den Begehungen Ventile getauscht wurden, ist aber kein Nachweis: Der
Ventil-Score sinkt nach jeder Begehung, nicht nur nach einem Ventiltausch, und die beiden Winter sind verschieden.

## Wie verlässlich die Empfehlungen sind

Geprüft ist das in Notebook 35 an den begangenen Stationen, mit Kreuzvalidierung über Stationsgruppen.

- **Reihenfolge:** Unter den ersten 10 Stationen nach dem Ventil-Score des LSTM-Modells hatten 7 einen Ventilbefund
  (Test E). Nach der Priorität des Monitoring-Modells waren es 5, Zufall wären etwa 2.
- **Reparatur (mittel):** Das Modell im Dashboard findet 8 von 11 Ventilfällen bei 4 Fehlalarmen (Test C).
- **Reparatur (hoch):** Das Fehlerbild „ventil“ des Monitoring-Modells war bei 4 von 4 Stationen richtig, findet aber
  nur 4 von 11 Ventilfällen. „Hoch“ ist deshalb selten, aber verlässlich.
- **Dämmung:** Das Modell im Dashboard findet 15 von 22 Dämmungsfällen bei 7 Fehlalarmen. Der Vorsprung vor der besten
  Einzelregel ist nicht gesichert, deshalb nur ein Hinweis.
- **Kapazität:** Die Regel findet 5 von 9 Fällen bei 1 Fehlalarm (AUC 0,76).

Alle Zahlen sind rückblickend an vorhandenen Begehungen geprüft. Ob die Reihenfolge im Betrieb trägt, zeigt erst eine
Begehung nach der Liste (siehe [Prüfung nach vorn](../ausblick/pruefung.md)).

## Was bewusst nicht empfohlen wird

- **Keine Empfehlung „Regelung optimieren“.** Kein Modell erkennt diese Maßnahme. In Notebook 35 landen 24 bzw. 25 von
  31 Fällen mit Regelungsoptimierung in „kein Handlungsbedarf“ (Test C).
- **Kein Sortieren nach Meldungen der Wächter.** Vor Begehungen mit Befund gab es nicht mehr Verschlechterungen als bei
  Vergleichsstationen (Notebook 21).
- **Kein Sortieren nach Potenzial und keine Einspar-Schätzung in Euro.** Das Potenzial sagt nicht vorher, wo eine
  Begehung am meisten bringt (Notebook 35, Test D, Rangkorrelation 0,16).
- **Keine Empfehlung zu Filter, Durchfluss und Sollwert.** Diese Maßnahmen hinterlassen in den Zählerdaten keine Spur
  (Notebook 36, siehe [Verworfene Ansätze](../grenzen/verworfene_ansaetze.md#fehlerarten-ohne-messspur)).
