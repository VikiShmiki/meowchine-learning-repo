"""Evaluate the policy-first path, including the subset where ML can add a suggestion."""

import numpy as np

from smart_recycling.data.ml_evaluation import concept_weights
from smart_recycling.guidance import GuidanceClassifier


class RecordingSuggester:
    """Observe actual policy calls, rather than approximating the routing conditions."""

    def __init__(self, delegate=None):
        self.delegate = delegate
        self.called = False
        self.model_version = delegate.model_version if delegate else "evaluation-probe"

    def suggest(self, text):
        self.called = True
        return self.delegate.suggest(text) if self.delegate else None


def policy_fallback_mask(rows, policy, threshold):
    probe = RecordingSuggester()
    classifier = GuidanceClassifier(policy, threshold, category_suggester=probe)
    mask = []
    for row in rows:
        probe.called = False
        classifier.decide(row["text"])
        mask.append(probe.called)
    return np.asarray(mask, dtype=bool)


def _label(category, kind, broad_labels):
    if not category:
        return ""
    if not broad_labels:
        if kind == "wearable_clothes":
            return "clothes"
        if kind in {"electronics", "small_electronics"}:
            return "electronics"
    return str(category)


def _summary(records):
    fallback = [r for r in records if r["ml_called"]]
    supported = [r for r in fallback if r["label"]]
    accepted = [r for r in fallback if r["suggested_label"]]
    correct = [r for r in accepted if r["label"] == r["suggested_label"]]
    result = dict(
        rows=len(records),
        concept_groups=len({r["group"] for r in records}),
        policy_handled_rows=len(records) - len(fallback),
        fallback_rows=len(fallback),
        fallback_concepts=len({r["group"] for r in fallback}),
        fallback_supported_rows=len(supported),
        fallback_held_rows=len(fallback) - len(supported),
        accepted_suggestions=len(accepted),
        correct_suggestions=len(correct),
        held_false_suggestions=sum(not r["label"] for r in accepted),
        supported_coverage=sum(bool(r["label"]) for r in accepted) / len(supported)
        if supported
        else None,
        accepted_accuracy=len(correct) / len(accepted) if accepted else None,
        rules_supported_correct=sum(
            bool(r["label"]) and r["rules_label"] == r["label"] for r in records
        ),
        rules_plus_suggestions_supported_correct=sum(
            bool(r["label"]) and (r["rules_label"] or r["suggested_label"]) == r["label"]
            for r in records
        ),
    )
    weight = concept_weights(fallback)
    supported_mass = sum(w for r, w in zip(fallback, weight, strict=True) if r["label"])
    accepted_mass = sum(w for r, w in zip(fallback, weight, strict=True) if r["suggested_label"])
    correct_mass = sum(
        w
        for r, w in zip(fallback, weight, strict=True)
        if r["label"] and r["label"] == r["suggested_label"]
    )
    result["concept_weighted"] = dict(
        supported_coverage=float(
            sum(
                w
                for r, w in zip(fallback, weight, strict=True)
                if r["label"] and r["suggested_label"]
            )
            / supported_mass
        )
        if supported_mass
        else None,
        accepted_accuracy=float(correct_mass / accepted_mass) if accepted_mass else None,
    )
    return result


def evaluate_serving(rows, suggester, policy, threshold, *, broad_labels=False):
    """Replay actual suggestions; ML must not change a policy decision or grant routing."""
    baseline = GuidanceClassifier(policy, threshold)
    probe = RecordingSuggester(suggester)
    classifier = GuidanceClassifier(policy, threshold, category_suggester=probe)
    records = []
    for row in rows:
        original = baseline.decide(row["text"])
        probe.called = False
        answer = classifier.decide(row["text"])
        for field in ("status", "category", "item_kind", "facility_ids", "abstained"):
            if getattr(answer, field) != getattr(original, field):
                raise AssertionError(f"ML changed policy authority: {row['group']}: {field}")
        records.append(
            dict(
                text=row["text"],
                group=row["group"],
                variant=row["variant"],
                label=row["label"],
                rules_status=original.status,
                rules_label=_label(original.category, original.item_kind, broad_labels),
                ml_called=probe.called,
                suggested_label=_label(
                    answer.suggested_category, answer.suggested_item_kind, broad_labels
                ),
                suggestion_score=answer.suggestion_score,
            )
        )
    return dict(
        scope="Development diagnostic; suggestions are not disposal decisions",
        overall=_summary(records),
        by_variant={
            variant: _summary([r for r in records if r["variant"] == variant])
            for variant in sorted({r["variant"] for r in records})
        },
        records=records,
    )
