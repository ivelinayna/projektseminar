---
name: begehungs-wirkungsanalyse
description: Wirkung von Begehungen/Interventionen in den HAST-Zeitreihen prüfen — Vorher/Nachher, Zeitfenster um die Begehung, Kontrollgruppe, Diff-in-Diff, Cluster-Wanderung, Freitext-Kodierung. Verwenden bei Aufgaben wie „Verändern sich Cluster vor/nach Begehung", „Zeitfenster um Begehung", „Intervention attributieren", „Begehungslabels verbessern".
---

# Wirkungsanalyse der Begehungen

Ziel: Prüfen, ob Begehungen/Interventionen in den Zeitreihen sichtbar sind
und ob Cluster- oder Zustandsänderungen auf die Intervention
zurückgeführt werden können. Baut auf Notebook
`03_wirkungsanalyse_begehungen.ipynb` auf.

## Datenbasis

- Begehungen: `src/load_begehungen.py` — Änderungs-Kategorie,
  Begehungszeiten (teilweise mit Uhrzeit), Heiz-/TWW-Zeiten, Sollwerte
  alt/neu, Ja/Nein-Reparaturmarkierungen (Filter, Ventil, Stellantrieb,
  Dämmung, Regler). Adresse→Zähler über `Zuordnung.xlsx` (66/66).
- Freitext-Notizen: 57 der 66 Begehungen haben eine Notiz mit dem
  tatsächlichen Befund („Regler schliesst nicht ganz", „Zirk Pumpe defekt
  geölt") — **kodieren**, um Fälle zu erklären, in denen Kategorie und
  Messergebnis auseinandergehen.
- Label-Falle: Die dramatischste Reparatur (Zähler 68956351, Ventil
  3 Jahre offen, geschlossen am 09.09.2024) steht **nicht** in der
  Begehungstabelle → Labels aus Messdaten gegenprüfen.

## Vorgehen

1. **Zeitfenster festlegen — fachlich kritischster Schritt.**
   - Vorher- und Nachher-Fenster symmetrisch um das Begehungsdatum;
     Fensterlänge als Parameter (Referenz: 14 Tage aus Notebook 02/03).
   - Begehungstag selbst aus den Fenstern ausschließen (Tag der
     Intervention ist Mischzustand).
   - Bei bekannten Begehungsuhrzeiten (~Hälfte der Stationen): Prüfung,
     ob die Begehung im Stundenverlauf nachweisbar ist.
   - Zusätzlich **Endfenster** am Rand der Datenhistorie betrachten
     (Team-Vorgabe: Zeitfenster am Ende prüfen) — Effekte, die erst spät
     auftreten oder Datenrand-Artefakte.
   - Saisonalität beachten: Vorher/Nachher über Jahreszeitenwechsel
     verfälscht Rücklauf-Vergleiche → ggf. gleiche Kalenderwochen des
     Vorjahrs als Vergleich.
2. **Vorher/Nachher je Station:** Rücklauf, Spreizung, Durchfluss,
   Heizstunden; Änderung gegen dokumentierte Kategorie und Sollwert-
   Änderung (Heizzeiten alt/neu wurden in 4/5 Fällen in den Daten
   bestätigt — Referenzbefund).
3. **Kontrollgruppe & Diff-in-Diff:** Stationen ohne Begehung im selben
   Zeitraum. Ergebnis bisher: Rücklaufänderung monoton über
   Kategoriestufen, aber **nicht signifikant** (Wilcoxon p ≈ 0,4) — als
   Ausgangslage kennen, nicht als Widerlegung lesen.
4. **Cluster-Wanderung:** Fenster-Features (Skill `zeitreihen-features`)
   clustern (Skill `clustering-benchmark`) und prüfen: Wechselt die
   Station nach der Begehung den Cluster? Bewegt sie sich Richtung
   „gesundem" Cluster (niedrigerer Rücklauf, höhere Spreizung)? Bewegung
   ohne dokumentierte Intervention genauso berichten (Kandidaten für
   fehlende Labels).
5. **Attribution dokumentieren:** Tabelle Station × Fenster ×
   (Kategorie, Freitext-Kodierung, gemessene Änderung, Cluster-Wechsel,
   plausibel ja/nein). Zählerwechsel-Fälle (5 Adressen) separat
   kennzeichnen — Vorher/Nachher vergleicht dort zwei Geräte.

## Fallstricke

- Label-Leakage nicht noch einmal einbauen: Features für ein
  Vorher-Fenster dürfen die Begehung nicht enthalten (beim ML-
  Klassifikator waren 84 % der Fenster kontaminiert — siehe
  `docs/ml-klassifikator.md`).
- Basisrate-Problem: 76–82 % der Stationen haben „mind. eine Maßnahme" —
  Vergleiche immer gegen Kontrollgruppe, nie absolut.
- Inbetriebnahmen von Fehlern trennen (Fall 72167783: Rücklauf 18,6 →
  71,0 °C nach Begehung — vor Mittelwertbildung klären).
