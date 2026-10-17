---
name: zeitreihen-features
description: Feature-Engineering und zeitliche Aggregation der stündlichen HAST-Zählerdaten (Zustandsfenster, persistente Anomalien, Qualitätskriterien). Verwenden bei Aufgaben wie „Stundendimension aggregieren", „Zeitfenster-Features bauen", „Anomalien über längere Zeit", „features.py erweitern".
---

# Zeitreihen-Features & zeitliche Aggregation (HAST)

Ziel: Aus stündlichen Zählerdaten zeitlich aufgelöste Zustandsfeatures
bauen, statt ein Durchschnittsprofil über die gesamte Historie — denn
`hast_features.csv` mittelt über alles und beschreibt vergangene Zustände
(Fall 68956351 gilt dort noch als Problemfall, obwohl repariert).

## Datenbasis

- Loader `src/load_timeseries.py`: führt Exportgenerationen
  (`<nr>__n.csv` / `<nr>_2025n.csv`) zusammen, dedupliziert, Stundenraster.
- Kanäle: kumulative Energie (kWh), Volumenstrom (l/h), Leistung (kW),
  ΔT, Vorlauf/Rücklauf (°C), kumulatives Volumen (m³).
- Zähler↔Adresse jahresbezogen über `Zuordnung.xlsx`
  (`src/load_begehungen.py` zeigt den Umgang mit Zählerwechseln).
- Qualitätsregeln aus `src/meter_quality.py` (365-Tage-Fenster,
  Mindestabdeckung 60 %) als Referenz — aber Fenster parametrisieren.

## Vorgehen

1. **Fensterdefinition wählen und begründen.** Referenz: 14-Tage-Zustände
   aus Notebook 02 („Stundendimension: 14-Tage-Zustände statt ein Profil
   für zwei Jahre"). Fensterlänge als Parameter, Überlappung angeben.
   Kompromiss: kurz genug für zeitliche Auflösung um Begehungen, lang
   genug für stabile Mittelwerte.
2. **Features pro Fenster** analog `compute_hast_features()` berechnen
   (Rücklauf-Mittel Winter/geladen, Spreizung, Leerlaufanteil,
   Sommer-Durchfluss-Baseline etc.). Saisonale Features (Winter/Sommer)
   innerhalb des Fensters sauber trennen oder als Jahreszeit-Kontext
   mitführen.
3. **`full_load_hours` korrekt normieren**: Energie im Fenster auf
   Fensterstunden beziehen bzw. auf 8760 h/Jahr hochrechnen — niemals
   durch die Gesamthistorie teilen (bekannter Bug in `src/features.py:130`).
4. **Persistente Anomalien:** Anomalie-Indikatoren (Basis in Notebook
   `hast_zeitreihen_analyse.ipynb`, Abschnitt 7, und Scores aus Notebook
   02, Schritt 18) fensterweise berechnen und nur als Befund zählen, wenn
   sie **über mehrere aufeinanderfolgende Fenster** bestehen. Einzelne
   Ausreißerfenster separat ausweisen.
5. **Qualität transparent machen:** Abdeckung je Fenster (coverage)
   mitführen; Fenster mit zu geringer Abdeckung markieren statt still
   zu verwerfen. Nicht zu viel wegfiltern — Team-Vorgabe.
6. **Zählerwechsel kennzeichnen:** Fenster, die einen Zählertausch
   enthalten (Zuordnung.xlsx, fünf bekannte Adressen), flaggen — sie
   vergleichen sonst zwei Geräte.
7. **Ausgabe:** langes Format (Zähler × Fenster × Feature) nach
   `data/processed/`; dient als Eingabe für `clustering-benchmark`
   (Cluster je Zeitfenster → Cluster-Wanderung) und für den
   Regressions-/Entscheidungsbaum auf Fenster-Features.

## Fallstricke

- Reale Stundenspitzen übersteigen die Vertragsleistung — Schwellen aus
  Vertragsdaten nicht als harte Filter verwenden.
- `72167783`: Rücklauf sprang von 18,6 auf 71,0 °C nach Begehung —
  Inbetriebnahme oder Fehler, **vor** jeder Mittelwertbildung klären.
- Export-Overlaps zwischen den zwei CSV-Generationen sind bereits
  dedupliziert — kein zweites Mal deduplizieren und dadurch Lücken
  erzeugen.
