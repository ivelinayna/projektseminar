# Weitere Versuche

Zwei eigene Ansätze liegen außerhalb der Hauptkette, im Ordner `notebooks/weitere_versuche`. Auf ihnen baut nichts
auf, und das Dashboard nutzt sie nicht. Sie haben eigene Seiten, weil sie jeweils einen ganz anderen Weg prüfen:
Fachwissen statt Lernen aus den Begehungen und das Leitungsnetz als Teil des Modells. Alle verworfenen Ansätze des
Projekts stehen mit Ergebnis und Zahlen unter [Verworfene Ansätze](../grenzen/verworfene_ansaetze.md).

**Bayes-Diagnose (Notebook 38).** Statt aus den Begehungen zu lernen, rechnet Naive Bayes mit einer
Fehler-Symptom-Matrix, die von Hand aus der Physik gefüllt ist. Nur das Ventil hat eine klare Spur (AUC 0,92 gegen
„kein Befund“). Regler und Einstellung, der häufigste Befund, hinterlassen keine. Die Matrix ist nicht mit der ÜZ
abgestimmt, und wie gut das Modell prüft, hängt an ihren genauen Stufen. Mehr unter [Bayes-Diagnose](bayes.md).

**Graphenmodell auf dem Netz (Notebook 39).** Ein GNN soll die Abweichungen des Normalverhaltensmodells mit den
Messwerten der Nachbarn im Netz erklären. Dasselbe Modell ohne Kanten ist praktisch gleich gut: Das Netz trägt
+0,010 und −0,009 bei, je Station nicht signifikant. Mehr unter [GNN: Hilft das Netz?](gnn.md).
