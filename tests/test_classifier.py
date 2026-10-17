import pytest

from smart_recycling.classifier import RuleClassifier
from smart_recycling.domain import WasteCategory


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("wine bottle", WasteCategory.GLASS),
        ("old magazines", WasteCategory.PAPER_TETRAPAK),
        ("plastic shampoo bottle", WasteCategory.PLASTIC_METAL),
        ("used diaper", WasteCategory.GENERAL),
        ("broken phone charger", WasteCategory.SPECIAL_UNSUPPORTED),
    ],
)
def test_rules_classify_known_examples(text: str, expected: WasteCategory) -> None:
    result = RuleClassifier().predict(text)

    assert result.category is expected
    assert result.abstained is False
    assert 0.0 <= result.confidence <= 1.0


def test_rules_abstain_without_a_signal() -> None:
    result = RuleClassifier().predict("mysterious household object")

    assert result.category is None
    assert result.confidence == 0.0
    assert result.abstained is True


def test_rules_return_no_category_below_threshold() -> None:
    result = RuleClassifier(threshold=0.99).predict("paper")

    assert result.category is None
    assert result.confidence > 0.0
    assert result.abstained is True


def test_threshold_is_validated() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        RuleClassifier(threshold=1.1)
