# English LaTeX report

`ActivityLink_Report.tex` is the canonical report source. The layout uses a classic
academic article style with a centered title, black numbered headings and plain
page numbers. The PDF is generated
with pdfLaTeX, not HTML/browser printing. It contains ten A4 pages: a dedicated title page, a clickable table of contents
and eight report pages. The cover prints Martina Speciale and student ID 603047 as ordinary text,
without editable fields or borders. The complete PDF is delivered separately
from the source ZIP.

From the project root, with a LaTeX installation containing the packages listed
in the source preamble:

```sh
sh scripts/build_report.sh
```

The build uses the supplied vector figures and Grafana screenshots and runs pdfLaTeX twice. It writes
intermediate files under `runtime/report-latex/`, preserves an existing PDF in
`deliverables/archive/`, and creates `deliverables/ActivityLink_Report.pdf`.
Author details can be changed in the LaTeX source before rebuilding.

The figures are generated from the preserved 2 November hardware measurements.
To regenerate them, use a Python environment with Matplotlib (the pinned version
is recorded in `requirements-report.txt`):

```sh
python docs/report/make_figures.py
```

Regenerating figures does not rerun hardware experiments or alter archived data.
The report distinguishes the 2 November stress campaign, 4 November hardware
regression, mocked queue saturation check and historical machine-learning test.
Legacy HTML report files in the operational workspace are not the deliverable
source and are excluded from the submission ZIP.

## Grafana screenshots

Figure 2 contains real browser captures of the first adaptive/baseline hardware
pair. Measurements were recorded on 2 November; screenshots were captured on
4 November. The light theme is native Grafana. Only the top dashboard row is
captured; chart values and labels are not edited. The adjacent `.png.json` files
record the run IDs, time ranges, source summaries and capture URLs. The images
show missing HAR telemetry, the differing LED response and recovery. They do not
represent new experiments or physical unplug tests.

Compilation uses the supplied PNG files and needs no running services. Optional
recapture requires the prepared Mac stack with its original SQL measurements,
Grafana on port 3000, local credentials under `runtime/native-stack/`, Node.js 22
and Google Chrome in `/Applications`. From the project root, choose new output
names to preserve the supplied evidence:

```sh
node docs/report/capture_grafana.mjs results/2026-11-02-final/stress/pair-1-adaptive/summary.json runtime/grafana-adaptive-new.png
node docs/report/capture_grafana.mjs results/2026-11-02-final/stress/pair-1-baseline/summary.json runtime/grafana-baseline-new.png
```

The capture tool uses an isolated headless browser and does not alter the
dashboard, backend or archived measurements. Dongles are unnecessary when
viewing these preserved runs; new hardware measurements require them.

## Cover and reading order

The cover includes the official University of Pisa horizontal blue logo, with
original artwork and source details in `assets-en/unipi-logo.SOURCE.md`. The
provided vector PDF preserves the downloaded SVG proportions and colors.

The body moves from the use case and an operating cycle to devices, machine
learning, MQTT/JSON choices and the two SQL tables. Experimental design and
results follow, ending with robustness, limitations and conclusions. Complete
startup commands remain in the reproduction guides rather than being duplicated
in the report. The report remains ten pages including cover and contents.
