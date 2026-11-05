#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_ROOT="$ROOT/runtime/report-latex"
OUTPUT="$ROOT/deliverables/ActivityLink_Report.pdf"
mkdir -p "$BUILD_ROOT" "$ROOT/deliverables"

# Isolate each compilation so concurrent runs cannot overwrite PDF objects or auxiliary files
BUILD_DIR=$(mktemp -d "$BUILD_ROOT/build.XXXXXX")
OUTPUT_TMP=$(mktemp "$ROOT/deliverables/.ActivityLink_Report.XXXXXX")
trap 'rm -f "$OUTPUT_TMP"' 0 HUP INT TERM
cd "$ROOT/docs/report"

# Two passes resolve the table of contents and internal links
for pass in 1 2; do
  pdflatex -interaction=nonstopmode -halt-on-error -no-shell-escape \
    -output-directory="$BUILD_DIR" ActivityLink_Report.tex \
    > "$BUILD_DIR/compile-pass$pass.log" 2>&1 || {
    cat "$BUILD_DIR/compile-pass$pass.log"
    exit 1
  }
done

# Preserve the previous deliverable before replacing it with the compiled report
if [ -f "$OUTPUT" ]; then
  mkdir -p "$ROOT/deliverables/archive"
  stamp=$(date +%Y%m%d-%H%M%S)
  cp "$OUTPUT" "$ROOT/deliverables/archive/ActivityLink_Report-$stamp.pdf"
fi

# Replace the deliverable atomically so readers never open a partially copied file
cp "$BUILD_DIR/ActivityLink_Report.pdf" "$OUTPUT_TMP"
mv -f "$OUTPUT_TMP" "$OUTPUT"
printf 'Compiled English LaTeX report: %s\n' "$OUTPUT"
