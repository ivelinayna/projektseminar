# Modellpakete für den Betrieb

Hier liegen die gelernten Modelle mit allem, was zum Anwenden gehört (Gewichte, Skalierung,
Kalibrierung, Schwelle, Metadaten). Der Ordner ist bis auf diese Datei **gitignored**: Die Pakete
sind aus Firmendaten gelernt und enthalten Zählernummern.

```
models/<name>/AKTUELL            Betriebsversion
models/<name>/<version>/paket.json
models/<name>/<version>/<dateien>
```

Bauen, prüfen, anzeigen:

```bash
python -m src.prognose_waechter --bauen --gegenprobe
python -m src.normalmodell_waechter --bauen
python -m src.fehlerklassen --bauen --gegenprobe
python -m src.modellpaket
```

Aufbau und Laden: Docstring von `src/modellpaket.py`. Geprüft werden die Pakete in
`notebooks/32_modellvergleich.ipynb`.
