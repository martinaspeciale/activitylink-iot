#!/bin/sh

# Local build only: no Homebrew installation, TLS, sudo or system service
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
BUILD_DIR=${BUILD_DIR:-tools/local-broker/build-no-tls}
if [ -x "$BUILD_DIR/src/mosquitto" ]; then
  echo "Local broker already available: $BUILD_DIR/src/mosquitto"
  exit 0
fi
ARCHIVE=tools/local-broker/mosquitto-2.0.22.tar.gz
EXPECTED=2f752589ef7db40260b633fbdb536e9a04b446a315138d64a7ff3c14e2de6b68

# Fetch the dependency during setup instead of distributing its source archive or executable
if [ ! -f "$ARCHIVE" ]; then
  mkdir -p tools/local-broker
  PARTIAL="$ARCHIVE.part"
  trap 'rm -f "$PARTIAL"' 0 HUP INT TERM
  curl -fL --retry 2 https://mosquitto.org/files/source/mosquitto-2.0.22.tar.gz -o "$PARTIAL"
  DOWNLOADED=$(shasum -a 256 "$PARTIAL")
  [ "${DOWNLOADED%% *}" = "$EXPECTED" ] || {
    echo 'Downloaded Mosquitto source checksum mismatch' >&2
    exit 1
  }
  mv "$PARTIAL" "$ARCHIVE"
fi
ACTUAL=$(shasum -a 256 "$ARCHIVE")
[ "${ACTUAL%% *}" = "$EXPECTED" ] || {
  echo 'Mosquitto source checksum mismatch' >&2
  exit 1
}
SOURCE=tools/local-broker/mosquitto-2.0.22
if [ ! -d "$SOURCE" ]; then
  tar -xzf "$ARCHIVE" -C tools/local-broker
fi
PATCH="$ROOT/patches/mosquitto-2.0.22-no-tls-cmake.patch"
if patch -d "$SOURCE" -p1 --dry-run -R <"$PATCH" >/dev/null 2>&1; then
  echo 'No-TLS CMake patch already applied'
else
  patch -d "$SOURCE" -p1 <"$PATCH"
fi
cmake -S "$SOURCE" -B "$BUILD_DIR" -DWITH_TLS=OFF -DWITH_CLIENTS=OFF \
  -DWITH_APPS=OFF -DWITH_CJSON=OFF -DWITH_PLUGINS=OFF -DWITH_SRV=OFF \
  -DWITH_LIB_CPP=OFF -DWITH_BUNDLED_DEPS=ON -DDOCUMENTATION=OFF
cmake --build "$BUILD_DIR" --target mosquitto -j2
