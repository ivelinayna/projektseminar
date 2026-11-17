# Prüfung und Statistik

Mit 53 begangenen Stationen, davon 11 mit Ventil- und 9 mit Vertragsbefund, entscheidet die Prüfung
mehr über die Aussagekraft als das Modell. Dieses Kapitel beschreibt, wie geprüft wurde und warum so.
Gerechnet wird in den Notebooks 27, 29 bis 32, 38 und 39, die Prüfwerkzeuge stehen in
`src/pruefstand.py` und `src/finalvergleich.py`.

## Was gemessen wird

**Fehlerart: AUC statt Accuracy oder F1.** Beim Ventil haben 20 % der Stationen einen Befund. Wer immer
„kein Befund“ sagt, liegt zu 80 % richtig und findet keinen einzigen Fall. Accuracy und F1 hängen
außerdem an einer gewählten Grenze und an der Basisrate. Die AUC bewertet einen Score über alle Grenzen
zugleich: Sie ist die Wahrscheinlichkeit, dass von zwei Stationen, eine mit und eine ohne Befund, die mit
Befund den höheren Score hat. 0,5 ist Raten, 1 ist perfekt. So sind Fehlerarten mit 9 und mit 36 Fällen
vergleichbar.

Für den Betrieb zählt zusätzlich, wie viele Verdachtsfälle echt waren:

- **Precision an fester Grenze:** Verdacht ab einer Wahrscheinlichkeit von 0,5. Die Grenze steht vorher
  fest und wird nicht nach den Testwerten verschoben.
- **Precision@10:** Wie viele der zehn am höchsten eingestuften Stationen hatten wirklich einen Befund?
  Das beantwortet die praktische Frage, wenn das Team nur zehn Stationen begehen kann.

**Alarm: Trefferquote bei gegebener Fehlalarmquote.** Ein Wächter, der öfter alarmiert, trifft
automatisch öfter. Verglichen wird deshalb immer bei gleicher Alarmmenge: an eingerechneten Fehlern die
Trefferquote bei höchstens 5 % oder 10 % Fehlalarmen, an echten Begehungen der Anteil gemeldeter
Begehungen gegen den Anteil bei Vergleichsstationen im selben Zeitraum.

## Wie aufgeteilt wird

**Fehlerart: nach Stationen, verschachtelt.** Das Label gehört zur Station, und die Tage einer Station
hängen eng zusammen. Wer zufällig nach Tagen aufteilt, prüft eine Station mit ihren eigenen Nachbartagen.
Deshalb wird nach Stationen getrennt:

- **Außen:** fünf Teile über ganze Stationen (`StratifiedGroupKFold`, Seed 42). Jede Station ist genau
  einmal Teststation. Ein Zählertausch am selben Ort bleibt in einem Teil. Die Teile sind so gemischt,
  dass in jedem zwei bis drei Ventilfälle liegen.
- **Innen:** Auf den Lernstationen eines Teils wählt eine zweite, vierfache Kreuzvalidierung die
  Einstellungen des Modells: die Regularisierung `C` der logistischen Regression aus 0,03, 0,1, 0,3 und
  1,0, bei XGBoost Tiefe 1 bis 3 und 100 oder 300 Bäume. In Notebook 39 wählt sie auch, welcher
  Kandidat gewinnt.
- **LSTM-Encoder je Teil neu:** In Notebook 39 wird der Fingerabdruck für jeden der fünf Teile ohne die
  Teststationen neu gelernt. Die Teststation beeinflusst also weder das Netz noch die Regression noch die
  Auswahl.
- In den früheren Notebooks 27 bis 31 wird mit Leave-one-out geprüft, also jede Station einmal
  ausgelassen, und zusätzlich mit ganzen Straßen ausgelassen. Die Ergebnisse ändern sich dabei kaum.

**Wächter: nach der Zeit.** Ein Wächter wird im Betrieb immer auf die Zukunft angewendet. In Notebook
39 gilt eine gemeinsame Zeitachse für alle Wächter:

| Abschnitt | Zeitraum | wofür |
|---|---|---|
| Lernen | bis 31.01.2024 | Kennlinien und Gewichte der Netze |
| Kalibrieren | 08.02. bis 31.03.2024 | normale Schwankung je Station |
| Alarmlast einstellen | April und Mai 2024 | Schwelle jedes Wächters |
| Test | ab 08.06.2024 | alle Begehungen, eingerechnete Fehler |

Die 7 Tage Abstand sind das Eingabefenster des Prognose-LSTM. So teilen Lernen und Test keinen
Rohdatentag. In den Vorversuchen (Notebook 29 und 30) lag die Validierung noch in ganzen
Kalenderwochen zwischen den Trainingswochen. Das hat sich als zu leicht erwiesen: Das Netz kennt die
Woche davor und danach und muss nur eine Lücke füllen. Deshalb liegt die Probezeit in Notebook 39
zeitlich nach dem Lernen.

## Gleiche Bedingungen für alle

- **Gleiche Daten:** Alle Modelle lernen aus denselben Stundenreihen aus Notebook 00, auf denselben
  Stationen und Tagen.
- **Gleiche Alarmlast:** Das Monitoring-Modell behält seine Einstellung (CUSUM mit h = 5). Jeder andere
  Wächter bekommt so viele Alarme, wie es in der Einstellzeit gibt. Seine Schwelle wird dafür aus einem
  festen Raster gewählt, beim Prognose-LSTM ergibt das h = 10.
- **Einfache Gegner laufen mit:** das Mittel der letzten 7 Tage, die Sommernacht-Regel, die Auslastung
  zum alten Vertrag. Ein Modell muss sie schlagen, sonst lohnt es sich nicht.
- **Eingerechnete Fehler:** Echte Fehler haben nie einen bekannten Beginn. Deshalb werden Fehler mit
  bekanntem Beginn in echte Stundenwerte geschrieben, 30 Tage lang: Dauerdurchfluss von 50 oder
  150 l/h, Rücklauf plötzlich oder schleichend um 5 K höher, ein hängender Fühler. Alle Spalten bleiben
  stimmig, auch Energie- und Volumenzähler. So lässt sich auch das Monitoring-Modell prüfen, das aus
  Zählerständen rechnet.
- **Nur Daten vor der Begehung:** Merkmale für die Fehlerart kommen nur aus der Zeit vor der Begehung.
  Die Auslastung zum Anschlusswert bleibt draußen, weil der Anschlusswert bei 7 von 9 verkleinerten
  Verträgen schon der neue ist.

## Wie sicher ist ein Ergebnis?

| Verfahren | wofür | warum so |
|---|---|---|
| Bootstrap über Stationen, 2000 Ziehungen | 95-%-Intervall einer AUC oder Trefferquote | Die Station ist die unabhängige Einheit. Ziehen über Tage würde die Unsicherheit stark unterschätzen. |
| gepaarter Bootstrap | Unterschied zweier Modelle | In jeder Ziehung werden beide Modelle auf denselben Stationen bewertet. Schließt das Intervall der Differenz die 0 aus, gilt der Unterschied als gesichert. |
| Zufallstest (Permutation) | Ist eine AUC mehr als Zufall? | Labels werden gemischt, gezählt wird, wie oft der Zufall mindestens so gut ist. Bei Leave-one-out liegt der Zufall nicht bei 0,5, sondern darunter. |
| McNemar-Test | zwei Wächter Fall für Fall | Gezählt werden nur die Begehungen, bei denen genau einer der beiden meldet. |
| Binomial- und Fisher-Test | Alarmquote gegen Kontrollgruppe | Begehungen gegen nie begangene Stationen im selben Zeitraum |
| Holm-Korrektur | viele Tests auf einmal | Bei 15 Wächtern ist ein kleiner p-Wert leicht Zufall. Holm hebt die Schwelle schrittweise an. |

Bei 11 Ventilfällen ist das 95-%-Intervall einer AUC rund ±0,13 breit. Unterschiede zwischen Modellen
unter etwa 0,1 sind mit diesen Fallzahlen nicht zu sehen. „Nicht gesichert“ heißt deshalb meistens: Die
Daten reichen nicht, nicht: Es gibt keinen Unterschied.

## Training der Netze

**Gelernt wird auf den Fehler, mit Gradientenabstieg.** Beide LSTM sagen etwas vorher, den nächsten Tag
oder den heutigen Tag aus der Vorwoche. Der Fehler ist der mittlere quadratische Abstand zwischen
Vorhersage und Messung (MSE). Nach jedem Stapel von 512 Tagen wird mit Backpropagation durch die Zeit
berechnet, in welche Richtung jedes Gewicht den Fehler verringert. Der Optimierer Adam macht dann einen
kleinen Schritt in diese Richtung. Er ist eine Form des Gradientenabstiegs, die die Schrittweite für jedes
Gewicht selbst anpasst.

| | Fingerabdruck (Notebook 29) | Prognose-LSTM (Notebook 30) |
|---|---|---|
| Lernrate zu Beginn | 0,003 | 0,002 |
| Lernrate halbieren | nach 5 Runden ohne Besserung | nach 4 Runden ohne Besserung |
| Early Stopping | nach 20 Runden ohne Besserung | nach 15 Runden ohne Besserung |
| höchstens | 300 Runden | 200 Runden |

**Early Stopping nur auf der Validierung.** Nach jeder Runde wird der Fehler auf Tagen gemessen, die das
Netz nicht lernt. Der beste Stand wird gemerkt. Wird der Fehler eine feste Zahl von Runden lang nicht
besser, ist Schluss, und der beste Stand bleibt. Ohne diese Bremse lernt das Netz die Trainingstage
auswendig. Ein Vorversuch in Notebook 29 zeigt das: Der Validierungsfehler steigt dort wieder, während
der Trainingsfehler weiter fällt. Kein Testwert und kein Befund steuert das Training.

**Wiederholbar.** Alle Seeds sind fest. In den Vorversuchen und in Notebook 39 rechnet die
Grafikkarte zusätzlich deterministisch (`cudnn.deterministic`). Ein frischer Lauf der Netze aus Notebook
29 und 30 ohne gespeicherte Gewichte lieferte dieselben Zahlen wie die gespeicherte Fassung. Die
Gewichte werden unter `notebooks/models/` gespeichert und beim nächsten Lauf geladen.

## Warum keine Hyperparameter-Suche für die Netze

Gesucht wurde nur dort, wo es mit den Daten sauber geht: Die Regularisierung der Regression und Tiefe
und Baumzahl von XGBoost werden in der inneren Kreuzvalidierung gewählt. Für die Netze gibt es keine
Suche über Größe, Lernrate oder Fensterlänge nach den Befunden, aus drei Gründen:

- **Zu wenige Fälle.** Eine Suche nach der besten Variante an 11 Ventilfällen hieße, auf die Antworten zu
  schauen. Die gefundene Variante wäre zufällig die, die zu diesen 11 Stationen passt.
- **Die Netze lernen ohne Befunde.** Ihre Güte lässt sich ohne Labels messen: am Vorhersagefehler und
  bei Fingerabdruck an der Wiedererkennung einer Station im nächsten Winter. Daran wurden die Varianten
  in den Vorversuchen verglichen: Engpass mit 4, 8 oder 16 Zahlen, Vorhersage gegen Nachbilden des Tages,
  nur begangene gegen alle Stationen, 1 gegen 7 Tage Eingabe.
- **Die Unterschiede sind klein.** Zwischen 8 und 16 Zahlen im Engpass oder zwischen den Lernvarianten
  liegen bei der Fehlererkennung nur Hundertstel, weit innerhalb der Unsicherheit.

Die einzige Stellgröße, die beim Training selbst entschieden wird, ist der Zeitpunkt des Stopps, und der
hängt nur am Vorhersagefehler.

## Warum das Modell im Lernteil gewählt wird

Wer mehrere Modelle prüft und den Sieger nach den Testwerten nimmt, bekommt eine zu gute Zahl. Genau das
ist zuerst passiert: Die Regression auf Kennzahlen und LSTM-Zahlen war im Test die beste, mit einer
Ventil-AUC von 0,88. In Notebook 39, Abschnitt 19, wird die Wahl deshalb in den Lernteil verlegt: In
jedem der fünf Teile entscheidet nur die innere Prüfung, welcher Kandidat gewinnt, erst danach wird
getestet. So kommt die Fehlerart auf eine Ventil-AUC von 0,84 und eine Dämmungs-AUC von 0,78. Die 0,88
war um etwa 0,05 zu optimistisch und wird nicht behauptet.

In der inneren Prüfung lagen zwei Kandidaten gleichauf: die Regression nur auf den 16 LSTM-Zahlen und
die auf Kennzahlen und LSTM-Zahlen. Gewählt ist die Regression nur auf den LSTM-Zahlen, aus zwei Gründen.
Sie ist einfacher. Und sie vermeidet ein Leck über das Vorwissen: Die 12 Kennzahlen sind physikalisch
begründet, wurden aber festgelegt, als die Begehungsprotokolle und Fälle wie 68956351 schon bekannt
waren. Die 16 LSTM-Zahlen hat das Netz dagegen ohne Befund-Labels gelernt. Die Kennzahlen bleiben
trotzdem wichtig: Mit ihnen wird ein Verdacht im Hausfenster des Dashboards begründet.
