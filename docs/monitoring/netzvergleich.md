# Netzvergleich und Wintervergleich

**Notebook 19:** `notebooks/5_monitoring/19_netzvergleich.ipynb` · **Code:** `src/netzvergleich.py`,
`src/kennlinien_monitor.py`, `src/stationsblatt.py`, Tests in `tests/test_netzvergleich.py`,
`tests/test_kennlinien_monitor.py` und `tests/test_stationsblatt.py`

Das Notebook hat drei Teile:

- **Teil A, Netzvergleich:** Welche Stationen laufen schlechter als die anderen? Alle 93 Stationen, egal ob begangen.
  Das Ergebnis geht in die Priorität ein.
- **Teil B, Wintervergleich:** Hat die Begehung etwas gebracht? Dieselbe Station im Kernwinter vor und nach der
  Begehung, verglichen mit Stationen ohne Begehung.
- **Teil C, Stationsblatt:** beides zusammen mit dem [Tagesmonitor](tagesmonitor.md) als ein Blatt je Station.

Gerechnet wird nur im **Kernwinter** (Dezember bis Februar) und nur auf Betriebsstunden. Dann heizen alle Stationen,
und der Vergleich ist fair. Teil A und der Tagesmonitor bilden zusammen das Monitoring-Modell.

## Teil A: Kennzahlen je Station und Kernwinter

Für jede Station und jeden Kernwinter wird eine Kennlinie gerechnet: eine Gerade durch log(Volumenstrom) über
log(Leistung). Sie zeigt, ob das Wasser dem Bedarf folgt. Daraus entstehen fünf Kennzahlen:

| Kennzahl | schlecht ist | Bedeutung |
|---|---|---|
| Spreizung bei Medianleistung | klein | wie stark das Wasser abkühlt |
| Steigung der Kennlinie | klein | gesund etwa 0,9, offenes Ventil etwa 0 (das Wasser fließt immer gleich) |
| Streuung um die Kennlinie | groß | wie unruhig die Station regelt |
| Anteil der Stunden mit Rücklauf über 50 °C | groß | |
| Wasser je kW Anschlusswert | groß | |

- Es zählen nur Betriebsstunden mit Leistung, Volumenstrom und Spreizung über null. Die 7 Tage vor und nach einer
  Begehung fallen heraus, weil der Eingriff kein Normalbetrieb ist.
- Eine Station braucht mindestens 300 Betriebsstunden im Kernwinter, sonst ist die Kennlinie zu unsicher.
- Stationen je Winter: 22/23 41, 23/24 86, 24/25 84, 25/26 4. Der Winter 21/22 fällt ganz heraus, weil es dort nur
  Tageswerte gibt. 25/26 hat nur die vier Nachlieferungszähler und damit keinen Netzwert.

## Teil A: Vergleich mit dem Netz

Jede Kennzahl wird nur mit den anderen Stationen desselben Winters verglichen, ohne Training und ohne Labels. Aus
377.385 Betriebsstunden werden so 215 Zeilen (Station und Winter) mit je fünf Zahlen.

- **z-Wert je Kennzahl** = (Wert minus Median des Winters) / (1,4826 × MAD). Der MAD ist robust: Ein einzelner
  Ausreißer bläht den Maßstab nicht auf. Das Vorzeichen ist so gedreht, dass positiv immer schlechter heißt.
- **Score** = Mittel der fünf z-Werte, Rang 1 ist die schlechteste Station des Winters. Score 0 heißt so gut wie die
  typische Station, +1 im Mittel eine übliche Streuung schlechter.
- **Auffällig** = mindestens 2 der 5 Kennzahlen im schlechtesten Zehntel des Winters.
- Wasser je kW und Spreizung hängen zusammen (Spearman −0,69 bis −0,78), bleiben aber unter der Grenze von 0,9, ab
  der derselbe Befund doppelt zählen würde.

**So entsteht der Score bei 68956351 im Winter 23/24:**

| Kennzahl | Station | Median Netz | z |
|---|---|---|---|
| Spreizung | 3,35 K | 25,69 K | +2,92 |
| Steigung | −0,11 | 0,90 | +3,64 |
| Streuung | 0,28 | 0,23 | +0,47 |
| Anteil Rücklauf über 50 °C | 0,99 | 0,35 | +1,58 |
| Wasser je kW | 70,9 l/h/kW | 13,6 l/h/kW | +8,19 |

Score = Mittel der fünf z-Werte = 3,36, Rang 1. Ein einzelner extremer z-Wert kann den Score hochziehen, hier Wasser je
kW.

**Was sich zeigt:**

- Auffällig sind 6 Stationen in 22/23, 9 in 23/24 und 12 in 24/25.
- **Ventilmuster:** In 23/24 haben die Ränge 1 bis 4 (68956351, 72167777, 72167782, 68956372) dasselbe Bild. Spreizung,
  Steigung, Rücklauf und Wasser je kW sind schlecht, die Streuung ist normal. Das passt zu einem offenen oder nicht
  regelnden Ventil.
- **Unruhig:** Einige Stationen stehen weit oben, haben aber nur eine schlechte Kennzahl, fast nur die Streuung
  (z = 3,4 bis 5,0), etwa 72135442 und 68956344. Mit Stundenwerten ist das nicht von Messproblemen zu trennen, weil
  Stundenwerte Momentaufnahmen sind und schnelles Takten nur zufällig erwischt wird.
- **Der Score misst die Station, nicht den Winter.** Über zwei Winter bleibt die Rangfolge stabil (Spearman 0,81 von
  22/23 auf 23/24, 0,74 von 23/24 auf 24/25). Echte Änderungen senken die Korrelation, etwa 68956351 nach der
  Reparatur: Score 3,36 auf 0,09, Rang 1 auf 40.

## Teil A: Chronisch auffällige Stationen

- **Chronisch** = in mindestens zwei Wintern auffällig. Von 92 Stationen mit Score sind 17 mindestens einmal
  auffällig und **8 chronisch**: 68956351, 80912182, 72135442, 72167782, 72135453, 72167793, 72135480 und 68956360.
- 72135453 und 72135480 sind in allen drei Wintern auffällig. 68956351 bleibt nach der Reparatur chronisch, weil zwei
  Winter reichen.
- **4 der 8 chronischen Stationen wurden nie begangen:** 68956360, 72135453, 72135480 und 72167793. Das sind
  Kandidaten für die nächste Begehung.
- Der Tagesmonitor sieht chronische Stationen nicht, weil schon ihr Lernjahr schlecht war. Nur der Netzvergleich findet
  sie.

**Gegenprobe innerhalb der Leistungsklasse.** Ist „auffällig“ nur ein Effekt der Hausgröße? Dieselbe Rechnung nur
gegen Stationen ähnlicher Größe (bis 5 kW, 5 bis 10 kW, über 10 kW Anschlusswert) ergibt 7 chronische Stationen, alle
7 auch im Netzvergleich (Jaccard 0,88). Nur 68956360 fällt heraus.

**Was die auffälligen Stationen gemeinsam haben.** Befunde gibt es nur für begangene Stationen, bei den chronischen
also für 4.

- Alle 4 begangenen chronischen Stationen haben einen Befund an Ventil oder Stellantrieb, beim Rest 9,6 % (Fisher
  p < 0,001). Unter den mindestens einmal auffälligen sind es 44 % gegen 11 % (p = 0,029).
- Die Größe spielt keine Rolle (Anschlusswert 12 gegen 10 kW, p = 0,38).
- Bei 4 Stationen, 12 getesteten Merkmalen und nicht zufällig ausgewählten Begehungen ist das ein Hinweis, kein
  Beweis.

## Teil B: Kernwinter vor gegen Kernwinter nach der Begehung

Der Wintervergleich vergleicht ganze Kernwinter statt Spätsommer mit Herbst. Vorwinter ist der jüngste Kernwinter vor
der Begehung, Nachwinter der früheste danach.

- Von 58 Begehungen sind 43 auswertbar. 6 haben keinen Nachwinter (Begehungen 2025), 5 keine Daten, 2 zu wenige
  Punkte und 2 keinen Vorwinter.
- 42 der 43 Paare sind 23/24 gegen 24/25. Der Winter 24/25 war deutlich kälter (27.366 gegen 22.619 Heizgradstunden,
  +21 %), also brauchten die Stationen meist mehr Wärme und mehr Wasser.

**Einzelfälle:**

- Klare Verbesserungen gibt es nur bei 68956351 (Wasser im Kernwinter 567 auf 103 l/h, Spreizung +21,6 K, Rang 1 auf
  40) und 68956372 (329 auf 131 l/h, Rang 4 auf 32).
- Die meisten Stationen sind unverändert, das Verhältnis des Wassers nachher zu vorher liegt bei 0,9 bis 1,1.
- Drei Stationen brauchen nachher deutlich mehr Wasser und sind danach neu auffällig: 72135442 (193 auf 407 l/h),
  80912173 (171 auf 323 l/h) und 68956359 (123 auf 243 l/h). Bei 80912173 gilt das auch bei gleicher Leistung, es
  liegt also nicht nur am kälteren Winter.

**Gegen die Kontrollgruppe:** 41 Stationen mit Begehung im Paar 23/24 gegen 24/25 und 29 Stationen ohne Begehung. Fünf
Stationen mit Begehung ohne Datum sind ausgeschlossen.

- Wasser nachher zu vorher: Begehung +7,5 %, Kontrolle +15 %. Beide Gruppen brauchen wegen des kälteren Winters mehr.
- Spreizung +0,43 K gegen −0,41 K, Anteil Rücklauf über 50 °C −2,1 Prozentpunkte gegen 0. Die begangenen Stationen
  sind leicht besser.
- **Kein Unterschied ist signifikant** (Mann-Whitney p 0,30 bis 0,92). Eine Wirkung der Begehungen auf Gruppenebene ist
  mit ganzen Kernwintern nicht nachweisbar. Mögliche Gründe: Wenige starke Erfolge gehen in vielen unveränderten Fällen
  unter, meist wurden nur Einstellungen geändert, und die Gruppen sind klein.
- Enger um den Termin und mit Tageswerten ist die Wirkung dagegen knapp nachweisbar, siehe
  [Tagesmonitor](tagesmonitor.md).

## Teil C: Stationsblatt

`src/stationsblatt.py` rechnet Netzvergleich, Wintervergleich, Tagesmonitor und Priorität in einem Durchlauf. Dieselbe
Funktion läuft in `python -m src.aktualisieren`. Je Station entsteht ein Blatt mit:

1. Steigung und Spreizung im gleitenden Fenster vor dem Netzband (10. bis 90. Perzentil aller Stationen am selben Tag),
   dazu Median und bestes Viertel,
2. den Konten des Tagesmonitors mit seinen Alarmen,
3. der Kennlinie je Kernwinter,
4. den z-Werten je Winter und Kennzahl als Heatmap,
5. einer Statuszeile mit Rang, chronisch, Priorität, Potenzial, Wintervergleich, Alarmen und Abkühlung bei 5 °C.

Beim Ventilfall 68956351 liegt die Steigung bis September 2024 bei etwa 0, weit unter dem Netzband, nach der Reparatur
bei etwa 1,4. Die Spreizung steigt von 1 bis 10 K unter dem Band auf 25 bis 35 K im besten Viertel.

Unter den zehn schlechtesten Stationen in 24/25 wurden vier nie begangen (72167793, 72135453, 80956410, 72135480), drei
davon sind chronisch. Ein hoher Score heißt dabei weder auffällig noch hohe Priorität: 68956344 steht auf Rang 5, hat
aber nur eine schlechte Kennzahl.

## Einordnung

- **Belastbar:** Die Rangliste ist über die Winter stabil, der Score misst die Station. Die chronischen Stationen hängen
  kaum von der Hausgröße ab. Der bekannte Fall 68956351 wird richtig erkannt, sowohl der Fehler (Rang 1) als auch die
  Reparatur (Rang 40, Steigung −0,11 auf 1,27).
- **Schwach:** Die Fallzahlen sind sehr klein (4 chronische mit Befund, 41 gegen 29 Stationen), und viele Tests stehen
  nebeneinander. Die Begehungen wurden nicht zufällig ausgewählt und liegen fast alle im Herbst 2024. Die Streuung ist
  nur bedingt aussagekräftig. Weil nur der Kernwinter zählt, fehlt der Nachtdurchfluss im Sommer, in den Notebooks 25
  bis 29 das stärkste Merkmal für ein offenes Ventil.
- **Gesetzt, nicht hergeleitet:** schlechtestes Zehntel, mindestens 2 Kennzahlen, 2 Winter für chronisch, 300
  Betriebsstunden, 20 Stationen je Winter, Leistungsklassen 5 und 10 kW, 7 Tage Puffer um Begehungen.
- **Offen:** die 4 chronischen, nie begangenen Stationen begehen. Bei 72135442, 80912173 und 68956359 die Notizen und
  Einstellungen der Begehung prüfen. Eine Sommerkennzahl ergänzen. Für die Regelhysterese Minutenwerte oder Daten des
  Reglers mit Stellsignal anfragen.

## Ausgaben

Das Notebook schreibt keine Dateien. Stationsblätter und `status.csv` für alle Stationen entstehen mit
`python -m src.stationsblatt` oder als Teil von `python -m src.aktualisieren` unter `outputs/stationsblatt/`.
