# Prüfung nach vorn

Alle Zahlen der Modelle sind rückblickend geprüft, an Begehungen, die es schon gab. Diese Begehungen waren nicht
zufällig ausgewählt, und die Modelle wurden gebaut, nachdem ihre Ergebnisse bekannt waren. Wie stark das die Zahlen
schönen kann, hat der Schritt vom ersten Prüfstand zum strengen Vergleich gezeigt (0,89 auf 0,84 beim Ventil, siehe
[Modellvergleich](modellvergleich.md#was-zuerst-nicht-stimmte)). Der nächste Schritt ist deshalb ein Test nach vorn: erst vorhersagen,
dann begehen.

## Vorschlag für den Test

1. **Vorher festlegen und aufschreiben,** welche Stationen begangen werden, was erwartet wird und wie gezählt wird.
   Danach wird nichts mehr geändert.
2. **Zwei Gruppen:** die nie begangenen Stationen mit dem höchsten Ventil-Score und gleich viele zufällig gewählte aus
   den übrigen Stationen. Das Team vor Ort weiß nicht, welche Station aus welcher Gruppe kommt.
3. **Erwartung:** In der Gruppe mit hohem Ventil-Score haben mehr Stationen einen Ventilbefund als in der zufälligen
   Gruppe. In Notebook 35 hatten unter den ersten 10 nach Ventil-Score 7 einen Ventilbefund, Zufall wären etwa 2
   gewesen.
4. **Protokoll** wie im [Probebetrieb](ausblick_probebetrieb.md): ob etwas kaputt war, was gemacht wurde und an
   welchem Tag.
5. **Auswertung:** der Anteil der Ventilbefunde in beiden Gruppen, verglichen mit einem exakten Test und mit der
   Richtung, die vorher festgelegt ist. Genauso für die Hinweise auf Dämmung und Kapazität.

Festlegen und Auswerten der Stichprobe übernehmen die Befehle `python -m src.betrieb pruefung-planen` und
`python -m src.betrieb pruefung-auswerten` (siehe [Betrieb bei der ÜZ](installation/betrieb.md#4-prufung-nach-vorn)).

Mit den Stationen, die die ÜZ in einer Saison begehen kann, bleibt auch dieser Test grob. Er misst aber zum ersten Mal,
was die Liste im Betrieb bringt, ohne dass die Modelle die Antworten kennen.

## Erfolgskontrolle mit den Wächtern

Nach jeder Begehung lässt sich zusätzlich prüfen, ob der Wächter eine Veränderung bemerkt. Das Monitoring-Modell hat in
Notebook 35 18 von 43 Begehungen als „besser“ bemerkt, an Vergleichsstationen waren es 24 %. Im Probebetrieb wird
seine Referenz vorher neu gelernt, sonst steht ein Teil seiner Konten am Deckel. Ob es dann mehr Begehungen bemerkt,
ist eine eigene Frage für den Test.
