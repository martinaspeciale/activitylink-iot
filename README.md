# ActivityLink

Three nRF52840 dongles provide activity recognition, LED feedback and a border
router. Recognition uses stored UCI HAR samples, not live motion. Green means
movement, blue means posture and red means stale data in adaptive mode.
The report PDF is supplied separately.

## Setup

Run commands from the project directory on **Intel macOS**, with Internet access,
Python 3.10, Git, CMake, a C compiler, GNU make (`gmake`) and the ARM GNU toolchain.

```sh
./scripts/demo.sh setup
./scripts/demo.sh check-tools
./scripts/demo.sh ports
```

Check the detected USB ports against `config/hardware.json` and update it if needed.
Setup installs dependencies without flashing devices. Already flashed dongles are
ready to use. Otherwise, run `./scripts/demo.sh build`, put each board in DFU mode
and upload with `./scripts/demo.sh flash har DFU_PORT` (requires `nrfutil`). Use
`feedback` or `router` for the other roles; stop the router connection before
flashing it.

## Demo

Connect all three dongles. In terminal 1:

```sh
./scripts/demo.sh router
```

Leave it running and enter the computer's password if prompted. In terminal 2:

```sh
./scripts/demo.sh start baseline
./scripts/demo.sh status
./scripts/demo.sh dashboard
```

Grafana: <http://127.0.0.1:3000>, username `admin`, password `password`.

Run `./scripts/demo.sh` for the command menu, or append a command directly:

- `pause` / `resume`: pause or resume HAR; pausing turns feedback off.
- `watch`: observe and record MQTT messages in another terminal.
- `status`: check services; `help`: list commands.
- `start adaptive`: enable red feedback when HAR data becomes stale.

SW1 toggles recognition on HAR and mutes/unmutes the LED on feedback.

To compare baseline and adaptive, keep the router and services running, resume
HAR, unmute feedback and run:

```sh
./scripts/demo.sh stress
```

The comparison runs baseline first, then adaptive. Each trial uses 10 seconds of
normal operation, 15 seconds discarding HAR telemetry at backend ingress and
15 seconds of recovery. The command prints the results directory and restores
adaptive control afterwards. Use `stress 3` for three pairs of trials.

To finish, run `./scripts/demo.sh stop-cloud`, stop `watch` and press Ctrl+C in
the router terminal. MySQL, Grafana and the broker may remain running.

## Notebook

Open `ml/ActivityLink_SVM.ipynb`. Use a separate Python 3.11+ environment,
install `requirements-notebook.txt`, select that environment as the notebook
kernel and run the cells in order. A compiler available as `gcc` is required.
The notebook downloads the dataset and saves its results without changing the
firmware.

On **Colab**, upload `requirements-notebook.txt` through **Files** into `/content`
before running the first code cell. It installs dependencies from that file.
If a restart is required, run cells from the beginning and re-upload the file
if it was reset. Hosted Colab execution remains unverified.

Dataset: *Human Activity Recognition Using Smartphones*, Reyes-Ortiz et al.,
[UCI](https://doi.org/10.24432/C54S4K), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
