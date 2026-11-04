#!/bin/sh
set -eu
mkdir -p vendor
if [ ! -e vendor/contiki-ng/.git ]; then
  git clone https://github.com/contiki-ng/contiki-ng.git vendor/contiki-ng
fi
EXPECTED=2b87baf3ebdde3c8e37ca791d2bc84bfd76c49a4
if [ "$(git -C vendor/contiki-ng rev-parse HEAD)" != "$EXPECTED" ]; then
  [ -z "$(git -C vendor/contiki-ng status --porcelain)" ] || {
    echo 'Vendor has local changes: refusing checkout' >&2
    exit 1
  }
  git -C vendor/contiki-ng checkout "$EXPECTED"
fi
git -C vendor/contiki-ng submodule update --init arch/cpu/arm/CMSIS arch/cpu/nrf/lib/nrfx arch/cpu/nrf/lib/tinyusb arch/cpu/nrf52840/lib/nrf52-sdk
if git -C vendor/contiki-ng apply --check ../../patches/contiki-v5.1-sw1-pin.patch 2>/dev/null; then
  git -C vendor/contiki-ng apply ../../patches/contiki-v5.1-sw1-pin.patch
else
  git -C vendor/contiki-ng apply --reverse --check ../../patches/contiki-v5.1-sw1-pin.patch
fi
