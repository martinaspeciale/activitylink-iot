# Riproduzione

Eseguire dalla root estratta. Configurazione verificata: Mac Intel, macOS12.7.6;
Python3.10 per il runtime, Python3.13 per il notebook. Le password sono generate
localmente in `runtime/native-stack/credentials.json`, non distribuite.

## Comandi della demo

`scripts/demo.sh` raccoglie i comandi esistenti in un menu leggibile e offre anche
l'esecuzione diretta. Usa il Python di `.venv` senza richiedere l'attivazione:

```sh
./scripts/demo.sh help
./scripts/demo.sh setup
./scripts/demo.sh ports
```

Per la demo, `./scripts/demo.sh router` resta attivo nel primo terminale; nel
secondo eseguire `./scripts/demo.sh start adaptive`, poi `./scripts/demo.sh dashboard`
e `./scripts/demo.sh` per aprire il menu. `watch` osserva MQTT da un terzo terminale
senza dipendere da SQL. `--dry-run` stampa i comandi senza eseguirli.

Scenari: `pause`, `resume`, `buttons`, `check`, `stress` o `stress 3`, `physical`,
`services`, `mysql-stop`/`mysql-start`, `broker-stop`/`broker-start`,
`stop-cloud`/`start-cloud`, `sql`, `queue` e `tests`. Attendere READY prima di
scollegare HAR in `physical`. Le interruzioni manuali richiedono il corrispondente
comando di riavvio. `build` e `flash ROLE DFU_PORT` sono operazioni esplicite di
manutenzione del firmware, non necessarie per avviare i dongle già programmati.

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

Setup applica la patch SW1 P1.06. Nessun flash automatico. Le immagini HEX
vengono generate nella directory scelta con `OUT_DIR` durante la compilazione.
Prima di caricare immagini verificare target, dispositivo DFU e bootloader.

## Avvio hardware

La procedura usa il target originale Contiki `connect-router`.
Sul Mac si usa `gmake` e una seriale `/dev/cu.usbmodem...` al posto di `/dev/ttyACM0`.
Il compilatore ARM deve essere nel PATH anche per leggere questo Makefile.
Sul Mac operativo il PATH è già configurato in `~/.zshrc`: basta aprire un nuovo
terminale. Su un altro host, aggiungere una sola volta alla propria `~/.zshrc`
la riga seguente, adattando il percorso all'installazione, poi aprire un nuovo terminale:

```sh
export PATH="$HOME/opt/arm-toolchains/arm-gnu-toolchain-12.3.rel1-darwin-x86_64-arm-none-eabi/bin:$PATH"
```

Questa è preparazione dell'ambiente, non un comando da ripetere a ogni demo.
Verificare con `command -v arm-none-eabi-gcc`.

**Terminale 1**, dalla root del progetto, con ambiente già predisposto:

```sh
source .venv/bin/activate
python -m serial.tools.list_ports -v
```

Caricare i nomi dei ruoli nel terminale corrente, dalla root del progetto:

```sh
source <(python scripts/ports.py)
```

Il piccolo `scripts/ports.py` legge le porte osservate in `config/hardware.json`
e stampa le assegnazioni di HAR, FEEDBACK e BORDER_ROUTER. `source` le applica
alla shell corrente; `python scripts/ports.py` da solo permette di mostrarle.
Non sono salvate in `~/.zshrc` e non si rilevano automaticamente nuovi dispositivi.
Confrontare le porte con l'enumerazione attuale; aggiornare l'inventario e ricaricare
lo script se un'associazione cambia. Poi, sempre dalla root:

```sh
cd vendor/contiki-ng/examples/rpl-border-router
gmake TARGET=nrf52840 BOARD=dongle PORT="$BORDER_ROUTER" connect-router
```

Lasciare il comando attivo. Il target avvia tunslip6; non carica firmware.
Se manca l'eseguibile tunslip6 può compilarlo. I default locali sono 115200 baud,
interfaccia utun10 e verbosità 2 (prima era esplicita a 3: cambiano solo i log).
Non aprire contemporaneamente la stessa seriale con un altro programma.

**Terminale 2**, aperto nella root del progetto:

```sh
source .venv/bin/activate
python scripts/native_stack.py status
python scripts/native_stack.py stop-cloud
python scripts/native_stack.py start --adaptive 1 --run-id demo-esame
open http://127.0.0.1:3000/d/activitylink
```

Gli script Python sono del progetto; non sono comandi forniti dalle slide.
`start` riusa un backend già attivo: `stop-cloud` prima dell'avvio permette di
applicare il run_id e la modalità scelti. Non serve esportare PYTHONPATH.

Durante la demo, nel Terminale 2, eseguire separatamente pausa e ripresa:

```sh
python scripts/control.py pause --host ::1
python scripts/control.py resume --host ::1
```

Al termine usare `python scripts/native_stack.py stop-cloud`, poi Ctrl+C nel
Terminale 1 e scollegare i dongle. stop-cloud ferma solo il backend: broker,
MySQL e Grafana possono restare attivi. Cambiare la procedura di lancio non
modifica firmware o modello; è stata verificata la generazione del comando
Contiki senza ripetere il collaudo sui dongle.

Grafana: http://127.0.0.1:3000/d/activitylink. Utente `admin`, password nel campo
`grafana_admin` del file locale. I servizi sono descritti in [NATIVE_MAC_STACK.md](NATIVE_MAC_STACK.md).

## Test e confronto

La suite include una prova aggiuntiva di saturazione della coda: 1005 messaggi,
1000 accodati e 5 scartati, con MQTT/SQL simulati. Dettagli e limiti:
[QUEUE_SATURATION_CHECK.md](QUEUE_SATURATION_CHECK.md).

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
scollegamento fisico, riavvio servizi, contratto SQL ed equivalenza ML.
`physical_failure_check.py` richiede l'azione fisica sull'HAR;
`service_recovery_check.py` interrompe e riavvia realmente i servizi del progetto.

## Notebook

English notebook instructions: [ml/README.md](../ml/README.md). Use a separate
Python 3.11+ environment; the saved run uses Python 3.13.5. Saved outputs include
two OOF figures and fold/per-class tables. The Colab setup cell requests the
source ZIP and copies only the required support files. Hosted execution remains
unverified.

```sh
python3.13 -m venv tools/ml-venv
tools/ml-venv/bin/python -m pip install -r requirements-notebook.txt
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


## ELF, HEX, DFU e controlli di integrità

### Dal codice al dispositivo

Il file C è un sorgente: istruzioni leggibili dalle persone. Il compilatore ARM
lo traduce in istruzioni per il microcontrollore. Il linker combina codice e dati
e ne stabilisce la collocazione in memoria. Il risultato della build viene
convertito nel formato richiesto dagli strumenti di programmazione.

```text
Sorgenti C e header del modello
              ↓ compilatore e linker
Programma ELF
              ↓ objcopy
Immagine Intel HEX
              ↓ strumenti Nordic di preparazione del pacchetto
Pacchetto DFU ZIP: immagine BIN + init packet DAT + manifest
              ↓ trasferimento USB al bootloader in modalità aggiornamento
Applicazione nella flash del dongle
```

È uno schema della procedura: il target di build può automatizzare più passaggi.
Lo script `scripts/build_firmware.sh` produce ELF e HEX ma non esegue il flash.
Il target `dfu-upload` comprende invece il caricamento.

### Tre rappresentazioni del programma

| Formato | Informazioni conservate | Impiego |
|---|---|---|
| ELF | Codice, dati, sezioni e altre informazioni della build; può includere simboli di debug | Ispezionare il programma e produrre altri formati |
| Intel HEX | Byte da programmare con indirizzi e controlli per record, in forma testuale | Rappresentare l'immagine destinata alla memoria |
| BIN | Byte dell'immagine senza i record testuali Intel HEX | Contenuto del pacchetto DFU usato qui |

L'estensione finale prodotta da Contiki può essere `.nrf` o `.nrf52840` pur
contenendo un ELF. Lo script copia questi risultati in file chiamati `.elf`.
Il formato è determinato dal contenuto, non dal solo suffisso del nome.

In questo progetto l'HEX include anche coefficienti e campioni in flash del HAR:
non è soltanto la funzione che accende il LED. Installare una nuova immagine può
quindi cambiare sia logica sia dati incorporati. La copia Git attuale non ha
modificato il modello installato.

### Capire un record HEX

Un record è una riga del formato. Esempio didattico, non immagine da caricare:

```text
:04 0000 00 01020304 F2
```

Gli spazi sono aggiunti per leggere: la riga effettiva sarebbe
`:0400000001020304F2`. Le coppie esprimono byte in base 16, che usa le cifre
0–9 e le lettere A–F. Qui `04` è il numero di byte dati, `0000` l'offset,
`00` il tipo record dati, `01020304` i quattro byte e `F2` il controllo.
I record di estensione completano l'indirizzo: non tutte le righe scrivono dati.

Il controllo per riga rende la somma dei byte, checksum incluso, un multiplo di
256. Nell'esempio: 4 + 0 + 0 + 0 + 1 + 2 + 3 + 4 + 242 = 256.
È un controllo locale degli errori, non una firma dell'autore e non una prova
che il programma sia corretto.

Riferimento di formato: [Intel HEX, documentazione Keil](https://www.keil.com/support/docs/1584/_hlp_hexfile.htm).
Il checksum del formato controlla la coerenza di ogni record; non misura
la correttezza del programma.

### Che cosa fa DFU

DFU significa Device Firmware Update: è una procedura di aggiornamento, non un
linguaggio di programmazione. Il bootloader è il programma che può ricevere un
aggiornamento e predisporre l'avvio dell'applicazione. In modalità DFU il dongle
partecipa alla procedura di caricamento; non sta svolgendo il normale ruolo HAR,
feedback o router.

Nei pacchetti di flash noti del progetto sono presenti un `.bin`, un `.dat`
(init packet, con metadati di aggiornamento) e un `manifest.json` che li associa.
La generazione del pacchetto può convertire HEX in BIN. La presenza di un `.dat`
non basta a dichiarare che sia stata configurata una firma crittografica.
Riferimento: [Nordic, generazione dei pacchetti DFU](https://docs.nordicsemi.com/r/bundle/nrfutil/page/nrfutil-nrf5sdk-tools/nrfutil-nrf5sdk-tools-pkg.html/basic-usage).

La USB ha qui un impiego diverso dalla demo ordinaria: durante DFU trasporta
l'aggiornamento al bootloader; durante la demo sul router trasporta SLIP.
Gli identificativi USB possono differire tra modalità applicativa e DFU.
Per caricare un'immagine bisogna identificare ruolo, porta e modalità corretti.

Lo ZIP DFU contiene un aggiornamento per un dispositivo. Lo ZIP di consegna
contiene il progetto da esaminare: sorgenti, configurazioni e risultati. Non è
un pacchetto da inviare al bootloader. Il `manifest.json` del DFU è distinto dal
`MANIFEST.json` con gli hash dei file della repository.

### SHA-256 e confronto delle immagini

Un hash SHA-256 è un'impronta di 256 bit, normalmente mostrata come 64 caratteri
esadecimali. Serve a confrontare il contenuto di file. Non descrive il nome del
file né il suo ruolo. La verifica è utile quando il riferimento atteso proviene
da una fonte affidabile; un'impronta da sola non identifica l'autore.

Il checksum della riga HEX controlla un record. Il SHA-256 del file identifica
l'intero contenuto di quel file. Nessuno dei due esegue un test funzionale del
firmware. I checksum citati nelle slide IPv6/TCP/UDP riguardano invece traffico
di rete: condividono lo scopo generale di controllo d'integrità, ma non sono
questi stessi calcoli sul file di firmware.

Non si confronta lo SHA-256 di un HEX con quello di un pacchetto ZIP o di un BIN:
sono rappresentazioni diverse, quindi i file non hanno gli stessi byte. Per
verificare il codice applicativo si estraggono e normalizzano le immagini BIN,
poi si confronta lo stesso tipo di contenuto.

La normalizzazione del progetto usa `objcopy --gap-fill 0xff`: gli spazi senza
record dati sono riempiti esplicitamente con il byte FF. Per node2 i dati HEX
sono 79.428 byte, mentre l'intervallo BIN occupa 79.444 byte: i 16 byte aggiuntivi
sono un gap. Per confrontare un HEX con un BIN occorre ricostruire gli stessi indirizzi
e usare il medesimo valore di riempimento per i gap.

Questo confronto riguarda artefatti sul computer: **non è una rilettura completa
della flash dei dongle**. Per il comportamento reale si usano anche log, traffico,
pulsanti e prove funzionali. Hash uguale non implica comportamento certificato.

## Relazione LaTeX

Il PDF di dieci pagine è in inglese. I sorgenti sono in [report/ActivityLink_Report.tex](report/ActivityLink_Report.tex),
con figure vettoriali e istruzioni di compilazione. Dalla root: `sh scripts/build_report.sh`.
Il PDF resta separato dallo ZIP; lo ZIP include i sorgenti LaTeX.
