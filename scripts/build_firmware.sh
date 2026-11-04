#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
MAKE=${MAKE:-make}
OBJCOPY=${OBJCOPY:-arm-none-eabi-objcopy}
SIZE=${SIZE:-arm-none-eabi-size}
OUT_DIR=${OUT_DIR:-results/firmware/build-$(date +%Y%m%d-%H%M%S)}
[ ! -e "$OUT_DIR" ] || { echo 'Output already exists; choose a new OUT_DIR' >&2; exit 1; }
# Use the pinned Contiki revision so builds match the documented platform support.
EXPECTED=2b87baf3ebdde3c8e37ca791d2bc84bfd76c49a4
[ "$(git -C vendor/contiki-ng rev-parse HEAD)" = "$EXPECTED" ] || { echo 'Unexpected Contiki commit' >&2; exit 1; }
for tool in "$MAKE" "$OBJCOPY" "$SIZE"; do command -v "$tool" >/dev/null; done
# Clean between roles because NODE_ROLE changes which C code is compiled.
for role in 1 2; do
  "$MAKE" -C firmware/node TARGET=nrf BOARD=nrf52840/dongle clean
  "$MAKE" -C firmware/node TARGET=nrf BOARD=nrf52840/dongle ROLE="$role"
  out="$OUT_DIR/node$role"
  mkdir -p "$out"
  cp firmware/node/build/nrf/nrf52840/dongle/activitylink.nrf "$out/activitylink.elf"
  "$OBJCOPY" -O ihex "$out/activitylink.elf" "$out/activitylink.hex"
  "$SIZE" "$out/activitylink.elf" > "$out/size.txt"
  "$SIZE" -A "$out/activitylink.elf" > "$out/sections.txt"
done
# The router uses a different Contiki target from the application nodes; no image is flashed here.
br=vendor/contiki-ng/examples/rpl-border-router
"$MAKE" -C "$br" TARGET=nrf52840 BOARD=dongle
out="$OUT_DIR/border-router"
mkdir -p "$out"
cp "$br/build/nrf52840/dongle/border-router.nrf52840" "$out/border-router.elf"
"$OBJCOPY" -O ihex "$out/border-router.elf" "$out/border-router.hex"
"$SIZE" "$out/border-router.elf" > "$out/size.txt"
"$SIZE" -A "$out/border-router.elf" > "$out/sections.txt"
git -C vendor/contiki-ng rev-parse HEAD > "$OUT_DIR/contiki-commit.txt"
git -C vendor/contiki-ng diff > "$OUT_DIR/contiki-local.patch"
printf 'node1,node2: TARGET=nrf BOARD=nrf52840/dongle\nborder-router: TARGET=nrf52840 BOARD=dongle\n' > "$OUT_DIR/platforms.txt"
