# Begriffe

| Begriff | Bedeutung |
|---|---|
| HAST | Hausanschlussstation. Übergabe der Fernwärme ans Gebäude, mit Wärmezähler. In der Doku auch „Station“. |
| Vorlauf, Rücklauf | Temperatur des Wassers, das zur Station hin- und von ihr zurückfließt (°C). |
| Spreizung | Vorlauf minus Rücklauf. Hohe Spreizung heißt: die Station nutzt die Wärme gut aus. |
| Hoher Rücklauf | Rücklauf deutlich über dem Netzniveau. Wichtigstes Fehlerzeichen im Projekt. |
| Volumenstrom | Wassermenge pro Stunde (l/h). Viel Durchfluss bei wenig Leistung deutet auf einen hydraulischen Fehler. |
| Anschlusswert | Vertraglich vereinbarte Leistung der Station (kW). |
| Volllaststunden | Jahresenergie geteilt durch Anschlusswert. Zeigt, ob die Station über- oder unterdimensioniert ist. |
| Begehung | Besuch eines Monteurs an der Station. Ergebnis: geänderte Einstellungen und ein Freitext. Wichtigste Quelle für Labels. |
| Label | Bekannte „richtige Antwort“ für einen Fall, hier aus den Begehungen (z. B. Ventil getauscht). |
| Kernwinter | Dezember bis Februar. Viele Auswertungen nutzen nur diese Monate, weil im Sommer kaum geheizt wird. |
| Heizgradtage | Maß für die Kälte eines Zeitraums. Je kälter, desto mehr Heizgradtage. |
| Kennlinie | Erwarteter Rücklauf oder Verbrauch einer Station abhängig von der Außentemperatur. |
| CUSUM | Verfahren, das kleine, aber dauerhafte Abweichungen aufsummiert und ab einer Schwelle Alarm gibt. |
| Wächter | Verfahren, das laufend prüft, ob sich eine Station verschlechtert, und Alarm gibt. |
| Erkenner | Verfahren, das für einen Zeitraum sagt, welcher Fehler vorliegt (z. B. Ventil, Dämmung). |
| Folie 5 | Handlungsklassen aus der Aufgabenstellung der ÜZ: Reparatur (Regelventil tauschen), Regelungsoptimierung, kein Handlungsbedarf. Dazu Hinweise auf Dämmung und Kapazitätsanpassung. |
| Netzvergleich | Station wird mit den anderen Stationen im Netz bei gleicher Außentemperatur verglichen. |
| Potenzial, Hebel | Wie viel sich verbessern ließe, wenn die Station so gut liefe wie das beste Viertel im Netz. |
| Clustering | Stationen oder Stunden ohne Labels in ähnliche Gruppen einteilen (z. B. K-Means). |
| Silhouette | Maß für die Trennschärfe von Clustern zwischen −1 und 1. Unter 0,25 gibt es kaum echte Gruppen. |
| ARI | Adjusted Rand Index. Misst, wie ähnlich zwei Clusterungen sind. 1 heißt gleich, 0 heißt Zufall. |
| AUC | Fläche unter der ROC-Kurve. 0,5 ist Raten, 1 ist perfekt. |
| Balanced Accuracy | Trefferquote, bei der jede Klasse gleich zählt. Bei zwei Klassen ist 0,5 Raten. |
| Holm-Korrektur | Strengere Schwelle, wenn viele Tests auf einmal gemacht werden. Schützt vor Zufallstreffern. |
| Diff-in-Diff | Vorher/Nachher-Vergleich mit Kontrollgruppe. Trennt die Wirkung der Begehung vom Wetter. |
| LSTM | Lernendes Modell für Zeitreihen. Hier für Prognose und als Merkmalsgeber (Embedding). |
| Embedding | Kurze Zahlenfolge, die ein Modell aus einer langen Zeitreihe gewinnt. |
| XGBoost | Verfahren aus vielen Entscheidungsbäumen. Hier als Vergleich zum LSTM. |
| Logischer Graph | Netz aus `Nodes_Edges.ods`: wer hängt an wem, ohne Geometrie. |
| Räumlicher Graph | Netz aus den Shapefiles: echter Rohrverlauf mit Längen. |
| GNN | Graph Neural Network. Lernendes Modell, das die Netzstruktur nutzt. Hier nur als Entwurf. |
| BHKW | Blockheizkraftwerk. Zähler 86792512 ist beispielsweise eines. Er ist keine Übergabestation und fällt deshalb seit Notebook 00 aus der Auswertung heraus. |
| Modellpaket | Gespeichertes, fertig gelerntes Modell in `models/`, damit das Dashboard nichts neu lernen muss. |
