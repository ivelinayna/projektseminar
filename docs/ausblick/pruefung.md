# Prüfung nach vorn

Alle Zahlen der Modelle sind rückblickend geprüft, an Begehungen, die es schon gab. Diese Begehungen waren nicht
zufällig ausgewählt, und die Modelle wurden gebaut, nachdem ihre Ergebnisse bekannt waren. Wie stark das die Zahlen
schönen kann, hat der Schritt vom ersten Prüfstand zum strengen Vergleich gezeigt (0,89 auf 0,84 beim Ventil, siehe
[Modellvergleich](../vergleich/modellvergleich.md#was-zuerst-nicht-stimmte)). Der nächste Schritt ist deshalb ein Test nach vorn: erst vorhersagen,
dann begehen.

## Vorschlag für den Test

1. **Vorher festlegen und aufschreiben,** welche Stationen begangen werden, was erwartet wird und wie gezählt wird.
   Danach wird nichts mehr geändert.
2. **Zwei Gruppen:** die nie begangenen Stationen mit dem höchsten Ventil-Score und gleich viele zufällig gewählte aus
   den übrigen Stationen. Das Team vor Ort weiß nicht, welche Station aus welcher Gruppe kommt.
3. **Erwartung:** In der Gruppe mit hohem Ventil-Score haben mehr Stationen einen Ventilbefund als in der zufälligen
   Gruppe. In Notebook 35 hatten unter den ersten 10 nach Ventil-Score 7 einen Ventilbefund, Zufall wären etwa 2
   gewesen.
4. **Protokoll** wie im [Probebetrieb](probebetrieb.md): ob etwas kaputt war, was gemacht wurde und an
   welchem Tag.
5. **Auswertung:** der Anteil der Ventilbefunde in beiden Gruppen, verglichen mit einem exakten Test und mit der
   Richtung, die vorher festgelegt ist. Genauso für die Hinweise auf Dämmung und Kapazität.

**Wie groß die Stichprobe sein sollte.** Bei kleinen Gruppen findet der Test einen echten Unterschied oft nicht. Die
Tabelle zeigt die Teststärke, also die Wahrscheinlichkeit, dass ein einseitiger exakter Test nach Fisher einen
Unterschied bei p < 0,05 erkennt (Simulation mit je 2.000 Läufen):

| Stationen je Gruppe | Ventilbefund 70 % gegen 20 % | 50 % gegen 20 % | 40 % gegen 20 % |
|---|---|---|---|
| 10 | 63 % | 25 % | 13 % |
| 15 | 81 % | 37 % | 19 % |
| 21 | 93 % | 51 % | 29 % |

- 70 % gegen 20 % entspricht dem Ergebnis aus Notebook 35 (7 von 10 gegen etwa 2 bei Zufall). Nach vorn geprüft
  fallen solche Zahlen meist kleiner aus als rückblickend.
- Mit 15 Stationen je Gruppe, also 30 Begehungen, ist der Test deutlich aussagekräftiger als mit 10. Im Stand vom
  November 2026 gibt es 42 nie begangene Stationen mit Ventil-Score, also höchstens 21 je Gruppe.
- Ein Ergebnis über p = 0,05 heißt bei diesen Gruppengrößen nicht, dass die Liste nichts taugt, sondern dass die Fälle
  für eine Aussage nicht reichen.

Mit den Stationen, die die ÜZ in einer Saison begehen kann, bleibt auch dieser Test grob. Er misst aber zum ersten Mal,
was die Liste im Betrieb bringt, ohne dass die Modelle die Antworten kennen.

## Erfolgskontrolle mit den Wächtern

Nach jeder Begehung lässt sich zusätzlich prüfen, ob der Wächter eine Veränderung bemerkt. Das Monitoring-Modell hat in
Notebook 35 18 von 43 Begehungen als „besser“ bemerkt, an Vergleichsstationen waren es 24 %. Im Probebetrieb wird
seine Referenz vorher neu gelernt, sonst steht ein Teil seiner Konten am Deckel. Ob es dann mehr Begehungen bemerkt,
ist eine eigene Frage für den Test.
