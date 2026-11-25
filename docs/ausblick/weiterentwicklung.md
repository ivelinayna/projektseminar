# Weiterentwicklung

Hier stehen die nächsten Schritte an den Modellen und am Monitoring. Was die ÜZ selbst tun kann, damit die Daten
besser werden, steht unter [Vorschlag für künftige Begehungen](begehungen.md). Die offenen Fragen, die nur die ÜZ
beantworten kann, stehen unter [Offene Fragen an die ÜZ](../grenzen/offene_fragen.md).

## Lernende Modelle

- **Mit besseren Begehungsdaten neu prüfen.** Der größte Hebel liegt vor dem Modell. Wenn das Protokoll festhält, ob
  etwas kaputt war und seit wann, lassen sich Filter, Durchfluss und Sollwert als Fehlerart prüfen und eine
  Frühwarnung überhaupt testen (Notebook 36). Jede so protokollierte Begehung ist außerdem ein neuer Fall. Bei 11
  Ventilfällen sind Unterschiede unter etwa 0,1 AUC nicht sichtbar. Mit mehr Fällen lassen sich auch die Hinweise auf
  Dämmung und Kapazität sicherer prüfen ([Vorschlag für künftige Begehungen](begehungen.md#was-das-bringt)).
- **Dämmung physikalisch erklären.** Die Abkühlrate im Stillstand ist ein erster Hinweis (AUC 0,69, nicht gesichert,
  Notebook 36). Sie sollte an neuen Daten mit vorher festgelegter Richtung geprüft werden. Dazu fehlt das Baujahr der
  Gebäude, bisher nur bei 14 Stationen bekannt
  ([Vorschlag für künftige Begehungen](begehungen.md#3-zahlerdaten-und-stammdaten)). Es ist der letzte ungeprüfte
  Faktor, der das Muster des LSTM-Modells erklären könnte.
- **Winter 2025/26 auswerten,** sobald Daten für mehr Zähler vorliegen, und die Modelle danach nach den Regeln unter
  [Betrieb mit neuen Daten](betrieb.md#regeln-fur-den-betrieb) neu lernen.
- **Weitere Teilnetze.** Die Pakete enthalten alles, was zum Anwenden gehört. Das Prognose-LSTM muss neue Stationen
  aber erst kalibrieren, und die Fehlerklassen müssten mit Begehungen aus dem neuen Netz geprüft werden, bevor die
  Empfehlungen dort gelten.

## Monitoring

- **Referenz neu lernen,** nach jeder Begehung und zu jeder Heizperiode. Sonst stehen die Konten des Monitoring-Modells
  am Deckel und können nicht neu melden (siehe [Betrieb mit neuen Daten](betrieb.md#regeln-fur-den-betrieb)).
- **Außentemperatur glätten.** Die Temperatur über 2 bis 3 Tage mitteln oder um einen Tag verzögern und prüfen, ob die
  Wellen von Alarmen nach Kälteeinbrüchen kleiner werden
  ([Netzereignisse](../monitoring/netzereignisse.md#einordnung),
  [Tagesmonitor](../monitoring/tagesmonitor.md#einordnung)).
- **Sommerkennzahl im Netzvergleich.** Der Netzvergleich zählt nur den Kernwinter. Ihm fehlt damit der Nachtdurchfluss
  im Sommer, das stärkste Merkmal für ein offenes Ventil ([Netzvergleich](../monitoring/netzvergleich.md#einordnung)).
- **Minutenwerte für die Regelhysterese.** Für einzelne Stationen Minutenwerte oder Reglerdaten mit Stellsignal
  erheben. Mit Stundenwerten und Tagesmitteln bleibt eine Regelhysterese unsichtbar
  ([Datenanalyse](../ergebnisse/datenanalyse.md#schwingende-regelung)).

## Dashboard

- **Streamlit-App als Alternative zur HTML-Datei.** Eine Fassung mit denselben Inhalten liegt schon im Repository. Sie
  könnte auf einem Server der ÜZ laufen und um eine Rückmeldung nach Begehungen erweitert werden
  ([Dashboard als Streamlit-App](streamlit.md)).
