"""Test-only server: real application and data, fake external HTTP transports."""

import base64
import io
import json
from dataclasses import replace
from pathlib import Path

import httpx
from PIL import Image

from smart_recycling import api
from smart_recycling.ors import ORSProvider
from smart_recycling.vision import OpenAIVisionProvider, VisionService

PIPELINE_CASES = {
    row["id"]: row
    for row in json.loads(
        (Path(__file__).parent / "fixtures/pipeline/cases.json").read_text(encoding="utf-8")
    )
}
pipeline_case = None
pipeline_fault = None
pipeline_calls = []


def external(request):
    global pipeline_fault
    body = json.loads(request.content)
    if request.url.host == "api.openai.com":
        assert body["store"] is False
        assert body["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;")
        # White synthetic photo -> legacy jar fixture; blue -> new disposal workflow fixtures.
        encoded = body["input"][0]["content"][1]["image_url"].split(",", 1)[1]
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            red, green, blue = image.convert("RGB").getpixel((0, 0))
            assert image.format == "JPEG" and max(image.size) <= 1280
            assert not image.getexif()
        if pipeline_case is not None:
            pipeline_calls.append({"service": "vision"})
            if pipeline_fault == "vision":
                pipeline_fault = None
                return httpx.Response(503, json={"error": "simulated provider outage"})
            row = PIPELINE_CASES[pipeline_case]
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "items": [
                                {
                                    "description": row["mk_text"]
                                    if "Macedonian using Cyrillic" in body["instructions"]
                                    else row["text"],
                                    "item_kind": row["kind"],
                                    "visible_condition": row["condition"],
                                    "reason": "Симулирано набљудување на моделот."
                                    if "Macedonian using Cyrillic" in body["instructions"]
                                    else "Simulated model observation.",
                                }
                            ]
                        }
                    )
                },
            )
        if red > green + 100 and red > blue + 100:
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "items": [
                                {
                                    "description": "blue shirt",
                                    "item_kind": "wearable_clothes",
                                    "visible_condition": "uncertain",
                                    "reason": "Identifiable garment.",
                                }
                            ]
                        }
                    )
                },
            )
        if green > red + 80 and green > blue + 80:
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "items": [
                                {
                                    "description": "old phone",
                                    "item_kind": "small_electronics",
                                    "visible_condition": "uncertain",
                                    "reason": "Identifiable small device.",
                                }
                            ]
                        }
                    )
                },
            )
        if blue > red + 100 and blue > green + 100:
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "items": [
                                {
                                    "description": "used tissue",
                                    "item_kind": "ordinary_residual",
                                    "visible_condition": "not_empty_or_contaminated",
                                    "reason": "Identifiable used household tissue.",
                                },
                                {
                                    "description": "old charger",
                                    "item_kind": "electronics",
                                    "visible_condition": "uncertain",
                                    "reason": "Electrical household device.",
                                },
                            ]
                        }
                    )
                },
            )
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "items": [
                            {
                                "description": "empty glass jar",
                                "item_kind": "empty_glass_packaging",
                                "visible_condition": "appears_empty_clean",
                                "reason": "Visible empty jar",
                            }
                        ]
                    }
                )
            },
        )
    assert request.url.host == "api.openrouteservice.org"
    assert any(p in request.url.path for p in ("foot-walking", "driving-car"))
    points = body.get("locations", body.get("coordinates"))
    if pipeline_case is not None:
        assert set(body) <= {
            "locations",
            "metrics",
            "resolve_locations",
            "coordinates",
            "radiuses",
            "instructions",
            "continue_straight",
        }
        pipeline_calls.append(
            {
                "service": "matrix" if "/matrix/" in request.url.path else "directions",
                "profile": "foot-walking" if "foot-walking" in request.url.path else "driving-car",
                "points": points,
            }
        )
        if pipeline_fault == "routing":
            pipeline_fault = None
            return httpx.Response(503, json={"error": "simulated provider outage"})
    if "/matrix/" in request.url.path:
        return httpx.Response(
            200,
            json={
                "durations": [
                    [abs(i - j) * 60 for j in range(len(points))] for i in range(len(points))
                ],
                "sources": [{"location": p} for p in points],
                "destinations": [{"location": p} for p in points],
            },
        )
    return httpx.Response(
        200,
        json={
            "features": [
                {
                    "geometry": {"type": "LineString", "coordinates": points},
                    "properties": {
                        "way_points": list(range(len(points))),
                        "segments": [{}] * (len(points) - 1),
                        "summary": {"distance": 1200, "duration": 900},
                    },
                }
            ]
        },
    )


transport = httpx.MockTransport(external)
api.settings = replace(api.settings, ors_api_key="fixture-key")
api.route_service.provider = ORSProvider("fixture-key", transport)
api.vision_service = VisionService(
    OpenAIVisionProvider(
        "fixture-key", "fixture-model", client=httpx.AsyncClient(transport=transport)
    ),
    api.classifier.policy["version"],
)
app = api.app


@app.post("/__test/reset-account-budget")
def reset_account_budget():
    """Only the isolated fixture server exposes this, never production."""
    with api.community_store.connection() as db:
        db.execute(
            "DELETE FROM usage WHERE bucket LIKE 'account:%' OR bucket LIKE 'registration:%'"
        )
    return {"reset": True}


@app.post("/__test/reset-routing-budget")
def reset_routing_budget():
    """Test-server-only isolation between browser cases; production has no reset route."""
    with api.route_service._lock:
        assert api.route_service._active == 0
        api.route_service._started.clear()
    return {"reset": True}


@app.post("/__test/pipeline-case/{case_id}")
def select_pipeline_case(case_id: str, fault: str | None = None):
    """Fixture selection is deliberately test-server-only, never in the production app."""
    global pipeline_case, pipeline_fault
    assert case_id in PIPELINE_CASES
    assert fault in {None, "vision", "routing"}
    reset_routing_budget()
    pipeline_case, pipeline_fault = case_id, fault
    pipeline_calls.clear()
    return {"case": case_id, "provider": "simulated"}


@app.get("/__test/pipeline-calls")
def get_pipeline_calls():
    return {"calls": pipeline_calls}
