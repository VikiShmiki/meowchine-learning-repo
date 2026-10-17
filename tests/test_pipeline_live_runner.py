"""The paid smoke runner itself is tested without making external requests."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pipeline_runner", ROOT / "scripts/check_six_stream_pipeline.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
CASES = json.loads((runner.FIXTURES / "cases.json").read_text())


@pytest.mark.parametrize("photos", [True, False])
def test_runner_is_bounded_and_never_routes_incomplete_photo_basket(photos):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("classify"):
            body = json.loads(request.content)
            row = next(row for row in CASES if row["text"] == body["text"])
            return httpx.Response(
                200,
                json={
                    "item_kind": row["kind"],
                    "status": "ready_for_site_matching"
                    if "manual_kind" in body
                    else "confirm_condition",
                    "model_version": "fixture",
                },
            )
        if request.url.path.endswith("photo-suggestions"):
            # Wrong prediction must fail, never silently replaced with expected kind.
            return httpx.Response(
                200,
                headers={"cache-control": "no-store"},
                json={
                    "requires_user_confirmation": True,
                    "items": [{"item_kind": "batteries"}],
                    "model_version": "fixture",
                },
            )
        if request.url.path.endswith("sites"):
            return httpx.Response(200, json={"sites": []})
        assert request.url.path.endswith("trips")
        assert len(json.loads(request.content)["items"]) == 6
        return httpx.Response(503, json={"error": "not logged"})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(handler)
    ) as client:
        report = runner.run_checks(client, CASES, photos=photos)
    assert report["passed"] is False
    assert calls.count("/api/v1/photo-suggestions") == (6 if photos else 0)
    assert calls.count("/api/v1/trips") == 4
    assert len(report["checks"]) == (18 if photos else 10)
    if photos:
        assert report["checks"][-1]["detail"] == "Not routed: incomplete validated basket"


def test_general_asset_has_no_acceptance_profile():
    sites = {
        "bin": {
            "assets": [
                {
                    "id": "asset",
                    "acceptance": None,
                    "asset_type": "waste_container",
                    "source_materials": ["mixed_municipal_waste"],
                }
            ]
        }
    }
    body = {
        "profile": "foot-walking",
        "provider": "openrouteservice",
        "distance_m": 10,
        "duration_s": 20,
        "ends_at_last_stop": True,
        "geometry": {"type": "LineString", "coordinates": [[21.4, 42], [21.41, 42]]},
        "stops": [
            {
                "site_id": "bin",
                "asset_ids": ["asset"],
                "item_kinds": ["general"],
                "unverified_materials": ["general"],
            }
        ],
    }
    runner.verify_trip(body, [{"material": "general"}], "walking", sites)
    body["stops"][0]["asset_ids"] = ["nonexistent"]
    with pytest.raises(AssertionError):
        runner.verify_trip(body, [{"material": "general"}], "walking", sites)


def test_fixture_images_are_valid_bounded_and_metadata_free():
    from PIL import Image

    assert len(CASES) == len({row["id"] for row in CASES}) == 6
    for row in CASES:
        path = runner.FIXTURES / "images" / row["photo"]
        assert path.stat().st_size < 8 * 1024 * 1024
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert not image.getexif()
            image.load()
