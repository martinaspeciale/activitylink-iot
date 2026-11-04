"""Execute the submission notebook locally with outputs in a fresh directory."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--dataset", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
notebook_path = ROOT / "ml/ActivityLink_SVM561_Reproduce.ipynb"
shutil.copy2(notebook_path, args.out / "notebook-before.ipynb")
notebook = nbformat.read(notebook_path, as_version=4)

# Discard old outputs so saved results come from this execution
for cell in notebook.cells:
    if cell.cell_type == "code":
        cell.execution_count = None
        cell.outputs = []

# Keep generated candidates and measurements in the requested output directory
os.environ["ACTIVITYLINK_RESULTS_DIR"] = str((args.out / "artifacts").resolve())
os.environ["ACTIVITYLINK_DATASET"] = str(args.dataset.resolve())
os.environ["JUPYTER_PATH"] = str(ROOT / "tools/ml-venv/share/jupyter")
notebook.metadata["execution_note"] = "Executed sequentially in a local Jupyter kernel via nbclient; not hosted Colab"
notebook.metadata["language_info"]["version"] = sys.version.split()[0]
NotebookClient(
    notebook, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}}
).execute()
nbformat.write(notebook, args.out / "ActivityLink_SVM561_Reproduce.ipynb")
nbformat.write(notebook, notebook_path)
print(
    json.dumps(
        {
            "status": "PASS",
            "runtime": "local Mac Python; not hosted Colab",
            "executed_cells": sum(c.cell_type == "code" for c in notebook.cells),
            "notebook": str(notebook_path),
        },
        indent=2,
    )
)
