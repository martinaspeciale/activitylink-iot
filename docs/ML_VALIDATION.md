# Validazione ML senza accesso al test durante il training

Correzione metodologica del 2 novembre 2026. Il protocollo attuale separa training,
validazione interna e ripetizione del benchmark storico. La correzione non può
annullare le consultazioni del test già avvenute nei lavori precedenti.

## Percorso canonico

`ml/retrain.py` legge **esclusivamente** `train/X_train.txt`, `train/y_train.txt`
e `train/subject_train.txt`. Può completare training e validazione anche se la
directory `test/` non esiste, come verifica un test automatico.

La ricetta resta quella fissata: tutte le 561 feature, `StandardScaler` e
`LinearSVC(C=0.1, dual='auto', max_iter=5000, random_state=42)`. Non si esegue
selezione di feature, ricerca di C o calibrazione di soglie. Non si sceglie una
ricetta dopo aver confrontato i nuovi punteggi.

La validazione usa **5 fold GroupKFold sui 21 soggetti del training ufficiale**.
Ogni soggetto compare nel lato di validazione di un solo fold. A ogni fold viene
creata una nuova pipeline: media e scala sono apprese soltanto sulle righe del
training di quel fold. Non si standardizza l'intero dataset prima della divisione.
Il protocollo viene salvato prima del calcolo delle metriche.

Le predizioni out-of-fold (OOF) sono quelle prodotte sulle righe escluse di volta
in volta dal fit. La metrica aggregata è calcolata su tutte queste predizioni.
Il modello candidato finale viene poi appreso su tutto il training ufficiale.

## Risultati della validazione interna

Fonte: [validation.json](../results/2026-11-02-ml-isolation/validation.json).

| Metrica | Risultato |
|---|---:|
| Finestre valutate OOF | 7.352 |
| Soggetti del training | 21 |
| Accuracy OOF aggregata | 93,77% |
| Macro-F1 OOF aggregato | **93,66%** |
| Media macro-F1 dei 5 fold | 93,65% |
| Deviazione standard tra fold | 4,03 punti percentuali |
| Intersezione soggetti fit/validazione | 0 in ogni fold |

| Fold | Macro-F1 |
|---|---:|
| 1 | 89,09% |
| 2 | 89,98% |
| 3 | 98,68% |
| 4 | 95,67% |
| 5 | 94,84% |

La media dei fold attribuisce uguale peso ai cinque punteggi; la metrica OOF
aggrega prima tutte le predizioni. La deviazione standard descrive la variabilità
tra questi gruppi: non è un intervallo di confidenza e i fold non sono cinque
esperimenti indipendenti, perché i rispettivi training si sovrappongono.

I fold mostrano variabilità tra soggetti che il solo numero del test storico non
rendeva visibile. Non significano che il 96,29% precedente fosse inventato.

## Benchmark storico, separato e soltanto descrittivo

`ml/evaluate_historical.py` carica un candidato **già addestrato** e calcola le
metriche sul test ufficiale. Non contiene `fit`, selezione di feature o soglie.
Non modifica il candidato, non sceglie il modello e non lo rifiuta se le predizioni
differiscono dal riferimento congelato.

È stato rimosso dal vecchio retraining il vincolo che interrompeva l'esecuzione
quando le predizioni sul test non coincidevano con quelle del modello distribuito.
Il confronto rimane una misura descrittiva, non un criterio di accettazione.

Il test comprende 2.947 finestre di 9 soggetti disgiunti dal training. Il candidato
mantiene accuracy **96,20%**, macro-F1 **96,29%** e **112 errori**; questi valori
sono registrati in [historical-test.json](../results/2026-11-02-ml-isolation/historical-test.json).
Sono una ripetizione di un benchmark già noto, **non una nuova valutazione cieca**.

Il firmware continua a usare il riferimento congelato: non viene sostituito dal
training o dal notebook. I test hardware già registrati restano associati a quel
modello. Il candidato appena riaddestrato è un artefatto separato; l'accordo sul
test non impone identità dei coefficienti né equivalenza su ogni ingresso possibile.

## Notebook storici esclusi

I notebook `IoT_ML_Comparison_v2`, `IoT_ML_Robustness_v3`,
`HAR_nRF52840_Contiki_audit` e `originals/HAR_nRF52840_Contiki` sono marcati come
archivi esplorativi e bloccati all'avvio. Non sono inclusi nello ZIP. Conservano
tracce del lavoro storico, non costituiscono percorsi di training approvati.
In particolare, la selezione di feature basata su `ACC_TE/GYR_TE` del notebook
originale non viene utilizzata nel percorso canonico SVM561.

L'unico notebook eseguibile della consegna è `ActivityLink_SVM561_Reproduce.ipynb`,
che esegue training isolato, validazione per soggetto, export del riferimento e,
in una cella distinta, benchmark storico descrittivo e verifica C/Python.

## Riproduzione

Dalla root, con le dipendenze in `requirements-ml.txt`:

```sh
tools/ml-venv/bin/python ml/retrain.py \
  --dataset 'results/2026-11-02-final/ml-reproduction/UCI HAR Dataset' \
  --out results/NUOVO-TRAIN-ISOLATO

tools/ml-venv/bin/python -m unittest discover -s ml/tests -v
```

Solo se si vuole ripetere il benchmark storico, dopo il training:

```sh
tools/ml-venv/bin/python ml/evaluate_historical.py \
  --dataset 'results/2026-11-02-final/ml-reproduction/UCI HAR Dataset' \
  --candidate results/NUOVO-TRAIN-ISOLATO/svm561.json \
  --output results/NUOVO-TRAIN-ISOLATO/historical-test.json
```

Senza `--dataset`, il trainer scarica l'archivio UCI verificandone SHA-256. Il
download può contenere entrambi gli split: il training apre comunque solo `train/`.
L'archivio dei dati non viene aggiunto allo ZIP di consegna.

## Cosa dichiarare all'esame

«Il training non usa il test ufficiale. Ho verificato la ricetta con cinque fold
separati per soggetto sul solo training, riapprendendo lo scaler dentro ogni fold:
macro-F1 OOF 93,66%. Il 96,29% è invece il macro-F1 sul test ufficiale già
consultato storicamente. Le due misure hanno protocolli diversi e non vanno confuse».

La validazione interna della ricetta storica **non azzera l'influenza delle scelte
di sviluppo passate**. Per una conferma esterna realmente nuova occorrono dati
non consultati, con un protocollo fissato prima di acquisirne o valutarne gli esiti.

Fonti metodologiche: [scikit-learn 1.8, leakage e Pipeline](https://scikit-learn.org/1.8/common_pitfalls.html#data-leakage)
e [validazione con gruppi](https://scikit-learn.org/1.8/modules/cross_validation.html#cross-validation-iterators-for-grouped-data).
