# English LaTeX report

`ActivityLink_Report.tex` is the canonical report source. The PDF is generated
with pdfLaTeX, not HTML/browser printing. It contains eight A4 pages and two
fillable author fields on page 1. The complete PDF is delivered separately
from the source ZIP.

From the project root, with a LaTeX installation containing the packages listed
in the source preamble:

```sh
sh scripts/build_report.sh
```

The build uses the supplied vector figures and runs pdfLaTeX twice. It writes
intermediate files under `runtime/report-latex/`, preserves an existing PDF in
`deliverables/archive/`, and creates `deliverables/ActivityLink_Report.pdf`.
Fill in the author fields after the final compilation; rebuilding creates a
fresh PDF from the source.

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
