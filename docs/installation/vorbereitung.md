# Vorbereitung

Das Projekt lässt sich auf zwei Wegen ausführen: mit Docker oder lokal mit Python. Beide setzen dasselbe voraus: den
Code aus dem Repository, die Daten der ÜZ und ausreichend Speicherplatz auf dem Rechner. Diese Seite gilt für beide
Wege. Danach folgt [Start mit Docker](docker.md) oder [Lokaler Start ohne Docker](lokal.md).

## Docker oder lokale Installation

| | Docker | lokal |
|---|---|---|
| Installation | Docker Desktop | Python 3.11 und die Pakete aus `requirements.txt` |
| Paketstände | fest im Image, auf jedem Rechner gleich | abhängig von der eigenen Installation |
| Grafikkarte | wird nicht genutzt, PyTorch rechnet auf dem Prozessor | wird genutzt, sofern vorhanden |
| geeignet für | Ergebnisse nachvollziehen, Dashboard erzeugen, Tests | LSTMs neu lernen, Änderungen am Code |

- Zum Nachvollziehen der Ergebnisse genügt Docker. Die lernenden Notebooks laden die gespeicherten Gewichte aus
  `notebooks/models/` oder halten vor dem Lernen an.
- Neu gelernt wird nur, wenn im Notebook `SELBST_TRAINIEREN = True` gesetzt ist (siehe
  [Ausführung](ausfuehrung.md#gespeicherte-modelle-oder-selbst-lernen)). Mit Grafikkarte dauert das Minuten, auf dem
  Prozessor mehrere Stunden.

## Voraussetzungen

- Git oder alternativ der ZIP-Download von GitHub
- Internetzugang beim ersten Lauf: `python -m src.weather` lädt die Außentemperatur vom DWD, die Karte im Dashboard
  lädt Kartenkacheln.
- Speicherplatz: Die Rohdaten umfassen ca. 400 MB. Nach einem vollständigen Lauf kommen ca. 400 MB aufbereitete Daten
  und ca. 150 MB Ergebnisse hinzu, mit Docker zusätzlich ca. 5 GB für das Image.
- Für Docker mindestens 4 GB Arbeitsspeicher (siehe [Start mit Docker](docker.md))

## Befehle im Terminal ausführen

Alle Befehle in dieser Dokumentation werden in einem Terminal eingegeben, einem Fenster für Textbefehle.

| Betriebssystem | Programm | so zu finden |
|---|---|---|
| Windows | PowerShell | Startmenü, nach „PowerShell“ suchen |
| macOS | Terminal | Spotlight (Cmd+Leertaste), nach „Terminal“ suchen |
| Linux | Terminal | Anwendungsmenü |

- Jede Zeile in einem grauen Kasten ist ein eigener Befehl. Die Befehle werden einzeln und nacheinander ausgeführt:
  Zeile kopieren, im Terminal einfügen, mit Enter bestätigen und warten, bis der Befehl fertig ist. Fertig ist er, wenn
  wieder die leere Eingabezeile erscheint.
- Text hinter `#` ist eine Erläuterung. Er kann mitkopiert werden, das Terminal ignoriert ihn.
- Alle Befehle beziehen sich auf den Projektordner. Ein neu geöffnetes Terminal steht im persönlichen Ordner. Mit `cd`
  wird in den Projektordner gewechselt, z. B. `cd projektseminar`.
- Manche Befehle starten ein Programm, das weiterläuft, z. B. JupyterLab. Solange es läuft, nimmt dieses Terminal keine
  weiteren Befehle an. Weitere Befehle werden dann in einem zweiten Terminalfenster ausgeführt, nach einem erneuten
  `cd` in den Projektordner. `Strg+C` im ersten Fenster beendet das Programm.

## Repository herunterladen

**Mit Git:** Im Terminal ausführen:

```bash
git clone https://github.com/ivelinayna/projektseminar.git
cd projektseminar
```

`git clone` lädt das Repository in einen neuen Ordner `projektseminar`, `cd projektseminar` wechselt in diesen Ordner.
Unter Windows muss Git vorher installiert werden ([git-scm.com](https://git-scm.com/)).

**Ohne Git:** Auf der GitHub-Seite des Projekts *Code → Download ZIP* wählen, die Datei entpacken und im Terminal mit
`cd` in den entpackten Ordner wechseln.

Dieser Ordner ist der Projektordner. Alle weiteren Befehle werden dort ausgeführt.

## Daten der ÜZ ablegen

Die Daten der ÜZ sind vertraulich und nicht im Repository enthalten. Ohne sie läuft kein Notebook. Sie werden ohne
Unterordner und mit den Dateinamen der Lieferung nach `data/raw/` kopiert.

| Datei | Inhalt | gebraucht für |
|---|---|---|
| `<Zählernummer>__n.csv`, `<Zählernummer>_2025n.csv` | Stundenwerte je Zähler | alle Auswertungen |
| `<Zählernummer>.ods` | Nachlieferung für fünf Zähler bis Juli 2026 | alle Auswertungen |
| `*Ergebnis_Optimierung_FW*.xlsx` | Begehungen | Labels, Modelle, Dashboard |
| `Zuordnung.xlsx` | Zählernummer zu Abnahmestelle, je Jahr ein Blatt | Begehungen, Netz, Dashboard |
| `Nodes_Edges.ods` | logisches Netz mit Anschlusswert | Netz, Dashboard |
| `Leitungsverlauf_LineString.*`, `_Point.*`, `_MultiPoint.*` | Rohrverlauf als Shapefile (je `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`) | Netz, Dashboard |
| `Leitungsverlauf.kml` | Rohrverlauf als KML | optional, Notebooks 31 und 33 |
| `zensus/.../Zensus2022_Baujahr_JZ_100m-Gitter.csv` | Gebäude nach Baujahr im 100-m-Gitter (öffentlich, etwa 200 MB) | optional |

Inhalt und Eigenheiten der Dateien beschreiben [Zählerdaten](../datengrundlage/zaehlerdaten.md), [Begehungen](../datengrundlage/begehungen.md)
und [Netz und Zuordnung](../datengrundlage/netz_und_zuordnung.md).

### Handliste mit Koordinaten

- Die Lage der Häuser stammt aus einer von Hand gepflegten Liste `adressen_koordinaten.ods` mit den Spalten `adresse`,
  `koordinate` und `quelle`. Da sie Adressen enthält, liegt auch sie nicht im Repository.
- Sie gehört nach `data/manual/adressen_koordinaten.ods`.
- Ohne diese Liste laufen alle Modelle, nicht aber die Netzkarte und das Dashboard.

### Handtabellen für Notebook 38

- Notebook 38 (Bayes-Diagnose, Anhang) liest zwei von Hand gepflegte Tabellen:
  `data/manual/fehler_symptom_matrix_entwurf.xlsx` und `data/manual/pruefliste_begehungsnotizen.xlsx`.
- Sie liegen nicht im Repository. Ohne sie bricht nur Notebook 38 ab, alle anderen laufen.

### Kodierbogen für Notebook 03

- Notebook 03 liest den von Hand gepflegten Kodierbogen `data/processed/kodierbogen_freitexte.xlsx` (Blatt `Kodierung`).
- Er liegt nicht im Repository. Ohne ihn überspringt Notebook 03 nur den Abgleich mit der Handkodierung.

### Außentemperatur

Die Außentemperatur der DWD-Station Kitzingen muss nicht abgelegt werden. `python -m src.weather` lädt sie beim ersten
Lauf nach `data/raw/weather/`. Danach liest das Projekt aus diesem Zwischenspeicher.

## Beim Ausführen erzeugte Dateien

| Ordner | Inhalt | geschrieben von |
|---|---|---|
| `data/processed/` | Stundenreihen je Zähler und alle Zwischentabellen | Notebook 00 und die folgenden |
| `outputs/` | Bilder, Ergebnistabellen, Daten für das Dashboard | Notebooks und Befehle |
| `notebooks/models/` | Gewichte der LSTMs | Notebooks 27 und 28 |
| `models/` | Modellpakete für das Dashboard | Notebook 35 oder die Befehle unter [Ausführung](ausfuehrung.md) |
| `notebooks/daten_cache/` | Netz-Cache | Notebook 31 |
| `notebooks/fernwaerme_dashboard_final.html` | fertiges Dashboard | Notebook 37 |

Diese Ordner und Dateien sind in der Datei `.gitignore` eingetragen. Git übernimmt sie deshalb nicht ins Repository,
sie bleiben nur auf dem eigenen Rechner.

## Datenschutz

- Rohdaten, Zwischenergebnisse, Gewichte und Modellpakete werden nie ins Repository übernommen (committet). Sie stammen
  aus Firmendaten der ÜZ und enthalten Zählernummern.
- Die Netz-Notebooks 31 bis 33 und die Dashboard-HTML zeigen Adressen. Sie sind nur für den internen Gebrauch bestimmt.
- Wer am Code mitarbeitet, prüft vor jedem Commit mit `git status`, welche Dateien übernommen werden. Erscheint dort
  eine Datei aus `data/`, `outputs/` oder `models/`, ist die `.gitignore` unvollständig.
