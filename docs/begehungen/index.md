# Begehungen auswerten

Zwischen August 2024 und September 2025 hat die ÜZ Stationen begangen und festgehalten, was sie dabei geändert hat.
Was in der Begehungstabelle steht, beschreibt [Begehungen](../datengrundlage/begehungen.md) unter *Datengrundlage*. Die
Begehungen sind die einzige unabhängige Auskunft darüber, was an den Stationen tatsächlich los war. Dieser Teil stellt
deshalb zwei Fragen:

1. **Haben die Begehungen gewirkt?** Ändert sich das Betriebsverhalten einer Station danach messbar?
   (Notebooks 02, 04, 05 und 06)
2. **Taugen die Begehungen als Label?** Lässt sich aus ihnen ablesen, welche Station einen Fehler hatte, und wenn
   nicht, woraus dann? (Notebook 03)

Alle Notebooks liegen unter `notebooks/2_begehungen/` und laufen nach Notebook 00.

## Die Notebooks

| Notebook | Frage | Ergebnis in einem Satz |
|---|---|---|
| [02 Wirkung im 21-Tage-Fenster](wirkung.md)<br>`02_wirkung.ipynb` | Ändert sich der Rücklauf in den drei Wochen nach der Begehung? | Die Richtung passt zur dokumentierten Änderung, ist aber nicht signifikant. |
| [03 Label aus Messdaten](labels.md)<br>`03_labels.ipynb` | Wann ist eine Station auffällig, allein aus den Messdaten? | Eine Regel aus Durchfluss und Spreizung erkennt schwere Dauerzustände, aber keine zeitweisen Fehler. |
| [04 Wintervergleich](wintervergleich.md)<br>`04_wintervergleich.ipynb` | Sinkt der Rücklauf vom Winter vor der Begehung zum Winter danach? | Gegenüber Stationen ohne Begehung um 2,0 K (p ≈ 0,008). |
| [05 Performance wie auf der ÜZ-Folie](performance.md)<br>`05_performance.ipynb` | Lassen sich die +13,4 % der ÜZ-Folie nachrechnen? | Gleiche Richtung, aber je nach Rechnung nur 4 bis 9 %. |
| [06 Prognose mit ARIMA](arima.md)<br>`06_arima.ipynb` | Weicht der Rücklauf nach der Begehung von einer Prognose ab? | Deutliche Sprünge sind häufiger als ohne Begehung, der typische Fall ändert sich kaum. |

## Wie die Notebooks aufeinander aufbauen

- **02 legt die Grundlage.** Es ordnet jede Begehung über `Zuordnung.xlsx` einem Zähler zu. Den Loader dafür
  (`src/load_begehungen.py`) nutzen alle folgenden Notebooks. Die Begehung ist hier ein Ereignis („was hat sich danach
  geändert?“), kein Label.
- **03 zieht die Folgerung aus 02.** Die Änderungskategorie der Begehungstabelle beschreibt, wie viel der Monteur
  verstellt hat, nicht wie schlecht die Station lief. Ein Label muss deshalb aus den Messdaten kommen.
- **04 verlängert die Fenster.** Die drei Wochen aus 02 liegen meist am Beginn der Heizperiode und messen den
  Jahresgang mit. 04 vergleicht ganze Kernwinter und rechnet die Witterung über Heizgradstunden heraus.
- **05 prüft die Kennzahl der ÜZ.** Energie je m³ Heizwasser gegen die Außentemperatur, wie auf der Folie
  „Vergleich Gesamteffizienz vor und nach der Optimierung von HAST“.
- **06 ersetzt den Vergleich durch eine Prognose.** Ein Modell aus der Zeit vor der Begehung sagt voraus, wie der
  Rücklauf bei gleichem Wetter weitergelaufen wäre.

## Gesamtbild

- **Die Richtung stimmt überall.** Nach der Begehung sinkt der Rücklauf, und die Performance steigt. Je mehr laut
  Begehungstabelle geändert wurde, desto deutlicher (02). Im Wintervergleich (04) sind die Kategorien dafür zu dünn
  besetzt.
- **Abgesichert ist sie nur über ganze Winter mit Kontrollgruppe.** Der Wintervergleich (04) ist mit −2,0 K
  (p ≈ 0,008) das belastbarste Ergebnis. Die kurzen Fenster (02) und die Performance (05) bleiben ohne gesicherten
  Effekt, außer in der saubersten Fassung der Performance (p ≈ 0,04).
- **Drei Schwächen teilen alle Notebooks:**
    - Begangen wurden eher auffällige Stationen, keine Zufallsauswahl. Eine Kontrollgruppe fängt den allgemeinen Trend
      ab, nicht diesen Auswahleffekt. Es heißt deshalb immer „passt zu einer Wirkung“, nie „belegt eine Wirkung“.
    - 34 der 58 datierten Begehungen liegen im September 2024. Es gibt praktisch nur ein Winterpaar, und der Winter
      danach war rund 21 % kälter.
    - Die Begehungstabelle hält fest, was eingestellt wurde, aber nicht, ob vorher ein Fehler vorlag.
- **Ein Fall zieht sich durch alle Notebooks: Zähler 68956351.** Ein Ventil stand fast drei Jahre offen und wurde am
  09.09.2024 getauscht. Noch am selben Tag fiel der Durchfluss von rund 500 auf nahezu 0 l/h. 02 findet ihn als
  größten Ausschlag im Durchfluss, das Label aus 03 kippt genau in diesem Monat, und 06 findet ihn ohne Vorwissen als
  stärkste Abweichung. Der Tausch steht nur im Freitext der Begehungstabelle, in den Maßnahmen-Spalten ist nichts
  angekreuzt.
- **Stationen ändern ihren Zustand meist ohne Begehung.** Nur 2 von 36 Beginnen und 2 von 37 Enden eines auffälligen
  Zustands fallen in einen Begehungsmonat (03).

Was die Monteure in den Freitexten notiert haben, wertet Notebook 14 aus (siehe
[Stationsbilder und Befunde](../stationsbilder.md)). Wie künftige Begehungen so festgehalten werden, dass sich diese
Fragen besser beantworten lassen, steht unter [Rückmeldung aus dem Probebetrieb](../ausblick_probebetrieb.md#ruckmeldung-aus-dem-probebetrieb).

## Ausgaben

Alle Tabellen landen unter `data/processed/` und bleiben lokal, der Ordner ist von Git ausgeschlossen.

| Notebook | Datei | Inhalt |
|---|---|---|
| 02 | `begehungen_aufbereitet.csv` | Begehungstabelle mit Zählernummer, 66 Zeilen × 26 Spalten, **enthält Adressen** |
| 02 | `begehungs_wirkung.csv`, `.json` | Änderung je Begehung im 21-Tage-Fenster, mit Kontrollwert, **enthält Adressen** |
| 03 | `station_monat_label.csv`, `.json` | Label je Station und Monat, 2.300 Zeilen |
| 04 | `wintervergleich_kernwinter.csv`, `wintervergleich_erweitert.csv` | Winter davor gegen Winter danach je Begehung |
| 06 | `arima_begehungen.csv`, `arima_modellvergleich.csv` | Abweichung von der Prognose je Begehung, Fehler je Modell |

Notebook 05 schreibt nur Grafiken nach `outputs/`.
