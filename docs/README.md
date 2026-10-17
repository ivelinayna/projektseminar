# Dokumentation — Fernwärme Fault Detection (ÜZ Mainfranken / Wiesentheid)

Projektseminar JMU Würzburg in Kooperation mit ÜZ Mainfranken.
Ziel: datengestützte Fault Detection und Performance-Optimierung für
Hausübergabestationen (HAST) im Fernwärmenetz Wiesentheid, später
skalierbar auf weitere ÜZ-Teilnetze.

## Inhalt

| Dokument | Inhalt |
|---|---|
| [pipeline.md](pipeline.md) | Module, Datenfluss, CLI-Kommandos, erzeugte Artefakte |
| [output_NB12-15.md](output_NB12-15.md) | Ergebnisse der Notebooks 12 bis 15 mit Grafiken: Ternärdiagramme, Stationsbilder, Kennlinienmonitor, Begehungsnotizen |

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
