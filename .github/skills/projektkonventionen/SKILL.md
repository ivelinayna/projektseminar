---
name: projektkonventionen
description: Verbindliche Arbeitsregeln für das Fernwärme-Projektseminar — Git ohne KI-Attribution, Datenschutz für ÜZ-Rohdaten, Umgang mit Negativbefunden, Notebook-/Doku-Stil, Sprache. Immer beachten bei Commits, Doku, Notebooks und Datenhandling in diesem Repo.
---

# Projektkonventionen (Projektseminar ÜZ Mainfranken)

Diese Regeln gelten für jede Änderung im Repo.

## Git & Commits — keine KI-Attribution

- **Niemals** `Co-authored-by`-Trailer oder sonstige Hinweise auf
  Copilot/Claude/KI-Assistenten in Commit-Messages, PR-Beschreibungen,
  Code-Kommentaren oder Docs.
- Commit-Autor/-Committer ist ausschließlich die lokal konfigurierte
  Nutzer-Identität; `git config user.name`/`user.email` nicht verändern.
  Keine KI-typischen Branch-Präfixe (z. B. `copilot/...`) für Branches,
  die gepusht werden.
- Commit-Nachrichten: Deutsch, kurz, im Stil der Historie, z. B.
  „Wirkungsanalyse: Zell-Notes, Begehungsexport, Test und Doku" oder
  „K-Means-Notebook: Stationscluster mit Zell-Notes und Lauf-Kontext".
- Vor jedem Commit: `git diff --cached` prüfen, dass keine Daten aus
  `data/` oder `outputs/` und keine KI-Verweise enthalten sind.

## Datenschutz

- `data/raw/`, `data/processed/`, `data/manual/`, `outputs/` sind
  gitignored — so belassen. Keine Zählerdaten, Adressen oder Kundendaten
  in committed Dateien kopieren.
- Notebook-Outputs vor dem Commit leeren, wenn sie Zeitreihen auf
  Stationsebene oder Adressen zeigen; aggregierte Tabellen sind ok.

## Wissenschaftliche Praxis

- **Fehlgeschlagene Ansätze dokumentieren, nicht löschen** — sie gehören
  in die Abgabe. Vorbild: `docs/ml-klassifikator.md` (Negativergebnis
  sauber ausgewertet).
- Jede Analyse endet mit ehrlicher Einordnung: was ist belastbar, was ist
  schwach, was blockiert. Signifikanzniveaus und Basisraten nennen.
- **[Entscheidung]-Punkte** (Baseline-Rekalibrierung,
  Fehlertyp→Maßnahme-Mapping, Zählertausch-Stitching, Geocoding,
  Waisen-HAST) nicht eigenmächtig festlegen — als offene Frage in
  `docs/naechste-schritte.md` dokumentieren — die Datei ist gitignored
  (nur lokal, niemals committen/pushen).
- Nicht zu viel wegfiltern; Ausschlüsse immer mit Grund tabellieren.

## Code & Struktur

- Exploration in `notebooks/` (fortlaufend nummeriert, deutschsprachige
  Zell-Notes, „Zusammenfassung & Bewertung" am Ende — Stil der Notebooks
  00–03), wiederverwendbare Logik nach `src/`, Tests nach `tests/`
  (pytest, vorhandene Testdateien als Muster).
- Adress-Joins immer über `_normalize_address()` aus `src/load_data.py`.
- Keine Wiesentheid-Hardcodes in Loadern (Skalierung auf weitere
  Teilnetze ist Ziel).
- Bestehende Code-Identifiers (teils englisch) nicht umbenennen; neue
  Docs, Kommentare und UI-Texte auf Deutsch.
- Änderungen an der Pipeline: Smoke-Test-Status in `docs/pipeline.md`
  aktualisieren; README-Tabelle pflegen, wenn Module dazukommen.
