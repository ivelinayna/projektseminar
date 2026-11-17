# Daten

Alle Rohdaten kommen von der ÜZ Mainfranken. Sie sind vertraulich und liegen nur lokal in `data/raw/`. Der Ordner ist
gitignored.

## Datenschutz

- `data/raw/`, `data/processed/`, `data/manual/`, `outputs/` und `models/` werden nie committet.
- In der Doku stehen keine Adressen, Kundennummern oder V-PINs. Stationen heißen hier nur nach ihrer Zählernummer.
- Die Dashboard-HTML und einige Netz-Notebooks zeigen Adressen. Sie sind nur für den internen Gebrauch.

## Quellen

| Quelle | Datei in `data/raw/` | Inhalt |
|---|---|---|
| Zählerdaten | `<Zählernummer>__n.csv`, `<Zählernummer>_2025n.csv` | Stundenwerte je Zähler |
| Nachlieferung | `<Zählernummer>.ods` | fünf Zähler bis Juli 2026 |
| Begehungen | `*Ergebnis_Optimierung_FW*.xlsx` | 66 Begehungen mit Alt- und Neuwerten und Freitext |
| Zuordnung | `Zuordnung.xlsx` | Zählernummer zu Abnahmestelle, je Jahr ein Blatt |
| Netz (logisch) | `Nodes_Edges.ods` | Knoten, Kanten, Anschlusswert |
| Netz (räumlich) | `Leitungsverlauf_*.shp` und Begleitdateien | Rohrverlauf als Geometrie |
| Außentemperatur | wird geholt, Cache in `data/raw/weather/` | DWD-Station 2600 Kitzingen, stündlich |
| Netz (KML) | `Leitungsverlauf.kml` | Rohrverlauf für die Karten in Notebook 34 und 36, optional |
| Baujahr | `zensus/.../Zensus2022_Baujahr_JZ_100m-Gitter.csv` | Zensus 2022 im 100-m-Gitter, öffentlich, optional |

Der Dateiname der Begehungstabelle ändert sich zwischen Lieferungen. Der Code sucht sie deshalb per Muster.

### Zählerdaten

- Spalten: Zeitstempel, Energie (kWh), Volumenstrom (l/h), Leistung (kW), Spreizung (°C), Vorlauf (°C), Rücklauf
  (°C), Volumen (m³).
- Energie und Volumen sind Zählerstände, sie wachsen also immer weiter.
- Zwei Exportgenerationen überlappen: bis etwa Mai 2024 und bis etwa Juli 2025. Zusammen 154 Dateien für 101 Zähler ab
  etwa November 2021.
- Bei gleichem Zeitstempel gewinnt die neuere Datei.
- Der Zeitstempel hat oft einen Minutenversatz (z. B. `13:01`). Es gibt vereinzelt negative Werte und Lücken.

### Nachlieferung (ODS)

- Fünf Zähler mit Daten bis 20.07.2026, gut ein Jahr länger als die CSV.
- Energie und Volumen fehlen. Notebook 00 rechnet sie aus Leistung und Durchfluss nach und markiert diese Zeilen.
- Die Werte stehen mit Faktor 1000. Der Faktor wird aus den Daten bestimmt.
- Im Überlappungszeitraum stimmen ODS und CSV überein. Zusammenführen ist deshalb zulässig.

### Begehungen

- 66 Begehungen, die Ground Truth des Projekts.
- Alt- und Neuwerte: Anlagenkonfiguration, Heizzeiten, Vertragsleistung, Regelparameter.
- Ja/Nein-Angaben zu Filter, Ventil, Stellmotor, Dämmung und Regler.
- Freitext des Monteurs bei 57 von 66 Begehungen. Die Notebooks 16 und 19 ordnen ihn Fehlerkategorien zu.

### Zuordnung und Netz

- Zählernummer zu Abnahmestelle immer über `Zuordnung.xlsx` (deckt alle Zähler ab).
- Den Anschlusswert in kW gibt es nur in `Nodes_Edges.ods`. Beide Quellen werden kombiniert.
- Adressen werden immer über `load_data._normalize_address()` verglichen. Ein einfacher Textvergleich trifft nur einen
  kleinen Teil.

## Aufbereitung in Notebook 00

Notebook 00 ist der einzige Ladeweg für die Stundenreihen.

- Es schreibt je Zähler eine Stundenreihe nach `data/processed/real_meters/`.
- Alle anderen Notebooks und Module lesen diese Reihen über `src/nb00_daten.lade_serien()`.
- Stationsmerkmale kommen aus `nb00_daten.stationsfeatures()`. Nur so stimmen die Zählerstände der Nachlieferung.
- Nach jeder neuen Datenlieferung zuerst Notebook 00 ausführen, dann die anderen.
- Notebook 01 füllt kurze Lücken in den Reihen und zeigt, wie viele Stunden fehlen.

## Bekannte Probleme

| Problem | Folge |
|---|---|
| 8 Stationen hängen im logischen Netz an keiner Kante | fehlen in Netzauswertungen |
| OpenStreetMap kennt im Neubaugebiet zu wenige Hausnummern | Kartenpositionen einzelner Stationen sind ungenau |
| Zählerwechsel ohne Datum (zwei Adressen) | Reihen lassen sich nicht zusammensetzen |
| CSV endet im Juli 2025 | netzweite Auswertungen enden dort |
| Bei 8 Begehungen fehlt das Datum, bei einigen Zählern beginnt die Reihe erst danach | diese Fälle fehlen im Vorher/Nachher-Vergleich |
| Begehungstabelle lässt Reparaturen aus (Beispiel Zähler 68956351) | Labels sind unvollständig |
| Zähler 41704231 und 41704232 sind Temperaturfühler im Heizhaus | keine Übergabestationen |
| Zähler 86792512 ist laut Zuordnung ein BHKW | Sonderfall, kein normaler Hausanschluss |
