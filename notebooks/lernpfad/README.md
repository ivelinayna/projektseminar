# Lernpfad: vom einfachen Modell zum LSTM

Hier baue ich die Modellarbeit des Projekts selbst noch einmal auf, Schritt für Schritt:
erst Daten und eine einfache Baseline mit scikit-learn, dann Sequenzen, dann das LSTM
zur Fehlererkennung, ein Wächter für Veränderungen und zum Schluss die Einteilung aller
Stationen nach Folie 5.

- **Daten:** die Ausgaben von Notebook 00 (`data/processed/real_meters/*.csv`,
  `data/processed/hast_features.csv`), die Außentemperatur über `src/weather.py`, die
  Begehungen über `src/load_begehungen.py`, `src/inspections.py` und `src/befundcodes.py`.
  Damit rechnet der Lernpfad auf denselben Daten wie die Notebooks 27 bis 32.
- **Referenz für Vorgehen und Story:** die lokale Vorarbeit (Notebooks 01 bis 22 dort). Deren
  Zahlen beruhen auf einer anderen Aufbereitung und dürfen abweichen. Zahlen vergleiche ich mit
  den Notebooks 27 bis 32 hier im Repo.
- **Plan und Stand:** [`LERNPLAN.md`](LERNPLAN.md), **Protokoll:** [`PROTOKOLL.md`](PROTOKOLL.md).
- **Nummern:** Der Lernpfad ist vor der Umbenennung für die Abgabe entstanden. Im Text stehen die
  neuen Nummern, im Code und in den Ausgaben vereinzelt noch die alten (z. B. 19, heute 28). Die
  Zuordnung steht in `docs/notebooks.md` unter „Alte und neue Nummern“.

## Regeln

- Rohdaten und Ausgaben von Notebook 00 werden nur gelesen, nie verändert.
- Eigene Zwischenergebnisse nach `data/processed/lernpfad/`, Modellgewichte nach
  `notebooks/models/lernpfad/`. Beides ist gitignored. So überschreibt der Lernpfad nichts,
  was die Notebooks 27 bis 32 brauchen.
- Bilder für den Report nach `docs/assets/lernpfad/`, der Text dazu in `docs/lernpfad.md`.
- Stationen heißen nach ihrer Zählernummer. Keine Adressen in Code, Kommentaren oder
  Ausgaben. Der Report auf Read the Docs ist öffentlich.
- Kernel: `projektseminar`. Jedes Notebook findet das Repo über die Suche nach `src/` wie in
  den anderen Notebooks.
- Report lokal ansehen: `.venv/bin/mkdocs serve` im Repo-Ordner, dann im Browser
  `http://127.0.0.1:8000`.
