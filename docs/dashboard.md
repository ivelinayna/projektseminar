# Dashboard

Das Dashboard zeigt für jede Station, ob Handlungsbedarf besteht und welche Maßnahme die Modelle vorschlagen.

## Warum eine HTML-Datei und kein Streamlit

- Das Hauptdashboard ist eine einzelne HTML-Datei aus Notebook 37.
- Sie läuft in jedem Browser, ohne Python und ohne Server. Man kann sie per Doppelklick öffnen oder weitergeben.
- Die Modelle rechnen vorher. Das Dashboard liest nur fertige Tabellen. Deshalb ist es schnell und braucht kein `torch`.
- Streamlit hätte einen laufenden Python-Server gebraucht. Für eine Abgabe und für die ÜZ ist die Datei einfacher.
- Die erste Fassung als Streamlit-App (Rücklauf-Ampel, Juli 2026) ist archiviert und nicht mehr im Repo.

## Inhalt

Drei Reiter:

| Reiter | Inhalt |
|---|---|
| Karte | Stationen auf dem Netzplan. Färbung nach Dringlichkeit, Maßnahme, Wächter-Meldungen, Potenzial oder Messwerten. Klick öffnet ein Hausfenster mit Empfehlung, Verdacht, Stand im Netz, Veränderung und Befund. |
| Handlungsliste | Alle Zähler nach Dringlichkeit sortiert. Klick springt zur Station auf der Karte. |
| So funktioniert's | Welche Frage mit welchem Modell beantwortet wird und warum. |

## Erzeugen

Reihenfolge:

1. Notebook 00 (Stundenreihen) und `python -m src.weather` (Außentemperatur).
2. Modellpakete bauen: Notebook 35 oder die Befehle unter [Schnellstart](schnellstart.md).
3. `python -m src.dashboard_daten` wendet die Pakete auf die aktuellen Daten an und schreibt nach `outputs/dashboard/`.
4. Notebook 31 ausführen. Es baut den Netz-Cache `notebooks/daten_cache/`.
5. Notebook 37 ausführen. Es schreibt `notebooks/fernwaerme_dashboard_final.html`.

Ansehen:

- Datei direkt im Browser öffnen, oder
- mit Docker: `docker compose up dashboard`, dann http://localhost:8000/fernwaerme_dashboard_final.html.

Die Karte lädt Kartenkacheln und die Bibliothek Leaflet aus dem Internet. Ohne Netz bleibt der Hintergrund leer.

## Was in `outputs/dashboard/` steht

`src/dashboard_daten.py` rechnet in fünf Schritten:

1. Stundenreihen aus Notebook 00 und Außentemperatur laden.
2. Wächter anwenden: Tagesmonitor (Paket `normalmodell`) und Prognose-LSTM (Paket `prognose_lstm`).
3. Folie-5-Klasse für die letzte Heizperiode und für die Zeit vor den Begehungen (Paket `fehlerklassen`).
4. Netzvergleich und Potenzial: Rang im Netz, Fehlerbild, Abstand zum besten Viertel.
5. Empfehlung je Station, Netzeffizienz je Monat und Optimierungspotenzial.

Alles nur mit Zählernummern. Die Adressen kommen erst in Notebook 37 aus der Zuordnung dazu.

## Weitere Exporte

| Datei | Erzeugt von | Inhalt |
|---|---|---|
| `notebooks/dashboard_export.py` | Notebooks 31 und 32 | erste Fassung der Netzkarte |
| `notebooks/dashboard_monitor.py` | Notebook 33 | Netzkarte mit Monitor-Status |
| `src/dashboard_map.py` | `python -m src.main --dashboard` | einfache Folium-Karte |

## Datenschutz

- Die Dashboard-HTML enthält Adressen. Sie ist gitignored und nur für den internen Gebrauch.
- Keine Screenshots davon in diese Doku einbinden.
