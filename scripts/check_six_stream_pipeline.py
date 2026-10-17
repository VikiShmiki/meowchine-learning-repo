"""Opt-in live six-stream check. Maximum six vision and six trip requests; no retries."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from smart_recycling.routing_models import STREAM_KINDS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/pipeline"
ORIGIN = {"latitude": 41.9965, "longitude": 21.4314}


def verify_trip(body, items, mode, sites):
    """Check every requested kind and recorded asset, not merely HTTP 200."""
    expected = set()
    for item in items:
        kind = item.get("manual_kind", item.get("material"))
        if kind == "clothes":
            kind = "wearable_clothes"
        if kind == "electronics" and item.get("small_only"):
            kind = "small_electronics"
        expected.add(kind)
    covered = set()
    assert body["profile"] == ("foot-walking" if mode == "walking" else "driving-car")
    assert body["provider"] == "openrouteservice"
    assert body["distance_m"] > 0 and body["duration_s"] > 0
    assert body["geometry"]["type"] == "LineString"
    assert len(body["geometry"]["coordinates"]) >= 2
    assert body["ends_at_last_stop"] is True
    for stop in body["stops"]:
        by_id = {asset["id"]: asset for asset in sites[stop["site_id"]]["assets"]}
        assert stop["asset_ids"] and set(stop["asset_ids"]) <= by_id.keys()
        assets = [by_id[asset_id] for asset_id in stop["asset_ids"]]
        accepted = {
            kind
            for asset in assets
            if asset["acceptance"]
            for kind in asset["acceptance"]["accepted_item_kinds"]
        }
        for kind in stop["item_kinds"]:
            if kind in {"general", "ordinary_residual"}:
                assert "general" in stop["unverified_materials"]
                assert any(
                    a["asset_type"] == "waste_container"
                    and "mixed_municipal_waste" in a["source_materials"]
                    for a in assets
                )
            else:
                assert STREAM_KINDS.get(kind, {kind}) <= accepted
            covered.add(kind)
    assert covered == expected, f"Missing/extra stop kinds: {expected ^ covered}"


def run_checks(client, cases, fixture_dir=FIXTURES, *, photos=True):
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "origin": ORIGIN,
        "synthetic_images": True,
        "checks": [],
    }
    report["photos_requested"] = photos
    baskets = {"picker": [], "text": []}
    if photos:
        baskets["photo"] = []

    def record(name, action):
        try:
            detail = action()
            report["checks"].append({"name": name, "passed": True, "detail": detail})
        except (AssertionError, KeyError, ValueError, TypeError, httpx.HTTPError) as error:
            # Never persist arbitrary HTTP response bodies or request headers.
            detail = (
                f"HTTP {error.response.status_code}"
                if isinstance(error, httpx.HTTPStatusError)
                else str(error)
                if isinstance(error, AssertionError)
                else type(error).__name__
            )
            report["checks"].append({"name": name, "passed": False, "detail": detail})
        print(json.dumps(report["checks"][-1]), flush=True)

    def confirm(row, text, kind, entry):
        item = {"text": text, "manual_kind": kind, "condition_confirmed": True}
        response = client.post("/api/v1/classify", json=item)
        response.raise_for_status()
        assert response.json()["status"] == "ready_for_site_matching", "Confirmation held"
        assert response.json()["item_kind"] == row["kind"], "Confirmed kind changed"
        baskets[entry].append(item)

    for row in cases:
        baskets["picker"].append(
            {
                "material": row["material"],
                "condition_confirmed": True,
                "accept_unverified": row["id"] == "general",
                "small_only": row["id"] == "electronics",
            }
        )

        def text_check(row=row):
            response = client.post("/api/v1/classify", json={"text": row["text"]})
            response.raise_for_status()
            body = response.json()
            assert body["item_kind"] == row["kind"], f"Observed kind: {body['item_kind']}"
            assert body["status"] in {"confirm_condition", "ready_for_site_matching"}
            confirm(row, row["text"], body["item_kind"], "text")
            return {"kind": body["item_kind"], "model": body["model_version"]}

        def photo_check(row=row):
            response = client.post(
                "/api/v1/photo-suggestions",
                content=(fixture_dir / "images" / row["photo"]).read_bytes(),
                headers={"Content-Type": "image/png"},
            )
            response.raise_for_status()
            body = response.json()
            assert body["requires_user_confirmation"] is True
            assert response.headers["cache-control"] == "no-store"
            assert len(body["items"]) == 1, f"Observed {len(body['items'])} items"
            item = body["items"][0]
            assert item["item_kind"] == row["kind"], f"Observed kind: {item['item_kind']}"
            assert item["status"] == "candidate", f"Photo held: {item['status']}"
            # Actual model description + kind, never fixture text to hide a bad prediction.
            confirm(row, item["description"], item["item_kind"], "photo")
            return {"kind": item["item_kind"], "model": body["model_version"]}

        record("text/" + row["id"], text_check)
        if photos:
            record("photo/" + row["id"], photo_check)

    response = client.get("/api/v1/sites?scope=citizen")
    response.raise_for_status()
    sites = {site["id"]: site for site in response.json()["sites"]}
    for entry, items in baskets.items():
        for mode in ("walking", "driving"):

            def route_check(items=items, mode=mode):
                assert len(items) == len(cases), "Not routed: incomplete validated basket"
                response = client.post(
                    "/api/v1/trips",
                    json={
                        "items": items,
                        "mode": mode,
                        "origin": ORIGIN,
                        "share_coordinates": True,
                    },
                )
                response.raise_for_status()
                body = response.json()
                verify_trip(body, items, mode, sites)
                return {
                    "stops": len(body["stops"]),
                    "profile": body["profile"],
                    "distance_m": body["distance_m"],
                    "dataset": body["dataset_version"],
                    "policy": body["policy_version"],
                }

            record(f"route/{entry}/{mode}", route_check)
    report["passed"] = all(check["passed"] for check in report["checks"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--without-photos",
        action="store_true",
        help="Check picker/text routes only, with no vision API spending",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/pipeline-live-results.json"
    )
    args = parser.parse_args()
    url = urlparse(args.url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("Use the local app; it holds the configured API credentials.")
    cases = json.loads((FIXTURES / "cases.json").read_text())
    with httpx.Client(base_url=args.url, timeout=60) as client:
        report = run_checks(client, cases, photos=not args.without_photos)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
