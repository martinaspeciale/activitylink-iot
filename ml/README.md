# ActivityLink machine-learning notebook

`ActivityLink_SVM561_Reproduce.ipynb` is the single submission notebook. Its
English explanations, executed tables and figures cover the dataset, five-fold
subject-grouped OOF validation, final candidate fitting, C export, host C/Python
agreement and a separately labelled historical test benchmark.

## Local execution

Use a dedicated Python 3.11+ environment (validated here with Python 3.13.5),
separate from the backend environment. Install
`requirements-notebook.txt`, select that environment as the notebook kernel and
run all cells from the project root or `ml/`. No dongles or backend services are
needed. A host `gcc` command is required for the C-equivalence section.

```sh
python -m pip install -r requirements-notebook.txt
```

The dataset is downloaded automatically with checksum verification unless
`ACTIVITYLINK_DATASET` points to an extracted `UCI HAR Dataset` directory.
Output defaults to a fresh timestamped directory under `results/`.
`ACTIVITYLINK_RESULTS_DIR` can select another empty output directory.

On the prepared Mac, the saved notebook can also be regenerated with:

```sh
tools/ml-venv/bin/python scripts/execute_notebook.py \
  --dataset 'results/2026-11-02-final/ml-reproduction/UCI HAR Dataset' \
  --out results/NEW-NOTEBOOK-RUN
```

The executor requires a new run directory, archives the prior notebook there,
executes in a Jupyter kernel and stores generated artifacts in its `artifacts/`
subdirectory. It also updates the canonical notebook with the actual outputs.
The external dataset path above is specific to the working Mac; it is not
bundled in the submission ZIP. For a fresh download, run the notebook directly.

## Colab setup

Open the same `.ipynb` in Google Colab and select a CPU runtime. The first code
cell installs the numerical and plotting dependencies. Restart the runtime if
required after installation, then run from the beginning. When prompted, upload
the project's source ZIP. The cell copies only six support files into an isolated
notebook-support directory; it does not deploy firmware or start services.

The UCI dataset is then downloaded automatically. Source:
https://colab.research.google.com/notebooks/io.ipynb

This branch is prepared for Colab, but the supplied saved outputs come from a
local Jupyter kernel. Hosted Google Colab execution remains unverified. The
notebook metadata and `execution-summary.json` state the execution environment.

## Files and interpretation

- `ml/retrain.py` provides the same fixed recipe for command-line training
- `ml/evaluate_historical.py` evaluates an already fitted candidate without selection
- `scripts/verify_model.py` checks the frozen reference on the host C compiler
- `models/svm561.json` and the shipped C headers remain unchanged

OOF validation is the primary evaluation. The previously consulted official test
is a historical benchmark, not a new blind test. The candidate JSON and C header
are new artifacts; neither replaces the deployed reference automatically.
Numerical equality with the command-line workflow is checked when validating
the revised notebook. No notebook change retrains or flashes the dongles.
