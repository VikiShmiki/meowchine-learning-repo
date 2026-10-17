import asyncio
import base64
import io
import json
import threading

import httpx
import pytest
from PIL import Image

from smart_recycling.vision import (
    MAX_UPLOAD_BYTES,
    ModelPhotoAnalysis,
    ModelPhotoItem,
    OpenAIVisionProvider,
    SuggestionStatus,
    VisibleCondition,
    VisionError,
    VisionService,
    prepare_image,
)


def png_bytes(width: int = 40, height: int = 30) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (width, height), "green")
    exif = Image.Exif()
    exif[0x010E] = "private description"
    image.save(output, format="PNG", exif=exif)
    return output.getvalue()


def test_prepare_image_resizes_and_removes_metadata() -> None:
    prepared = prepare_image(png_bytes(2400, 1200), "image/png")

    prefix, encoded = prepared.split(",", 1)
    assert prefix == "data:image/jpeg;base64"
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
        assert image.size == (1280, 640)
        assert image.format == "JPEG"
        assert len(image.getexif()) == 0


@pytest.mark.parametrize(
    ("raw", "content_type", "code"),
    [
        pytest.param(b"", "image/png", "empty_image", id="empty"),
        pytest.param(b"not an image", "image/png", "invalid_image", id="invalid"),
        pytest.param(png_bytes(), "image/gif", "unsupported_image", id="unsupported"),
        pytest.param(
            b"x" * (MAX_UPLOAD_BYTES + 1),
            "image/jpeg",
            "image_too_large",
            id="too-large",
        ),
    ],
)
def test_prepare_image_rejects_unsafe_uploads(raw: bytes, content_type: str, code: str) -> None:
    with pytest.raises(VisionError) as caught:
        prepare_image(raw, content_type)
    assert caught.value.code == code


def test_openai_provider_uses_private_structured_image_request() -> None:
    async def run() -> ModelPhotoAnalysis:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer test-key"
            body = json.loads(request.content)
            assert body["model"] == "test-vision-model"
            assert body["store"] is False
            assert body["input"][0]["content"][1]["detail"] == "low"
            assert body["text"]["format"]["strict"] is True
            model_output = {
                "items": [
                    {
                        "description": "clear glass jar",
                        "item_kind": "empty_glass_packaging",
                        "visible_condition": "appears_empty_clean",
                        "reason": "It appears to be an empty glass container.",
                    }
                ]
            }
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": json.dumps(model_output)}],
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAIVisionProvider(
                "test-key", "test-vision-model", client=client, timeout_seconds=1
            )
            return await provider.analyze("data:image/jpeg;base64,fixture")

    result = asyncio.run(run())
    assert result.items[0].item_kind == "empty_glass_packaging"


@pytest.mark.parametrize(
    "body",
    [
        {"output": [None]},
        {"output": "invalid"},
        {"output": [{"type": "message", "content": [None]}]},
        {"output": [{"type": "message", "content": "invalid"}]},
    ],
)
def test_malformed_provider_envelope_returns_safe_error(body):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
        ) as client:
            with pytest.raises(VisionError) as failure:
                await OpenAIVisionProvider("test-key", "fixture", client=client).analyze(
                    "data:image/jpeg;base64,fixture"
                )
            assert failure.value.code == "invalid_vision_response"
            assert failure.value.status == 502

    asyncio.run(run())


def test_photo_preprocessing_does_not_block_other_async_requests(monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def slow_prepare(raw, content_type):
        entered.set()
        release.wait(3)
        return "data:image/jpeg;base64,fixture"

    class Provider:
        configured = True
        model = "fixture"

        async def analyze(self, image):
            assert release.is_set()
            return ModelPhotoAnalysis(items=[])

    monkeypatch.setattr("smart_recycling.vision.prepare_image", slow_prepare)

    async def run():
        task = asyncio.create_task(VisionService(Provider(), "test").suggest(b"image", "image/png"))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert not task.done()
            assert not release.is_set()
        finally:
            release.set()
            result = await task
        assert result.items == []

    asyncio.run(run())


def test_service_derives_safe_statuses_instead_of_trusting_a_category() -> None:
    class FakeProvider:
        configured = True
        model = "fixture-model"

        async def analyze(self, image_data_url: str) -> ModelPhotoAnalysis:
            assert image_data_url.startswith("data:image/jpeg;base64,")
            return ModelPhotoAnalysis(
                items=[
                    ModelPhotoItem(
                        description="glass jar",
                        item_kind="empty_glass_packaging",
                        visible_condition=VisibleCondition.APPEARS_EMPTY_CLEAN,
                        reason="Visible glass packaging.",
                    ),
                    ModelPhotoItem(
                        description="plastic bottle with liquid",
                        item_kind="empty_plastic_bottle",
                        visible_condition=VisibleCondition.NOT_EMPTY_OR_CONTAMINATED,
                        reason="It appears to contain liquid.",
                    ),
                    ModelPhotoItem(
                        description="battery",
                        item_kind="batteries",
                        visible_condition=VisibleCondition.UNCERTAIN,
                        reason="It resembles a household battery.",
                    ),
                ]
            )

    result = asyncio.run(
        VisionService(FakeProvider(), "policy-v1").suggest(png_bytes(), "image/png")
    )

    assert result.requires_user_confirmation is True
    assert result.items[0].category == "glass"
    assert result.items[0].status is SuggestionStatus.CANDIDATE
    assert result.items[1].category is None
    assert result.items[1].status is SuggestionStatus.NEEDS_REVIEW
    assert result.items[2].category == "special_unsupported"
    assert result.items[2].status is SuggestionStatus.SPECIALIST


@pytest.mark.parametrize(
    "description,kind,reason",
    [
        ("glass jar", "empty_glass_packaging", "The jar is dirty."),
        ("plastic bottle", "empty_plastic_bottle", "It is not empty."),
        ("paper", "clean_paper", "It is coated."),
        ("cardboard box", "clean_cardboard", "It is greasy."),
        ("стаклено шише", "empty_glass_packaging", "валкано"),
        ("пластично шише", "empty_plastic_bottle", "не е празно"),
        ("hartija", "clean_paper", "laminirano"),
        ("plasticno sise", "empty_plastic_bottle", "valkano"),
        ("glass bottle", "empty_plastic_bottle", "Visible packaging."),
        ("стаклено шише", "clean_paper", "видлив предмет"),
        ("glass bottle and plastic bottle", "empty_glass_packaging", "Two items."),
        ("пластично шише и весник", "empty_plastic_bottle", "видлив предмет"),
        ("phone and glass bottle", "electronics", "Visible objects."),
        ("телефон и маица", "small_electronics", "видлив предмет"),
        ("unknown object", "empty_plastic_bottle", "The shape is unclear."),
        ("glass jar", "empty_glass_packaging", "A ceramic object is visible too."),
    ],
)
def test_photo_explanation_cannot_be_overridden_by_clean_enum(description, kind, reason):
    item = ModelPhotoItem(
        description=description,
        item_kind=kind,
        visible_condition=VisibleCondition.APPEARS_EMPTY_CLEAN,
        reason=reason,
    )
    result = VisionService._suggestion(item)
    assert result.status is SuggestionStatus.NEEDS_REVIEW
    assert result.category is None
    assert result.item_kind == "other"
    assert result.description == description
    assert result.reason == reason


@pytest.mark.parametrize("description", ["dirty glass jar", "валкано стаклено шише"])
def test_photo_description_condition_is_checked_as_well_as_reason(description):
    result = VisionService._suggestion(
        ModelPhotoItem(
            description=description,
            item_kind="empty_glass_packaging",
            visible_condition="appears_empty_clean",
            reason="Visible packaging.",
        )
    )
    assert result.status is SuggestionStatus.NEEDS_REVIEW
    assert result.item_kind == "other"


@pytest.mark.parametrize(
    "description,kind,condition",
    [
        ("clear glass jar", "empty_glass_packaging", "appears_empty_clean"),
        ("plastic bottle", "empty_plastic_bottle", "appears_empty_clean"),
        ("metal can", "empty_metal_can", "appears_empty_clean"),
        ("clean paper", "clean_paper", "appears_empty_clean"),
        ("cardboard box", "clean_cardboard", "appears_empty_clean"),
        ("Tetra Pak", "empty_tetrapak", "appears_empty_clean"),
        ("стаклено шише", "empty_glass_packaging", "appears_empty_clean"),
        ("plasticno sise", "empty_plastic_bottle", "appears_empty_clean"),
        ("phone", "small_electronics", "uncertain"),
        ("clean shirt", "wearable_clothes", "uncertain"),
        ("used tissue", "ordinary_residual", "not_empty_or_contaminated"),
        ("употребена пелена", "ordinary_residual", "not_empty_or_contaminated"),
    ],
)
def test_supported_photo_candidates_keep_explicit_confirmation(description, kind, condition):
    result = VisionService._suggestion(
        ModelPhotoItem(
            description=description,
            item_kind=kind,
            visible_condition=condition,
            reason="Visible object.",
        )
    )
    assert result.status is SuggestionStatus.CANDIDATE
    assert result.item_kind == kind
    assert result.category is not None


@pytest.mark.parametrize(
    "reason,expected_kind",
    [
        ("Contains pesticide.", "other"),
        ("содржи хемикалии", "other"),
        ("A battery is visible inside.", "batteries"),
    ],
)
def test_photo_specialist_hazards_take_precedence_over_conflicting_enum(reason, expected_kind):
    result = VisionService._suggestion(
        ModelPhotoItem(
            description="plastic bottle and glass jar",
            item_kind="empty_plastic_bottle",
            visible_condition="appears_empty_clean",
            reason=reason,
        )
    )
    assert result.status is SuggestionStatus.SPECIALIST
    assert result.item_kind == expected_kind
    assert result.category == "special_unsupported"


def test_contaminated_electronics_require_review():
    result = VisionService._suggestion(
        ModelPhotoItem(
            description="phone",
            item_kind="small_electronics",
            visible_condition="not_empty_or_contaminated",
            reason="Visible device.",
        )
    )
    assert result.status is SuggestionStatus.NEEDS_REVIEW
    assert result.item_kind == "other"
