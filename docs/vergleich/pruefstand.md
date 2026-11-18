# Erster Prüfstand

Im Projekt sind viele Modelle und Regeln entstanden, und fast jedes Notebook hat sich selbst geprüft: mit eigenem
Zeitraum, eigenen Stationen, eigener Kontrollgruppe und eigener Alarmmenge. So lassen sich die Ergebnisse nicht
vergleichen. Das Normalverhaltensmodell bemerkte in Notebook 20 70 % der Begehungen gegen 53 % bei
Kontrollstationen, das Prognose-LSTM in Notebook 30 11 bis 17 % gegen 13 %. Welcher Wächter besser ist, folgt daraus
nicht.

Notebook 32 und 38 schicken deshalb alle Kandidaten über denselben Prüfstand. Die Prüfungen stehen als Funktionen in
`src/pruefstand.py`, damit jeder Kandidat genau dieselbe Prüfung durchläuft. Die Zahlen auf dieser Seite sind der
erste Stand. Was daran zu optimistisch war, steht am Ende der Seite.

## Zwei Wächter unter gleichen Bedingungen

Notebook 32 vergleicht die beiden Wächter des Projekts: das Normalverhaltensmodell (Notebook 20) und das
Prognose-LSTM (Notebook 30).

- **Dieselbe Prüfung:** Das Prüfverfahren aus Notebook 20 ist als Funktion nachgebaut und Fall für Fall an dessen
  Zahlen kontrolliert (30 von 43, p = 0,017). Gezählt wird, ob eine begangene Station im Fenster von 7 Tagen vor bis 60 Tage
  nach der Begehung einen Alarm hat, und wie oft Kontrollstationen im selben Fenster alarmieren.
- **Dieselbe Grundlage:** 86 Stationen, Heiztage ab Juni 2024, 43 Begehungen.
- **Dieselbe Alarmmenge:** Die Schwelle des LSTM wird so gewählt, dass es etwa gleich viele Alarme gibt wie beim
  Normalverhaltensmodell. Wer öfter alarmiert, trifft sonst automatisch öfter.

| Prüfung | Normalverhaltensmodell | Prognose-LSTM |
|---|---|---|
| Begehungen bemerkt (−7 bis +60 Tage) | 30 von 43 (70 %) gegen 50 %, p = 0,008 | 16 von 43 (37 %) gegen 32 %, p = 0,26 |
| in den ersten 14 Tagen | 36 % gegen 22 %, p = 0,033 | 18 % gegen 17 % |
| Fall für Fall | 15 Begehungen nur hier bemerkt | 1 Begehung nur hier bemerkt (McNemar p = 0,001) |

Eine Begehung verschiebt den Betrieb im Median nur um etwa eine halbe Streuung. Ein CUSUM-Konto summiert solche
kleinen Verschiebungen auf, eine feste Schwelle an zwei Tagen sieht sie nicht. Der Unterschied kann also an der
Alarmregel liegen und nicht am Modell. Das prüft Notebook 38, indem es beides getrennt austauscht.

## Alle Modelle des Projekts

Notebook 38 erweitert den Vergleich auf jedes Modell des Projekts, das einen Tagesalarm oder einen Wert je Station
liefert, für die drei Aufgaben der Folie 5. Dafür gelten feste Regeln:

1. Der Prüfstein steht fest, bevor Ergebnisse vorliegen: Begehungen und eingerechnete Fehler für den Alarm, Befunde
   für die Fehlerart, Treffer der Klasse für das Unterteilen.
2. Regeln laufen mit. Eine Regel ist ein Modell ohne Lernen.
3. Alle Kandidaten bekommen dieselben Stationen und Tage, dieselbe Alarmmenge und nur Daten, die sie nicht gelernt
   haben.
4. Jede Zahl hat ein Unsicherheitsintervall, zwei Kandidaten werden gepaart verglichen, bei vielen Tests wird nach
   Holm korrigiert.
5. Bei Gleichstand gewinnt das Einfachere.

Ein Wächter besteht dabei aus zwei Bausteinen, die sich getrennt austauschen lassen: einer **Erwartung** (Kennlinie,
LSTM oder Wochenmittel) und einer **Alarmregel** (Schwelle an zwei Tagen oder CUSUM).

### Alarm

Gemeinsame Grundlage sind 79 Stationen mit 15.142 Heiztagen vom 01.06.2024 bis 09.06.2025, dieselben 43 Begehungen
und ein Budget von 204 Alarmen, so viele wie beim Normalverhaltensmodell. Geprüft werden 15 Wächter, die
Holm-Korrektur geht über alle 15. Eine Auswahl:

| Wächter (Erwartung + Regel) | bemerkt | Kontrolle | p | p nach Holm |
|---|---|---|---|---|
| Tagesmonitor (Kennlinie + CUSUM, Notebook 22) | 33 von 43 | 53 % | 0,001 | 0,017 |
| Normalverhaltensmodell (Notebook 20) | 30 von 43 | 50 % | 0,008 | 0,08 |
| Wochenmittel + Schwelle (ohne Lernen) | 24 von 43 | 36 % | 0,006 | 0,07 |
| Prognose-LSTM + CUSUM | 24 von 43 | 40 % | 0,022 | 0,20 |
| Kennlinienmonitor (Notebook 15) | 27 von 43 | 53 % | 0,14 | 0,94 |
| Prognose-LSTM + Schwelle (Notebook 30) | 16 von 43 | 32 % | 0,26 | 1 |
| Detektoren aus Notebook 18 | 6 bis 18 von 43 | – | ≥ 0,07 | ≥ 0,57 |

- Nach der Korrektur bleibt nur Kennlinie mit CUSUM gesichert.
- Die Alarmregel ist ein eigener Baustein: Dieselben z-Werte des LSTM bemerken mit CUSUM 24 statt 16 Begehungen.
- Dem LSTM fehlen zur Kennlinie trotzdem 6 bis 9 Fälle. Es nimmt die letzten 7 Tage als Eingang und übernimmt eine
  bleibende Veränderung nach einer Woche in seine Erwartung.

Plötzliche Fehler, eingerechnet in echte Stundenwerte aus dem Sommer 2024, bei höchstens 10 % Fehlalarmen in 8
Tagen:

| Erwartung + Regel | Bypass 150 l/h | Bypass 50 l/h | Fühler hängt | Sollwert +5 K |
|---|---|---|---|---|
| Prognose-LSTM + Schwelle | 84 % | 55 % | 43 % | 19 % |
| Prognose-LSTM + CUSUM | 81 % | 48 % | 36 % | 17 % |
| Wochenmittel + Schwelle | 78 % | 40 % | 17 % | 16 % |

Wächter, die aus Zählerständen rechnen, lassen sich so noch nicht prüfen. Notebook 38 verändert nur die
Stundenwerte, nicht die Energie- und Volumenzähler. Notebook 39 hält alle Spalten stimmig und prüft so auch das
Monitoring-Modell.

### Fehler erkennen

- **Ventil:** 27 Kandidaten laufen gepaart gegen die Sommernacht-Regel, mit Holm über alle 27. Vorn liegen die
  Regression auf Kennzahlen und LSTM-Zahlen (0,89 [0,78; 0,98]), der Sommer-Nachtdurchfluss (0,88) und die
  Schweregrad-Punkte aus Notebook 19 (0,87). Keiner ist gesichert besser als die Regel. Random Forest (0,77) und
  XGBoost (0,75) sind auch mit allen Merkmalen nicht besser, XGBoost ist gesichert schlechter. Flottenvergleiche wie
  Netzvergleich, Potenzial und K-Means liegen bei 0,67 bis 0,74. Sie messen „schlechter als andere“, und das ist nur
  zur Hälfte ein Ventil.
- **Dämmung:** Nur die Regression auf Kennzahlen und LSTM-Zahlen ist besser als Raten (0,75 [0,58; 0,89]).
  Flottenmaße zeigen die umgekehrte Richtung: Ein Dämmungsbefund kommt eher bei Stationen vor, die im Netz gut
  aussehen.
- **Überdimensionierung:** Die Auslastung zum alten Vertrag kommt auf 0,78, die erste Regel des Projekts mit dem
  Anschlusswert nur auf 0,51, weil der Anschlusswert oft schon der neue Vertrag ist.

### Monitoring-Modell gegen LSTM-Kette

Im Projekt gibt es zwei vollständige Systeme: das Monitoring-Modell (Kennlinie, Tagesmonitor, Netzvergleich,
Notebooks 15 und 21 bis 26) und die LSTM-Kette aus diesem Teil (Notebooks 27 bis 32). Kopf an Kopf, gepaart auf
denselben Fällen:

| Aufgabe | Monitoring-Modell | LSTM-Kette | besser |
|---|---|---|---|
| Begehungen bemerken | 33 von 43 | 16 von 43 (Schwelle), 24 von 43 (CUSUM) | Monitoring-Modell |
| plötzliche Fehler im Sommer | rechnet im Sommer nicht | Bypass 150 l/h zu 84 % | LSTM-Kette |
| Ventil erkennen (AUC) | Netzvergleich 0,73 | 0,89, Differenz +0,16 [+0,02; +0,31] | LSTM-Kette |
| Dämmung erkennen (AUC) | Netzvergleich 0,38 | 0,75 | LSTM-Kette |

Beim Alarm gewinnt das Monitoring-Modell, beim Erkennen die LSTM-Kette. Die beste Lösung kombiniert beide. So ist das
Endmodell in Notebook 39 gebaut.

### Haus oder Netz

Notebook 38 prüft auch, ob das Leitungsnetz hilft: Nachbar-Alarme abziehen, Netzmedian abziehen, Merkmale der
Nachbarn bis zwei Kanten. Keine Variante verbessert Alarm oder Erkennung. Offene Ventile häufen sich nicht in
Strängen, die Fehler sitzen im einzelnen Haus. Das Netz zählt nur als Ganzes, über Wetter, Vorlauf und
Begehungswellen, und das fangen Kennlinie und Tagesmonitor schon ab.

## Was an diesem Prüfstand zu optimistisch war

Bei der Nachprüfung fielen vier Schwächen auf:

- Der LSTM-Encoder war einmal auf allen begangenen Stationen gelernt, also auch auf den Teststationen.
- Die Parameter für das gleiche Alarmbudget wurden auf denselben Fällen gewählt, an denen gemessen wird.
- Die Auslastung zum Anschlusswert war als Merkmal dabei, obwohl der Anschlusswert oft schon der neue ist.
- Das beste Modell für die Fehlerart wurde nach den Testwerten gewählt.

Notebook 39 rechnet deshalb alles neu und strenger. Beim Ventil kommt es auf 0,84 statt 0,89 (siehe
[Strenger Vergleich und Entscheidung](endmodell.md)). Für Aussagen gelten die Zahlen aus Notebook 39. Die
Rollen der beiden Systeme bleiben gleich: das Monitoring-Modell für den Alarm in der Heizperiode, die LSTM-Kette für
die Fehlerart und die warmen Tage.
