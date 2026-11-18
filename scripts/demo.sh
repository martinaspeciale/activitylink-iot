#!/bin/sh

# Run from any directory; every command below uses the same project root
set -eu
export PYTHONDONTWRITEBYTECODE=1
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
WORK="$ROOT"
if [ -d "$ROOT/workspace" ]; then WORK="$ROOT/workspace"; fi
PYTHON="$WORK/.venv/bin/python"
MAKE=${MAKE:-gmake}
DRY_RUN=0

case "${1:-}" in
    --dry-run|--show|show)
        DRY_RUN=1
        shift
        ;;
esac

# The prepared host keeps the ARM tools here; an explicit override takes precedence
ARM_TOOLCHAIN_BIN=${ARM_TOOLCHAIN_BIN:-"$HOME/opt/arm-toolchains/arm-gnu-toolchain-12.3.rel1-darwin-x86_64-arm-none-eabi/bin"}
if [ -d "$ARM_TOOLCHAIN_BIN" ]; then
    PATH="$ARM_TOOLCHAIN_BIN:$PATH"
    export PATH
fi

format_arguments() {
    for argument in "$@"; do
        case "$argument" in
            ''|*[!a-zA-Z0-9_./:=+,-]*)
                quoted=$(printf '%s' "$argument" | sed "s/'/'\\\\''/g")
                printf " '%s'" "$quoted"
                ;;
            *) printf ' %s' "$argument" ;;
        esac
    done
}

print_command() {
    printf '+'
    format_arguments "$@"
    printf '\n'
}

run() {
    print_command "$@"
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
    OUT="$WORK/results/demo/$(date +%Y%m%d-%H%M%S)-$1-$$"
    echo "Results: $OUT"
}

stack() {
    need_python
    run "$PYTHON" support/scripts/native_stack.py "$@"
}

# Display assignments without sourcing the user's shell configuration
ports() {
    need_python
    run "$PYTHON" scripts/ports.py
    run "$PYTHON" -m serial.tools.list_ports -v
}

help_text() {
    cat <<'HELP'
Usage: ./scripts/demo.sh [show] COMMAND [ARGUMENTS]
       ./scripts/demo.sh

Preparation: setup | check-tools | ports | config | router | build
Upload:      flash har|feedback|router DFU_PORT
Operation:   start [adaptive|baseline] | status | dashboard | watch [a|b]
             pause | resume | buttons | stop-cloud | start-cloud
Comparison:  stress [PAIRS] (automatic; default 1 pair)
Manual:      stress start baseline|adaptive
             stress on | stress off | stress stop | stress status | stress cancel
Services:    mysql-stop | mysql-start | broker-stop | broker-start

show COMMAND prints its commands without executing them.
Router stays in a separate terminal; Ctrl+C stops its connection.
Setup targets Intel macOS. Build does not flash; flash requires DFU mode.
Stress withholds HAR messages at cloud ingress, not on the radio.
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
            'show '*) show_choice "${choice#show }" ;;
            'start adaptive') invoke start adaptive ;;
            'start baseline') invoke start baseline ;;
            'watch a') invoke watch a ;;
            'watch b') invoke watch b ;;
            'stress 3') invoke stress 3 ;;
            'stress start baseline') invoke stress start baseline ;;
            'stress start adaptive') invoke stress start adaptive ;;
            'stress on') invoke stress on ;;
            'stress off') invoke stress off ;;
            'stress stop') invoke stress stop ;;
            'stress status') invoke stress status ;;
            'stress cancel') invoke stress cancel ;;
            setup|check-tools|ports|config|router|build|start|status|dashboard|watch|pause|resume|buttons|stop-cloud|start-cloud|stress|mysql-stop|mysql-start|broker-stop|broker-start)
                invoke "$choice"
                ;;
            *) echo 'Use a command shown above; flash ROLE DFU_PORT is available outside the menu' ;;
        esac
    done
}

# Split menu words without eval or filename expansion; command validation stays in the case below
show_choice() {
    request=$1
    set -f
    set -- $request
    if ! sh "$ROOT/scripts/demo.sh" show "$@"; then
        echo 'Unknown command or arguments; see help' >&2
    fi
    set +f
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
            run "$BOOTSTRAP" -m venv "$WORK/.venv"
        fi
        run "$PYTHON" -m pip install -r requirements.txt
        run "$PYTHON" support/scripts/setup_native_stack.py
        run sh support/scripts/setup_mosquitto.sh
        run sh support/scripts/setup_contiki.sh
        echo 'ARM GNU tools, GNU make and Nordic nrfutil are separate firmware-tool prerequisites'
        ;;
    check-tools)
        echo "Project: $ROOT"
        for tool in "$MAKE" arm-none-eabi-gcc arm-none-eabi-objcopy gcc cmake curl git nrfutil; do
            if ! run command -v "$tool"; then
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
        if [ "$DRY_RUN" -eq 1 ] && [ ! -x "$PYTHON" ]; then
            run "$PYTHON" scripts/ports.py
            BORDER_ROUTER='${BORDER_ROUTER from config/hardware.json}'
        else
            print_command "$PYTHON" scripts/ports.py
            ASSIGNMENTS=$("$PYTHON" scripts/ports.py)
            eval "$ASSIGNMENTS"
            if [ "$DRY_RUN" -eq 0 ] && [ ! -e "$BORDER_ROUTER" ]; then
                echo 'Border-router port absent; compare demo.sh ports with config/hardware.json' >&2
                exit 1
            fi
        fi
        echo 'Leave this terminal open; enter the sudo password here if requested'
        run "$MAKE" -C "$WORK/vendor/contiki-ng/examples/rpl-border-router" \
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
            run "$MAKE" -C "$WORK/vendor/contiki-ng/examples/rpl-border-router" \
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
        BROKER=${1:-a}
        case "$BROKER" in
            a|b) ;;
            *) echo 'Use watch [a|b]' >&2; exit 2 ;;
        esac
        need_python
        new_result "watch-$BROKER"
        run "$PYTHON" scripts/demo_status.py --watch "$OUT" --broker "$BROKER"
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
    stop-cloud) stack stop-cloud ;;
    start-cloud)
        stack stop-cloud
        stack start-cloud --adaptive 1 --run-id "demo-adaptive-$(date +%Y%m%d-%H%M%S)-$$"
        ;;
    stress)
        case "${1:-}" in
            start)
                MODE=${2:-baseline}
                case "$MODE" in
                    baseline|adaptive) ;;
                    *) echo 'Use stress start baseline|adaptive' >&2; exit 2 ;;
                esac
                need_python
                new_result stress-manual
                run "$PYTHON" scripts/hardware_stress.py --out "$OUT" --control start --mode "$MODE"
                exit
                ;;
            on|off|stop|status|cancel)
                need_python
                run "$PYTHON" scripts/hardware_stress.py --control "$1"
                exit
                ;;
        esac
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
    mysql-stop) stack stop-mysql ;;
    mysql-start) stack start-mysql ;;
    broker-stop) stack stop-broker ;;
    broker-start) stack start-broker ;;
    *)
        help_text
        exit 2
        ;;
esac
