# ML-Zustandsklassifikator: Evaluation

Generiert am 2026-07-20 von `src/ml_classifier.py`. Additive Evaluation -
kein bestehendes Modul und nicht das Dashboard verändert.

> **Datenschutz:** aggregierte Metriken, keine Zählernummern im Report.

## 1. Aufgabenstellung — Klassifikation, keine Vorhersage

Vorhergesagt wird der **dokumentierte Zustand** einer Station (welche
Begehungsmaßnahme wurde durchgeführt), nicht ein künftiger Ausfall.
Eine echte Ausfall**vorhersage** ist mit diesen Daten unmöglich: es
gibt keine Ausfall-Zeitpunkte, nur eine einmalige Begehungsmomentaufnahme
je Station. Die Aufgabe ist damit eine Zustands-Klassifikation aus
Zeitreihen-Features gegen die Begehung als Ground Truth.

## 2. Stichprobe und Klassenverteilung

- **49 Stationen** mit auswertbaren Features UND dokumentierter Begehung.
- Binäres Ziel „mindestens eine Maßnahme": **40 positiv / 9
  negativ** (Basisrate 82 %).
- 22 numerische Features. Bei 49 Samples ist das
  Verhältnis Features:Samples ≈ 1:2.2 — hohe
  Overfitting-Gefahr; deshalb bewusst einfache Modelle, Regularisierung,
  flache Bäume, kein Tuning.

### Je Maßnahmentyp — Machbarkeitsprüfung

- **Filter gereinigt** (24 positiv / 25 negativ): ausgewertet.
- **Durchfluss neu** (18 positiv / 31 negativ): ausgewertet.
- **Dämmung neu** (20 positiv / 29 negativ): ausgewertet.
- **Vertragsleistung geändert** (9 positiv): zu klein (< 12), **methodisch nicht vertretbar** - weggelassen.
- **Stellmotor getauscht** (2 positiv): zu klein (< 12), **methodisch nicht vertretbar** - weggelassen.
- **Stellventil getauscht** (2 positiv): zu klein (< 12), **methodisch nicht vertretbar** - weggelassen.
- **Regler getauscht** (0 positiv): zu klein (< 12), **methodisch nicht vertretbar** - weggelassen.

Stellmotor/Stellventil (je 2 positiv) und Regler (0) werden **nicht**
modelliert — ein Modell auf 2 positiven Fällen wäre methodisch wertlos.

## 3. Leakage-Analyse (kritisch)

Die Begehungen liegen laut [echte-daten-integration.md](echte-daten-integration.md)
im Zeitraum der Analysefenster. Konkret für die 49 gelabelten Stationen:

| Lage der Begehung zum Feature-Fenster | Stationen |
|---|---|
| **IM Fenster** (Features enthalten Zustand nach Reparatur) | 41 |
| nach dem Fenster (sauber) | 3 |
| ohne verwertbares Datum | 5 |

**Das ist der wichtigste Befund:** bei 41 von 49 Stationen
(84 %) enthält das Feature-Fenster Betriebsdaten aus der
Zeit NACH der dokumentierten Maßnahme. Die Features spiegeln dann teils
den bereits reparierten Zustand — jedes Modell (Regel oder ML) lernt
gegen ein kontaminiertes Label. Die saubere Teilmenge (Begehung nach
Fenster) umfasst nur **3 Stationen** und ist damit **zu klein
für eine separate, belastbare Auswertung** — eine harte Limitation,
keine behebbare Stellschraube ohne neue Daten (frühere Begehungen oder
frühere Zeitreihen von ÜZ).

## 4. Drei Vergleichsmaßstäbe (binär, stratifizierte 5-fold-CV)

Mittelwert ± Streuung über die Folds. **Die Streuung ist bei n=49 die
entscheidende Zahl.**

| Ansatz | precision | recall | f1 | balanced_acc |
|---|---|---|---|---|
| trivial (immer Befund) | 0.82 ± 0.04 | 1.00 ± 0.00 | 0.90 ± 0.02 | 0.50 ± 0.00 |
| Regel-Baseline | 0.82 ± 0.04 | 1.00 ± 0.00 | 0.90 ± 0.02 | 0.50 ± 0.00 |
| LogReg | 0.73 ± 0.08 | 0.55 ± 0.15 | 0.62 ± 0.12 | 0.33 ± 0.14 |
| RandomForest | 0.79 ± 0.02 | 0.85 ± 0.12 | 0.81 ± 0.06 | 0.42 ± 0.06 |

Lesart: Der triviale Klassifikator erreicht per Basisrate eine Precision
von ~0.82 und Recall 1.0 — jede sinnvolle Alternative muss
das schlagen, ohne den Recall zu opfern. Balanced Accuracy 0.50 beim
trivialen Klassifikator ist der eigentliche Nullpunkt: er erkennt die
negative Klasse (keine Maßnahme) per Definition nie.

## 5. Je-Typ-Ergebnisse (nur methodisch vertretbare Typen)

**Filter gereinigt** (24/25):

| Ansatz | precision | recall | f1 | balanced_acc |
|---|---|---|---|---|
| trivial (immer Befund) | 0.49 ± 0.02 | 1.00 ± 0.00 | 0.66 ± 0.02 | 0.50 ± 0.00 |
| LogReg | 0.64 ± 0.20 | 0.59 ± 0.11 | 0.59 ± 0.10 | 0.59 ± 0.14 |
| RandomForest | 0.58 ± 0.04 | 0.55 ± 0.18 | 0.55 ± 0.14 | 0.59 ± 0.06 |

**Durchfluss neu** (18/31):

| Ansatz | precision | recall | f1 | balanced_acc |
|---|---|---|---|---|
| trivial (immer Befund) | 0.37 ± 0.04 | 1.00 ± 0.00 | 0.54 ± 0.05 | 0.50 ± 0.00 |
| LogReg | 0.16 ± 0.14 | 0.18 ± 0.15 | 0.17 ± 0.14 | 0.38 ± 0.13 |
| RandomForest | 0.33 ± 0.42 | 0.20 ± 0.27 | 0.23 ± 0.29 | 0.52 ± 0.16 |

**Dämmung neu** (20/29):

| Ansatz | precision | recall | f1 | balanced_acc |
|---|---|---|---|---|
| trivial (immer Befund) | 0.41 ± 0.02 | 1.00 ± 0.00 | 0.58 ± 0.02 | 0.50 ± 0.00 |
| LogReg | 0.59 ± 0.21 | 0.60 ± 0.20 | 0.57 ± 0.17 | 0.62 ± 0.14 |
| RandomForest | 0.58 ± 0.21 | 0.45 ± 0.19 | 0.46 ± 0.09 | 0.57 ± 0.05 |

Bei Dämmung neu, Filter gereinigt liegt ein ML-Modell in der mittleren Balanced Accuracy über dem trivialen Klassifikator, und zwar um mehr als eine Streuung — der einzige Lichtblick der ganzen Auswertung. Belastbar ist das trotzdem nicht: die Fold-Streuung (±0.14 in der Größenordnung) ist bei n=49 fast so groß wie der Vorsprung selbst, und die Leakage-Kontamination aus Abschnitt 3 gilt hier genauso.

## 6. Feature-Wichtigkeiten (binär, Plausibilitätskontrolle)

Auf allen Daten gefittet, nur zur Interpretation (nicht metrisch
bewertet). Top nach |LogReg-Koeffizient|:

| feature | logreg_coef | rf_importance |
|---|---|---|
| rt_above_50_share_loaded | 0.858 | 0.03 |
| dt_mean_loaded | 0.839 | 0.038 |
| flow_short_cycle_power | 0.807 | 0.066 |
| rt_p95 | -0.746 | 0.07 |
| standby_dt | -0.728 | 0.072 |
| p95_load_share | -0.645 | 0.026 |
| peak_load_kw | 0.566 | 0.055 |
| dt_std_loaded | -0.527 | 0.074 |

**Fachliche Plausibilitätskontrolle:** Die stärksten LogReg-Koeffizienten sind rt_above_50_share_loaded, dt_mean_loaded, flow_short_cycle_power. Dass Rücklauf-/ΔT-Größen (Auskühlung, Wärmeübertragung) oben stehen, ist fachlich plausibel — es ist derselbe Effizienz-Indikator, auf dem die Ampel beruht. Zugleich taucht `flow_short_cycle_power` weit oben auf — genau das FFT-Feature, das die Regel-Baseline auf echten Daten wertlos macht (reales Zapfverhalten oszilliert ohnehin im 4–12h-Band). Das Modell greift also teils auf ein nicht-diskriminierendes Merkmal zu. LogReg- und RF-Ranking widersprechen sich in den Top-3 deutlich — ein weiteres Zeichen instabiler, nicht belastbarer Feature-Zuschreibungen bei n=49.

## 7. Schlussfolgerung

**ML bringt mit dieser Datenlage keinen Mehrwert.** Das beste ML-Modell (RandomForest) erreicht eine Balanced Accuracy von 0.42 und schlägt damit **weder** den trivialen Klassifikator noch die Regel-Baseline (beide Balanced Accuracy 0.50). Beide ML-Modelle liegen bei der Balanced Accuracy sogar unter dem Zufallsnullpunkt 0.50 — sie erkennen die Minderheitsklasse (keine Maßnahme, nur 9 Fälle) schlechter als Raten. Die Gründe sind strukturell, nicht durch Modellwahl behebbar:

1. **Massive Label-Kontamination:** 41/49 Begehungen liegen im Feature-Fenster (Abschnitt 3); die Features beschreiben teils den reparierten Zustand.
2. **Extreme Klassen-Unbalance bei winziger Stichprobe:** 40/9 bei n=49. Jeder CV-Fold enthält ~2 negative Fälle — die Streuung (oben) ist entsprechend groß und jedes Ergebnis kaum belastbar.
3. **Feature:Sample-Verhältnis ~1:2.2:** Overfitting ist bei 22 Features und n=49 kaum vermeidbar.

Die Regel-Baseline ihrerseits ist ebenfalls nicht nützlich — sie meldet schlicht alles als Befund und ist damit identisch zum trivialen Klassifikator (Balanced Accuracy 0.50). Die ehrliche Gesamtaussage: **auf dieser Datenbasis trennt weder Regel noch ML zuverlässig zwischen Stationen mit und ohne Handlungsbedarf.** Voraussetzung für einen sinnvollen nächsten Versuch sind Daten ohne Leakage (Zeitreihen VOR der jeweiligen Begehung) und mehr negative Fälle — beides nur über ÜZ zu beschaffen, nicht über bessere Modelle.
