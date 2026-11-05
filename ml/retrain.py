"""Train and validate a fixed recipe using ONLY the official training subjects.

The historical test benchmark is deliberately a separate, read-only evaluation
(ml/evaluate_historical.py). No test score selects or accepts this model.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import zipfile

import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[1]
URL = (
    'https://archive.ics.uci.edu/static/public/240/human+activity+recognition+using+smartphones.zip'
)
SHA = 'c00b803081a5c797cd5e4b83700a9810b38d53d9d84e01917e090e1fdbc81031'

# Keep the training recipe fixed; the official test does not choose these settings
RECIPE = dict(
    features=561,
    C=0.1,
    dual='auto',
    max_iter=5000,
    random_state=42,
    folds=5,
    grouping='subject',
    feature_selection=False,
    hyperparameter_search=False,
    rejection_threshold=False,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_dataset(out):
    archive = out / 'har.zip'
    if not archive.exists() or digest(archive) != SHA:
        temp = archive.with_suffix('.part')
        with urllib.request.urlopen(URL, timeout=120) as src, temp.open('wb') as dst:
            while chunk := src.read(1048576):
                dst.write(chunk)
        if digest(temp) != SHA:
            raise RuntimeError('Dataset checksum mismatch')
        os.replace(temp, archive)

    # The archive contains both splits, but train_only() reads only the training files
    with zipfile.ZipFile(archive) as z:
        z.extractall(out / 'download')
    with zipfile.ZipFile(out / 'download/UCI HAR Dataset.zip') as z:
        z.extractall(out)
    return out / 'UCI HAR Dataset'


def grouped_validation(X, y, subjects, folds=5):
    """No access to a dataset path or to official test arrays is possible here."""
    pipeline = make_pipeline(
        StandardScaler(),
        LinearSVC(
            C=RECIPE['C'],
            dual=RECIPE['dual'],
            max_iter=RECIPE['max_iter'],
            random_state=RECIPE['random_state'],
        ),
    )
    predictions = np.zeros_like(y)
    coverage = np.zeros(len(y), dtype=int)
    rows = []

    # Group by person so windows from one person cannot appear on both sides of a fold
    for fold, (train, valid) in enumerate(GroupKFold(n_splits=folds).split(X, y, subjects), 1):
        training_subjects = sorted(map(int, set(subjects[train])))
        validation_subjects = sorted(map(int, set(subjects[valid])))
        if set(training_subjects) & set(validation_subjects):
            raise RuntimeError('Subject leakage')

        # Fit a fresh scaler and classifier using only the training part of this fold
        fitted = clone(pipeline).fit(X[train], y[train])
        pred = fitted.predict(X[valid])

        # Collect out-of-fold predictions; each row is evaluated once without training on it
        predictions[valid] = pred
        coverage[valid] += 1
        rows.append(
            dict(
                fold=fold,
                training_subjects=training_subjects,
                validation_subjects=validation_subjects,
                subject_overlap=0,
                training_rows=len(train),
                validation_rows=len(valid),
                scaler_samples_seen=int(fitted[0].n_samples_seen_),
                accuracy=float(accuracy_score(y[valid], pred)),
                macro_f1=float(f1_score(y[valid], pred, average='macro', zero_division=0)),
            )
        )
        print(f'Fold {fold}/{folds}: macro-F1={rows[-1]["macro_f1"]:.6f}', flush=True)
    if not np.all(coverage == 1):
        raise RuntimeError('Each training row must be held out exactly once')
    result = dict(
        scope='internal grouped validation of a fixed historical recipe; not a new blind external test',
        official_test_used=False,
        model_selection_on_test=False,
        recipe=RECIPE,
        folds=rows,
        rows=len(y),
        subjects=sorted(map(int, set(subjects))),
        oof_accuracy=float(accuracy_score(y, predictions)),
        oof_macro_f1=float(f1_score(y, predictions, average='macro', zero_division=0)),
        fold_macro_f1_mean=float(np.mean([r['macro_f1'] for r in rows])),
        fold_macro_f1_std=float(np.std([r['macro_f1'] for r in rows], ddof=1)),
        confusion_matrix=confusion_matrix(y, predictions).tolist(),
        classification_report=classification_report(
            y, predictions, output_dict=True, zero_division=0
        ),
        all_rows_predicted_once=True,
        limitation='Recipe already existed historically; this does not erase past consultation of the official test.',
    )
    return pipeline, result, predictions


def train_only(dataset, out):
    out.mkdir(parents=True, exist_ok=True)

    # The protocol is fixed and written BEFORE fitting or reporting any score
    (out / 'protocol.json').write_text(json.dumps(RECIPE, indent=2) + '\n')
    paths = [
        dataset / 'train' / name for name in ('X_train.txt', 'y_train.txt', 'subject_train.txt')
    ]
    X = np.loadtxt(paths[0])
    y = np.loadtxt(paths[1], dtype=int)
    subjects = np.loadtxt(paths[2], dtype=int)
    if X.ndim != 2 or X.shape[1] != 561 or len(X) != len(y) or len(y) != len(subjects):
        raise ValueError('Invalid training shapes')
    if not np.isfinite(X).all() or not set(y) <= set(range(1, 7)):
        raise ValueError('Invalid training values')
    pipeline, result, predictions = grouped_validation(X, y, subjects, RECIPE['folds'])

    # Refit the same fixed recipe on all training subjects, without reading test/
    fitted = pipeline.fit(X, y)
    scaler, svm = fitted.steps[0][1], fitted.steps[1][1]

    # Fold standardization into the linear coefficients so C accepts the original features
    weights = svm.coef_ / scaler.scale_
    bias = svm.intercept_ - weights @ scaler.mean_
    model = dict(
        name='svm561',
        classes=svm.classes_.tolist(),
        indices=list(range(561)),
        weights=weights.tolist(),
        bias=bias.tolist(),
    )

    # Write a candidate to the output directory; leave the deployed firmware model unchanged
    (out / 'svm561.json').write_text(json.dumps(model))
    np.savetxt(
        out / 'oof_predictions.csv',
        np.column_stack((subjects, y, predictions)),
        fmt='%d',
        delimiter=',',
        header='subject,true,predicted',
        comments='',
    )
    result.update(
        numpy=np.__version__,
        sklearn=sklearn.__version__,
        files_sha256={str(p.relative_to(dataset)): digest(p) for p in paths},
        candidate_sha256=digest(out / 'svm561.json'),
        firmware_replaced=False,
    )
    (out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path)
    parser.add_argument('--out', type=Path, default=ROOT / 'results/train-only')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    dataset = args.dataset or prepare_dataset(args.out)
    result = train_only(dataset, args.out)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
