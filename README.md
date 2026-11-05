# ActivityLink

ActivityLink combines activity classification on an nRF52840 dongle with a separate
feedback dongle and a border router. The Python backend receives MQTT telemetry,
stores it in MySQL and controls the feedback LED. Grafana displays the controller
metrics. Sensing is simulated with stored UCI HAR features; classification runs
on the device. Green means movement, blue means posture and red signals unavailable
recent data. HAR SW1 pauses/resumes recognition; feedback SW1 mutes/unmutes its LED.

This archive contains the project source, configuration, training notebook and
scripts used to run the application and reproduce its scenarios. The report PDF
is supplied separately. Dependencies and generated results are not bundled.

## Preparation

The native service setup targets Intel macOS. Install Python 3.10, Git, CMake and
a host C compiler. Firmware compilation and the router target also require GNU
make and the ARM GNU toolchain; firmware upload additionally requires Nordic
`nrfutil` compatible with the Contiki DFU targets. The launcher recognises the
prepared ARM toolchain path; `ARM_TOOLCHAIN_BIN` and `NRFUTIL` can override it.

From the extracted project directory:

```sh
./scripts/demo.sh setup
./scripts/demo.sh doctor
./scripts/demo.sh ports
```

Setup creates `.venv`, installs runtime dependencies, downloads the pinned
MySQL/Grafana releases and builds Mosquitto from its downloaded source. Downloads
are checked against the hashes recorded in the setup scripts. Contiki-NG is
fetched at the configured revision and the board patch is applied. Setup does
not flash devices. The source archives, executables and environment created by
setup remain local.

Check the role-to-port assignments in `config/hardware.json` against the current
USB enumeration. `config/devices.json` contains the static sensor/actuator roles.
The launcher shows both files with `./scripts/demo.sh config`. Already flashed
dongles boot when powered; they do not need a software launch command.

## Run the application

Connect the three dongles. In terminal 1:

```sh
./scripts/demo.sh router
```

Leave it running. Enter the host password in that terminal if requested to create
the IPv6 interface. In terminal 2:

```sh
./scripts/demo.sh start adaptive
./scripts/demo.sh dashboard
./scripts/demo.sh
```

The last command opens the control menu. `start baseline` selects control without
adaptation. `show COMMAND` prints the underlying commands without executing them,
including from the menu, for example `show stress 3` or `show pause`.

`pause` and `resume` send HAR commands; `buttons` explains the physical SW1 actions.
`watch`, in an optional third terminal, records actual MQTT telemetry independently
of MySQL. Grafana may stop receiving metrics when SQL or the backend is stopped;
MQTT observations remain available only while the broker is reachable. The
Grafana account is `admin`; its locally generated password is in
`runtime/native-stack/credentials.json`. Do not distribute this file.

## Experimental scenarios

Use `./scripts/demo.sh help` for the complete command list.

- `stress` runs one adaptive/baseline pair; `stress 3` runs three alternating pairs.
  Each run has 10 seconds of normal operation, 15 seconds withholding HAR messages
  at application ingress and 15 seconds of recovery. This does not generate radio congestion.
- `physical` records HAR unplug/replug. Start adaptive control, resume HAR and unmute
  feedback first. Keep HAR connected until `READY`, then unplug only HAR for at
  least 15 seconds and reconnect it.
- `services` automatically stops/restarts MySQL and then the broker, checking recovery.
- `mysql-stop`/`mysql-start`, `broker-stop`/`broker-start` and
  `stop-cloud`/`start-cloud` provide manual service interruptions. Restore a manually
  stopped service explicitly. Observe the feedback watchdog through MQTT or the physical LED;
  while the broker is absent, its state cannot be received over MQTT.
- `check` verifies pause/resume, fresh telemetry, SQL and Grafana queries. Run it with
  active nodes and unmuted feedback after about 15 seconds of normal operation.
- `sql`, `queue` and `tests` run the SQL data-contract checks, the software queue test
  and the backend/protocol suite. Queue testing uses mocked MQTT and SQL.

Scenarios create new directories under `results/demo/`; SQL and queue checks are
distinct from radio-device experiments. The automatic stress/service helpers
restore normal control, while manual stop commands require the matching start.

To finish, run `./scripts/demo.sh stop-cloud`, stop `watch` if active, press Ctrl+C
in the router terminal and disconnect the dongles. MySQL, Mosquitto and Grafana
may remain running.

## Firmware maintenance

`./scripts/demo.sh build` compiles the three roles without flashing. To upload,
put the selected board into DFU mode and use
`./scripts/demo.sh flash har|feedback|router /dev/cu.DFU_PORT`, choosing one role
and its observed bootloader port. A DFU port need not match the application port.
Stop the router connection before flashing that board. Maintenance is unnecessary
for a demonstration with firmware already installed.

## Machine-learning workbook

`ml/ActivityLink_SVM561_Reproduce.ipynb` contains the training procedure, results,
plots and dataset reference. Use a separate Python 3.11+ environment:

```sh
python3.13 -m venv tools/ml-venv
tools/ml-venv/bin/python -m pip install -r requirements-notebook.txt
```

Select that environment as the Jupyter kernel and execute cells in order from the
project root or `ml/`. A host C compiler accessible as `gcc` is needed for the
C/Python comparison. The notebook downloads the UCI dataset unless an existing
copy is specified with `ACTIVITYLINK_DATASET`. Its Colab setup accepts this source
ZIP; complete local execution is verified, while hosted Colab execution remains
unverified. Retraining saves a separate model without changing the firmware.

## Dataset source

*Human Activity Recognition Using Smartphones*, Reyes-Ortiz J., Anguita D.,
Ghio A., Oneto L. and Parra X.,
[UCI Machine Learning Repository](https://doi.org/10.24432/C54S4K),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Included samples are selected published features converted to float32;
classifier weights are learned from the training split. Downloaded dependencies
retain their original licence notices.

## Repository

Questa repository è stata creata il 3 novembre 2026 dallo stato completo del
progetto. La cronologia è ricostruita per componenti con date convenzionali
dal 20 ottobre al 3 novembre 2026. Le date dei commit non documentano quando
le singole parti sono state effettivamente sviluppate o collaudate.
