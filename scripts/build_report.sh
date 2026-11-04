#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_DIR="$ROOT/runtime/report-latex"
OUTPUT="$ROOT/deliverables/ActivityLink_Report.pdf"
mkdir -p "$BUILD_DIR" "$ROOT/deliverables"
cd "$ROOT/docs/report"

# Two passes resolve PDF form fields and document references
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
cp "$BUILD_DIR/ActivityLink_Report.pdf" "$OUTPUT"
printf 'Compiled English LaTeX report: %s\n' "$OUTPUT"
