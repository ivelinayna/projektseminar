# Netzereignisse

**Notebook 24:** `notebooks/5_monitoring/24_netzereignisse.ipynb` · **Code:** `src/netzereignisse.py`, Nachbarn aus
`src/nachbarschaft.py`, Tests in `tests/test_netzereignisse.py` und `tests/test_nachbarschaft.py`

Der [Tagesmonitor](tagesmonitor.md) bewertet jede Station einzeln. Beginnen viele Alarme gleichzeitig, liegt die
Ursache eher außerhalb des Hauses: Kälte, Vorlauf oder eine Welle von Begehungen. Das Notebook fragt deshalb:

1. Gibt es Tage, an denen mehr Alarme beginnen als zufällig?
2. Alarmieren Nachbarn im Leitungsnetz gemeinsam?
3. Was folgt daraus für die Priorität, und welcher Status kommt auf die Netzkarte?

Grundlage sind die 491 Alarme des Tagesmonitors an 84 Stationen.

## Netzereignistage

- Als Zeitpunkt eines Alarms zählt der geschätzte Beginn der Änderung. Der CUSUM braucht im Median acht Tage bis zur
  Schwelle.
- Je Tag wird gezählt, wie viele Stationen im Fenster ±3 Tage einen Alarm beginnen.
- **Vergleich:** Die Alarme jeder Station werden 1.000-mal zufällig innerhalb ihrer Überwachungstage verschoben.
- **Netzereignis** = Tageswert über dem 95-%-Quantil des größten Tageswerts der Zufallsläufe. Das schützt gegen die
  vielen Tests auf einmal. Getrennt nach Richtung, zur Prüfung auch mit ±1 und ±7 Tagen.

In allen Varianten gibt es 7 bis 123 % mehr gleichzeitige Stationspaare als zufällig (p global höchstens 0,04). Mit
±3 Tagen ergeben sich drei Episoden:

| Richtung | Zeitraum | Stationen | Umstände |
|---|---|---|---|
| schlechter | 09. bis 12.12.2022 | 12 von 40 | Temperatursturz von 3,4 auf −3,7 °C, Vorlauf unverändert bei rund 74 °C, keine Begehungen |
| besser | 08. bis 14.09.2024 | 16 von 53 | Neustart von 52 der 53 Stationen nach der Sommerpause, 36 Begehungen im Umfeld |
| besser | 05. bis 07.11.2024 | 12 von 65 | Abkühlung, höherer Vorlauf (70,2 auf 72,4 °C) und 12 Begehungen zugleich |

- **Dezember 2022** passt zu einer Kennlinie, die schnelle Kälteeinbrüche nicht abfängt, weil sie das Tagesmittel
  desselben Tages nutzt und das Gebäude verzögert reagiert. Das ist ein Hinweis auf eine Schwäche des Modells, nicht
  auf Hausfehler.
- **September 2024** ist ein Artefakt des Neustarts nach dem Sommer, auch wenn viele Begehungen in die Zeit fallen.
- **November 2024** lässt sich nicht trennen.
- An den 54 Tagen mit mindestens 5 K Abkühlung binnen einer Woche beginnen gut doppelt so oft Verschlechterungen
  (8,3 % gegen 3,8 % der überwachten Stationen). Über alle Tage ist der Zusammenhang schwach (rho 0,05).

## Gleichzeitige Alarme bei Nachbarn

- Nachbarn wie in [Notebook 23](nachbarn.md) über den logischen Leitungsgraphen, bis eine, zwei oder drei Kanten.
- Gleichzeitig heißt: Alarme derselben Richtung, deren Beginn höchstens drei Tage auseinander liegt.
- Die Stationen werden 10.000-mal zufällig auf die Knoten verteilt. So misst der Test nur den Effekt der Nähe im Netz,
  nicht die netzweiten Ereignisse.

**Ergebnis:**

- **Verschlechterungen** kommen bei Nachbarn nicht häufiger gemeinsam vor als bei zufälligen Paaren (p 0,21 bis 0,48).
- **Verbesserungen** kommen bei Nachbarn etwas häufiger gleichzeitig (p 0,018 bis 0,035 bei allen drei Weiten). Viele
  dieser Paare beginnen am 11.09.2024, das passt zu gemeinsamen Begehungsterminen.
- Wie in Notebook 23 gibt es keinen Hinweis auf Probleme einzelner Stränge.

## Nachbarn über die Luftlinie

Mit den Koordinaten aus der Handliste `data/manual/adressen_koordinaten.ods` wird derselbe Test für Häuser im Umkreis
von 50, 100 und 200 m gerechnet.

- Gemeinsam auffällig werden nahe Häuser in keinem Radius und keinem Winter häufiger als zufällig (p 0,2 bis 1,0).
- Die Scores sehr naher Häuser hängen leicht zusammen: bei 50 m in allen drei Wintern positiv (rho 0,11 bis 0,32), bei
  100 m nicht mehr.
- Gleichzeitige Verschlechterungen sind in allen drei Radien etwas häufiger als zufällig (p 0,010 bis 0,036). Bei
  zwölf Tests sind einzelne kleine p-Werte Zufall, alle drei zeigen aber in dieselbe Richtung. Der Effekt bei 50 m passt
  eher zu ähnlichen Gebäuden als zu einem Fehler im Netz.

## Markierung je Alarm und Wirkung auf die Priorität

Jeder Alarm trägt jetzt zwei Markierungen:

- `netzereignis`: Der Alarm beginnt höchstens drei Tage neben einem Netzereignistag derselben Richtung. Das trifft 46
  der 491 Alarme, davon 13 Verschlechterungen.
- `nachbar_gleichzeitig`: Ein Nachbar bis zwei Kanten hat einen Alarm derselben Richtung, Beginn höchstens drei Tage
  daneben. Das trifft 66 Alarme.

Die Priorität aus [Notebook 21](alarme.md) bleibt. Zur Prüfung wird sie zusätzlich ohne die Verschlechterungen an
Netzereignistagen gerechnet:

- Alle 16 Stationswinter mit Priorität hoch bleiben hoch.
- Vier fallen von mittel auf niedrig. Alle vier sind im Netzvergleich unauffällig und haben nur einen
  Verschlechterungsalarm, der in eine Netzwelle fällt.

Der Nutzen liegt vor allem im Betrieb: Ein neuer Alarm an einem Netzereignistag wird zuerst gegen Wetter und Netz
geprüft, bevor jemand hinfährt.

## Einordnung

- **Belastbar:** Im Leitungsgraphen alarmieren Nachbarn bei Verschlechterungen nicht gemeinsam. Die Auffälligkeiten
  passen zu Ursachen an der einzelnen Station.
- **Schwach:** Der Graph hat keine Längen und Drücke. Die Schwelle ist streng, Wellen mit fünf oder sechs Stationen
  fallen darunter. Der Beginn eines Alarms ist nur geschätzt. Ob die gleichzeitigen Verschlechterungen naher Häuser an
  ähnlichen Gebäuden liegen, ist nicht geprüft.
- **Offen:** die Kennlinie mit geglätteter oder um einen Tag verzögerter Temperatur rechnen und prüfen, ob die Wellen
  kleiner werden.

## Ausgaben

| Datei | Inhalt |
|---|---|
| `outputs/monitor_status.csv` | je Station und Kernwinter Priorität, Netzwert, Rang, Fehlerbild, chronisch und Alarmzahlen |
| `outputs/monitor_alarme.csv` | alle Alarme mit den Markierungen `netzereignis` und `nachbar_gleichzeitig` |
| `outputs/netzereignistage.csv` | die Episoden mit Zeitraum und Umständen |

Nur Zählernummern, keine Adressen. Notebook 33 legt alle drei Dateien auf eine Kopie der Netzkarte aus Notebook 31.
