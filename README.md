# ActivityLink — progetto individuale IoT 2026

Sorgenti della configurazione verificata: tre dongle nRF52840, MQTT, backend
Python/MySQL e Grafana. La [relazione PDF](ActivityLink_Report.pdf) è inclusa nella root della repository e viene consegnata separatamente dallo ZIP del codice.

## Contenuto

- `firmware/`: HAR con SVM locale, attuatore e configurazione applicativa.
- `backend/`, `config/`, `infra/`: validazione, controllo da SQL e dashboard.
- `ml/ActivityLink_SVM561_Reproduce.ipynb`: unico notebook della release, eseguito.
- `models/`, `data/`: modello congelato, campioni e attribuzione UCI HAR.
- `scripts/`, `tests/`: setup, build, controllo e riproduzione delle verifiche.
- `results/`: immagini HEX e risultati essenziali citati nella relazione.
- `MANIFEST.json`: dimensioni e SHA-256 dei file distribuiti.

Guida: [riproduzione](docs/REPRODUCE.md), [stack Mac](docs/NATIVE_MAC_STACK.md),
[attribuzioni e componenti](THIRD_PARTY.md).

Dopo il setup, dalla root `make connect-router` avvia il collegamento SLIP.
Il target richiama il programma Contiki già compilato; per una porta diversa
usare `make connect-router PORT=/dev/cu.usbmodem...`.

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
