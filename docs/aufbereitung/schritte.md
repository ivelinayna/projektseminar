# Die Schritte im Einzelnen

Notebook 00 arbeitet die Schritte in dieser Reihenfolge ab. Zu jedem Schritt steht, was er macht und warum es ihn
gibt. Wie die Schritte im Lauf des Projekts entstanden sind, steht auf den Seiten zu den Änderungen.

## 1 · Dateien einsammeln

- Je Zähler gibt es bis zu drei Exporte: `<Zählernummer>__n.csv` (2024), `<Zählernummer>_2025n.csv` (2025) und
  `<Zählernummer>.ods` (Nachlieferung bis Juli 2026).
- **Falscher Dateiname:** Der Export 2024 von Zähler 72135480 heißt `721354800__n.csv`, mit einer 0 zu viel. Der
  Fehler steckt schon im Export der ÜZ. Eine feste Zuordnung im Code hängt die Datei an den richtigen Zähler.
- **Keine Hausstationen:** 8 Zähler fliegen sofort heraus: das BHKW, die HHS-Kessel I bis IV, der Ölspitzenkessel und
  zwei Temperaturfühler im Heizhaus. Weil sie gar nicht erst in `real_meters/` landen, sieht sie kein späteres
  Notebook.

## 2 · Jede Datei lesen und prüfen

Die Reihenfolge der Schritte in der Lesefunktion ist wichtig:

1. **Spreizung ergänzen:** Eine Datei (81050517, Export 2025) liefert die Spreizung nicht mit. Sie ist per Definition
   Vorlauf minus Rücklauf und wird berechnet, statt den ganzen Zähler zu verwerfen. Das passiert vor der
   Skalierungskorrektur, denn eine Differenz skaliert genauso wie ihre Summanden.
2. **Pflichtspalten prüfen:** Fehlt eine der fünf Messgrößen, wird nur dieser eine Zähler übersprungen und mit Grund
   aufgelistet. Der Lauf bricht nicht ab, und nichts fällt stillschweigend weg.
3. **Zeilen ohne Messwert verwerfen:** Eine Zeile fliegt nur heraus, wenn alle fünf Messgrößen leer sind. Das sind
   Zählerstände an Stichtagen, keine Messungen. Nullwerte bleiben drin: 0 ist eine Messung, leer nicht.
4. **ODS zurückrechnen:** Die ODS-Dateien speichern alle Werte 1000-fach zu groß. Erkannt wird das am Median der
   Vorlauftemperatur (über 1000).
5. **Plausibilität prüfen:** Werte außerhalb physikalischer Grenzen werden auf leer gesetzt. Erst zurückrechnen, dann
   prüfen. Andersherum würde jeder ODS-Wert als unmöglich aussortiert.

| Messgröße | erlaubter Bereich |
|---|---|
| Durchfluss | −1.000 bis 50.000 l/h |
| Leistung | −2.000 bis 2.000 kW |
| Spreizung | −60 bis 100 °C |
| Vor- und Rücklauf | −20 bis 130 °C |

- Die Grenzen sind bewusst weit gefasst. Sie sollen kaputte Dateien abfangen, keine ungewöhnlichen, aber echten
  Betriebszustände.
- Negative Leistung bleibt erhalten. Bei 72167783 fließt nach der Abtrennung tatsächlich Wärme rückwärts (bis
  −14,7 kW). Das ist ein Befund, kein Messfehler.
- Im aktuellen Lauf liegt keine einzige Messzelle außerhalb. Die Prüfung sichert vor allem künftige Exporte ab.

## 3 · Je Zähler zusammenführen

- Alle Dateien eines Zählers werden aneinandergehängt und nach Zeitstempel sortiert.
- **Abrunden auf die volle Stunde:** Dieselbe Stunde steht im einen Export als 13:00, im anderen als 13:01. Ohne
  Abrunden gelten beide als verschiedene Zeitpunkte und landen doppelt in der Reihe.
- **Zwei Arten von Dubletten**, getrennt gezählt:
    - *Exportüberlappung* (gleicher Zeitstempel, 367.298 Zeilen): normal, die Exporte decken bewusst denselben
      Zeitraum ab.
    - *Minutenversatz* (13:00 und 13:01, 29.945 Zeilen): der eigentliche Fallstrick. Betrifft 3 Zähler stark:
      68956353 (47 % der Zeilen), 80912193 (31 %) und 66761022 (17 %).
- **Welcher Export gewinnt:** Bei Überlappung gilt der neuere Export. Ausnahme ist die ODS: Sie hat keine
  Zählerstände und darf CSV-Stunden mit gemessenem Zählerstand nicht überschreiben. Sie verlängert die Reihe nur
  nach hinten.
- **Keine Umrechnung nach UTC:** Getestet und wieder verworfen. Die doppelte Stunde bei der Zeitumstellung im Oktober
  enthält in den Exporten nur eine Ablesung, es gibt also keine zweite Stunde zu retten. Jede Variante der Umrechnung
  hat Messstunden gekostet:

| Variante | Ergebnis |
|---|---|
| Doppelte Stunde automatisch erkennen | scheitert bei 166 von 198 Dateien |
| Doppelte Stunde als leer setzen | 405 Messstunden verloren |
| Doppelte Stunde als Winterzeit lesen | 240 Messstunden verloren, weil durch die Verschiebung mehr Zeilen der Exporte in dieselbe Stunde fallen |

Die Zeitstempel bleiben deshalb deutsche Lokalzeit wie in den Rohdaten.

## 4 · Lückenloses Stundenraster

- Die Exporte enthalten nur gemessene Stunden. Eine Lücke war eine fehlende Zeile und damit unsichtbar.
- Jetzt bekommt jede Stunde zwischen erster und letzter Messung eine Zeile. Nicht gemessene Stunden bleiben leer.
  Damit gilt „eine Zeile ist eine Stunde“. Das braucht die Frequenzanalyse (FFT) für die Regelhysterese, die mit genau
  einer Stunde Abstand je Zeile rechnet.
- Je Zähler stehen drei Werte in der Übersicht: gemessene Stunden, Länge des Rasters und die Abdeckung als Verhältnis
  der beiden.
- Ergebnis: 80 % der Rasterstunden sind gemessen, je Zähler 46 % bis 100 %, Median 79 %. 84 % der fehlenden Stunden
  fallen in die Tageswert-Phase bis etwa November 2022 (45 Zähler mit nur einem Wert je Tag um 23 Uhr). Echte Lücken
  sind also selten.

## 5 · Adresse und Anschlusswert zuordnen

- **Adresse** aus `Zuordnung.xlsx` (Zähler und Adresse je Jahr, 102 Zähler). Die Tabelle ist vollständiger als
  `Nodes_Edges.ods`. Bei einem Adresswechsel gilt das neuere Jahr.
- **Anschlusswert** gibt es nur in `Nodes_Edges.ods` (99 Zähler). Er wird in drei Stufen gesucht:
    1. direkt über die Zählernummer,
    2. sonst über die Adresse: Nach einem Zählertausch steht in `Nodes_Edges.ods` noch die alte Nummer. Der neue
       Zähler findet seinen Anschlusswert dann über die gemeinsame Adresse.
    3. aber nur, wenn an der Adresse genau ein Zähler mit Daten steht. Stehen dort mehrere, gilt der Wert als
       „geteilt“, und keiner bekommt ihn.
- **Adresskorrektur:** Zwei Zähler (80912175 und 80912177) stehen in `Nodes_Edges.ods` und im Blatt 2024 von
  `Zuordnung.xlsx` unter der Hausnummer eines anderen Hauses desselben Eigentümers. Die richtige Adresse steht als
  Korrektur im Code.

| Herkunft des Anschlusswerts | HAST |
|---|---|
| direkt über die Zählernummer | 85 |
| über die Adresse (nach Zählertausch) | 2 |
| geteilt (zwei Stationen auf einem Grundstück) | 2 |
| fehlt (Zähler steht in keiner Tabelle) | 4 |

## 6 · Kennzahlen je Station

Clustering braucht eine Tabelle mit einer Zeile je Station. Jede Stundenreihe wird deshalb auf 14 Kennzahlen
verdichtet, zum Beispiel:

| Kennzahl | Rechnung |
|---|---|
| `rt_mean_winter` | Mittel der Rücklauftemperatur im Winter (Dezember bis März) |
| `dt_mean_loaded` | Mittel der Spreizung, wenn die Station läuft (über 0,5 kW) |
| `summer_flow_baseline` | Median des Durchflusses im Sommer (Juni bis August), Hinweis auf Dauerdurchfluss |
| `flow_ceiling_slope_per_month` | Trend des oberen Durchflusses (95.-Perzentil) je Monat, Hinweis auf einen zusetzenden Filter |
| `flow_short_cycle_power` | Anteil der 4- bis 12-Stunden-Schwingung im Durchfluss (FFT), Hinweis auf Regelhysterese |
| `idle_share` | Anteil der gemessenen Stunden mit fast keiner Leistung |

Was die Kennzahlen im Clustering zeigen, steht unter *Vorgehen → Merkmale und Clustering*.
