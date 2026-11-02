# Riproduzione

Eseguire dalla root estratta. Configurazione verificata: Mac Intel, macOS12.7.6;
Python3.10 per il runtime, Python3.13 per il notebook. Le password sono generate
localmente in `runtime/native-stack/credentials.json`, non distribuite.

## Setup e firmware

```sh
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements-native.txt
.venv/bin/python scripts/setup_native_stack.py
sh scripts/setup_mosquitto.sh
sh scripts/setup_contiki.sh
```

Lo stack nativo scarica MySQL8.0.31 e Grafana11.6.0 ufficiali con SHA-256 fissato.
Mosquitto2.0.22 senza TLS è fornito come eseguibile Intel e archivio sorgenti con
licenze. Se occorre ricompilarlo servono CMake e compilatore C.

Per ricompilare il firmware, aggiungere al PATH la toolchain ARM GNU12.3 e usare:

```sh
MAKE=gmake OUT_DIR=results/NUOVA-BUILD sh scripts/build_firmware.sh
gmake -C vendor/contiki-ng/tools/serial-io tunslip6
```

Setup applica la patch SW1 P1.06. Nessun flash automatico. Le immagini HEX e i
checksum della configurazione collaudata sono in `results/2026-11-02-final/firmware/`.
Prima di caricare immagini verificare target, dispositivo DFU e bootloader.

## Avvio hardware

Enumerare prima le porte; quelle in `config/hardware.json` sono le identità osservate.

```sh
.venv/bin/python -m serial.tools.list_ports -v
sudo vendor/contiki-ng/tools/serial-io/tunslip6 \
 -s /dev/cu.usbmodemFA8130D5146E1 -B 115200 -t utun10 -v 3 fd00::1/64
```

Lasciare SLIP attivo e non aprire contemporaneamente la seriale router. In un altro
terminale avviare stack e input utente:

```sh
.venv/bin/python scripts/native_stack.py start --run-id demo-esame
.venv/bin/python scripts/native_stack.py status
.venv/bin/python scripts/control.py pause --host ::1
.venv/bin/python scripts/control.py resume --host ::1
```

Grafana: http://127.0.0.1:3000/d/activitylink. Utente `admin`, password nel campo
`grafana_admin` del file locale. I servizi sono descritti in [NATIVE_MAC_STACK.md](NATIVE_MAC_STACK.md).

## Test e confronto

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python tests/backend_sql_contract.py --output results/NUOVO-SQL.json
.venv/bin/python scripts/native_stack_check.py --out results/NUOVO-CHECK \
 --run-id demo-esame --commands
.venv/bin/python scripts/hardware_stress.py --out results/NUOVO-STRESS --repeats 3
```

Il confronto usa nodi reali e perdita selettiva all'ingresso cloud:10s normali,
15s di scarto telemetria HAR,15s di ripresa; tre coppie adaptive/baseline. Il controller
ordinario viene fermato per il test e ripristinato alla fine. Non avviare un altro
controller o emulatore con gli stessi ID.

I risultati finali essenziali sono in `results/2026-11-02-final/`: stress,
scollegamento fisico, riavvio servizi, contratto SQL, equivalenza ML e memoria.
`physical_failure_check.py` richiede l'azione fisica sull'HAR;
`service_recovery_check.py` interrompe e riavvia realmente i servizi del progetto.

## Notebook

```sh
python3.13 -m venv tools/ml-venv
tools/ml-venv/bin/python -m pip install -r requirements-ml.txt nbclient nbformat ipykernel
tools/ml-venv/bin/python ml/retrain.py --out results/NUOVO-TRAIN
tools/ml-venv/bin/python scripts/execute_notebook.py \
 --dataset 'results/NUOVO-TRAIN/UCI HAR Dataset' --out results/NUOVO-NOTEBOOK
```

Il dataset UCI viene scaricato con verifica SHA-256. Il notebook può essere eseguito
con i sorgenti anche in Colab; il servizio ospitato non è stato verificato. Le
metriche riproducono un benchmark storico già noto. Il nuovo training non sostituisce
il modello congelato del firmware. Attribuzione: `data/ATTRIBUTION.md`.

Il trainer legge solo `train/` e produce `validation.json`: 5 fold per soggetto,
scaler riappreso in ciascun fold, ricetta fissa e nessuna selezione sul test.
La valutazione storica del test è un programma distinto, `ml/evaluate_historical.py`,
eseguito esplicitamente dal notebook dopo il training. Non approva né rifiuta il
candidato in base al test. Vedere [ML_VALIDATION.md](ML_VALIDATION.md).
Verifica dell'isolamento: `tools/ml-venv/bin/python -m unittest discover -s ml/tests -v`.
