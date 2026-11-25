# Was nicht getragen hat

Nicht jeder Ansatz hat getragen. Die Tabellen nennen jeden in einem Satz, geordnet nach den Kapiteln des Vorgehens.
Ausführlich und mit allen Zahlen stehen sie unter [Negativbefunde im Detail](negativbefunde.md), die Ansätze der
lernenden Modelle auf deren Seiten und im [Modellvergleich](../vergleich/modellvergleich.md).

## Begehungen auswerten

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Lernen auf dem Label „Maßnahme ja/nein“ | 16, 25, 29 | Das Label ist bei 40 von 49 Stationen wahr und sagt nicht, welcher Fehler vorlag. Ein Klassifikator schlägt darauf die triviale Vorhersage nicht. | [Details](negativbefunde.md#1-uberwachtes-lernen-auf-begehungslabels) |
| Begehungstabelle als Label | 02, 03, 14, 25 | Reparaturen stehen teils nur im Freitext, und ein leeres Feld heißt nicht sicher „nein“. | [Details](negativbefunde.md#2-labelqualitat-der-begehungstabelle) |
| Wirkung der Begehung im Diff-in-Diff | 02 | Die Richtung passt, gesichert ist sie nicht. Das Ergebnis hängt an Fenster und Kontrollgruppe. | [Details](negativbefunde.md#6-begehungswirkung-im-diff-in-diff) |
| Vorjahresvergleich über ein ganzes Jahr | 04 | Ein volles Jahr nach der Begehung gibt es nur für 2 von 58 Begehungen. | [Details](negativbefunde.md#7-vorjahresvergleich-uber-ein-langes-fenster) |
| Flachere Kennlinie nach der Optimierung | 05 | Der Unterschied zeigt in die erwartete Richtung, ist aber nicht von null zu unterscheiden. | [Details](negativbefunde.md#8-flachere-kennlinie-nach-optimierung) |
| ARIMA für den Tagesrücklauf | 06 | Reines ARIMA ist schlechter als das 7-Tage-Mittel. Was hilft, ist die Außentemperatur, nicht das Zeitreihenmodell. | [Details](negativbefunde.md#9-arima-als-zeitreihenmodell) |

## Merkmale und Clustering

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Stationen clustern | 07, 08 | Kein Cluster trennt die Begehungen. Die Stationen bilden eher ein Kontinuum als Gruppen. | [Details](negativbefunde.md#4-stationsclustering) |
| Clustern je Leistungsklasse | 09 | Getrennt nach Klasse wird die Silhouette schlechter. Die Leistungsklasse bleibt nur Kontext. | [Details](negativbefunde.md#5-clustering-je-leistungsklasse) |

## Stationsbilder und Befunde

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Regelart und Kennlinie als Erfolgsmaß | 11, 12 | Weder die Modulationsart noch die Steigung der Kennlinie ändern sich durch die Begehung. | [Details](negativbefunde.md#10-modulationsart-und-kennlinienparameter-als-erfolgsma) |
| Kennlinienmonitor | 13 | Er trifft Begehungen kaum öfter als der Zufall und hält im Wächtervergleich nach Holm nicht. | [Details](negativbefunde.md#13-kennlinienmonitor) |

## Anomalien und Monitoring

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Feste Regeln mit den alten Schwellen | 16 | Mit den alten Schwellen treffen sie fast alle Stationen. Kalibriert sind sie bewertbar, aber nicht richtig. | [Details](negativbefunde.md#3-regel-baseline-mit-festen-schwellen) |
| Anomaliedetektoren | 16 | Isolation Forest, Zustandsanteil und Dynamikscore bestehen die Prüfung an den Begehungen nicht. | [Details](negativbefunde.md#11-anomaliedetektoren) |
| Restkategorie in der Musterzuordnung | 17 | In der ersten Fassung blieben 50 von 93 Stationen ohne Muster. Das lag an der Rechnung mit MAD, nicht an den Daten. | [Details](negativbefunde.md#12-restkategorie-in-der-musterzuordnung) |
| CUSUM als Frühwarnung | 20, 21 | Die Alarme kommen nach der Begehung, nicht davor. Er taugt zur Erfolgskontrolle, nicht zur Frühwarnung. | [Details](negativbefunde.md#14-cusum-als-fruhwarnung) |
| Bestwert und Lückenfüllung | 01, 19, 22 | Der Bestwert sagt keine Befunde vorher, und bei Lücken über einen Tag bleibt die Füllung ungenau. | [Details](negativbefunde.md#20-bestwert-und-luckenfullung) |
| Nachbarn und Netzereignisse | 23, 24 | Auffällige Stationen häufen sich im Netz nicht. Die Welle im Dezember 2022 folgt einem Kälteeinbruch. | [Details](negativbefunde.md#15-nachbarn-und-netzereignisse) |

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

## Netz einbeziehen

| Ansatz | Notebook | Warum er nicht getragen hat | mehr dazu |
|---|---|---|---|
| Lage der Häuser per Geocoding | 24, 31 | Der Dienst fand meist nur die Straße. Die Lage kommt jetzt aus einer Handliste. | [Details](negativbefunde.md#17-geocoding-und-netzgeometrie) |

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

Kleinere Versuche, die nur noch im Verlauf des Repositorys liegen, stehen am Ende der Detailseite unter
[Nicht mehr im Abgabestand](negativbefunde.md#nicht-mehr-im-abgabestand).
