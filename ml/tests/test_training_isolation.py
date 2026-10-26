"""Regression tests for subject separation and train-only file access."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from ml.retrain import grouped_validation, train_only


class TrainingIsolationTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(5)
        self.groups = np.repeat(np.arange(6), 12)
        self.y = np.tile(np.arange(1, 7), 12)
        self.X = rng.normal(size=(72, 561)) + self.groups[:, None] * 10
        self.X[:, :6] += np.eye(6)[self.y - 1] * 4

    def test_scaler_fitted_only_on_each_fold_training_rows(self):
        fitted_rows = []
        original = StandardScaler.fit

        def spy(scaler, X, y=None, sample_weight=None):
            fitted_rows.append(X.copy())
            return original(scaler, X, y, sample_weight)

        with patch.object(StandardScaler, 'fit', spy):
            _, report, predictions = grouped_validation(self.X, self.y, self.groups, folds=3)
        splits = list(GroupKFold(n_splits=3).split(self.X, self.y, self.groups))
        for seen, (train, valid), row in zip(fitted_rows, splits, report['folds']):
            np.testing.assert_array_equal(seen, self.X[train])
            self.assertFalse(set(self.groups[train]) & set(self.groups[valid]))
            self.assertEqual(row['scaler_samples_seen'], len(train))
        self.assertEqual(len(fitted_rows), 3)
        self.assertEqual(len(predictions), len(self.y))
        self.assertTrue(report['all_rows_predicted_once'])

    def test_training_succeeds_without_any_test_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'train').mkdir()
            for name, data in [('X_train.txt', self.X), ('y_train.txt', self.y),
                               ('subject_train.txt', self.groups)]:
                np.savetxt(root / 'train' / name, data,
                           fmt='%.18e' if data.ndim == 2 else '%d')
            original = np.loadtxt
            accessed = []

            def read(path, *args, **kwargs):
                accessed.append(Path(path))
                self.assertEqual(Path(path).parent.name, 'train')
                return original(path, *args, **kwargs)

            with patch('ml.retrain.np.loadtxt', side_effect=read):
                report = train_only(root, root / 'out')
            self.assertEqual(len(accessed), 3)
            self.assertFalse(report['official_test_used'])
            self.assertFalse(report['recipe']['hyperparameter_search'])
            self.assertFalse((root / 'test').exists())
            self.assertTrue((root / 'out/svm561.json').is_file())


if __name__ == '__main__':
    unittest.main()
