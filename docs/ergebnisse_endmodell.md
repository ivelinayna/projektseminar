# Endmodell

Das Endmodell ist kein einzelnes Modell. Für jede Frage aus der Aufgabenstellung ist das Modell gewählt, das im
strengen Vergleich in Notebook 35 am besten abgeschnitten hat. Wo zwei Modelle gleichauf lagen, ist das einfachere und
erklärbare gewählt. Wie verglichen wurde, steht unter [Strenger Vergleich](vergleich/endmodell.md), die Prüfregeln
unter [Prüfdesign und Statistik](vergleich/pruefung.md).

Verglichen wurden die beiden fertigen Ansätze des Projekts:

- **Monitoring-Modell:** Kennlinie je Station mit CUSUM (Tagesmonitor), dazu Netzvergleich und Potenzial.
- **LSTM-Modell:** das [Prognose-LSTM](modelle/prognose.md) als Wächter und die
  [Fehlerklassen](modelle/klassen.md) aus dem [Fingerabdruck](modelle/lstm.md).

## Gewähltes Modell je Frage

| Frage | Modell | Ergebnis in Notebook 35 | Urteil |
|---|---|---|---|
| Veränderung in der Heizperiode, Erfolgskontrolle | Monitoring-Modell: Kennlinie + CUSUM, h = 5 | 18 von 43 Begehungen als „besser“ bemerkt, Kontrolle 24 %, p = 0,006 | Pilot mit Einschränkungen |
| Veränderung an warmen Tagen, plötzlicher Dauerdurchfluss | Prognose-LSTM + CUSUM, h = 10, auf allen Stationen gelernt | 78 % der Dauerdurchflüsse von 150 l/h bei höchstens 5 % Fehlalarmen, Wochenmittel 45 % | Pilot mit Einschränkungen |
| Regelventil tauschen | logistische Regression nur auf den 16 LSTM-Zahlen | AUC 0,84 mit Modellwahl im Lernteil, gleichauf mit der Sommernacht-Regel (0,85) | Pilot |
| Hinweis Dämmung | dasselbe Modell | AUC 0,78 mit Modellwahl im Lernteil, beste Einzelregel 0,61 | weitere Validierung nötig |
| Hinweis Kapazitätsanpassung | Regel „Spitzenlast zum alten Vertrag“ | AUC 0,76 [0,58; 0,93], 5 von 9 bei 1 Fehlalarm, gelernte Modelle höchstens 0,53 | Pilot mit Einschränkungen |
| Stationsleistung, Netzeffizienz | Monitoring-Modell: Netzvergleich je Kernwinter, Potenzial | Ventilfall 68956351 vor der Reparatur auf Rang 1 | Pilot, nur beschreibend |
| Regelungsoptimierung | keins | von keinem Modell getroffen | ungeeignet |
| Durchfluss, Sollwert, Filter als Ursache | keins | AUC 0,26 bis 0,57 | nicht erkennbar |
| Frühwarnung vor einem Fehler | keins | der Beginn ist bei keinem Befund bekannt | nicht prüfbar |

Die Werte in eckigen Klammern sind 95-%-Intervalle über Stationen. „Pilot“ heißt: brauchbar für den Probebetrieb,
nicht für eine Entscheidung ohne Prüfung vor Ort.

## Warum diese Wahl

**Überwachung.**

- In der Heizperiode bemerkt das Monitoring-Modell die Begehungen am deutlichsten. Das Prognose-LSTM liegt auf Höhe der
  Kontrolle (10 von 43 gegen 26 %).
- An eingebauten Fehlern im Winter liegt das Monitoring-Modell vorn, zum Beispiel beim Rücklauf +5 K mit 47 % gegen 33 %.
  Der Vorteil kommt von der festen Referenz, nicht vom Modelltyp: Ein LSTM, das wie das Monitoring-Modell gegen eine feste
  Referenz prüft, liegt praktisch gleichauf (46 %). Bei Gleichstand bleibt die einfachere, erklärbare Kennlinie.
- An warmen Tagen rechnet nur das Prognose-LSTM. Dort schlägt es das Wochenmittel deutlich.
- Zusammen ergänzen sich beide im Winter: Über alle eingebauten Fehler steigt die Trefferquote von 51 % auf 60 %,
  ohne mehr Fehlalarme. An echten Begehungen meldet das Prognose-LSTM aber nicht öfter als an Vergleichsstationen. An
  Heiztagen bleibt es deshalb ein Hinweis.

**Fehlerart und Klasse.**

- Ventil: Mit Modellwahl im Lernteil liegt das gelernte Modell gleichauf mit der festen Sommernacht-Regel
  (Unterschied −0,01 [−0,14; +0,12]). Besser ist es nicht belegt. Im Hausfenster des Dashboards wird ein Verdacht
  deshalb mit der Sommernacht-Regel begründet, die ein Techniker nachvollziehen kann.
- Warum die Regression nur auf den LSTM-Zahlen gewählt ist und die zuerst genannten 0,88 nicht gelten, steht unter
  [Prüfdesign und Statistik](vergleich/pruefung.md#warum-das-modell-im-lernteil-gewahlt-wird).
- Reihenfolge (Test E): Unter den ersten 10 Stationen nach Ventil-Score hatten 7 einen Ventilbefund. Nach der
  Priorität des Monitoring-Modells sind es 5, Zufall wären etwa 2.
- Folie 5: Die Klasse „Regelventil tauschen“ trifft das LSTM-Modell bei 8 von 11 Ventilfällen, das Monitoring-Modell bei 4
  von 11. Dessen Fehlerbild „ventil“ ist dafür sehr genau (4 von 4 richtig) und dient als Bestätigung. „Regelparameter
  optimieren“ trifft keins der beiden.
- Dämmung: Nur das gelernte Modell findet ein Muster. Der Vorsprung vor der besten Einzelregel (+0,17 [−0,04; +0,38])
  ist knapp nicht gesichert, die Ursache physikalisch ungeklärt. Deshalb nur ein Hinweis mit niedriger Dringlichkeit.
- Kapazität: Dem gelernten Modell fehlt die Auslastung zum alten Vertrag, deshalb bleibt die Regel.

**Lage im Netz.** Netzvergleich und Potenzial beschreiben eine Station, sagen die Wirkung einer Begehung aber kaum
vorher (Rangkorrelation 0,16, p = 0,30). Das Dashboard zeigt deshalb Rang und Potenzial, aber keine Einspar-Schätzung.

## Was daraus folgt

Aus dem Vergleich entsteht ein System aus mehreren Teilen, die sich ergänzen:

- **Zwei Wächter, die sich nach Jahreszeit ablösen:** das Monitoring-Modell in der Heizperiode, das Prognose-LSTM an
  warmen Tagen und bei Stationen ohne Referenz.
- **Ein Ventil-Score,** der die Reihenfolge der Begehungen vorgibt und im Dashboard mit der Sommernacht-Regel begründet
  wird.
- **Hinweise auf Dämmung und Kapazität** mit niedriger Dringlichkeit.
- **Keine Aussage** zu Regelungsoptimierung, Filter, Durchfluss und Sollwert. Warum diese Fehlerarten in den
  Zählerdaten keine Spur hinterlassen, steht unter [Was nicht getragen hat](nicht_getragen.md).

Wie daraus eine Empfehlung je Station wird, steht unter [Handlungsempfehlungen](ergebnisse_handlungsempfehlungen.md),
wie sie angezeigt wird, unter [Dashboard](ergebnisse_dashboard.md). Wo die Modelle aufhören, steht unter
[Grenzen der Modelle](grenzen_modelle.md).
