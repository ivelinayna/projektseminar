# Was nicht getragen hat

Nicht jeder Ansatz hat getragen. Hier steht je Ansatz kurz die Idee, das Ergebnis und warum er nicht weiterverfolgt
wurde.

## Lernende Modelle und Modellvergleich

**Unüberwachte Anomaliescores (Gesamtpipeline, August).** Die erste Pipeline suchte ohne Labels nach ungewöhnlichen
Stunden: Isolation Forest, LOF, PCA und Abstand zu K-Means-Clustern. Gegen das Ersatzlabel „Maßnahme ja oder nein“
lag die AUC bei 0,49 bis 0,53, von 10 Ereignissen wurden höchstens 2 gefunden. „Ungewöhnlich“ ist nicht „defekt“:
Ohne Erwartung, was für diese Station bei diesem Wetter normal ist, findet ein Score nur seltene Betriebszustände.
Daraus folgten die Labels je Fehlerart und die Wächter, die jede Station mit sich selbst vergleichen. Das Notebook ist
nicht mehr im Abgabestand: Es nutzte eine eigene Datenaufbereitung mit 78 statt 93 Stationen, seine Zahlen passen
deshalb nicht zu den übrigen Notebooks. Es liegt im Verlauf des Repositorys (Commit `1b5798b`), seine Zahlen stehen
auch in Notebook 38.

**Regelparameter optimieren (Notebook 28).** K-Means teilt die Stationen nach ihrem Regelverhalten im Winter in
„Optimum“ (70) und „schlechter“ (18), mit einer Silhouette von 0,44. Die Gegenprobe gegen die Ventilbefunde
(p = 0,021) hält nach der Holm-Korrektur nicht (0,13). Die Klasse „Regelparameter optimieren“, die darauf aufbaut,
trifft in Notebook 39 keinen Befund. Das Dashboard empfiehlt sie deshalb nicht (siehe
[Fehlerart und Klasse je Station](modelle/klassen.md)).

**XGBoost und Random Forest (Notebook 31).** Baum-Modelle mit Wechselwirkungen sind nirgends besser als die
logistische Regression oder die Regel. Wechselwirkungen bringen −0,03 bis +0,05. Bei der Dämmung schwankt XGBoost je
nach Startwert zwischen 0,74 und 0,87, und die wichtigsten Merkmale wechseln von Durchgang zu Durchgang. Bei gut 50
Stationen ist ein Modell mit vielen Bäumen zu unruhig.

**Ein LSTM direkt auf die Befunde.** Selbst das kleine Netz der Vorversuche hat 283.856 Gewichte, beim Ventil gibt es
11 Fälle. Ein Netz, das direkt auf die Befunde lernt, würde jede Station auswendig lernen. Deshalb lernt das LSTM ohne
Labels, und erst eine logistische Regression sieht die Befunde (siehe [LSTM-Fingerabdruck](modelle/lstm.md)).

**Prognose-LSTM an echten Begehungen (Notebook 32).** An eingerechneten Fehlern findet das Prognose-LSTM plötzliche
Veränderungen gut. An echten Begehungen bemerkt es aber nicht mehr als an Vergleichsstationen: 16 von 43 gegen 32 %
(p = 0,26). Das Normalverhaltensmodell aus Notebook 20 bemerkt 30 von 43, Fall für Fall 15 zu 1 (McNemar p = 0,001).
Ein möglicher Grund: Das LSTM bekommt die letzten 7 Tage als Eingang, eine bleibende Veränderung wird so schnell Teil
seiner Erwartung. Das Prognose-LSTM bleibt deshalb auf die warmen Tage und plötzliche Fehler beschränkt.

**Ein einfacher Wächter ohne Netz (Notebook 30).** Das 7-Tage-Mittel als Erwartung mit einer festen Grenze von 5
Streuungen bemerkt an den Begehungen vor allem den Eingriff des Technikers: 12 seiner 16 Treffer liegen am
Begehungstag oder am Tag danach, die bleibende Veränderung danach sieht er nicht. An einen echten Schaden gewöhnt er sich nach einer Woche.

**Varianten der Netze (Notebook 29 und 30).** Nicht gewählt wurden: ein Autoencoder, der den Tag nur nachbildet
(erkennt Stationen schlechter wieder), Lernen auf allen statt nur auf begangenen Stationen beim Fingerabdruck
(Vorgabe der Betreuung, der Unterschied ist klein), ein Engpass von 16 statt 8 Zahlen (bei den Befunden nicht besser)
und das Vorhersagen der Abweichung vom 7-Tage-Mittel (nur im Test knapp vorn).

**Erster Prüfstand zu optimistisch (Notebook 38).** Der erste Vergleich aller Modelle ergab beim Ventil 0,89 für die
Regression auf Kennzahlen und LSTM-Zahlen. Der Encoder hatte dort aber die Teststationen gesehen, die Schwellen kamen
von den Testfällen, und die Auslastung zum Anschlusswert war als Merkmal dabei. Notebook 39 hat alles neu und streng
gerechnet, mit 0,84 als Ergebnis (siehe [Erster Prüfstand](vergleich/pruefstand.md)).

**Das Leitungsnetz als Merkmal (Notebook 38).** Nachbar-Alarme abziehen, den Netzmedian abziehen oder Merkmale der
Nachbarn dazunehmen verbessert weder Alarm noch Erkennung. Den Netzmedian abzuziehen macht den Tagesmonitor sogar
schlechter (25 statt 33 von 43), weil die Begehungen als Welle kamen und der Abzug ihre Wirkung herausnimmt.

**Fehlerarten ohne Spur (Notebook 41).** Neue Kennzahlen aus der Physik, mit vorher festgelegter Richtung, finden
bei Filter, Durchfluss und Sollwert nichts Gesichertes. Der Grund liegt vor dem Modell: Nur der Ventiltausch ändert
nachher messbar etwas (Durchfluss in Sommernächten, AUC 0,81, nach Holm gesichert). Nach Dämmung, Filterreinigung
oder neu eingestelltem Durchfluss bleibt die Station in den Zählerdaten gleich. Sollwert (62 % der Begehungen) und
Filter (47 %) sind eher Routine als gefundene Fehler. Hier würden bessere Begehungsprotokolle mehr helfen als bessere
Modelle. Bei der Dämmung gibt es einen ersten physikalischen Hinweis, die Abkühlrate im Stillstand (AUC 0,69, nicht
gesichert).
