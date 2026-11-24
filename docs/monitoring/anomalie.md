# Anomalieerkennung ohne Labels

**Notebook 16:** `notebooks/5_monitoring/16_anomalie.ipynb` · **Code:** `src/dynamik.py`, `src/tagespanel.py`,
`src/anomalie.py`, `src/regelkalibrierung.py`, Tests in den gleichnamigen Dateien unter `tests/`

Ein überwachter Klassifikator auf den Begehungen bleibt unter der Trivialrate (Balanced Accuracy 0,33 bzw. 0,42 gegen
0,50, siehe [Negativbefunde](../nicht_getragen/negativbefunde.md)). Dieses Notebook benennt auffällige Stationen
deshalb ohne Label. Eine **Anomalie** ist hier eine Abweichung vom physikalisch erwartbaren Verhalten, die über
mehrere Tage anhält. Fünf Detektoren treten gegeneinander an. Ein brauchbarer Detektor muss nach einer Begehung
sinken, bei Stationen ohne Begehung im selben Zeitraum nicht.

## Datenbasis und Tagespanel

- Stundenreihen von 93 Zählern aus Notebook 00, 01.11.2021 bis 20.07.2026, dazu 41.312 Stunden Außentemperatur vom
  DWD.
- **Tagespanel:** eine Zeile je Station und Tag, gemeinsame Grundlage aller Detektoren. Es enthält Tageswerte der
  Messgrößen, Dynamikkennzahlen, Zustandsanteile, Tagesmitteltemperatur und Heizgradstunden.
- 88.792 Stationstage, davon 99,8 % mit genug Messstunden. 20 % der Tage haben keine einzige Laststunde, die Dynamik
  ist für 78,7 % berechnet, die Zustandsanteile für 95,7 %. Auswertbare Tage sind markiert, verworfen wird nichts.

## Die fünf Detektoren

| Detektor | Was er misst | Grundlage |
|---|---|---|
| Netzresiduum | Rücklauf über der Erwartung einer gemeinsamen Regression für alle Stationen | Tagesmedian des Rücklaufs gegen Außentemperatur, Lastanteil und mittlere Leistung |
| Stationsresiduum | Rücklauf über der Erwartung einer eigenen Regression je Station | wie oben, je Station |
| Isolation Forest | seltene Tage, die sich leicht von den übrigen abtrennen lassen | 8 Merkmale, 63.570 Tage, 92 Stationen, Anteil 5 % |
| Zustandsanteil | Zeitanteil im Betriebszustand „Kurzschlussverdacht“ | Stundencluster aus [Notebook 09](../clustering/validierung.md) |
| Dynamikscore | Rücklauf, der kaum auf Lastwechsel reagiert oder unruhig ist | Kopplung Rücklauf–Vorlauf und zweite Ableitung des Rücklaufs |

- **Die beiden Residuen beantworten verschiedene Fragen.** Das Netzresiduum fragt, wer im Netzvergleich schlecht
  auskühlt. Bauartbedingte Unterschiede fallen dabei auf, ohne dass etwas defekt ist. Das Stationsresiduum fragt, wann
  sich eine Station verschlechtert hat. Eine von Anfang an schlechte Station wird dabei zu ihrer eigenen Norm, und das
  Stationsmittel ist per Konstruktion null.
- **Das Netzmodell erklärt wenig.** R² = 0,035 auf 85.676 Tagen. Mittlere Leistung (p < 0,001) und Außentemperatur
  (p = 0,027) tragen, der Lastanteil nicht (p = 0,09). Belastbar ist damit die Rangfolge der Stationen, nicht der
  absolute Wert.
- **Zustandsanteil:** Der Cluster mit Kurzschlussverdacht wird über sein Profil bestimmt, nicht über die Nummer, die
  vom Startwert abhängt. Hier ist es Cluster 1 mit 4,2 K Spreizung, 71 °C Rücklauf und 13,1 % aller Stunden. 18 von 92
  Stationen liegen im Mittel über 20 %.
- **Dynamikscore:** Die Hypothese war, dass ein festsitzendes Ventil einen trägen Rücklauf und ein defekter Regler ein
  unruhiges Signal erzeugt. Der Anteil praktisch stehender Rücklaufstunden fällt heraus, weil er über alle
  Stationstage keine Streuung hat. Bei stündlicher Messung und 0,1 K Auflösung ist ein stehender Rücklauf kaum zu
  beobachten.

## Übereinstimmung der Detektoren

Verglichen werden die Stationsmittel mit der Spearman-Rangkorrelation und die jeweils 15 höchsten Stationen mit dem
Jaccard-Index.

- Netzresiduum und Zustandsanteil sind sich am ähnlichsten (Spearman 0,69, Jaccard 0,67). Der Isolation Forest liegt
  dazwischen (0,58 zum Netzresiduum, 0,49 zum Zustandsanteil).
- Der Dynamikscore korreliert mit allen anderen negativ (−0,08 bis −0,49), seine Top 15 überschneiden sich mit den
  anderen höchstens zu 0,03.
- Das Stationsresiduum lässt sich auf Stationsebene nicht sinnvoll vergleichen, weil sein Mittel per Konstruktion null
  ist.

## Persistenz

- Ein Tag ist auffällig, wenn der Score über dem 90. Perzentil aller Stationstage liegt (Netzresiduum 22,1 K).
- **Persistent auffällig** heißt: mindestens 7 auffällige Tage im 14-Tage-Fenster.
- Ohne diese Bedingung haben 43 Stationen beim Netzresiduum einen Treffer, 13,5 % der Stationstage sind auffällig. Mit
  ihr sind es 27 Stationen und 9,8 % der Tage. **19 Stationen** sind an mehr als 10 % ihrer Tage persistent auffällig.

## Prüfung an den Begehungen

- Je Begehung ein Fensterpaar im Kernwinter vor und nach dem Eingriff, dieselben Fenster für 42 Kontrollzähler ohne
  Begehung, wie im [Wintervergleich](../begehungen/wintervergleich.md). Auswertbar sind 43 Begehungen (Isolation
  Forest 42).
- Bestanden heißt: Der Diff-in-Diff, also die Änderung bei den begangenen Zählern minus die Änderung bei den
  Kontrollen, ist negativ und hat p < 0,05.

| Detektor | Diff-in-Diff | p | bestanden |
|---|---|---|---|
| Netzresiduum | −1,34 | 0,017 | ja |
| Stationsresiduum | −0,86 | 0,041 | ja |
| Isolation Forest | +0,001 | 0,62 | nein |
| Zustandsanteil | 0,00 | 0,76 | nein |
| Dynamikscore | +0,02 | 0,89 | nein |
| zum Vergleich: Tagesmedian des Rücklaufs | −1,74 K | 0,009 | ja |
| zum Vergleich: Rücklauf nur in Laststunden | −0,69 K | 0,09 | nein |

- Nur die beiden Residuen bestehen. Der rohe Tagesmedian des Rücklaufs leistet dasselbe. Der Effekt der Residuen kommt
  also großteils aus der Zielgröße, nicht aus dem Modell.
- Alle auswertbaren Begehungen teilen dasselbe Fensterpaar. Der Diff-in-Diff gleicht damit die Witterung aus, aber
  keinen Zeiteffekt, der nur die begangenen Stationen betrifft.

## Plausibilisierung über den Energieeinsatz

Kostet eine hohe Punktzahl Energie? Verglichen wird die Energie je Heizgradstunde im obersten Fünftel jedes Detektors
mit dem Rest (Mann-Whitney).

- Isolation Forest 0,31 gegen 0,24 kWh/Kh (p = 0,022), Zustandsanteil 0,31 gegen 0,24 (p = 0,040). Das Netzresiduum
  zeigt nur dieselbe Richtung (0,30 gegen 0,26, p = 0,35).
- Der Dynamikscore zeigt umgekehrt 0,19 gegen 0,31 (p < 0,001). Er bildet eher Betriebsintensität oder Stationsgröße
  ab als ein Fehlverhalten.
- Beim Stationsresiduum ist der Unterschied ein Artefakt, weil das Fünftel Stationsmittel sortiert, die per
  Konstruktion null sind.
- Die Kennzahl gleicht Winterhärte und Länge der Historie aus, nicht die Gebäudegröße.

## Muster je Station

Jede Station bekommt ein beschreibendes Muster, woran die Auffälligkeit im Messsignal hängt. Die Regeln stehen auf
Quantilen der Stationsmediane, nicht auf festen Schwellen aus der Literatur.

| Muster | Stationen |
|---|---|
| kein eindeutiges Muster | 50 |
| unruhige Regelung | 16 |
| Rücklauf über Erwartung ohne weiteres Merkmal | 12 |
| Rücklauf reagiert kaum, Verdacht festsitzendes oder offenes Ventil | 7 |
| Rücklauf folgt dem Vorlauf, Verdacht hydraulischer Kurzschluss | 5 |
| Durchfluss ohne nennenswerte Abnahme | 3 |

- Von den 19 persistent auffälligen Stationen haben 9 nur „Rücklauf über Erwartung“ und 5 gar kein Muster.
- Die Ventilregel greift knapp über der Auflösungsgrenze, nur eine dieser Stationen (66761022) ist persistent
  auffällig. „Unruhige Regelung“ hängt am Dynamikscore, der die Prüfung nicht bestanden hat.
- Den hohen Anteil ohne Muster behebt [Notebook 17](empfehlung.md).

## Nachkalibrierung der Regel-Baseline

Die Regel-Baseline in `src/fault_detection.py` passt mit ihren ursprünglichen Schwellen nicht zu den echten Daten.
Einzelne Regeln treffen fast alle oder keine Station, etwa `flow_short_cycle_power` 83 von 93 und `peak_load_share`
keine.

- Neue Schwelle je Regel: das Quantil, das rund 15 % der Stationen trifft. Die 15 % sind gesetzt, angelehnt an die
  19 von 93 persistent auffälligen Stationen.
- Mit den alten Schwellen erhielten 44 Stationen das Label `control_hysteresis` und keine das Label `healthy`. Nach der
  Kalibrierung sind 38 Stationen `healthy`, der Rest verteilt sich auf sechs Fehlerbilder.
- Das macht die Regeln bewertbar, nicht richtig. Wie die kalibrierte Baseline im Modellvergleich abschneidet, steht
  unter [Modellvergleich](../modellvergleich.md).

## Einordnung

- **Belastbar:** Netzresiduum und Stationsresiduum bestehen die Prüfung an 43 Begehungen mit 42 Kontrollzählern. Die
  Trefferliste ist plausibel: 68956351 mit dem drei Jahre offenen Ventil steht auf Rang 4, persistent auffällig an
  77 % der Tage. Das ist ein Hinweis, keine Validierung.
- **Schwach:** Die Residuen bringen gegenüber dem rohen Rücklauf keinen Gewinn. Das Netzmodell erklärt wenig
  (R² = 0,035), und die Energie je Heizgradstunde ist nicht nach Gebäudegröße bereinigt.
- **Offen:** Die Zielquote von 15 % ist gesetzt. Werte von `peak_load_share` über 1,0 können echte Lastspitzen oder zu
  niedrige Anschlusswerte in der Knotentabelle sein. Ob eine auffällige Station den zugeordneten Fehler hat, lässt
  sich mit 57 Freitexten nicht zeigen.

## Ausgaben

- `data/processed/anomaliescores.csv`: Scores je Station mit Persistenz, Muster und Energie je Heizgradstunde.
- `anomalie_validierung.csv`, `regelkalibrierung.csv` und der Lauf-Kontext `anomaliescores.json`.
- Nur Zählernummern, keine Adressen.
