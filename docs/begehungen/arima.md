# Prognose mit ARIMA

**Notebook 06:** `notebooks/2_begehungen/06_arima.ipynb` · **Code:** `src/zeitreihenmodell.py`, Tests in
`tests/test_zeitreihenmodell.py`

Die Vergleiche in [Notebook 02](wirkung.md) und [Notebook 04](wintervergleich.md) kämpfen mit der Jahreszeit. Dieses
Notebook dreht die Frage um: Ein Modell aus der Zeit **vor** der Begehung sagt voraus, wie der Rücklauf bei gleichem
Wetter weitergelaufen wäre. Weicht die Messung danach deutlich davon ab, ist das ein Hinweis auf eine Wirkung, kein
Nachweis.

## Tagesreihe und Modelle

- **Tageswert:** Mittel des Rücklaufs über die Stunden mit mehr als 0,5 kW Leistung, mindestens 12 solche Stunden je
  Tag. Tage ab 15 °C Außentemperatur bleiben leer.
- **ARIMA** schreibt eine Reihe aus ihren eigenen letzten Werten fort. **SARIMAX** nimmt einen Wochenterm und äußere
  Größen dazu, hier die Außentemperatur.
- Zum Vergleich: die reine Kennlinie (Rücklauf gegen Außentemperatur) und das Mittel der letzten 7 Tage.
- Gerechnet wird als Regression mit AR-Fehlern, also SARIMAX ohne MA-Teil, weil `statsmodels` im Projekt fehlt.

## Welches Modell prognostiziert am besten?

- Rollende Fenster je Zähler ohne Begehung: 56 Tage anpassen, 14 Tage vorhersagen, Außentemperatur als bekannt
  angenommen. 87 Zähler, 1.695 Fenster.
- **Am besten ist Außentemperatur plus AR(1)** (`arx_100`): mittlerer Fehler 2,11 °C gegen 2,66 °C beim
  7-Tage-Mittel.
- Reines ARIMA ist schlechter als das 7-Tage-Mittel, ohne Wetter schreibt es nur den letzten Stand fort.
- Der Wochenterm bringt nichts, der AR-Term gegenüber der reinen Kennlinie nur 0,02 °C. Der Gewinn kommt aus der
  Außentemperatur.

## Prognose über die Begehung

- Anpassung auf bis zu 365 Tagen vor der Begehung, Prognose der 90 Tage danach. Das Vorjahr wird so über die
  Außentemperatur verglichen statt über den Kalender.
- **Abweichung** = Messung minus Prognose, gemittelt über die Heiztage danach. Negativ heißt: Rücklauf niedriger als
  bei gleichem Wetter erwartet.
- **z** = Abweichung geteilt durch die übliche Streuung von Fenstern ohne Begehung.
- 40 von 53 Begehungen sind auswertbar, 13 haben zu wenige Heiztage davor oder danach.

## Placebo und Kontrollgruppe

| Gruppe | außerhalb von z = ±2 |
|---|---|
| Begehungen | 16 von 40 (40 %) |
| Fenster ohne Begehung (Placebo) | 138 von 710 (19 %) |
| Stationen ohne Begehung mit Pseudodatum (Kontrolle) | 21 von 97 (22 %) |

- Nach Begehungen gibt es häufiger einen deutlichen Sprung: gegen Placebo p = 0,002, gegen Kontrolle p = 0,035.
- 11 der 16 auffälligen Begehungen haben danach einen niedrigeren Rücklauf, 5 einen höheren.
- **Der typische Fall ändert sich kaum:** Median −0,55 °C gegen −0,24 °C bei der Kontrolle (p = 0,23).
- Die Abweichung hängt mit der Rücklaufänderung aus Notebook 02 zusammen (Spearman 0,54), ist aber kein unabhängiger
  Beleg.

## Einzelfall 68956351

Vorher 70,5 °C, danach 37,7 °C, das Vorher-Modell erwartet 71,9 °C. Das ist die größte Abweichung unter allen
Begehungen (z = −19,7), gefunden ohne Wissen über die Reparatur.

## Einordnung

- **Belastbar:** Die Außentemperatur lohnt sich als Erklärungsgröße. Nach Begehungen gibt es häufiger einen deutlichen
  Sprung als bei Stationen ohne Begehung.
- **Schwach:** Für eine Zeitreihenstruktur in den Tagesmitteln gibt es keinen Beleg. Der typische Fall ändert sich
  wenig, und die Ziehungen je Kontrollstation sind nicht unabhängig.
- **Offen:** Große Sprünge im Herbst 2024 ohne Begehung (69513891 rund −21 °C, 72167777 −14 °C, 80956410 +19 °C)
  lassen sich nur über eine Rückfrage bei der ÜZ klären. Die Außentemperatur stammt aus Kitzingen statt aus
  Wiesentheid.

## Ausgaben

`data/processed/arima_begehungen.csv` (Abweichung je Begehung) und `arima_modellvergleich.csv` (Fehler je Modell).
