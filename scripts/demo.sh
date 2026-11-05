#!/bin/sh

# Run from any directory; every command below uses the same project root
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
MAKE=${MAKE:-gmake}
DRY_RUN=0

if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi

# The prepared host keeps the ARM tools here; an explicit override takes precedence
ARM_TOOLCHAIN_BIN=${ARM_TOOLCHAIN_BIN:-"$HOME/opt/arm-toolchains/arm-gnu-toolchain-12.3.rel1-darwin-x86_64-arm-none-eabi/bin"}
if [ -d "$ARM_TOOLCHAIN_BIN" ]; then
    PATH="$ARM_TOOLCHAIN_BIN:$PATH"
    export PATH
fi

run() {
    printf '+'
    printf ' %s' "$@"
    printf '\n'
    if [ "$DRY_RUN" -eq 0 ]; then
        "$@"
    fi
}

need_python() {
    if [ "$DRY_RUN" -eq 0 ] && [ ! -x "$PYTHON" ]; then
        echo 'Run ./scripts/demo.sh setup first' >&2
        exit 1
    fi
}

new_result() {
    OUT="$ROOT/results/demo/$(date +%Y%m%d-%H%M%S)-$1-$$"
    echo "Results: $OUT"
}

stack() {
    need_python
    run "$PYTHON" scripts/native_stack.py "$@"
}

# Display assignments without sourcing the user's shell configuration
ports() {
    need_python
    run "$PYTHON" scripts/ports.py
    run "$PYTHON" -m serial.tools.list_ports -v
}

help_text() {
    cat <<'HELP'
Usage: ./scripts/demo.sh [--dry-run] COMMAND [ARGUMENTS]

Preparation
  setup                   Create .venv, install runtime dependencies and prepare local services/Contiki
  doctor                  Check tools and enumerate the observed USB ports
  ports                   Show role assignments and current USB enumeration
  config                  Display the device-role and USB inventory files
  router                  Connect the border router; leave this terminal running (Ctrl+C to stop)
  build                   Compile all three firmware roles without flashing
  flash ROLE DFU_PORT     Explicit firmware upload; ROLE is har, feedback or router

Normal operation
  start [adaptive|baseline] Start services and a fresh control run (default: adaptive)
  status                  Show project service status
  dashboard               Open Grafana with the latest observed controller run selected
  watch                   Observe/log actual MQTT telemetry without relying on MySQL (Ctrl+C to stop)
  pause | resume          Send the HAR P/R command
  buttons                 Show the physical HAR pause and feedback mute procedure
  check                   Verify fresh nodes, pause/resume, SQL and Grafana queries
  stop-cloud              Stop only the Python backend
  start-cloud             Resume adaptive backend control

Scenarios
  stress [PAIRS]          Controlled HAR message withholding: 10s normal, 15s loss, 15s recovery
                          One pair by default; use stress 3 for three alternating pairs
  physical               Record manual HAR unplug/replug; act only after READY
  services               Automatically stop/restart MySQL, then the broker, and verify recovery
  mysql-stop | mysql-start    Manual database interruption/recovery
  broker-stop | broker-start  Manual MQTT interruption/recovery
  sql                     Real temporary-schema duplicate/order/freshness checks
  queue                   Software queue overflow check with mocked MQTT and SQL
  tests                   Run the backend/protocol unit suite

Already flashed dongles boot when powered; router connects their network to the host
Only flash rewrites a board; DFU mode and its USB port must be selected physically
Router disconnection is not an experimentally verified scenario in the report
The native service setup targets the prepared Intel macOS host
HELP
}

menu() {
    help_text
    echo 'Use another terminal for router; this menu remains available for scenarios'
    while true; do
        printf '\nCommand (help or exit): '
        IFS= read -r choice || break
        case "$choice" in
            exit|quit) break ;;
            help|'') help_text ;;
            'start adaptive') invoke start adaptive ;;
            'start baseline') invoke start baseline ;;
            'stress 3') invoke stress 3 ;;
            setup|doctor|ports|config|router|build|start|status|dashboard|watch|pause|resume|buttons|check|stop-cloud|start-cloud|stress|physical|services|mysql-stop|mysql-start|broker-stop|broker-start|sql|queue|tests)
                invoke "$choice"
                ;;
            *) echo 'Use a command shown above; flash ROLE DFU_PORT is available outside the menu' ;;
        esac
    done
}

# Run menu selections in a child shell so a failed scenario does not close the menu
invoke() {
    if [ "$DRY_RUN" -eq 1 ]; then
        if ! sh "$ROOT/scripts/demo.sh" --dry-run "$@"; then
            echo 'Command failed; inspect the message before continuing' >&2
        fi
    else
        if ! sh "$ROOT/scripts/demo.sh" "$@"; then
            echo 'Command failed; inspect the message before continuing' >&2
        fi
    fi
}

COMMAND=${1:-menu}
if [ "$#" -gt 0 ]; then
    shift
fi
case "$COMMAND" in
    help|--help|-h) help_text ;;
    menu) menu ;;
    setup)
        BOOTSTRAP=${PYTHON_BOOTSTRAP:-python3.10}
        if [ ! -x "$PYTHON" ]; then
            run "$BOOTSTRAP" -m venv .venv
        fi
        run "$PYTHON" -m pip install -r requirements-native.txt
        run "$PYTHON" scripts/setup_native_stack.py
        run sh scripts/setup_mosquitto.sh
        run sh scripts/setup_contiki.sh
        echo 'ARM GNU tools, GNU make and Nordic nrfutil are separate firmware-tool prerequisites'
        ;;
    doctor)
        echo "Project: $ROOT"
        for tool in "$MAKE" arm-none-eabi-gcc arm-none-eabi-objcopy gcc; do
            if ! command -v "$tool"; then
                echo "Missing tool: $tool"
            fi
        done
        ports
        ;;
    ports) ports ;;
    config)
        run cat config/hardware.json
        run cat config/devices.json
        ;;
    router)
        need_python
        if [ "$DRY_RUN" -eq 1 ]; then
            run "$PYTHON" scripts/ports.py
            BORDER_ROUTER='${BORDER_ROUTER from config/hardware.json}'
        else
            ASSIGNMENTS=$("$PYTHON" scripts/ports.py)
            eval "$ASSIGNMENTS"
            if [ ! -e "$BORDER_ROUTER" ]; then
                echo 'Border-router port absent; compare demo.sh ports with config/hardware.json' >&2
                exit 1
            fi
        fi
        echo 'Leave this terminal open; enter the sudo password here if requested'
        run "$MAKE" -C vendor/contiki-ng/examples/rpl-border-router \
            TARGET=nrf52840 BOARD=dongle "PORT=$BORDER_ROUTER" connect-router
        ;;
    build)
        new_result firmware
        run env "MAKE=$MAKE" "OUT_DIR=$OUT" sh scripts/build_firmware.sh
        ;;
    flash)
        ROLE=${1:-}
        DFU_PORT=${2:-}
        case "$ROLE" in
            har|feedback|router) : ;;
            *)
                echo 'Usage: demo.sh flash har|feedback|router /dev/cu.DFU_PORT' >&2
                exit 2
                ;;
        esac
        if [ -z "$DFU_PORT" ]; then
            echo 'Specify the USB port observed after entering DFU mode' >&2
            exit 2
        fi
        NRFUTIL=${NRFUTIL:-nrfutil}
        echo 'Upload to the selected DFU port; the board must already be in bootloader mode'
        if [ "$ROLE" = router ]; then
            run "$MAKE" -C vendor/contiki-ng/examples/rpl-border-router \
                TARGET=nrf52840 BOARD=dongle "PORT=$DFU_PORT" "NRFUTIL=$NRFUTIL" border-router.dfu-upload
        else
            NODE_ROLE=1
            if [ "$ROLE" = feedback ]; then
                NODE_ROLE=2
            fi
            run "$MAKE" -C firmware/node TARGET=nrf BOARD=nrf52840/dongle clean
            run "$MAKE" -C firmware/node TARGET=nrf BOARD=nrf52840/dongle \
                "ROLE=$NODE_ROLE" "PORT=$DFU_PORT" "NRFUTIL=$NRFUTIL" activitylink.dfu-upload
        fi
        ;;
    start)
        MODE=${1:-adaptive}
        case "$MODE" in
            adaptive) ADAPTIVE=1 ;;
            baseline) ADAPTIVE=0 ;;
            *)
                echo 'Mode must be adaptive or baseline' >&2
                exit 2
                ;;
        esac
        RUN_ID="demo-$MODE-$(date +%Y%m%d-%H%M%S)-$$"
        stack stop-cloud
        stack start --adaptive "$ADAPTIVE" --run-id "$RUN_ID"
        ;;
    status) stack status ;;
    dashboard)
        need_python
        run "$PYTHON" scripts/demo_status.py --dashboard
        ;;
    watch)
        need_python
        new_result watch
        run "$PYTHON" scripts/demo_status.py --watch "$OUT"
        ;;
    pause|resume)
        need_python
        run "$PYTHON" scripts/control.py "$COMMAND" --host ::1
        ;;
    buttons)
        cat <<'BUTTONS'
Keep the router and services running; use watch in another terminal
1. Press HAR SW1: HAR reports enabled=0 and both lights should turn off
2. Press HAR SW1 again: activity classification and green/blue feedback resume
3. Press feedback SW1: only its local light is muted; telemetry continues
4. Press feedback SW1 again to remove mute before any failure experiment
Do not use RESET; button presses are physical actions, not shell-generated input
BUTTONS
        ;;
    check)
        need_python
        new_result check
        if [ "$DRY_RUN" -eq 1 ]; then
            RUN_ID='ACTIVE_RUN_FROM_SQL'
        else
            RUN_ID=$("$PYTHON" scripts/demo_status.py --run-id)
        fi
        run "$PYTHON" scripts/native_stack_check.py --out "$OUT" --run-id "$RUN_ID" --commands
        ;;
    stop-cloud) stack stop-cloud ;;
    start-cloud)
        stack stop-cloud
        stack start-cloud --adaptive 1 --run-id "demo-adaptive-$(date +%Y%m%d-%H%M%S)-$$"
        ;;
    stress)
        PAIRS=${1:-1}
        case "$PAIRS" in
            ''|*[!0-9]*|0)
                echo 'Specify a positive integer number of pairs' >&2
                exit 2
                ;;
        esac
        need_python
        new_result stress
        echo 'Withhold HAR telemetry at application ingress; this does not generate radio congestion'
        run "$PYTHON" scripts/hardware_stress.py --out "$OUT" --repeats "$PAIRS"
        ;;
    physical)
        need_python
        new_result physical
        echo 'Keep all boards connected until READY; then unplug only HAR, wait at least 15s and replug'
        run "$PYTHON" scripts/physical_failure_check.py --out "$OUT"
        ;;
    services)
        need_python
        new_result services
        echo 'This automatically interrupts the project MySQL and broker; leave nodes/router connected'
        run "$PYTHON" scripts/service_recovery_check.py --out "$OUT"
        ;;
    mysql-stop) stack stop-mysql ;;
    mysql-start) stack start-mysql ;;
    broker-stop) stack stop-broker ;;
    broker-start) stack start-broker ;;
    sql)
        need_python
        new_result sql
        run mkdir -p "$OUT"
        run "$PYTHON" tests/backend_sql_contract.py --output "$OUT/summary.json"
        ;;
    queue)
        need_python
        echo 'Software test: real callback/consumer, mocked MQTT and SQL; no dongle traffic flood'
        run "$PYTHON" -m unittest discover -s tests -p test_backend_queue.py -v
        ;;
    tests)
        need_python
        run "$PYTHON" -m unittest discover -s tests -p 'test_*.py' -v
        ;;
    *)
        help_text
        exit 2
        ;;
esac
