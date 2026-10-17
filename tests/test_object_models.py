"""Six-class suggestions remain language-selected and policy-safe."""

import numpy as np

from smart_recycling.domain import WasteCategory
from smart_recycling.multilingual import BilingualSuggester, suggestion_language
from smart_recycling.object_models import ObjectSuggester


class Encoder:
    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 384), dtype=np.float32)


class Head:
    classes_ = np.array(
        [
            "clothes",
            "electronics",
            "glass",
            "paper_tetrapak",
            "plastic_metal",
            "special_unsupported",
        ]
    )

    def __init__(self, winner):
        self.winner = winner

    def predict_proba(self, vectors):
        scores = np.zeros((len(vectors), 6))
        scores[:, self.winner] = 1
        return scores


def test_object_labels_map_to_specialist_review_not_automatic_route():
    clothes = ObjectSuggester(Head(0), Encoder(), "en").suggest("hoodie")
    electronics = ObjectSuggester(Head(1), Encoder(), "mk").suggest("телефон")
    assert (clothes.category, clothes.item_kind) == (
        WasteCategory.SPECIAL_UNSUPPORTED,
        "wearable_clothes",
    )
    assert (electronics.category, electronics.item_kind) == (
        WasteCategory.SPECIAL_UNSUPPORTED,
        "electronics",
    )


def test_selected_page_language_controls_model_even_for_opposite_script():
    bilingual = BilingualSuggester(
        ObjectSuggester(Head(2), Encoder(), "en"),
        ObjectSuggester(Head(1), Encoder(), "mk"),
    )
    token = suggestion_language.set("mk")
    try:
        assert bilingual.suggest("glass").item_kind == "electronics"
    finally:
        suggestion_language.reset(token)
    token = suggestion_language.set("en")
    try:
        assert bilingual.suggest("стакло").category == WasteCategory.GLASS
    finally:
        suggestion_language.reset(token)
