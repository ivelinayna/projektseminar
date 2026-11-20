# Dashboard

Das Dashboard zeigt für jede Station, ob Handlungsbedarf besteht und welche Maßnahme die Modelle vorschlagen.

## Streamlit statt HTML-Datei

- Das Dashboard ist eine Streamlit-App: `src/dashboard_app.py`.
- Früher war es eine HTML-Datei aus Notebook 37. Die App kann dasselbe: gleiche Reiter, Bedienung, Farben, Texte und Regeln.
- Die Regeln stehen in `src/dashboard_app_logik.py`, nachgebaut aus dem JavaScript der HTML-Fassung.
- `tests/test_dashboard_app.py` lässt das alte JavaScript in Node.js laufen und vergleicht Zeichen für Zeichen mit der App.
- Die Modelle rechnen vorher. Die App liest nur fertige Daten, braucht also kein `torch`.
- Die HTML-Datei gibt's noch, wenn man in Notebook 37 `HTML_SCHREIBEN = True` setzt.
- Die erste Streamlit-App (Rücklauf-Ampel, Juli 2026) ist archiviert und nicht mehr im Repo.

## Inhalt

Drei Reiter:

| Reiter | Inhalt |
|---|---|
| Karte | Zeitregler mit Abspielen. Stationen auf dem Rohrbaum, Fließrichtung und Leistung in den Leitungen. Färbung nach Dringlichkeit, Maßnahme, Wächter-Meldungen, Potenzial oder Messwerten. Klick öffnet ein Hausfenster mit Empfehlung, Verdacht, Stand im Netz, Veränderung und Befund. |
| Handlungsliste | Alle Zähler nach Dringlichkeit sortiert. Klick springt zur Station auf der Karte. |
| So funktioniert's | Welche Frage mit welchem Modell beantwortet wird und warum. |

## Erzeugen

Reihenfolge:

1. Notebook 00 (Stundenreihen) und `python -m src.weather` (Außentemperatur).
2. Modellpakete bauen: Notebook 35 oder die Befehle unter [Schnellstart](schnellstart.md).
3. `python -m src.dashboard_daten` wendet die Pakete auf die aktuellen Daten an und schreibt nach `outputs/dashboard/`.
4. Notebook 31 ausführen. Es baut den Netz-Cache `notebooks/daten_cache/`.
5. Notebook 37 ausführen. Es schreibt `outputs/dashboard/app/` (`daten.json` mit Karte und Modellergebnissen, `messwerte.npy` mit den Stundenwerten).

Starten:

```bash
streamlit run src/dashboard_app.py     # im Repo-Ordner, dann http://localhost:8501
```

- mit Docker: `docker compose up dashboard`, dann http://localhost:8000.
- Die Kartenkacheln kommen aus dem Internet. Ohne Netz bleibt der Hintergrund leer, Rohrplan und Gebäudekanten sind trotzdem da.

## Unterschiede zur HTML-Fassung

Inhalt und Regeln sind gleich. Anders ist nur, was Streamlit nicht hergibt:

- Abspielen ist langsamer, ca. 1 Schritt pro Sekunde statt 4. Jeder Schritt lädt die Seite neu.
- Gesamtleistung: Klicken setzt den Zeitpunkt, Ziehen geht nicht. Dafür gibt's den Zeitregler.
- „Karte“ in der Handlungsliste zoomt immer auf Stufe 18, auch wenn man schon näher dran war.

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

- `outputs/dashboard/app/` und die Dashboard-HTML enthalten Adressen. Beides ist gitignored und nur für den internen Gebrauch.
- Keine Screenshots davon in diese Doku einbinden.
