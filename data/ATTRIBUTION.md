# Provenienza dei campioni

Dataset: **Human Activity Recognition Using Smartphones**.
Reyes-Ortiz J., Anguita D., Ghio A., Oneto L., Parra X. (2013).
UCI Machine Learning Repository, https://doi.org/10.24432/C54S4K.
Fonte: https://archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones.
Licenza indicata da UCI: **Creative Commons Attribution 4.0 International**,
https://creativecommons.org/licenses/by/4.0/.

Il progetto usa feature pre-elaborate del dataset, non nuove registrazioni fisiche.
`replay.csv` e `firmware_samples.json` conservano campioni selezionati; il firmware
include 24 vettori (quattro per classe) esportati in float32 in `samples.h`.
I pesi SVM sono derivati dal training ufficiale con scaler appreso solo sul training.
La selezione della demo non costituisce una nuova misura di accuratezza.

La pipeline di riproduzione verifica SHA-256 del download e dei file di training/test.
L'archivio completo del dataset non è incluso nello ZIP finale: viene scaricato
dal notebook o da ml/retrain.py. Sono mantenuti riferimento e attribuzione originali.
