"""Concept-weighted development metrics; spellings are correlated observations."""

from collections import Counter

import numpy as np
from sklearn.metrics import classification_report, log_loss


def concept_weights(rows):
    """Each concept has total weight one, shared equally among its spelling rows."""
    counts = Counter(r["group"] for r in rows)
    labels = {}
    for row in rows:
        if not row["group"] or labels.setdefault(row["group"], row["label"]) != row["label"]:
            raise ValueError("A concept must have one nonempty group and a consistent label")
    return np.array([1 / counts[r["group"]] for r in rows], dtype=float)


def metrics(rows, scores, classes, accepted=None):
    """Keep raw row diagnostics alongside the equally weighted concept metrics."""
    truth = np.array([r["label"] for r in rows])
    pred = np.asarray(classes)[scores.argmax(axis=1)]
    supported = truth != ""

    def summarize(weight):
        result = dict(
            class_report=classification_report(
                truth[supported],
                pred[supported],
                labels=list(classes),
                sample_weight=weight[supported],
                output_dict=True,
                zero_division=0,
            )
            if supported.any()
            else None,
            nll=float(
                log_loss(
                    truth[supported],
                    scores[supported],
                    labels=list(classes),
                    sample_weight=weight[supported],
                )
            )
            if supported.any()
            else None,
        )
        if accepted is not None:
            correct = supported & (truth == pred)
            result.update(
                supported_coverage=float(
                    weight[accepted & supported].sum() / weight[supported].sum()
                )
                if supported.any()
                else None,
                accepted_accuracy=float(weight[accepted & correct].sum() / weight[accepted].sum())
                if accepted.any()
                else None,
            )
        return result

    result = dict(
        concept_groups=len({r["group"] for r in rows}),
        supported_rows=int(supported.sum()),
        held_rows=int((~supported).sum()),
        **summarize(np.ones(len(rows))),
        concept_weighted=summarize(concept_weights(rows)),
    )
    if accepted is not None:
        result.update(
            accepted=int(accepted.sum()),
            held_false_suggestions=int((accepted & ~supported).sum()),
            accepted_concepts=len(
                {r["group"] for r, hit in zip(rows, accepted, strict=True) if hit}
            ),
            held_false_suggestion_concepts=len(
                {
                    r["group"]
                    for r, hit in zip(rows, accepted, strict=True)
                    if hit and not r["label"]
                }
            ),
        )
    return result


def select_gate(rows, probabilities, similarities, classes):
    """Select maximum concept-weighted coverage with >=95% accuracy and no held accepts."""
    if not rows:
        return 1.01, 1.01
    weight = concept_weights(rows)
    truth = np.array([r["label"] for r in rows])
    pred = np.asarray(classes)[probabilities.argmax(axis=1)]
    best = (0, 1.01, 1.01)
    for threshold in (0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        for similarity in (0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            accepted = (probabilities.max(axis=1) >= threshold) & (similarities >= similarity)
            mass = weight[accepted].sum()
            if (
                mass > 0
                and not (accepted & (truth == "")).any()
                and weight[accepted & (truth == pred)].sum() / mass >= 0.95 - 1e-12
            ):
                # Rounding only stabilizes tie-breaking across equivalent spelling counts.
                candidate = (round(float(mass), 12), threshold, similarity)
                if candidate > best:
                    best = candidate
    return best[1], best[2]
