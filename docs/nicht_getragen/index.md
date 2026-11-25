# Was nicht getragen hat

Nicht jeder Ansatz hat getragen. Diese Ergebnisse gehören zur Abgabe, weil sie zeigen, wo die Daten an Grenzen stoßen
und welche Wege sich nicht lohnen. Alle Ansätze aus dem Projekt stehen mit Ergebnis und Zahlen unter
[Negativbefunde im Detail](negativbefunde.md). Zwei Versuche aus dem Anhang haben eigene Seiten.

## Eigene Versuche im Anhang

**Bayes-Diagnose (Notebook 38).** Statt aus den Begehungen zu lernen, rechnet Naive Bayes mit einer
Fehler-Symptom-Matrix, die von Hand aus der Physik gefüllt ist. Nur das Ventil hat eine klare Spur (AUC 0,92 gegen
„kein Befund“). Regler und Einstellung, der häufigste Befund, hinterlassen keine. Die Matrix ist nicht mit der ÜZ
abgestimmt, und wie gut das Modell prüft, hängt an ihren genauen Stufen. Mehr unter [Bayes-Diagnose](bayes.md).

**Graphenmodell auf dem Netz (Notebook 39).** Ein GNN soll die Abweichungen des Normalverhaltensmodells mit den
Messwerten der Nachbarn im Netz erklären. Dasselbe Modell ohne Kanten ist praktisch gleich gut: Das Netz trägt
+0,010 und −0,009 bei, je Station nicht signifikant. Mehr unter [GNN: Hilft das Netz?](gnn.md).
