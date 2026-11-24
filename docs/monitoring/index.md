# Anomalien und Monitoring

Die Begehungen liefern kein brauchbares Fehlerlabel (siehe [Label aus Messdaten](../begehungen/labels.md)), und die
Stationen zerfallen nicht in klare Typen (siehe [Merkmale und Clustering](../clustering/index.md)). Dieser Teil
verzichtet deshalb auf Labels und fragt stattdessen, wann eine Station von einem Maßstab abweicht. Als Maßstab dienen
zwei Vergleiche:

- **Station gegen Netz:** Läuft die Station schlechter als die anderen Stationen im selben Winter?
- **Station gegen sich selbst:** Läuft die Station schlechter als in ihrem ersten Jahr bei gleichem Wetter?

Aus beiden Vergleichen ist das **Monitoring-Modell** entstanden: der Netzvergleich (Notebook 19) und der Tagesmonitor
mit CUSUM (Notebook 20), ergänzt um das Potenzial gegenüber dem besten Viertel (Notebook 22). Es ist eines der beiden
Modelle, die unter [Modelle vergleichen](../vergleich/modellvergleich.md) gegen das LSTM-Modell antreten, und liefert im
Dashboard Priorität, Meldungen und Potenzial.

Alle Notebooks liegen unter `notebooks/5_monitoring/` und laufen nach Notebook 00. Notebook 18 braucht zusätzlich die
Tageswerte aus Notebook 10.

## Die Notebooks

| Notebook | Frage | Ergebnis in einem Satz |
|---|---|---|
| [16 Anomalieerkennung ohne Labels](anomalie.md)<br>`16_anomalie.ipynb` | Welcher von fünf Detektoren benennt auffällige Stationen, ohne ein Label zu brauchen? | Nur die beiden Rücklaufresiduen bestehen die Prüfung an den Begehungen, drei Detektoren nicht. |
| [17 Von der Anomalie zur Empfehlung](empfehlung.md)<br>`17_empfehlung.ipynb` | Lässt sich jeder auffälligen Station ein Muster, eine Maßnahme und ein Schweregrad zuordnen? | Alle 26 auffälligen Stationen haben ein Muster, am häufigsten den Verdacht auf hydraulischen Kurzschluss. |
| [18 Normalverhaltensmodell](normalverhalten.md)<br>`18_normalverhalten.ipynb` | Lässt sich eine Veränderung an einer Station wetterbereinigt aus Tageswerten erkennen? | Ja, vor allem über die Wassermenge. Die Alarme treffen die Begehungen öfter als Stationen ohne Begehung. |
| [19 Netzvergleich und Wintervergleich](netzvergleich.md)<br>`19_netzvergleich.ipynb` | Welche Stationen laufen im Kernwinter schlechter als das Netz, und hat die Begehung etwas gebracht? | 8 Stationen sind chronisch auffällig, 4 davon nie begangen. Eine Wirkung auf Gruppenebene ist mit ganzen Wintern nicht nachweisbar. |
| [20 Tagesmonitor](tagesmonitor.md)<br>`20_tagesmonitor.ipynb` | Läuft eine Station schlechter als in ihrem Lernjahr? | Der Abkühlungskanal trifft Begehungen fast doppelt so oft wie Stationen ohne Begehung, der Fenstermonitor aus Notebook 13 nicht. |
| [21 Alarme bewerten](alarme.md)<br>`21_alarme.ipynb` | In welche Richtung zeigen die Treffer, und taugt der Alarm für eine Priorität? | Die Treffer kommen fast nur aus Besserungsalarmen. Der Tagesmonitor taugt zur Erfolgskontrolle, nicht zur Frühwarnung. |
| [22 Bestes Viertel als Maßstab](bestwert.md)<br>`22_bestwert.ipynb` | Zeigt der Abstand zum besten Viertel mehr als der Abstand zum Median? | Die Rangfolge bleibt gleich, neu sind Lücken in physikalischen Einheiten und eine Potenzialstufe. |
| [23 Vergleichsgruppen und Nachbarn](nachbarn.md)<br>`23_nachbarn.ipynb` | Ändert ein Vergleich mit ähnlich großen Stationen oder mit den Nachbarn im Netz das Bild? | Nein. Die Rangfolge bleibt, und auffällige Stationen häufen sich im Netz nicht. |
| [24 Netzereignisse](netzereignisse.md)<br>`24_netzereignisse.ipynb` | Gibt es Tage, an denen viele Stationen gleichzeitig alarmieren? | Ja, vor allem nach einem Kälteeinbruch. Solche Alarme werden markiert, die Spitze der Priorität bleibt gleich. |

## Wie die Notebooks aufeinander aufbauen

- **16 und 17 sind der erste Ansatz.** Ein Erwartungswertmodell schätzt den Rücklauf bei gegebenem Wetter und gegebener
  Last, die Abweichung davon ist das Anomaliesignal. Notebook 17 ordnet den auffälligen Stationen ein Muster und eine
  Maßnahme zu. Beides arbeitet auf Stundenwerten und einem Tagespanel aus Stationstagen.
- **18 wechselt auf Tageswerte aus Zählerständen.** Jede Station lernt in ihrem ersten Jahr eine Kennlinie gegen die
  Außentemperatur, ein CUSUM meldet anhaltende Abweichungen. Das Notebook arbeitet für sich, ohne Code in `src/`.
- **19 und 20 bilden das Monitoring-Modell.** Notebook 19 vergleicht jede Station mit dem Netz, Notebook 20 setzt die
  Idee aus Notebook 18 als Modul in `src/tagesmonitor.py` um. Beide laufen gemeinsam in `src/stationsblatt.py` und
  damit auch in `python -m src.aktualisieren`.
- **21 bis 24 prüfen und ergänzen das Monitoring-Modell.** Notebook 21 untersucht Schwelle und Richtung der Alarme und
  legt die Priorität fest, Notebook 22 ergänzt das Potenzial. Die Notebooks 23 und 24 prüfen, ob das Leitungsnetz
  oder netzweite Ereignisse hinter den Auffälligkeiten stehen.

## Gesamtbild

- **Abweichung vom Netz und Abweichung von sich selbst messen Verschiedenes.** Der Netzvergleich zeigt den Zustand
  einer Station, der Tagesmonitor eine Veränderung. Beide hängen nicht zusammen (Fisher p = 0,31, Notebook 21) und
  ergänzen sich deshalb.
- **Dauerhaft schlechte Stationen findet nur der Netzvergleich.** Der Tagesmonitor lernt das Übliche, nicht das Gute.
  Beim Ventilfall 68956351 war das Ventil schon im Lernjahr offen, der Fehler galt deshalb als normal. Im Netzvergleich
  stand die Station in zwei Wintern auf Rang 1.
- **Der Rücklauf trägt das Signal.** In Notebook 16 bestehen nur die Detektoren auf dem Rücklauf die Prüfung, und
  der rohe Tagesmedian des Rücklaufs leistet dasselbe. Dynamik, Zustandsanteile und Isolation Forest reagieren nicht
  auf die Begehungen.
- **Das wiederkehrende Bild ist viel Wasser bei wenig Abkühlung.** Es heißt in Notebook 17 Kurzschlussverdacht, in
  Notebook 19 Ventilmuster und in Notebook 21 Fehlerbild Ventil. Alle vier begangenen chronisch auffälligen Stationen
  hatten einen Befund an Ventil oder Stellantrieb (Notebook 19).
- **Die Alarme sehen die Wirkung einer Begehung, sie warnen nicht vorher.** Die Treffer um die Begehung kommen fast
  ganz aus Besserungsalarmen. Im halben Jahr davor gibt es nicht mehr Verschlechterungsalarme als bei Stationen ohne
  Begehung (Notebook 21).
- **Das Netz erklärt die Auffälligkeiten nicht.** Weder im Leitungsgraphen noch über die Luftlinie häufen sich
  auffällige Stationen (Notebooks 23 und 24). Gleichzeitige Alarme vieler Stationen gehen eher auf das Wetter zurück.

## Ausgaben

Die Notebooks 19 bis 23 schreiben keine Dateien. Ihr Ergebnis entsteht im Betrieb über `src/stationsblatt.py`
(Stationsblätter, `status.csv`) und `python -m src.aktualisieren`.

| Notebook | Datei | Inhalt |
|---|---|---|
| 16 | `data/processed/anomaliescores.csv`, `anomalie_validierung.csv`, `regelkalibrierung.csv`, `anomaliescores.json` | Scores je Station mit Persistenz und Muster, Prüfung an den Begehungen, kalibrierte Regelschwellen |
| 17 | `data/processed/empfehlungsliste.csv`, `empfehlung_kontext.json` | Muster, Schweregrad und Maßnahme je auffälliger Station |
| 18 | `data/processed/normalmodell_*.csv`, `normalmodell.json` | Kennlinien, Tagesverläufe, Alarme, Wirkung und Treffer des Normalverhaltensmodells |
| 24 | `outputs/monitor_status.csv`, `monitor_alarme.csv`, `netzereignistage.csv` | Status je Station und Winter für die Netzkarte in Notebook 33 |

Alle Dateien enthalten nur Zählernummern, keine Adressen. Die Ausgaben von Notebook 18 nutzen die Notebooks 30
und 34.
