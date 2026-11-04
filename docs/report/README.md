# English LaTeX report

`ActivityLink_Report.tex` is the report source. The ten-page English PDF uses a
classic academic layout with a dedicated cover, official University of Pisa logo,
clickable contents and eight body pages. Martina Speciale and student ID 603047
are ordinary cover text, without editable fields or borders.

## Build

From the project root, with pdfLaTeX and the packages listed in the source preamble:

```sh
sh scripts/build_report.sh
```

The build uses the supplied vector figures and PNG screenshots, runs pdfLaTeX
twice and writes `deliverables/ActivityLink_Report.pdf`. Intermediate files go to
`runtime/report-latex/`; an existing PDF is preserved in `deliverables/archive/`.
No Python packages, browser, running services or dongles are needed for compilation.
Author details can be changed in the LaTeX source before rebuilding.
The compiled report is submitted separately from the source ZIP.

## Figures and provenance

The supplied architecture and quantitative chart are vector PDFs. Figure 2 shows
real Grafana views of the first adaptive/baseline hardware pair, recorded on
2 November and captured on 4 November. Grafana's native light theme is used;
only the upper dashboard row is captured, without editing values or labels.
Adjacent `.png.json` files record run IDs, source summaries, capture time and
selected time ranges. These are views of archived measurements, not new experiments.

`assets-en/unipi-logo.SOURCE.md` records the official source of the supplied
vector logo. Its complete artwork, colors and proportions are preserved.

All assets required to compile the report are included. Internal figure-generation
and browser-capture utilities are excluded from the submission.
