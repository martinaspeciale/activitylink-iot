"""Evaluate a trained candidate on the historical UCI test split."""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]


def evaluate(dataset, candidate):
    model = json.loads(candidate.read_text())

    # This separate evaluation reads the already consulted test; it performs no fitting
    X = np.loadtxt(dataset / 'test/X_test.txt')
    y = np.loadtxt(dataset / 'test/y_test.txt', dtype=int)
    groups = np.loadtxt(dataset / 'test/subject_test.txt', dtype=int)
    training_groups = np.loadtxt(dataset / 'train/subject_train.txt', dtype=int)
    if set(groups) & set(training_groups):
        raise ValueError('Official train/test subject overlap')
    weights = np.asarray(model['weights'])
    bias = np.asarray(model['bias'])

    # Choose the largest linear score; these scores are not class probabilities
    pred = np.asarray(model['classes'])[(X @ weights.T + bias).argmax(axis=1)]

    # Compare with the shipped reference without replacing either model
    frozen = json.loads((ROOT / 'models/svm561.json').read_text())
    old = np.asarray(frozen['classes'])[(X.astype(np.float32).astype(np.float64)
        @ np.asarray(frozen['weights']).T + frozen['bias']).argmax(axis=1)]
    return dict(scope='historical benchmark only; already consulted; no training or selection',
                source='https://doi.org/10.24432/C54S4K', test_rows=len(y),
                test_subjects=sorted(map(int, set(groups))), subject_overlap=0,
                accuracy=float(accuracy_score(y, pred)),
                macro_f1=float(f1_score(y, pred, average='macro', zero_division=0)),
                errors=int((pred != y).sum()),
                confusion_matrix=confusion_matrix(y, pred).tolist(),
                classification_report=classification_report(y, pred, output_dict=True, zero_division=0),
                prediction_mismatches_vs_shipped=int((pred != old).sum()),
                max_weight_difference=float(np.abs(weights - frozen['weights']).max()),
                used_for_selection=False, firmware_replaced=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in (args.candidate.resolve(), (ROOT / 'models/svm561.json').resolve()):
        raise ValueError('Evaluation must not overwrite a model')
    result = evaluate(args.dataset, args.candidate)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
