# Dokumentation — Fernwärme Fault Detection (ÜZ Mainfranken / Wiesentheid)

Projektseminar JMU Würzburg in Kooperation mit ÜZ Mainfranken.
Ziel: datengestützte Fault Detection und Performance-Optimierung für
Hausübergabestationen (HAST) im Fernwärmenetz Wiesentheid, später
skalierbar auf weitere ÜZ-Teilnetze.

## Inhalt

| Dokument | Inhalt |
|---|---|
| [datenquellen.md](datenquellen.md) | Alle Rohdatenquellen, verifizierte Kennzahlen, bekannte Datenprobleme |
| [datensichtung.md](datensichtung.md) | Generiertes Daten-Profiling der echten Zeitreihen (`src/profile_timeseries.py`) |
| [echte-daten-integration.md](echte-daten-integration.md) | Generiert: Qualitätsklassen, Auswahltrichter, Baseline-Ergebnis auf echten Daten (`src/detect_real.py`) |
| [dashboard.md](dashboard.md) | Streamlit-Dashboard: Start, Ampellogik (Winter-Rücklauf), Datenquellen, bewusste Auslassungen |
| [ml-klassifikator.md](ml-klassifikator.md) | Generiert: ML-Zustandsklassifikation vs. Baseline, Leakage-Analyse, ehrliches Negativergebnis (`src/ml_classifier.py`) |
| [pipeline.md](pipeline.md) | Module, Datenfluss, CLI-Kommandos, erzeugte Artefakte |
| [annahmen-limitationen.md](annahmen-limitationen.md) | Annahmen, Grenzen der aktuellen Ergebnisse, gescheiterte/verworfene Ansätze |
| [naechste-schritte.md](naechste-schritte.md) | Priorisierte To-dos und offene Entscheidungen |

## Begriffe (bewusst getrennt halten)

- **HAST** — Hausübergabestation, ein Kundenanschluss mit Wärmemengenzähler.
- **Junction** — reiner Topologie-Knoten im logischen Graph, kein Kunde.
- **Logischer Graph** — abstrakte Netztopologie aus `Nodes_Edges.ods`
  (Adressen als Knoten). Visualisierung: `outputs/logical_topology.png`.
- **Räumlicher Graph** — physische Rohrgeometrie aus den Shapefiles
  (Koordinaten als Knoten). Visualisierung: `outputs/network_map_*.html`.
- **Dashboard-Karte** — geografische Folium-Karte (`outputs/dashboard_map.html`),
  nicht mit dem abstrakten Graphen verwechseln.

## Datenschutz

`data/raw/` enthält vertrauliche ÜZ-Daten (Adressen, Kunden- und
Zählernummern, Verbräuche) und ist gitignored — niemals committen oder
in Review-Artefakte aufnehmen. Auch `data/processed/` und `outputs/`
können abgeleitete sensible Daten enthalten; vor Weitergabe prüfen.
