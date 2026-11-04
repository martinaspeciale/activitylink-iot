"""Compile shipped C predictor and compare with shipped JSON coefficients.
No training/tuning. Default: shipped replay rows; --dataset: full official test.
"""
import argparse, csv, ctypes, hashlib, json, subprocess, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--dataset", type=Path)
p.add_argument("--output", type=Path, default=ROOT / "results/model-equivalence.json")
a = p.parse_args()
m = json.loads((ROOT / "models/svm561.json").read_text())
if a.dataset:
    X = np.loadtxt(a.dataset / "test/X_test.txt")
else:
    with (ROOT / "data/replay.csv").open() as f:
        X = np.array([[float(r[f"x{i}"]) for i in range(561)] for r in csv.DictReader(f)])

# Use float32 inputs to match the representation consumed by the C predictor
X = np.ascontiguousarray(X, dtype=np.float32)
expected = np.array(m["classes"])[(X.astype(np.float64) @ np.array(m["weights"]).T + m["bias"]).argmax(axis=1)]

# Compile and run the shipped predictor on the host, not on the ARM device
with tempfile.TemporaryDirectory() as temp:
    d = Path(temp)
    (d / "predict.c").write_text('#include "svm561_predictor.h"\nint predict(const float *x) { return har_predict(x); }\n')
    subprocess.run(["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIC", "-shared",
                    "-I", str(ROOT / "models"), str(d / "predict.c"), "-o", str(d / "predict.so")], check=True)
    lib = ctypes.CDLL(str(d / "predict.so"))
    lib.predict.argtypes = [ctypes.POINTER(ctypes.c_float)]
    lib.predict.restype = ctypes.c_int
    actual = np.array([lib.predict(x.ctypes.data_as(ctypes.POINTER(ctypes.c_float))) for x in X])

# Agreement between implementations is distinct from accuracy against true labels
result = dict(scope="host GCC; shipped JSON vs shipped C; no ARM execution",
              samples=len(X), mismatches=int((actual != expected).sum()),
              header_sha256=hashlib.sha256((ROOT / "models/svm561_predictor.h").read_bytes()).hexdigest(),
              compiler=subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0])
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
if result["mismatches"]: raise SystemExit(1)
