"""Evidence-scoped classification, clarification and specialist guidance."""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from smart_recycling.classifier import RuleClassifier
from smart_recycling.domain import Prediction, WasteCategory
from smart_recycling.language import policy_text
from smart_recycling.minilm import MiniLMError

logger = logging.getLogger(__name__)

MODEL_VERSION = "policy-rules-v3"
ItemKind = Literal[
    "empty_glass_packaging",
    "empty_plastic_bottle",
    "empty_metal_can",
    "clean_paper",
    "clean_cardboard",
    "empty_tetrapak",
    "ordinary_residual",
    "electronics",
    "small_electronics",
    "wearable_clothes",
    "batteries",
    "other",
]
CHOICES: dict[str, tuple[str, WasteCategory | None]] = {
    "empty_glass_packaging": ("Empty glass bottle or jar", WasteCategory.GLASS),
    "empty_plastic_bottle": ("Empty plastic bottle", WasteCategory.PLASTIC_METAL),
    "empty_metal_can": ("Empty metal food or drink can", WasteCategory.PLASTIC_METAL),
    "clean_paper": ("Clean, uncoated paper", WasteCategory.PAPER_TETRAPAK),
    "clean_cardboard": ("Clean, uncoated cardboard", WasteCategory.PAPER_TETRAPAK),
    "empty_tetrapak": ("Empty Tetra Pak drink carton", WasteCategory.PAPER_TETRAPAK),
    "ordinary_residual": (
        "Used household tissue or nappy (not clinical waste)",
        WasteCategory.GENERAL,
    ),
    "electronics": ("Electrical or electronic device", WasteCategory.SPECIAL_UNSUPPORTED),
    "small_electronics": (
        "Small device: phone, charger, cable or earbuds",
        WasteCategory.SPECIAL_UNSUPPORTED,
    ),
    "batteries": ("Battery", WasteCategory.SPECIAL_UNSUPPORTED),
    "wearable_clothes": ("Clean, wearable clothes for donation", WasteCategory.SPECIAL_UNSUPPORTED),
    "other": ("Something else / unsure", None),
}
KIND_PATTERNS = {
    "empty_glass_packaging": r"\b(?:glass (?:bottles?|jars?)|wine bottles?|beer bottles?)\b",
    "empty_plastic_bottle": r"\b(?:plastic (?:shampoo )?bottles?|shampoo bottles?|pet bottles?)\b",
    "empty_metal_can": r"\b(?:alumini?um|aluminum|metal|tin|drink|soda|beverage|food) cans?\b",
    "clean_paper": r"\b(?:paper|newspapers?|magazines?)\b",
    "clean_cardboard": r"\bcardboard\b",
    "empty_tetrapak": r"\btetra\s*pak\b",
}
BATTERY = r"\b(?:batter(?:y|ies)|power\s*bank)\b"
SMALL_ELECTRONICS = r"\b(?:chargers?|phones?|smartphones?|cables?|earbuds?)\b"
LARGE_ELECTRONICS = (
    r"\b(?:laptops?|computers?|toasters?|kettles?|televisions?|tvs?|fridges?|"
    r"refrigerators?|washing machines?|freezers?|ovens?|dishwashers?|large|bulky)\b"
)


def is_small_electronics(text: str) -> bool:
    """Bounded small-device subset; mixed or uncertain sizes stay general electronics."""
    text = policy_text(text)
    return bool(re.search(SMALL_ELECTRONICS, text, re.I)) and not re.search(
        LARGE_ELECTRONICS, text, re.I
    )


ELECTRONICS = (
    r"\b(?:chargers?|electronics?|phones?|smartphones?|laptops?|computers?|cables?|earbuds?|"
    r"toasters?|kettles?|televisions?|tvs?|fridges?|refrigerators?|washing machines?|"
    r"electrical (?:devices?|appliances?))\b"
)
CLOTHES = (
    r"\b(?:clothes|clothing|t-?shirts?|shirts?|trousers|jeans|jackets?|coats?|"
    r"sweaters?|jumpers?|dresses|socks|skirts?)\b"
)
UNSUITABLE_CLOTHES = (
    r"\b(?:torn|ripped|damaged|unwearable|wet|mould\w*|mold\w*|stained|rags?|scraps?|"
    r"not\s+(?:clean|washed|wearable)|unwashed|dirty|soiled|contaminat\w*)\b"
)


def is_wearable_clothing(text: str) -> bool:
    """Recognize a garment, not proof of condition; explicit confirmation is still required."""
    text = policy_text(text)
    return bool(re.search(CLOTHES, text, re.I)) and not (
        re.search(UNSUITABLE_CLOTHES, text, re.I)
        or re.search(HELD, text, re.I)
        or specialist_type(text)
        or any(re.search(pattern, text, re.I) for pattern in KIND_PATTERNS.values())
    )


SPECIAL = (
    r"\b(?:medicin\w*|medications?|pills?|syringes?|needles?|chemicals?|pesticid\w*|paint|"
    r"solvent\w*|bleach|aerosol\w*|fluorescent|mercury|bulbs?|lamps?|motor oil|asbestos|"
    r"medical|clinical|infectious|blood|sharps|swollen|leaking|smoking|burnt)\b"
)
RESIDUAL = (
    r"(?:(?:a|an|my|some|i have|i want to|please|discard|throw away|dispose of|recycle|"
    r"where (?:can|do|should) i|how (?:can|do|should) i)\s+)*"
    r"(?:used|dirty|soiled)\s+(?:household\s+)?(?:tissues?|diapers?|napp(?:y|ies))"
    r"[.!?]?"
)


def is_residual(text: str) -> bool:
    """A bounded household subset, never the fallback for an unknown material."""
    text = policy_text(text)
    return bool(re.fullmatch(RESIDUAL, text.strip(), re.I))


HELD = (
    r"\b(?:dirty|greasy|soiled|contaminat\w*|coated|laminated|waxed|ceramic\w*|mirrors?|"
    r"drinking glass|window glass|diapers?|napp(?:y|ies)|food waste|paper cups?|paper towels?|"
    r"receipts?|tissues?|plastic bags?|plastic trays?|not empty|not clean|still contains|full of)\b"
)


class Choice(BaseModel):
    """An explicit user-confirmed item kind, not a site acceptance promise."""

    id: ItemKind
    label: str


class CategorySuggestion(Protocol):
    """Broad suggestion returned by an optional learned model."""

    category: WasteCategory
    score: float
    model_version: str


class CategorySuggester(Protocol):
    """Serving boundary for a learned category suggester."""

    model_version: str

    def suggest(self, text: str) -> CategorySuggestion: ...


class GuidanceResponse(BaseModel):
    """Additive classification API contract with an explicit next action."""

    model_config = ConfigDict(extra="forbid")
    category: WasteCategory | None
    confidence: float
    confidence_kind: Literal["heuristic_score", "manual_selection"] = "heuristic_score"
    abstained: bool
    model_version: str = MODEL_VERSION
    policy_version: str
    status: Literal["clarify", "confirm_condition", "ready_for_site_matching", "specialist", "held"]
    message: str
    item_kind: ItemKind | None = None
    clarification_question: str | None = None
    choices: list[Choice] = []
    evidence_ids: list[str] = []
    contact_url: str | None = None
    phone: str | None = None
    facility_ids: list[str] = []
    routing_available: Literal[False] = False
    suggested_category: WasteCategory | None = None
    suggestion_score: float | None = None
    suggestion_model_version: str | None = None
    suggested_item_kind: ItemKind | None = None


def specialist_type(text: str) -> str | None:
    """Detect specialist signals before ordinary recycling or manual overrides."""
    text = policy_text(text)
    if re.search(SPECIAL, text, re.I):
        return "other_specialist"
    if re.search(BATTERY, text, re.I):
        return "batteries"
    if re.search(ELECTRONICS, text, re.I):
        return "electronics"
    return None


def inferred_kind(text: str) -> str | None:
    """Only identify specific supported forms; generic material words are insufficient."""
    text = policy_text(text)
    matches = [kind for kind, pattern in KIND_PATTERNS.items() if re.search(pattern, text, re.I)]
    return matches[0] if len(matches) == 1 else None


class GuidanceClassifier:
    """Conservative rules baseline whose threshold is selected offline on validation data."""

    def __init__(
        self,
        policy: dict,
        threshold: float,
        category_suggester: CategorySuggester | None = None,
    ) -> None:
        self.policy = policy
        self.rules = RuleClassifier(threshold)
        self.category_suggester = category_suggester

    @property
    def suggestion_model_version(self) -> str | None:
        return self.category_suggester.model_version if self.category_suggester else None

    def predict(self, text: str) -> Prediction:
        """Return a broad category only when the reviewed policy supports the item form."""
        text = policy_text(text)
        if specialist_type(text):
            return Prediction(WasteCategory.SPECIAL_UNSUPPORTED, 0.99, False, MODEL_VERSION)
        if re.search(CLOTHES, text, re.I):
            return (
                Prediction(WasteCategory.SPECIAL_UNSUPPORTED, 0.99, False, MODEL_VERSION)
                if is_wearable_clothing(text)
                else Prediction(None, 0.0, True, MODEL_VERSION)
            )
        if is_residual(text):
            return Prediction(WasteCategory.GENERAL, 0.99, False, MODEL_VERSION)
        if re.search(HELD, text, re.I) or re.search(r"\b(?:not|isn t|isn't)\b", text, re.I):
            return Prediction(None, 0.0, True, MODEL_VERSION)
        kind = inferred_kind(text)
        if kind is None:
            return Prediction(None, 0.0, True, MODEL_VERSION)
        # Canonical form is used only for spelling/plural variants of recognized item kinds.
        raw = self.rules.predict(text)
        if raw.category != CHOICES[kind][1]:
            raw = self.rules.predict(CHOICES[kind][0])
        return Prediction(raw.category, raw.confidence, raw.abstained, MODEL_VERSION)

    def decide(
        self, text: str, manual_kind: ItemKind | None = None, condition_confirmed: bool = False
    ) -> GuidanceResponse:
        """Require explicit condition confirmation before returning an item for site matching."""
        source_text = text
        text = policy_text(text)
        subtype = specialist_type(text)
        manually_selected = subtype is None and manual_kind in {"electronics", "batteries"}
        if subtype is None and manual_kind in {"electronics", "small_electronics", "batteries"}:
            subtype = "electronics" if manual_kind == "small_electronics" else manual_kind
        base = {"policy_version": self.policy["version"]}
        choices = [Choice(id=key, label=value[0]) for key, value in CHOICES.items()]
        if subtype == "electronics" and not re.search(HELD, text, re.I):
            # Electronics stay a specialist category, with explicitly accepting destinations.
            # Don't silently discard an additional recyclable from a mixed description.
            if re.search(CLOTHES, text, re.I) or any(
                re.search(pattern, text, re.I) for pattern in KIND_PATTERNS.values()
            ):
                return GuidanceResponse(
                    **base,
                    category=None,
                    confidence=0,
                    abstained=True,
                    status="held",
                    message="Describe each item separately so every item gets a suitable stop.",
                )
            if manual_kind == "small_electronics" and not is_small_electronics(text):
                return GuidanceResponse(
                    **base,
                    category=None,
                    confidence=0,
                    abstained=True,
                    status="held",
                    message="For small-device collection, describe a phone, charger, cable or "
                    "earbuds. Use Electronics for larger devices or uncertain sizes.",
                )
            kind = (
                "small_electronics"
                if (
                    manual_kind == "small_electronics"
                    or (manual_kind is None and is_small_electronics(text))
                )
                else "electronics"
            )
            confirmed = manual_kind == kind and condition_confirmed
            guidance = self.policy["specialist_guidance"][kind]
            return GuidanceResponse(
                **base,
                category=WasteCategory.SPECIAL_UNSUPPORTED,
                confidence=0 if manual_kind else 0.99,
                confidence_kind="manual_selection" if manual_kind else "heuristic_score",
                abstained=False,
                item_kind=kind,
                status="ready_for_site_matching" if confirmed else "confirm_condition",
                message="Electrical items need separate collection — not general waste.",
                choices=[] if confirmed else choices,
                evidence_ids=guidance["evidence_ids"],
                facility_ids=guidance["facility_ids"],
                contact_url=guidance.get("contact_url"),
                phone=guidance.get("phone"),
            )
        if subtype:
            guidance = self.policy["specialist_guidance"][subtype]
            return GuidanceResponse(
                **base,
                category=WasteCategory.SPECIAL_UNSUPPORTED,
                confidence=0 if manually_selected else 0.99,
                confidence_kind="manual_selection" if manually_selected else "heuristic_score",
                abstained=False,
                status="specialist",
                message=guidance["message"],
                item_kind=subtype if subtype in {"electronics", "batteries"} else None,
                contact_url=guidance.get("contact_url"),
                phone=guidance.get("phone"),
                evidence_ids=guidance["evidence_ids"],
            )
        if re.search(CLOTHES, text, re.I) or manual_kind == "wearable_clothes":
            if not is_wearable_clothing(text):
                return GuidanceResponse(
                    **base,
                    category=None,
                    confidence=0,
                    abstained=True,
                    status="held",
                    message="Clothes donation accepts clean, washed, wearable garments only. "
                    "Describe garments separately; damaged textiles need different guidance.",
                )
            confirmed = manual_kind == "wearable_clothes" and condition_confirmed
            guidance = self.policy["specialist_guidance"]["wearable_clothes"]
            return GuidanceResponse(
                **base,
                category=WasteCategory.SPECIAL_UNSUPPORTED,
                confidence=0 if manual_kind else 0.99,
                confidence_kind="manual_selection" if manual_kind else "heuristic_score",
                abstained=False,
                item_kind="wearable_clothes",
                status="ready_for_site_matching" if confirmed else "confirm_condition",
                message="Donate clean, washed clothes that someone else can wear. "
                "These locations collect for reuse, not damaged-textile recycling.",
                choices=[] if confirmed else choices,
                evidence_ids=guidance["evidence_ids"],
                facility_ids=guidance["facility_ids"],
                contact_url=guidance["contact_url"],
            )
        residual = is_residual(text)
        if residual and manual_kind in {None, "ordinary_residual"}:
            confirmed = manual_kind == "ordinary_residual" and condition_confirmed
            return GuidanceResponse(
                **base,
                category=WasteCategory.GENERAL,
                confidence=0 if manual_kind else 0.99,
                confidence_kind="manual_selection" if manual_kind else "heuristic_score",
                abstained=False,
                item_kind="ordinary_residual",
                status="ready_for_site_matching" if confirmed else "confirm_condition",
                message="This item is not recyclable. Use general waste.",
                choices=[] if confirmed else choices,
                evidence_ids=["karpos_household"],
            )
        if manual_kind == "ordinary_residual":
            return GuidanceResponse(
                **base,
                category=None,
                confidence=0,
                abstained=True,
                status="held",
                message="General-waste suggestions currently cover used household tissues and "
                "nappies only. Unknown waste is not automatically general waste.",
            )
        if re.search(HELD, text, re.I) or manual_kind == "other":
            return GuidanceResponse(
                **base,
                category=None,
                confidence=0,
                abstained=True,
                status="held",
                message="Local disposal acceptance is not confirmed for this item. "
                "Check with the operator; exclusion from recycling does not mean general waste.",
                clarification_question="Can you describe the material and condition more clearly?",
            )
        prediction = self.predict(text)
        kind = manual_kind or (inferred_kind(text) if not prediction.abstained else None)
        if kind is None:
            try:
                suggestion = (
                    self.category_suggester.suggest(source_text)
                    if self.category_suggester
                    else None
                )
            except MiniLMError:
                logger.exception("MiniLM inference failed; continuing with policy clarification")
                suggestion = None
            if suggestion:
                suggested_kind = getattr(suggestion, "item_kind", None)
                choices.sort(
                    key=lambda choice: (
                        choice.id != suggested_kind if suggested_kind else False,
                        CHOICES[choice.id][1] != suggestion.category,
                        choice.label,
                    )
                )
            return GuidanceResponse(
                **base,
                category=None,
                confidence=prediction.confidence,
                abstained=True,
                status="clarify",
                message=(
                    "The learned model suggests a broad stream, but it cannot confirm the exact "
                    "item form or local acceptance."
                    if suggestion
                    else "I need a little more detail to choose the right stream."
                ),
                clarification_question=(
                    "Choose the exact item type below and check the suggested stream."
                    if suggestion
                    else "What is the item made of? Choose one item type below."
                ),
                choices=choices,
                suggested_category=suggestion.category if suggestion else None,
                suggestion_score=suggestion.score if suggestion else None,
                suggestion_model_version=suggestion.model_version if suggestion else None,
                suggested_item_kind=suggested_kind if suggestion else None,
            )
        category = CHOICES[kind][1]
        evidence = sorted(
            {
                e
                for profile in self.policy["profiles"]
                if kind in profile["accepted_item_kinds"]
                for e in profile["evidence_ids"]
            }
        )
        if not evidence:
            raise ValueError(f"Selected kind has no acceptance evidence: {kind}")
        confirmed = condition_confirmed and manual_kind is not None
        return GuidanceResponse(
            **base,
            category=category,
            confidence=0 if manual_kind else prediction.confidence,
            confidence_kind="manual_selection" if manual_kind else "heuristic_score",
            abstained=False,
            item_kind=kind,
            evidence_ids=evidence,
            status="ready_for_site_matching" if confirmed else "confirm_condition",
            message=(
                "Item details confirmed. A collection point must explicitly accept this item; "
                "add it to your trip to find compatible stops."
                if confirmed
                else "Confirm the item type, its empty/clean condition and no hazardous contents. "
                "A material category alone does not establish site acceptance."
            ),
            clarification_question=None
            if confirmed
            else "Is this the correct item type and condition?",
            choices=[] if confirmed else choices,
        )


def code_digest() -> str:
    """Hash serving rules with normalized newlines for Windows/Linux parity."""
    digest = hashlib.sha256()
    for name in ("classifier.py", "guidance.py", "language.py"):
        digest.update(Path(__file__).with_name(name).read_text(encoding="utf-8").encode())
    return digest.hexdigest()


def load_classifier(
    artifact_path: Path,
    policy_path: Path,
    category_suggester: CategorySuggester | None = None,
) -> GuidanceClassifier:
    """Fail startup if the evaluated artifact no longer matches rules or policy."""
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    policy_text = policy_path.read_text(encoding="utf-8")
    if (
        artifact["model_version"] != MODEL_VERSION
        or artifact["code_sha256"] != code_digest()
        or artifact["policy_sha256"] != hashlib.sha256(policy_text.encode()).hexdigest()
        or not artifact["validation_gate_passed"]
    ):
        raise ValueError(
            "Classifier artifact is stale or failed evaluation; run evaluate_guidance.py"
        )
    return GuidanceClassifier(
        json.loads(policy_text), artifact["threshold"], category_suggester=category_suggester
    )
