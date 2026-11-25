# Was nicht getragen hat

Nicht jeder Ansatz hat getragen. Hier stehen die Ansätze aus den lernenden Modellen, dem Modellvergleich und den
weiteren Versuchen im Anhang, jeder in einem Satz. Ausführlich stehen sie auf den Seiten der Modelle, im
[Modellvergleich](../vergleich/modellvergleich.md) und unter [Negativbefunde im Detail](negativbefunde.md). Dort
stehen auch die Ansätze aus den übrigen Teilen des Projekts.

## Lernende Modelle

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Unüberwachte Anomaliescores (Gesamtpipeline) | früher 12 | „Ungewöhnlich“ ist nicht „defekt“. Die Rangfolgen lagen beim Zufall (AUC 0,49 bis 0,53), gefunden wurden höchstens 2 von 10 Ereignissen. | [Details](negativbefunde.md#nicht-mehr-im-abgabestand) |
| Klasse „Regelparameter optimieren“ (K-Means) | 26 | Die Gegenprobe beim Ventil hält nach Holm nicht, und in Notebook 35 trifft die Klasse keinen Befund. Das Dashboard empfiehlt sie deshalb nicht. | [Fehlerart und Klasse](../modelle/klassen.md#optimum-oder-schlechter-k-means) |
| XGBoost und Random Forest | 29 | Sie sind nirgends besser als die logistische Regression oder die Regel. Bei gut 50 Stationen sind sie zu unruhig. | [Fehlerart und Klasse](../modelle/klassen.md#ein-modell-je-fehlerart) |
| Ein LSTM direkt auf die Befunde | 27 | 283.856 Gewichte gegen 11 Ventilfälle: Das Netz würde jede Station auswendig lernen. Deshalb lernt es ohne Labels. | [LSTM-Fingerabdruck](../modelle/lstm.md#warum-ein-netz-das-vorhersagt) |
| Andere Varianten der Netze | 27, 28 | Keine ist verlässlich besser. Der Autoencoder erkennt Stationen schlechter wieder, 16 statt 8 Zahlen helfen bei den Befunden nicht, und die Abweichung vom 7-Tage-Mittel liegt nur im Test knapp vorn. | [LSTM-Fingerabdruck](../modelle/lstm.md#das-endgultige-netz), [Prognose-LSTM](../modelle/prognose.md#was-ein-lstm-bringt) |
| Einfacher Wächter ohne Netz | 28 | Er bemerkt an den Begehungen vor allem den Eingriff selbst, 12 seiner 16 Treffer liegen am Begehungstag oder am Tag danach. An einen Schaden gewöhnt er sich nach einer Woche. | [Prognose-LSTM](../modelle/prognose.md#ein-einfacher-wachter-ohne-netz) |
| Prognose-LSTM als Alarm an echten Begehungen | 30 | Es meldet an Begehungen nicht öfter als an Vergleichsstationen (16 von 43 gegen 32 %). Im Dashboard überwacht es deshalb nur die warmen Tage. | [Details](negativbefunde.md#18-wachtervergleich) |

## Modelle vergleichen

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Erster Prüfstand | 34 | Er war zu großzügig, unter anderem kannte der Encoder die Teststationen. Beim Ventil wurden aus 0,89 im strengen Vergleich 0,84. | [Modellvergleich](../vergleich/modellvergleich.md#was-zuerst-nicht-stimmte) |
| Leitungsnetz als Merkmal | 34 | Nachbarn oder Netzmedian verbessern weder Alarm noch Erkennung. Den Netzmedian abzuziehen kostet den Tagesmonitor sogar Treffer, 25 statt 33 von 43. | [Modellvergleich](../vergleich/modellvergleich.md#haus-oder-netz) |
| Filter, Durchfluss und Sollwert erkennen | 29, 36 | Nach diesen Maßnahmen ändert sich in den Zählerdaten nichts Messbares. Sollwert und Filter sind eher Routine als gefundene Fehler. | [Details](negativbefunde.md#19-fehlerarten-ohne-messspur) |

## Weitere Versuche im Anhang

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Bayes-Diagnose | 38 | Nur das Ventil hat eine klare Spur. Die Fehler-Symptom-Matrix ist von Hand gefüllt und nicht mit der ÜZ abgestimmt. | [Bayes-Diagnose](bayes.md) |
| Graphenmodell auf dem Netz (GNN) | 39 | Dasselbe Modell ohne Kanten ist praktisch gleich gut, je Station bringt das Netz nichts Signifikantes. | [GNN](gnn.md) |
