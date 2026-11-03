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
Il target `dfu-upload` del laboratorio comprende invece il caricamento.

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
Il validatore usato nello sviluppo controlla proprio somma, lunghezza e indirizzi;
il riepilogo dei tre HEX distribuiti è in
`results/2026-11-02-final/firmware/summary.json`.

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
sono un gap. Con il riempimento coerente le immagini ricostruite dei tre ruoli
corrispondono ai BIN dei pacchetti DFU dei flash noti, come documenta `summary.json`.

Questo confronto riguarda artefatti sul computer: **non è una rilettura completa
della flash dei dongle**. Per il comportamento reale si usano anche log, traffico,
pulsanti e prove funzionali. Hash uguale non implica comportamento certificato.

### Collegamento con il corso

Riferimenti ai PDF del corso disponibili nella cartella originale, contando le
pagine del PDF:

- `Righetti_lab.pdf`, p. 77: output della build, compresi ELF, HEX, BIN e MAP.
- Pp. 7 e 14: installazione di `nrfutil` e strumenti Nordic.
- P. 90: compilazione e caricamento con il target `.dfu-upload`.
- P. 193: caricamento DFU del border router e successivo collegamento SLIP.
- `Righetti.pdf`, pp. 5 e 10: checksum nelle intestazioni di rete; non una lezione
  sul checksum Intel HEX o sul manifest SHA-256 del progetto.

Nei PDF controllati non è stata trovata una spiegazione dedicata dell'algoritmo
SHA-256 o della struttura Intel HEX a livello di singolo record. Questi controlli
approfondiscono e documentano la procedura di build e riproduzione; non vengono
presentati come esercizi obbligatori aggiuntivi del laboratorio.
