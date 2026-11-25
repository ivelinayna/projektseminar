# Weiterentwicklung

## Lernende Modelle

- **Bessere Begehungsprotokolle.** Der größte Hebel liegt vor dem Modell. Festhalten, ob etwas kaputt war und nicht nur,
  was gemacht wurde, und wann der Fehler vermutlich begonnen hat. Erst dann lassen sich Filter, Durchfluss und
  Sollwert als Fehlerart prüfen und eine Frühwarnung überhaupt testen (Notebook 36).
- **Mehr Fälle.** Jede protokollierte Begehung ist ein neues Label. Bei 11 Ventilfällen sind Unterschiede unter etwa
  0,1 AUC nicht sichtbar. Mit mehr Fällen lassen sich auch die Hinweise auf Dämmung und Kapazität sicherer prüfen.
- **Dämmung physikalisch erklären.** Die Abkühlrate im Stillstand ist ein erster Hinweis (AUC 0,69, nicht gesichert,
  Notebook 36). Sie sollte an neuen Daten mit vorher festgelegter Richtung geprüft werden. Dazu fehlt das Baujahr der
  Gebäude, bisher nur bei 14 Stationen bekannt. Es ist der letzte ungeprüfte Faktor, der das Muster des LSTM-Modells
  erklären könnte.
- **Winter 2025/26 auswerten,** sobald Daten für mehr Zähler vorliegen, und die Modelle danach nach den Regeln des
  [Probebetriebs](probebetrieb.md) neu lernen.
- **Weitere Teilnetze.** Die Pakete enthalten alles, was zum Anwenden gehört. Das Prognose-LSTM muss neue Stationen
  aber erst kalibrieren, und die Fehlerklassen müssten mit Begehungen aus dem neuen Netz geprüft werden, bevor die
  Empfehlungen dort gelten.

## Monitoring

- **Referenz neu lernen,** nach jeder Begehung und zu jeder Heizperiode. Sonst stehen die Konten des Monitoring-Modells
  am Deckel und können nicht neu melden (siehe [Probebetrieb](probebetrieb.md#regeln-fur-den-betrieb)).
- **Außentemperatur glätten.** Die Temperatur über 2 bis 3 Tage mitteln oder um einen Tag verzögern und prüfen, ob die
  Wellen von Alarmen nach Kälteeinbrüchen kleiner werden
  ([Netzereignisse](../monitoring/netzereignisse.md#einordnung),
  [Tagesmonitor](../monitoring/tagesmonitor.md#einordnung)).
- **Sommerkennzahl im Netzvergleich.** Der Netzvergleich zählt nur den Kernwinter. Ihm fehlt damit der Nachtdurchfluss
  im Sommer, das stärkste Merkmal für ein offenes Ventil ([Netzvergleich](../monitoring/netzvergleich.md#einordnung)).
- **Minutenwerte für die Regelhysterese.** Für einzelne Stationen Minutenwerte oder Reglerdaten mit Stellsignal
  erheben. Mit Stundenwerten und Tagesmitteln bleibt eine Regelhysterese unsichtbar
  ([Datenanalyse](../ergebnisse/datenanalyse.md#schwingende-regelung)).

## Labels

- **Fehler-Symptom-Matrix mit der ÜZ abstimmen.** Bisher ist keines der 132 Felder abgestimmt. Mit einer abgestimmten
  Matrix ließe sich die Bayes-Diagnose neu prüfen
  ([Bayes-Diagnose](../weitere_versuche/bayes.md#was-es-zum-weitermachen-brauchte)).
- **Neue Begehungen nach vorab festgelegten Regeln auswerten,** wie unter [Prüfung nach vorn](pruefung.md)
  beschrieben.

Die offenen Fragen, die nur die ÜZ beantworten kann, stehen unter
[Offene Fragen an die ÜZ](../grenzen/offene_fragen.md).
