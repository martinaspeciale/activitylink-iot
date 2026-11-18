#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
WORK="$ROOT"
if [ -d "$ROOT/workspace" ]; then WORK="$ROOT/workspace"; fi
CONTIKI="$WORK/vendor/contiki-ng"
PATCH="$ROOT/support/patches/contiki-v5.1-sw1-pin.patch"
mkdir -p "$WORK/vendor"
if [ ! -e "$CONTIKI/.git" ]; then
  git clone https://github.com/contiki-ng/contiki-ng.git "$CONTIKI"
fi
EXPECTED=2b87baf3ebdde3c8e37ca791d2bc84bfd76c49a4
if [ "$(git -C "$CONTIKI" rev-parse HEAD)" != "$EXPECTED" ]; then
  [ -z "$(git -C "$CONTIKI" status --porcelain)" ] || {
    echo 'Vendor has local changes: refusing checkout' >&2
    exit 1
  }
  git -C "$CONTIKI" checkout "$EXPECTED"
fi
git -C "$CONTIKI" submodule update --init arch/cpu/arm/CMSIS arch/cpu/nrf/lib/nrfx arch/cpu/nrf/lib/tinyusb arch/cpu/nrf52840/lib/nrf52-sdk
if git -C "$CONTIKI" apply --check "$PATCH" 2>/dev/null; then
  git -C "$CONTIKI" apply "$PATCH"
else
  git -C "$CONTIKI" apply --reverse --check "$PATCH"
fi
