# Erkenntnisse

Diese Seite sammelt, was das Projekt über die Daten und die Verfahren gelernt hat, geordnet nach den Teilen. Jede
Erkenntnis verweist auf die Stelle, an der sie entstanden ist.

## Daten

**1. Die Rohdaten brauchten eine eigene Prüfung.** In den Exporten waren ODS-Werte 1000-fach zu groß, Zeitstempel um
Minuten versetzt und ein Dateiname falsch. Erst die Rückmeldung der ÜZ zeigte, dass 8 Zähler keine Hausstationen
sind, darunter zwei Temperaturfühler im Heizhaus (siehe [Rohdaten lesbar machen](../aufbereitung/rohdaten.md) und
[Rückmeldung der ÜZ](../aufbereitung/uez_rueckmeldung.md)).

**2. Tageswerte gehören aus den Zählerständen.** Die Stundenwerte sind Momentaufnahmen. Eine Tagessumme daraus liegt
im Winter um bis zu ±30 % daneben, der Stand des Zählers um Mitternacht dagegen stimmt (siehe
[Zählerdaten](../datengrundlage/zaehlerdaten.md#stundenwerte-sind-momentaufnahmen)).

**3. Viele Daten ersetzen keine Labels.** Auf dem Papier sind es 93 Stationen und rund 1,7 Millionen gemessene
Stunden. Für die Frage, welche Auffälligkeit ein Fehler ist, fehlen aber Befunde mit Datum und klarer Fehlerart (siehe
[Datenanalyse](../ergebnisse/datenanalyse.md#fazit-zu-den-daten)).

## Begehungen

**1. Erst die Kontrollgruppe macht eine Wirkung belastbar.** Allein betrachtet sinkt der Rücklauf nach der Begehung
um 1,2 K, nicht gesichert. Gegen Stationen ohne Begehung im selben Winter sind es −2,0 K (p ≈ 0,008) (siehe
[Wintervergleich](../begehungen/wintervergleich.md#kontrollgruppe-und-diff-in-diff)).

**2. Nur gleiche Jahreszeiten vergleichen.** Ein Vorher-Nachher-Vergleich ohne gleiche Jahreszeit kann das Ergebnis
umdrehen: Naiv verbessern sich die Stationen ohne Begehung, im reinen Winterschnitt die begangenen (siehe
[Stationsbilder, Fallsammlung](../stationsbilder/index.md#am-rand-die-fallsammlung-notebook-15)).

**3. Die Folie der ÜZ hält nur in der Richtung.** Die Stationen setzen nach der Begehung mehr Energie je m³ um, aber
je nach Rechnung 4 bis 9 % statt 13,4 % (siehe [Performance](../begehungen/performance.md#einordnung)).

## Clustering

**1. Keine Stationstypen, aber jede Station prägt ihre Tage.** Die Stationen gehen fließend ineinander über. Die Tage
einer Station landen aber deutlich häufiger im selben Cluster als bei Zufall. Der Blick auf die einzelne Station
lohnt mehr als der auf Gruppen (siehe [Merkmale und Clustering](../clustering/index.md#gesamtbild)).

**2. Auf allen Ebenen zeigt sich dasselbe Muster.** Viel Wasser, kaum Abkühlung, hoher Rücklauf, auch nachts: bei den
Stunden als Kurzschlussverdacht, bei den Tagen als Dauerdurchfluss, bei den Stationen abgeschwächt als eigene Gruppe
(siehe [Merkmale und Clustering](../clustering/index.md#gesamtbild) und
[Datenanalyse](../ergebnisse/datenanalyse.md#dauerhafter-durchfluss)).

## Stationsbilder

**1. Die Station mit sich selbst vergleichen.** Der Kennlinienmonitor fand den Ventilfall 68956351 ohne Label und
traf mechanische Eingriffe häufiger als der Zufall (10 von 19, erwartet 5,6). Daran knüpft das Monitoring an (siehe
[Stationsbilder](../stationsbilder/index.md#3-die-station-mit-sich-selbst-vergleichen-notebook-13)).

**2. Die Aussage der Folie zur Regelung kehrt sich um.** Das Teilnetz ist überwiegend durchflussgeregelt, und
Stationen, die über die Spreizung regeln, arbeiten schlechter (siehe
[Stationsbilder](../stationsbilder/index.md#1-lasst-sich-die-folie-der-uz-nachbauen-notebook-11)).

## Monitoring

**1. Zustand und Veränderung sind zwei verschiedene Fragen.** Der Netzvergleich zeigt, wie gut eine Station läuft,
der Tagesmonitor, ob sie sich verändert. Beide hängen nicht zusammen und ergänzen sich. Dauerhaft schlechte Stationen
findet nur der Netzvergleich (siehe [Anomalien und Monitoring](../monitoring/index.md#gesamtbild)).

**2. Die Wächter taugen zur Erfolgskontrolle, nicht zur Frühwarnung.** Die Treffer um die Begehung kommen fast nur aus
Besserungsalarmen. Vorher gibt es nicht mehr Verschlechterungen als bei Stationen ohne Begehung (siehe
[Alarme bewerten](../monitoring/alarme.md#einordnung)).

**3. Der Rücklauf trägt das Signal.** Nur die Detektoren auf dem Rücklauf bestehen die Prüfung an den Begehungen, und
der rohe Tagesmedian leistet dasselbe (siehe [Anomalieerkennung](../monitoring/anomalie.md#einordnung)).

## Netz

**1. Das Netz erklärt die Auffälligkeiten nicht.** Auffällige Stationen häufen sich weder im Leitungsgraphen noch
über die Luftlinie, und das GNN gewinnt durch das Netz nichts Messbares (siehe
[Vergleichsgruppen und Nachbarn](../monitoring/nachbarn.md#einordnung),
[Netzereignisse](../monitoring/netzereignisse.md#einordnung) und
[GNN: Hilft das Netz?](../nicht_getragen/gnn.md#warum-das-netz-nichts-gebracht-hat)).

**2. Der Vorlauf bestätigt den Erzeuger.** Entlang des Rohrbaums ab dem Erzeuger hat das Haus weiter oben bei 36 von 38
Paaren den wärmeren Vorlauf (siehe [Rohrbaum](../netz_einbeziehen/rohrbaum.md) und
[Qualität](../datengrundlage/qualitaet.md#netz-und-zuordnung)).

## Lernende Modelle und Modellvergleich

**1. Ohne Erwartung findet ein Modell keinen Fehler, nur Seltenes.** Die erste Pipeline suchte ohne Labels nach
ungewöhnlichen Stunden und kam gegen „Maßnahme ja oder nein“ auf eine AUC von 0,49 bis 0,53. Getragen hat erst der
Vergleich jeder Station mit ihrem eigenen Normalverhalten: mit der Kennlinie im Monitoring-Modell und mit der
Vorhersage im Prognose-LSTM (siehe [Was nicht getragen hat](../nicht_getragen/index.md)).

**2. Erst ein strenger Prüfstand zeigt, was ein Modell kann.** Im ersten Prüfstand (Notebook 34) kam die Regression
auf Kennzahlen und LSTM-Zahlen beim Ventil auf eine AUC von 0,89. Dort hatte der Encoder die Teststationen gesehen,
und die Schwellen kamen aus den Testfällen. Im strengen Vergleich (Notebook 35), mit Modellwahl nur im Lernteil,
bleiben für das LSTM-Modell 0,84 (siehe [Modellvergleich](../vergleich/modellvergleich.md#was-zuerst-nicht-stimmte)).

**3. Eine einfache Regel ist oft gleich gut.** Beim Ventil liegt das LSTM-Modell mit 0,84 gleichauf mit der
Sommernacht-Regel (0,85). Bei der Kapazität ist die Regel mit 0,76 klar besser als jedes gelernte Modell (höchstens
0,53). Bei Gleichstand ist die erklärbare Regel gewählt, im Dashboard dient sie als Begründung.

**4. Das LSTM lohnt sich dort, wo Regeln fehlen.** An warmen Tagen rechnet nur das Prognose-LSTM: Es findet
eingebaute Dauerdurchflüsse von 150 l/h bei höchstens 5 % Fehlalarmen zu 78 %, das Wochenmittel zu 45 %. Bei der
Dämmung findet nur das LSTM-Modell ein Muster (0,78 gegen 0,61 für die beste Einzelregel, nicht gesichert). Und unter
den ersten 10 nach seinem Ventil-Score hatten 7 einen Ventilbefund, nach der Priorität des Monitoring-Modells 5
(Notebook 35, Test E).

**5. Überwachung braucht eine feste Referenz.** An echten Begehungen bemerkt das Normalverhaltensmodell aus
Notebook 18 bei gleich vielen Alarmen 30 von 43, das Prognose-LSTM 16 (Notebook 30, McNemar p = 0,001). Das
Prognose-LSTM sieht die letzten 7 Tage und gewöhnt sich an eine bleibende Veränderung. Dass es an der Referenz liegt
und nicht am Modelltyp, zeigt Notebook 35: Ein LSTM, das gegen eine feste Referenz prüft, findet einen eingebauten
Rücklauf +5 K praktisch so oft wie die Kennlinie des Monitoring-Modells (46 % gegen 47 %).

**6. Merkmale und Labels begrenzen mehr als das Verfahren.** XGBoost und Random Forest sind nirgends besser als die
logistische Regression oder die Regel (Notebook 29). Der Gewinn steckt in den Merkmalen: im Fingerabdruck bei Ventil
und Dämmung, in der richtig bezogenen Auslastung bei der Kapazität. Mit 11 Ventilfällen ist ein größeres Modell nicht
besser, sondern unruhiger.

**7. Nur der Ventiltausch hinterlässt eine Spur.** Nach dem Ventiltausch ändert sich der Durchfluss in Sommernächten
messbar (AUC 0,81, nach Holm gesichert). Nach Dämmung, Filterreinigung oder neu eingestelltem Durchfluss bleibt die
Station in den Zählerdaten gleich (Notebook 36). Sollwert (62 % der Begehungen) und Filter (47 %) sind eher Routine
als gefundene Fehler. Hier helfen bessere Begehungsprotokolle mehr als bessere Modelle: festhalten, ob etwas kaputt
war, nicht nur, was gemacht wurde.
