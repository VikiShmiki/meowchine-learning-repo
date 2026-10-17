"""Small, inspectable baseline for disposal classification."""

import re

from smart_recycling.domain import Prediction, WasteCategory
from smart_recycling.language import policy_text

MODEL_VERSION = "rules-v1"

KEYWORDS: dict[WasteCategory, tuple[tuple[str, int], ...]] = {
    WasteCategory.GLASS: (
        ("wine bottle", 5),
        ("glass bottle", 5),
        ("glass jar", 4),
        ("jar", 3),
        ("glass", 3),
    ),
    WasteCategory.PLASTIC_METAL: (
        ("plastic shampoo bottle", 5),
        ("shampoo bottle", 5),
        ("plastic bottle", 5),
        ("aluminium can", 4),
        ("aluminum can", 4),
        ("drink can", 4),
        ("tin can", 4),
        ("can", 2),
        ("plastic", 2),
    ),
    WasteCategory.PAPER_TETRAPAK: (
        ("old magazines", 5),
        ("magazine", 4),
        ("newspaper", 4),
        ("cardboard", 4),
        ("paper", 3),
        ("tetrapak", 5),
        ("tetra pak", 5),
    ),
    WasteCategory.GENERAL: (
        ("general waste", 5),
        ("food waste", 4),
        ("diaper", 4),
        ("nappy", 4),
        ("ceramic", 3),
    ),
    WasteCategory.SPECIAL_UNSUPPORTED: (
        ("phone charger", 5),
        ("laptop charger", 5),
        ("battery", 5),
        ("smartphone", 5),
        ("mobile phone", 5),
        ("fluorescent lamp", 5),
        ("medication", 5),
        ("hazardous chemical", 5),
        ("electronics", 4),
        ("charger", 4),
    ),
}


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.casefold()).split())


class RuleClassifier:
    """Weighted keyword baseline with deterministic confidence and abstention."""

    def __init__(self, threshold: float = 0.60) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold

    def predict(self, text: str) -> Prediction:
        normalized = _normalize(policy_text(text))
        scores = {
            category: sum(
                weight
                for phrase, weight in phrases
                if re.search(rf"\b{re.escape(phrase)}\b", normalized)
            )
            for category, phrases in KEYWORDS.items()
        }
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
        category, top_score = ranked[0]

        if top_score == 0:
            return Prediction(None, 0.0, True, MODEL_VERSION)

        runner_up = ranked[1][1]
        confidence = min(0.99, 0.55 + (0.07 * top_score) + (0.03 * (top_score - runner_up)))
        abstained = top_score == runner_up or confidence < self.threshold
        return Prediction(
            category=None if abstained else category,
            confidence=round(confidence, 2),
            abstained=abstained,
            model_version=MODEL_VERSION,
        )
