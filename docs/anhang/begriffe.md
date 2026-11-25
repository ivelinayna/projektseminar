# Begriffe

| Begriff | Bedeutung |
|---|---|
| HAST | Hausanschlussstation. Übergabe der Fernwärme ans Gebäude, mit Wärmezähler. In der Doku auch „Station“. |
| Vorlauf, Rücklauf | Temperatur des Wassers, das zur Station hin- und von ihr zurückfließt (°C). |
| Spreizung | Vorlauf minus Rücklauf. Hohe Spreizung heißt: die Station nutzt die Wärme gut aus. |
| Hoher Rücklauf | Rücklauf deutlich über dem Netzniveau. Wichtigstes Fehlerzeichen im Projekt. |
| Volumenstrom | Wassermenge pro Stunde (l/h). Viel Durchfluss bei wenig Leistung deutet auf einen hydraulischen Fehler. |
| Regelhysterese | Schaltabstand eines Reglers: Er greift erst ein, wenn die Abweichung eine Schwelle überschreitet. Ist er ungünstig eingestellt, pendelt die Regelung, oft im Minutentakt. In Stundenwerten ist das kaum zu sehen. |
| Anschlusswert | Vertraglich vereinbarte Leistung der Station (kW). |
| Volllaststunden | Jahreswärme geteilt durch die Spitzenlast. So viele Stunden bräuchte die Station bei Spitzenlast, um ihre Jahreswärme abzunehmen. |
| Begehung | Besuch eines Monteurs an der Station. Ergebnis: geänderte Einstellungen und ein Freitext. Wichtigste Quelle für Labels. |
| Label | Bekannte „richtige Antwort“ für einen Fall, hier aus den Begehungen (z. B. Ventil getauscht). |
| Kernwinter | Dezember bis Februar. Viele Auswertungen nutzen nur diese Monate, weil im Sommer kaum geheizt wird. |
| Kennlinie | Erwarteter Rücklauf oder Verbrauch einer Station abhängig von der Außentemperatur. |
| CUSUM | Verfahren, das kleine, aber dauerhafte Abweichungen aufsummiert und ab einer Schwelle Alarm gibt. |
| Wächter | Verfahren, das laufend prüft, ob sich eine Station verschlechtert, und Alarm gibt. |
| Erkenner | Verfahren, das für einen Zeitraum sagt, welcher Fehler vorliegt (z. B. Ventil, Dämmung). |
| Folie 5 | Handlungsklassen aus der Aufgabenstellung der ÜZ: Reparatur (Regelventil tauschen), Regelungsoptimierung, kein Handlungsbedarf. Dazu Hinweise auf Dämmung und Kapazitätsanpassung. |
| Netzvergleich | Station wird mit den anderen Stationen im Netz bei gleicher Außentemperatur verglichen. |
| Potenzial | Wie viel sich verbessern ließe, wenn die Station so gut liefe wie das beste Viertel im Netz. |
| Hebel | Trefferquote eines Alarms an den Begehungen geteilt durch die Quote bei Kontrollstationen. 1 heißt: nicht besser als Zufall. |
| Clustering | Stationen oder Stunden ohne Labels in ähnliche Gruppen einteilen (z. B. K-Means). |
| Silhouette | Maß für die Trennschärfe von Clustern zwischen −1 und 1. Unter 0,25 gibt es kaum echte Gruppen. |
| ARI | Adjusted Rand Index. Misst, wie ähnlich zwei Clusterungen sind. 1 heißt gleich, 0 heißt Zufall. |
| AUC | Fläche unter der ROC-Kurve. 0,5 ist Raten, 1 ist perfekt. |
| Balanced Accuracy | Trefferquote, bei der jede Klasse gleich zählt. Bei zwei Klassen ist 0,5 Raten. |
| Holm-Korrektur | Strengere Schwelle, wenn viele Tests auf einmal gemacht werden. Schützt vor Zufallstreffern. |
| p-Wert | Wahrscheinlichkeit, ein mindestens so deutliches Ergebnis allein durch Zufall zu bekommen. Unter 0,05 gilt es als gesichert (signifikant). |
| Wilcoxon-Test | Prüft, ob sich gepaarte Werte systematisch unterscheiden, etwa vor und nach einer Begehung an derselben Station. Setzt keine Normalverteilung voraus. |
| McNemar-Test | Vergleicht zwei Verfahren an denselben Fällen. Gezählt werden nur die Fälle, die genau eines der beiden trifft. |
| Rangkorrelation | Zusammenhang zweier Größen, gerechnet nur mit der Reihenfolge der Werte (Spearman). Zwischen −1 und 1, 0 heißt kein Zusammenhang. |
| Diff-in-Diff | Vorher/Nachher-Vergleich mit Kontrollgruppe. Trennt die Wirkung der Begehung vom Wetter. |
| ARIMA | Klassisches Zeitreihenmodell, das den nächsten Wert aus den vorigen Werten und ihren Änderungen vorhersagt. Hier für den Tagesrücklauf (Notebook 06). |
| Logistische Regression | Einfaches lernendes Modell, das aus Merkmalen die Wahrscheinlichkeit für ja oder nein schätzt, etwa für einen Ventilbefund. |
| LSTM | Lernendes Modell für Zeitreihen. Hier für Prognose und als Merkmalsgeber (Embedding). |
| Embedding | Kurze Zahlenfolge, die ein Modell aus einer langen Zeitreihe gewinnt. |
| XGBoost | Verfahren aus vielen Entscheidungsbäumen. Hier als Vergleich zur logistischen Regression und zur Regel, nirgends besser (Notebook 29). |
| Kantendatei | Netz aus `Nodes_Edges.ods`: welche Häuser im Netz nah beieinander hängen, ohne Rohrverlauf. |
| Rohrbaum | Netz aus dem Leitungsplan: kürzester Rohrweg vom Erzeuger zu jedem Haus mit Zähler (Notebook 32). |
| GNN | Graph Neural Network. Lernendes Modell, das die Netzstruktur nutzt. Hier nur als Entwurf. |
| BHKW | Blockheizkraftwerk. Zähler 86792512 ist beispielsweise eines. Er ist keine Hausanschlussstation und fällt deshalb seit Notebook 00 aus der Auswertung heraus. |
| Modellpaket | Gespeichertes, fertig gelerntes Modell in `models/`, damit das Dashboard nichts neu lernen muss. |
