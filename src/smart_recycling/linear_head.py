"""Portable numerical head: no pickle or training-library dependency at inference."""

import numpy as np

from smart_recycling.object_models import LABELS


def softmax(logits):
    values = np.asarray(logits, dtype=float)
    values = np.exp(values - values.max(axis=1, keepdims=True))
    return values / values.sum(axis=1, keepdims=True)


class LinearHead:
    def __init__(self, payload):
        self.classes_ = np.asarray(payload["classes"])
        self.coef_ = np.asarray(payload["coef"], dtype=float)
        self.intercept_ = np.asarray(payload["intercept"], dtype=float)
        self.prototypes = np.asarray(payload["prototypes"], dtype=float)
        self.temperature = float(payload["temperature"])
        self.threshold = float(payload["threshold"])
        self.similarity_threshold = float(payload["similarity_threshold"])
        if (
            tuple(self.classes_) != tuple(sorted(LABELS))
            or self.coef_.shape != (6, 384)
            or self.intercept_.shape != (6,)
            or self.prototypes.ndim != 2
            or self.prototypes.shape[1] != 384
            or not len(self.prototypes)
            or not 0.01 <= self.temperature <= 100
            or not 0 <= self.threshold <= 1.01
            or not 0 <= self.similarity_threshold <= 1.01
            or not all(np.isfinite(a).all() for a in (self.coef_, self.intercept_, self.prototypes))
            or not np.allclose(np.linalg.norm(self.prototypes, axis=1), 1, atol=1e-5)
        ):
            raise ValueError("Invalid numerical head schema or values")

    def predict_proba(self, vectors):
        return softmax((vectors @ self.coef_.T + self.intercept_) / self.temperature)

    def accepts(self, vectors, scores):
        return (scores.max(axis=1) >= self.threshold) & (
            (vectors @ self.prototypes.T).max(axis=1) >= self.similarity_threshold
        )
