"""Check a running local/container/hosted app without spending provider quota."""

import argparse
import json
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def get(base, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        base.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urlopen(request, timeout=15) as response:
        body = response.read()
        return (
            json.loads(body) if "application/json" in response.headers.get_content_type() else body
        )


def wait_for_health(url, wait_seconds):
    """Allow connection resets while a container's app is still starting."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            return get(url, "/health")
        except (URLError, TimeoutError, ConnectionError, HTTPException):
            if time.monotonic() >= deadline:
                raise SystemExit("FAIL: application did not become healthy") from None
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait-seconds", type=int, default=180)
    parser.add_argument("--require-minilm", action="store_true")
    parser.add_argument("--require-macedonian", action="store_true")
    args = parser.parse_args()
    health = wait_for_health(args.url, args.wait_seconds)
    assert health["status"] == "ok" and health["site_count"] > 0
    if args.require_minilm:
        assert health["text_suggestion_model"] != "unavailable", "MiniLM failed to load"
        suggestion = get(args.url, "/api/v1/classify", {"text": "a jar"})
        assert suggestion["suggestion_model_version"] == health["text_suggestion_model"]
        assert suggestion["suggested_category"] in {
            "glass",
            "plastic_metal",
            "paper_tetrapak",
            "special_unsupported",
        }
        assert suggestion["status"] == "clarify" and suggestion["abstained"] is True
        assert suggestion["category"] is None
    if args.require_macedonian:
        assert health["macedonian_suggestion_model"] != "unavailable"
        suggestion = get(
            args.url,
            "/api/v1/classify",
            {
                "text": "хартиено упатство",
                "language": "mk",
            },
        )
        assert suggestion["suggestion_model_version"] == health["macedonian_suggestion_model"]
        assert suggestion["suggested_category"] == "paper_tetrapak"
        assert suggestion["status"] == "clarify" and suggestion["category"] is None
        assert suggestion["choices"][0]["label"] != "Clean, uncoated paper"
        uncertain = get(
            args.url,
            "/api/v1/classify",
            {"text": "Листови од стара тетратка", "language": "mk"},
        )
        assert uncertain["status"] == "clarify" and uncertain["category"] is None
        assert uncertain["suggested_category"] is None  # The v3 gate may decline a suggestion.
        confirmed = get(
            args.url,
            "/api/v1/classify",
            {
                "text": "празно стаклено шише",
                "manual_kind": "empty_glass_packaging",
                "condition_confirmed": True,
                "language": "mk",
            },
        )
        assert confirmed["status"] == "ready_for_site_matching"
        assert confirmed["message"].startswith("Деталите")
    for path, marker in [("/", b"Recycling routes"), ("/city", b"10-minute walking access")]:
        assert marker in get(args.url, path), path
    for path in (
        "/static/i18n.js",
        "/static/locales/mk.json",
        "/static/app.js",
        "/static/styles.css",
        "/static/citizen.css",
        "/static/city.css",
        "/static/city.js",
        "/static/upgrades.js",
        "/static/path.js",
        "/static/trip.js",
        "/static/vendor/leaflet/leaflet.js",
    ):
        assert len(get(args.url, path)) > 100, path
    sites = get(args.url, "/api/v1/sites")
    assert len(sites["sites"]) == health["site_count"]
    parking = get(args.url, "/api/v1/parking")
    assert parking["license"] == "ODbL-1.0" and parking["places"]
    assert all(place["access"] in {"yes", "permissive"} for place in parking["places"])
    result = get(
        args.url,
        "/api/v1/classify",
        {
            "text": "empty glass jar",
            "manual_kind": "empty_glass_packaging",
            "condition_confirmed": True,
        },
    )
    assert result["status"] == "ready_for_site_matching"
    for text, kind, category in (
        ("used tissue", "ordinary_residual", "general"),
        ("old charger", "electronics", "special_unsupported"),
        ("old phone", "small_electronics", "special_unsupported"),
        ("clean shirt", "wearable_clothes", "special_unsupported"),
    ):
        decision = get(
            args.url,
            "/api/v1/classify",
            {
                "text": text,
                "manual_kind": kind,
                "condition_confirmed": True,
            },
        )
        assert decision["status"] == "ready_for_site_matching"
        assert decision["category"] == category
    citizen = get(args.url, "/api/v1/sites?scope=citizen")
    assert any(site["id"] == "ewaste-karpos-yard" for site in citizen["sites"])
    assert any(site["id"] == "ewaste-east-gate-mall" for site in citizen["sites"])
    assert sum("clothes" in site["materials"] for site in citizen["sites"]) == 5
    assert get(args.url, "/api/v1/coverage")["materials"]
    assert get(args.url, "/api/v1/upgrades?material=glass&n=5")
    print("PASS: health, pages, assets, confirmed guidance, real sites, coverage and upgrades")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"FAIL: endpoint returned HTTP {error.code}") from None
