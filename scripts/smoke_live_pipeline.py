"""Opt-in real photo API and walking/driving HTTP journeys using a public origin."""

import argparse
import io

import httpx
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    failures = []
    with httpx.Client(base_url=args.url, timeout=60) as client:
        # A blank synthetic image tests connectivity/structured output without personal data.
        output = io.BytesIO()
        Image.new("RGB", (256, 256), "white").save(output, format="PNG")
        photo = client.post(
            "/api/v1/photo-suggestions",
            content=output.getvalue(),
            headers={"Content-Type": "image/png"},
        )
        if photo.status_code == 200:
            body = photo.json()
            assert body["requires_user_confirmation"] is True
            assert photo.headers["cache-control"] == "no-store"
            if body["items"]:
                failures.append("photo: blank image produced item suggestions")
            else:
                print("PASS: live vision returns no items for a blank image")
        else:
            failures.append(f"photo: HTTP {photo.status_code}")
        sites_response = client.get("/api/v1/sites")
        sites_response.raise_for_status()
        sites = {s["id"]: s for s in sites_response.json()["sites"]}
        items = [
            {
                "text": "empty glass jar",
                "manual_kind": "empty_glass_packaging",
                "condition_confirmed": True,
            },
            {"text": "clean paper", "manual_kind": "clean_paper", "condition_confirmed": True},
        ]
        for item in items:
            answer = client.post("/api/v1/classify", json=item)
            assert answer.status_code == 200
            assert answer.json()["status"] == "ready_for_site_matching"
        for mode in ("walking", "driving"):
            trip = client.post(
                "/api/v1/trips",
                json={
                    "items": items,
                    "mode": mode,
                    "origin": {"latitude": 41.9965, "longitude": 21.4314},
                    "share_coordinates": True,
                },
            )
            if trip.status_code != 200:
                failures.append(f"{mode}: HTTP {trip.status_code}")
                continue
            body = trip.json()
            covered = set()
            for stop in body["stops"]:
                assets = [
                    a for a in sites[stop["site_id"]]["assets"] if a["id"] in stop["asset_ids"]
                ]
                accepted = {k for a in assets for k in a["acceptance"]["accepted_item_kinds"]}
                assert set(stop["item_kinds"]) <= accepted
                covered.update(stop["item_kinds"])
            assert covered == {item["manual_kind"] for item in items}
            assert body["distance_m"] > 0 and body["duration_s"] > 0
            assert len(body["geometry"]["coordinates"]) >= 2
            assert body["ends_at_last_stop"] is True
            print(f"PASS: live {mode}, {len(body['stops'])} compatible stops")
    if failures:
        raise SystemExit("FAIL: " + "; ".join(failures))


if __name__ == "__main__":
    main()
