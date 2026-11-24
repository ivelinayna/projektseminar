# Tagesmonitor

**Notebook 20:** `notebooks/5_monitoring/20_tagesmonitor.ipynb` · **Code:** `src/tagesmonitor.py`, eingebunden in
`src/stationsblatt.py`, Tests in `tests/test_tagesmonitor.py` und `tests/test_stationsblatt.py`

Der Tagesmonitor fragt: **Läuft die Station schlechter als früher?** Jede Station wird an jedem Heiztag mit sich selbst
verglichen. Er ist das Gegenstück zum [Netzvergleich](netzvergleich.md), der jede Station mit allen anderen vergleicht.
Die Idee stammt aus dem [Normalverhaltensmodell](normalverhalten.md). Notebook 20 setzt sie als Modul um, das im
Betrieb auf neuen Daten läuft, und ersetzt damit den Fensteralarm des Kennlinienmonitors aus
[Notebook 13](../stationsbilder/index.md).

Im Endmodell ist der Tagesmonitor der Alarmkanal des Monitoring-Modells, als Paket `normalmodell` (siehe
[Modellvergleich](../vergleich/modellvergleich.md)).

## Funktionsweise

- **Zwei Kanäle je Heiztag** (Tagesmittel unter 15 °C): Abkühlung in kWh/m³, das entspricht etwa der Spreizung mal 1,16,
  und Wassermenge.
- **Lernjahr:** Im ersten Jahr lernt das Modell, welcher Wert bei welcher Außentemperatur normal ist. Abkühlung als
  robuste Gerade (Theil-Sen), Wassermenge als Median je 2-K-Temperaturklasse, weil sie nicht linear ist.
- **CUSUM:** z = (heute minus erwartet) / übliche Schwankung der Station. Jeden Tag kommt z − 0,5 auf ein Konto, das nie
  unter null fällt. Steigt es über 5, gibt es einen Alarm. Zwei Konten, über und unter der Erwartung.
- **Richtung:** Ein Alarm heißt schlechter (Abkühlung sinkt oder Wasser steigt) oder besser. Ein neuer Alarm in
  dieselbe Richtung kommt erst, wenn das Konto zwischendurch bei null war.
- **Grenze:** Gelernt wird das Übliche, nicht das Gute. War die Station im Lernjahr schon defekt, gilt der Defekt als
  normal. Deshalb steht der Netzvergleich daneben.

## Tageswerte aus Zählerständen

Der Tagesmonitor nutzt nur Zählerstände (Energie und Volumen) und das Tagesmittel der Außentemperatur.

- **Warum:** Der Tagesverbrauch aus Zählerständen ist exakt, Stundenwerte sind nur Momentaufnahmen. Zählerstände gibt
  es auch in der Tageswert-Phase bis Ende 2022.
- **Tageswert:** Zählerstand um Mitternacht am Anfang und Ende des Tages. Fehlt der Stand um 0 Uhr, wird der nächste
  zwischen 22 und 2 Uhr genommen und auf 24 Stunden hochgerechnet.
- **Ausschlüsse:** Kein Tag wird gelöscht, der Grund steht dabei. Ausgeschlossen werden Tage ohne Zählerstand, mit
  Rücksprung, mit stehendem Zähler und der Folgetag, mit unter 5 kWh, mit unplausiblen Werten (über 70 kWh/m³) und ohne
  Tagesmittel der Temperatur.
- Von 85.983 Stationstagen sind 78.350 nutzbar, davon **55.746 Heiztage**.
- **Was fehlt:** Nachtdurchfluss, Takten, Tagesgang sowie Rücklauf und Vorlauf einzeln. Den Rücklauf und den
  Nachtdurchfluss deckt das [Prognose-LSTM](../modelle/prognose.md) ab.

## Lernjahr je Station

- Beginn am ersten nutzbaren Heiztag, Dauer 365 Kalendertage. Liegt eine Begehung darin, endet das Lernjahr 14 Tage
  vor der ersten Begehung.
- Überwacht wird eine Station mit mindestens 60 Heiztagen und 8 K Temperaturspanne im Lernjahr und Tagen danach.
- **89 Stationen werden überwacht.** Vier nicht: Bei dreien beginnen die Daten erst im Herbst 2024, bei einer gibt es
  nach dem Lernjahr keine nutzbaren Heiztage mehr.
- Zwei Gruppen nach Datenbeginn: 43 Stationen ab November 2021 mit langer Überwachung. 43 Stationen erst ab Herbst 2023,
  deren Lernjahr oft durch die Begehung im Herbst 2024 gekürzt ist. Bei ihnen beginnt die Überwachung praktisch erst
  mit der Begehung.

## Hilft die Temperatur?

Verglichen wird die gelernte Kurve mit einer Konstanten (Median des Lernjahrs), auf den ersten bis zu 120 Heiztagen
nach dem Lernjahr. Skill = 1 − Fehler Kurve / Fehler Median.

| Kanal | Stationen | Skill (Median) | Anteil positiv |
|---|---|---|---|
| Abkühlung | 67 | 0,01 | 54 % |
| Wassermenge | 67 | 0,28 | 84 % |

Bei der Wassermenge hilft die Temperatur klar. Bei der Abkühlung ist die Kurve fast eine Konstante. Für den CUSUM reicht
das als stabile Erwartung, das Wetter wird bei der Abkühlung aber kaum herausgerechnet.

**Kälteeinbrüche erzeugen Fehlalarme.** Vom 09. bis 12.12.2022 fiel das Tagesmittel von 3,4 auf −3,7 °C bei gleichem
Vorlauf im Netz. Die Häuser brauchen mehr Wärme, die Ventile öffnen, der Rücklauf steigt und kWh/m³ sinkt. Das ist
physikalisch normal, der Tagesmonitor meldet trotzdem „schlechter“, weil die Kurve den Abfall nicht erwartet und Gebäude
verzögert auf das Tagesmittel desselben Tages reagieren. Solche Wellen erkennt [Notebook 24](netzereignisse.md).
Abhilfe wäre, die Temperatur der letzten zwei bis drei Tage zu mitteln oder um einen Tag zu verzögern.

## Beispiel 68956351

Die Station mit dem jahrelang offenen Ventil, repariert am 09.09.2024. Ihr Lernjahr lag von November 2021 bis November
2022, das Ventil war also schon offen.

- 5 Alarme, davon 4 vor der Reparatur. Drei davon zeigen „besser“, obwohl das Ventil noch offen war.
- Der eigentliche Erfolg: Abkühlung „besser“ am 11.09.2024, zwei Tage nach der Reparatur (etwa 5 auf 25 kWh/m³).
- Der Fehler selbst wurde nie gemeldet, weil das Lernjahr ihn schon enthielt. Nur der Netzvergleich zeigt ihn.
- Ein Alarm heißt also „anders als im Lernjahr“, nicht „defekt“ oder „repariert“.

## Alarmlast

- **491 Alarme** bei 84 von 89 Stationen, im Median 1,2 je 100 Heiztage. Das sind gut zwei Alarme je Heizperiode und
  Station.
- 247 zeigen „schlechter“ (Abkühlung sinkt 152, Wasser steigt 95), 244 „besser“.
- Fast jede Station alarmiert regelmäßig. Ein Alarm allein ist deshalb kein Grund für eine Begehung. Hohe Priorität gibt
  es nur zusammen mit einer Auffälligkeit im Netzvergleich (siehe [Alarme bewerten](alarme.md)).

## Treffen die Alarme die Begehungen?

Treffer = Alarm in beliebiger Richtung 7 Tage vor bis 60 Tage nach der Begehung. Die Kontrollquote ist der Anteil der
Stationen ohne Begehung mit Alarm im selben Zeitraum. Das rechnet Herbst, Heizbeginn und Wetter heraus.

| Prüfung | Treffer | Quote | Kontrollquote | Hebel | p (einseitig) |
|---|---|---|---|---|---|
| Abkühlung | 22 von 43 | 0,51 | 0,27 | 1,87 | 0,001 |
| Wassermenge | 22 von 43 | 0,51 | 0,36 | 1,43 | 0,028 |
| einer der beiden | 29 von 43 | 0,67 | 0,51 | 1,32 | 0,022 |
| Fenstermonitor aus Notebook 13, einer der beiden | 31 von 43 | 0,72 | 0,74 | 0,97 | 0,69 |

- Der Fenstermonitor aus Notebook 13 schlägt auch ohne Begehung ständig an. Er wurde deshalb im Endmodell durch den
  Tagesmonitor ersetzt.
- Die Abkühlung trifft vor allem nicht mechanische Eingriffe (17 von 29, Hebel 2,1), die Wassermenge vor allem
  mechanische wie Ventil oder Schmutzfänger (9 von 14, Hebel 1,7, p = 0,039). Das passt dazu, dass Bauteile den
  Durchfluss ändern und Einstellungen eher die Abkühlung.
- **Vorsicht:** Der Treffer kommt fast nur aus „besser“-Alarmen nach der Begehung (siehe [Alarme bewerten](alarme.md)).
  Der Monitor sieht also die Veränderung durch den Eingriff, er warnt nicht vorher.

## Wirkung der Begehung

Residuum = gemessen minus erwartet aus dem Lernjahr, das Wetter ist damit herausgerechnet. Verglichen werden die
30 Heiztage nach mit den 30 vor der Begehung, abzüglich derselben Rechnung bei Stationen ohne Begehung
(Differenz-von-Differenzen).

| Kanal | Fälle | Diff-in-Diff | in erwarteter Richtung | p (Wilcoxon) |
|---|---|---|---|---|
| Abkühlung | 24 | +2,2 kWh/m³ | 63 % | 0,046 |
| Wassermenge | 24 | −8,0 % | 71 % | 0,029 |

- Es sind nur 24 Fälle, weil der Verlauf erst nach dem Lernjahr beginnt. Endet das Lernjahr 14 Tage vor der Begehung,
  fehlen Tage davor.
- Am deutlichsten wirken mechanische Eingriffe (7 Fälle): Abkühlung +4,8 kWh/m³, Wasser −13,9 % (p = 0,031).
- Die Kontrollgruppe zieht nach dem Termin 12 % mehr Wasser, weil die Temperaturkurve den Übergang vom Herbst in den
  Winter nicht ganz abfängt. Ohne Kontrollgruppe wäre keine Wirkung sichtbar.
- Anders als im [Wintervergleich](netzvergleich.md#teil-b-kernwinter-vor-gegen-kernwinter-nach-der-begehung) mit ganzen
  Kernwintern ist die Wirkung hier knapp nachweisbar. Beide Maße sind sich einig, welche Begehungen gewirkt haben
  (Spearman zwischen Wasser-Diff-in-Diff und Änderung der Steigung −0,64, p = 0,001).

## Gegenprobe: Abkühlung bei 5 °C gegen den Netzscore

Je Station und Kernwinter wird aus den Tageswerten eine Gerade kWh/m³ über der Temperatur gelegt und der Wert bei 5 °C
abgelesen. So werden alle Stationen bei derselben Temperatur verglichen.

- Spearman mit dem Netzscore aus Notebook 19: 0,88 (22/23), 0,87 (23/24), 0,88 (24/25). Von den zehn schlechtesten bei
  5 °C sind im Netzvergleich 6, 8 und 9 auffällig.
- Datenbasis (Zählerstände je Tag statt Momentaufnahmen je Stunde) und Methode (eine Gerade statt fünf Kennzahlen)
  sind unabhängig. Der Netzvergleich ist also kein Zufallsprodukt seiner Kennzahlauswahl.
- Anders als der Netzvergleich funktioniert die Abkühlung bei 5 °C auch im Winter 21/22.

## Einordnung

- **Belastbar:** Der Abkühlungskanal trifft Begehungen deutlich öfter als Stationen ohne Begehung, der Fenstermonitor
  nicht. Netzscore und Abkühlung bei 5 °C finden dieselben schlechten Stationen. Diff-in-Diff und Wintervergleich sind
  sich einig, welche Begehungen gewirkt haben.
- **Schwach:** Dauerfehler bleiben unsichtbar, weil das Lernjahr sie enthält. Bei der Abkühlung wird das Wetter kaum
  herausgerechnet, Kälteeinbrüche lösen Alarme aus. Die Alarmlast ist hoch, und eine dauerhafte Änderung wird nur
  einmal gemeldet. Die Fallzahlen sind klein (Treffertest 43, Diff-in-Diff 24, mechanisch 7).
- **Gesetzt, nicht hergeleitet:** k = 0,5, h = 5, Deckel des Kontos 10, Lernjahr 365 Tage, mindestens 60 Heiztage und
  8 K Spanne, Heizgrenze 15 °C, Toleranz ±2 Stunden um Mitternacht, Treffer-Fenster, 30 Heiztage, Normtemperatur 5 °C.
- **Offen:** Temperatur über mehrere Tage mitteln oder verzögern, die Wassermenge über die kälteste gelernte Temperatur
  hinaus fortschreiben, das Lernjahr nach einem bekannten Eingriff neu starten (siehe
  [Probebetrieb](../ausblick/probebetrieb.md)).

## Ausgaben

Das Notebook schreibt keine Dateien. Im Betrieb rechnet der Tagesmonitor in `src/stationsblatt.py` mit und erscheint im
Stationsblatt, in `status.csv` und im Bericht von `python -m src.aktualisieren`.
