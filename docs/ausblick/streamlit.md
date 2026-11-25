# Dashboard als Streamlit-App

Das Dashboard der Abgabe ist die HTML-Datei aus Notebook 37 (siehe [Dashboard bedienen](../ergebnisse/dashboard_bedienen.md)).
Zusätzlich liegt im Repository eine Fassung als Streamlit-App. Sie zeigt dasselbe: dieselben drei Reiter, dieselbe
Bedienung und dieselben Regeln. Für die Ergebnisse der Arbeit wird sie nicht gebraucht. Sie ist ein möglicher nächster
Schritt und kann bei Interesse genutzt oder weiter ausgebaut werden.

## Aufbau

- `src/dashboard_app.py` baut die Oberfläche, `src/dashboard_app_logik.py` enthält die Regeln dahinter. Die Regeln
  sind das JavaScript der HTML-Fassung, in Python nachgebaut.
- Die App liest ihre Daten aus der fertigen HTML-Datei `notebooks/fernwaerme_dashboard_final.html`. Sie rechnet keine
  Modelle und lernt nichts.
- `tests/test_dashboard_app.py` vergleicht beide Fassungen Zeichen für Zeichen, unter anderem Hausfenster, Legende,
  Farben der Häuser und Handlungsliste. Dafür läuft das JavaScript in Node.js. Ohne Node.js oder ohne die HTML-Datei
  werden diese Vergleiche übersprungen.

## Vor- und Nachteile gegenüber der HTML-Datei

**Vorteile**

- Läuft die App auf einem Server der ÜZ, sehen alle denselben Stand. Die HTML-Datei muss nach jedem Lauf neu verteilt
  werden.
- Nach einem neuen Lauf von Notebook 37 oder `python -m src.aktualisieren` zeigt die App beim nächsten Neuladen
  automatisch die neuen Daten.
- Erweiterungen werden in Python geschrieben statt in JavaScript, etwa ein Formular für die Rückmeldung nach einer
  Begehung oder ein Export der Handlungsliste.
- Es wird keine Datei mit Adressen verschickt. Die HTML-Datei lässt sich dagegen beliebig weitergeben.

**Nachteile**

- Es braucht Python, die zusätzlichen Pakete und einen laufenden Server. Die HTML-Datei öffnet man per Doppelklick.
- Die App hängt weiter an der HTML-Datei aus Notebook 37. Ändert sich deren Aufbau, muss `src/dashboard_app_logik.py`
  nachgezogen werden. Die Tests zeigen, wo beide Fassungen auseinanderlaufen.

## Installation und Start

Voraussetzung ist, dass Notebook 37 gelaufen ist und `notebooks/fernwaerme_dashboard_final.html` vorliegt (siehe
[Ausführung bis zum Dashboard](../installation/ausfuehrung.md#8-notebook-37-dashboard)). Die Pakete für Streamlit
gehören nicht zur normalen Installation und stehen deshalb in einer eigenen Datei `requirements-streamlit.txt`.

**Lokal:** Im Projektordner, mit aktivierter Umgebung wie unter [Lokaler Start ohne Docker](../installation/lokal.md):

```bash
pip install -r requirements-streamlit.txt
streamlit run src/dashboard_app.py
```

Danach http://localhost:8501 im Browser öffnen. `Strg+C` im Terminal beendet die App.

**Mit Docker:** Das Image enthält Streamlit nicht, und `docker compose build` oder `docker compose up` installieren
und starten es auch nicht. Nur bei Bedarf installiert der folgende Befehl die Pakete im Container und startet die App:

```bash
docker compose run --rm -p 127.0.0.1:8501:8501 jupyter sh -c "pip install 'streamlit>=1.50' 'streamlit-folium>=0.25' 'plotly>=5.20' && streamlit run src/dashboard_app.py --server.address 0.0.0.0 --server.headless true"
```

Danach ebenfalls http://localhost:8501 öffnen. Weil der Container nach dem Beenden gelöscht wird, installiert der
Befehl die Pakete bei jedem Start neu.

Wie die HTML-Datei zeigt die App Adressen. Sie ist nur für den internen Gebrauch bestimmt und sollte nur im Netz der
ÜZ erreichbar sein.

## Mögliche nächste Schritte

- Die App auf einem Server der ÜZ betreiben und `python -m src.aktualisieren` regelmäßig laufen lassen (siehe
  [Betrieb mit neuen Daten](betrieb.md)).
- Ein Formular für die Rückmeldung nach jeder Begehung ergänzen, mit den Angaben aus
  [Vorschlag für künftige Begehungen](begehungen.md). So entstehen die Daten, die für eine Prüfung der Modelle fehlen.
- Die Daten direkt aus `outputs/dashboard/` und dem Netz-Cache lesen statt aus der HTML-Datei. Dann braucht die App
  Notebook 37 nicht mehr.
