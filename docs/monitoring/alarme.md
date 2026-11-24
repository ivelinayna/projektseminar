# Alarme bewerten

**Notebook 21:** `notebooks/5_monitoring/21_alarme.ipynb` · **Code:** `src/alarmbewertung.py`, gerechnet über
`src/stationsblatt.py`, Tests in `tests/test_alarmbewertung.py`

Das Notebook baut auf dem Monitoring-Modell auf, also auf [Netzvergleich](netzvergleich.md) und
[Tagesmonitor](tagesmonitor.md). Es prüft vier Fragen:

1. Wie hängen Treffer und Alarmzahl von der Schwelle h ab?
2. In welche Richtung zeigen die Treffer, und warnt der CUSUM vor einer Begehung vor?
3. Ergeben Netzvergleich und Verschlechterungsalarm zusammen eine brauchbare Priorität?
4. Gibt es benennbare Fehlerbilder, und spielt das Baujahr eine Rolle?

Grundlage sind 491 Alarme des Tagesmonitors bei h = 5 auf 35.707 überwachten Heiztagen.

## Schwelle h

h ist die aufsummierte Abweichung, die ein Konto erreichen muss, bis ein Alarm kommt. Der Standard h = 5 stammt aus dem
Normalverhaltensmodell und ist nicht kalibriert. Die Alarme werden für h = 5 bis 20 neu gerechnet, jeweils mit dem
Treffertest aus Notebook 20 im Abkühlungskanal.

| h | Alarme | je 100 Heiztage | Treffer | Hebel | p (einseitig) |
|---|---|---|---|---|---|
| 5 | 491 | 1,38 | 22 von 43 | 1,87 | 0,001 |
| 8 | 335 | 0,94 | 18 von 43 | 1,57 | 0,023 |
| 10 | 282 | 0,79 | 16 von 43 | 1,38 | 0,093 |
| 15 | 223 | 0,63 | 14 von 43 | 1,44 | 0,087 |
| 20 | 178 | 0,50 | 10 von 43 | 1,34 | 0,20 |

- Bei h = 8 fallen die Alarme auf etwa zwei Drittel, der Hebel bleibt signifikant. Danach schwankt er, denn bei 43
  Begehungen verschiebt jede einzelne die Quote um gut zwei Prozentpunkte.
- Die Wassermenge ist bei keiner Schwelle signifikant.
- Eine klar beste Schwelle gibt es nicht. h = 8 ist eine Option, falls die Alarmzahl im Betrieb stört.

## Richtung der Alarme und Vorwarnung

Verschlechtert heißt: weniger Abkühlung oder mehr Wasser bei gleichem Wetter. Für einen Fehlermelder zählen nur
Verschlechterungen. Geprüft wird zusätzlich ein Vorlauffenster von 180 bis 7 Tagen vor der Begehung. Gäbe es dort mehr
Verschlechterungsalarme als bei den Kontrollen, würde der CUSUM vorwarnen.

| Richtung | Fenster | Fälle | Quote | Kontrollquote | Hebel | p (einseitig) |
|---|---|---|---|---|---|---|
| alle | um die Begehung | 43 | 0,67 | 0,51 | 1,32 | 0,022 |
| besser | um die Begehung | 43 | 0,58 | 0,22 | 2,68 | < 0,001 |
| schlechter | um die Begehung | 43 | 0,35 | 0,34 | 1,04 | 0,49 |
| schlechter | davor | 32 | 0,34 | 0,35 | 0,98 | 0,60 |

- **Der Hebel aus Notebook 20 kommt fast ganz aus Besserungsalarmen** (Hebel 2,7, p < 0,001). Das passt zu einer
  besseren Abkühlung nach der Begehung.
- Verschlechterungsalarme sind weder um die Begehung noch im halben Jahr davor häufiger als bei den Kontrollen.
- **Der Tagesmonitor taugt damit zur Erfolgskontrolle, nicht zur Frühwarnung.** Im Stationsblatt sind
  Verschlechterungsalarme deshalb gefüllt und Besserungsalarme hohl dargestellt.

## Priorität aus Netzvergleich und Verschlechterungsalarm

Je Station und Kernwinter:

- **hoch:** im Netzvergleich auffällig und mindestens ein Verschlechterungsalarm in der Heizperiode (1. Oktober bis
  30. April),
- **mittel:** eins von beiden,
- **niedrig:** keins.

| Winter | hoch | mittel | niedrig |
|---|---|---|---|
| 22/23 | 5 | 23 | 13 |
| 23/24 | 3 | 32 | 51 |
| 24/25 | 8 | 45 | 31 |

- Netzauffälligkeit und Verschlechterungsalarm hängen nicht zusammen (Fisher p = 0,31). Der Netzvergleich misst den
  Zustand gegenüber den anderen Stationen, der CUSUM eine Änderung gegenüber der eigenen Vergangenheit.
- **Prüfung an der nächsten Begehung:** 50 Stationswinter haben innerhalb von 400 Tagen danach eine Begehung mit
  Freitext. Nur der Netzvergleich zeigt eine Tendenz: Von 3 auffälligen Stationswintern hatten 2 einen Ventilbefund,
  von den übrigen 47 nur 6 (p ≈ 0,06).
- Der Verschlechterungsalarm trennt weder Ventil- noch mechanische Befunde. „Hoch“ ist damit nicht besser begründet als
  „im Netz auffällig“.
- Für die Reihenfolge der Begehungen bleibt der Netzvergleich maßgeblich, der Alarm zeigt den Zeitpunkt einer Änderung.

Aktuell haben 8 Stationen Priorität hoch, darunter die chronisch auffälligen 72135442, 72135453, 72167793 und 80912182.

## Fehlerbild aus dem Muster der schlechten Kennzahlen

Feste Regeln auf den schlechten Kennzahlen des Netzvergleichs, das erste passende Muster gewinnt. Die Texte beschreiben
ein Muster und womit es vereinbar ist, sie nennen keine Ursache und keine Maßnahme.

| Fehlerbild | schlechte Kennzahlen | Text im Stationsblatt |
|---|---|---|
| ventil | Steigung und Spreizung | Volumenstrom folgt der Leistung kaum, kleine Spreizung; konsistent mit offenem oder nicht regelndem Ventil |
| durchfluss | Spreizung und Rücklauf oder Wasser je kW | viel Wasser bei kleiner Spreizung oder hohem Rücklauf; konsistent mit zu hohem Durchfluss |
| unruhig | Streuung | Kennlinie unruhig; konsistent mit taktender Regelung oder Messproblem |
| regelung | Steigung | Volumenstrom folgt der Leistung kaum; konsistent mit Regelungsproblem |
| rücklauf | Rücklauf über 50 °C | oft Rücklauf über 50 °C |
| durchfluss_je_kw | Wasser je kW | hoher Volumenstrom je kW Anschlusswert |

- Unter 27 auffälligen Stationswintern ist das häufigste Muster eine flache Steigung mit kleiner Spreizung. Das passt
  zu einem offenen oder nicht regelnden Ventil.
- Das Fehlerbild „ventil“ trifft dieselben drei Stationswinter wie „im Netz auffällig“, zwei davon mit Ventilbefund.
  Plausibel, mit drei Fällen aber nicht belegt.
- Für die übrigen Fehlerbilder gibt es kaum Begehungen danach. Die Zuordnung von Fehlerbild zu Maßnahme bleibt offen.

## Baujahr als Kontext

- Das Baujahr kommt aus dem Freitext der Begehungen (20 Zähler), sonst aus dem Zensus 2022 im 100-m-Gitter. Der
  Zensuswert ist ein Gebietsmittel, weil die Geokodierung meist nur die Straße trifft.
- Alt heißt vor 1979, also vor der ersten Wärmeschutzverordnung. Wo Freitext und Zensus beide eindeutig sind, stimmen
  sie in 9 von 11 Fällen überein.
- Stationen in alten Gebäuden sind im Netzvergleich nicht häufiger auffällig, eher seltener (nicht signifikant).
- Das Baujahr bleibt Kontext in Statuszeile und Text, nicht Teil von Score oder Priorität.
- Kartendienste wie Google Maps wurden bewusst nicht genutzt, damit keine Kundenadressen an Dritte gehen.

## Einordnung

- **Belastbar:** der Befund zur Richtung der Alarme. Die Treffer um die Begehung kommen aus Besserungsalarmen, vorher
  gibt es nicht mehr Verschlechterungen als bei den Kontrollen.
- **Schwach:** alles, was an Begehungsbefunden hängt. Priorität und Fehlerbild „ventil“ zeigen eine Tendenz zu
  Ventilbefunden nur über den Netzanteil und mit drei Fällen. Fehlerbilder sind beschreibend, keine geprüfte Diagnose.
- **Offen:** Die Labels blockieren eine bessere Prüfung: 50 Stationswinter mit Begehung danach, davon nur 3 im Netz
  auffällig. Der nächste Schritt wäre ein vorab geplanter Test mit auffälligen und zufällig gezogenen Stationen, ohne
  dass das Team vor Ort weiß, welche welche ist (siehe [Prüfung nach vorn](../ausblick/pruefung.md)). Ebenso offen
  sind die Zuordnung von Fehlerbild zu Maßnahme und das Baujahr je Haus aus den Kundendaten der ÜZ.

## Ausgaben

Das Notebook schreibt keine Dateien. Priorität und Fehlerbild stehen im Betrieb in der Statuszeile des Stationsblatts
und in `status.csv`.
