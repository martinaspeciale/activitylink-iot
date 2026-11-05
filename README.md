# ActivityLink — progetto individuale IoT 2026

Sorgenti della configurazione verificata: tre dongle nRF52840, MQTT, backend
Python/MySQL e Grafana. La [relazione PDF](ActivityLink_Report.pdf) è inclusa nella root della repository e viene consegnata separatamente dallo ZIP del codice.

## Contenuto

- `firmware/`: HAR con SVM locale, attuatore e configurazione applicativa.
- `backend/`, `config/`, `infra/`: validazione, controllo da SQL e dashboard.
- `ml/ActivityLink_SVM561_Reproduce.ipynb`: unico notebook della release, eseguito.
- `ml/README.md`, `requirements-notebook.txt`: notebook setup and Colab instructions.
- `models/`, `data/`: modello congelato, campioni e attribuzione UCI HAR.
- `scripts/`, `tests/`: setup, build, controllo e riproduzione delle verifiche.
- `results/`: immagini HEX e risultati essenziali citati nella relazione.
- `MANIFEST.json`: dimensioni e SHA-256 dei file distribuiti.

Guida: [riproduzione](docs/REPRODUCE.md), [stack Mac](docs/NATIVE_MAC_STACK.md),
[attribuzioni e componenti](THIRD_PARTY.md).

## Avvio dopo il setup

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

## Comportamento

HAR classifica sul microcontrollore 24 vettori UCI HAR incorporati nella flash:
verde per movimento, blu per postura. Il sensing è simulato; muovere il dongle
non cambia i campioni. SW1 sospende/riprende il monitoraggio.

Il backend salva la telemetria in MySQL e legge SQL per comandare il feedback.
Oltre 6 secondi senza misure valide adaptive segnala rosso; baseline mantiene
l'ultima attività. Il feedback ha SW1 mute e watchdog locale oltre 8 secondi
senza comandi. Non è un dispositivo medico.

Contiki-NG v5.1 è fissato al commit
`2b87baf3ebdde3c8e37ca791d2bc84bfd76c49a4`. Nodi applicativi:
`TARGET=nrf BOARD=nrf52840/dongle`; router: `TARGET=nrf52840 BOARD=dongle`.
La configurazione collaudata è mista, non una migrazione uniforme.

Il notebook è eseguito sul Mac; l'hosting Colab non è verificato. Il retraining
mantiene le predizioni sul test storico ma può differire nei coefficienti:
l'export firmware usa esplicitamente `models/svm561.json` congelato.

Il trainer legge soltanto il training: validazione GroupKFold per soggetto, scaler
riappreso in ogni fold, ricetta fissa senza selezione sul test. Macro-F1 OOF
93,66%; il 96,29% sul test resta un benchmark storico già consultato.
Protocollo, limiti e riproduzione: [ML_VALIDATION.md](docs/ML_VALIDATION.md).

Il pacchetto esclude notebook alternativi, diagnostica di sviluppo, copie della
relazione, copione, screenshot personali, ambienti Python e credenziali locali.

## Repository

Questa repository è stata creata il 3 novembre 2026 dallo stato completo del
progetto. La cronologia è ricostruita per componenti con date convenzionali
dal 20 ottobre al 3 novembre 2026. Le date dei commit non documentano quando
le singole parti sono state effettivamente sviluppate o collaudate.

## Relazione in inglese e LaTeX

La relazione PDF è in inglese e deriva da [ActivityLink_Report.tex](docs/report/ActivityLink_Report.tex).
Sorgente, figure e [istruzioni di compilazione](docs/report/README.md) sono inclusi nel progetto.
Dalla root: `sh scripts/build_report.sh`. Il PDF compilato viene consegnato separatamente.
