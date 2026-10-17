"""Routing safety, directed optimization and provider-contract regressions; no live traffic."""

import itertools
import json
import math

import httpx
import pytest
from fastapi.testclient import TestClient

from smart_recycling import api
from smart_recycling.infrastructure_models import Acceptance
from smart_recycling.ors import ORSProvider
from smart_recycling.route_planner import shortlist, solve
from smart_recycling.routing import RoutingService
from smart_recycling.routing_models import STREAM_KINDS, Coordinates, RoutingError, TripRequest


@pytest.mark.parametrize("mode", ["walking", "driving"])
def test_known_streams_cover_all_capabilities_in_one_trip(mode):
    kinds = set().union(*STREAM_KINDS.values())
    planner, calls = service([site("all-streams", kinds)])
    payload = request(mode).model_dump()
    payload["items"] = [
        {"material": material, "condition_confirmed": True} for material in STREAM_KINDS
    ]
    result = planner.plan(TripRequest.model_validate(payload))
    assert len(result.stops) == 1
    assert set(result.stops[0].item_kinds) == set(STREAM_KINDS)
    assert len(calls) == 2


def test_stream_requires_full_asset_acceptance_and_confirmation():
    planner, calls = service([site("only-paper", ("clean_paper",))])
    payload = request().model_dump()
    payload["items"] = [{"material": "paper_tetrapak", "condition_confirmed": False}]
    with pytest.raises(RoutingError, match="Confirm empty"):
        planner.plan(TripRequest.model_validate(payload))
    payload["items"][0]["condition_confirmed"] = True
    with pytest.raises(RoutingError, match="No explicitly accepting"):
        planner.plan(TripRequest.model_validate(payload))
    assert calls == []


def test_mixed_stream_and_hazardous_item_does_not_bypass_policy():
    planner, calls = service([site("all-streams", set().union(*STREAM_KINDS.values()))])
    payload = request().model_dump()
    payload["items"][0] = {"material": "glass", "condition_confirmed": True}
    payload["items"][1]["text"] = "paint can"
    with pytest.raises(RoutingError, match="specialist guidance"):
        planner.plan(TripRequest.model_validate(payload))
    assert calls == []


@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("materials", [("general",), ("glass", "general")])
def test_recorded_general_bin_route_is_explicitly_unverified(mode, materials):
    general = site("general-bin", ())
    asset = general.assets[0].model_copy(
        update={
            "asset_type": "waste_container",
            "collection_mode": "drop_off_container",
            "source_materials": ("mixed_municipal_waste",),
            "acceptance": None,
        }
    )
    general = general.model_copy(update={"assets": (asset,)})
    planner, calls = service([site("glass-bin", ("empty_glass_packaging",)), general])
    payload = request(mode).model_dump()
    payload["items"] = [
        {"material": material, "condition_confirmed": True, "accept_unverified": True}
        for material in materials
    ]
    result = planner.plan(TripRequest.model_validate(payload))
    assert set().union(*(set(s.item_kinds) for s in result.stops)) == set(materials)
    stop = next(s for s in result.stops if "general" in s.item_kinds)
    assert stop.asset_ids == ["general-bin-asset"]
    assert stop.unverified_materials == ["general"]
    assert stop.acceptance_limits == []  # Do not invent an acceptance policy.
    assert any("not verified disposal" in warning for warning in result.warnings)
    assert len(calls) == 2


def test_general_requires_acknowledgement_and_never_uses_unrelated_or_closed_bins():
    closed = site("closed-general", (), status="closed")
    closed_asset = closed.assets[0].model_copy(
        update={
            "asset_type": "waste_container",
            "collection_mode": "drop_off_container",
            "source_materials": ("mixed_municipal_waste",),
            "acceptance": None,
        }
    )
    closed = closed.model_copy(update={"assets": (closed_asset,)})
    planner, calls = service([site("glass-only", ("empty_glass_packaging",)), closed])
    payload = request().model_dump()
    payload["items"] = [{"material": "general", "condition_confirmed": True}]
    with pytest.raises(RoutingError) as error:
        planner.plan(TripRequest.model_validate(payload))
    assert error.value.code == "unverified_acceptance"
    payload["items"][0]["accept_unverified"] = True
    with pytest.raises(RoutingError) as error:
        planner.plan(TripRequest.model_validate(payload))
    assert error.value.code == "no_compatible_site"
    assert calls == []


def test_general_does_not_allow_unconfirmed_or_hazardous_description_override():
    planner, calls = service([site("anything", ("empty_glass_packaging",))])
    payload = request().model_dump()
    payload["items"][0] = {
        "material": "general",
        "condition_confirmed": False,
        "accept_unverified": True,
    }
    with pytest.raises(RoutingError, match="Confirm"):
        planner.plan(TripRequest.model_validate(payload))
    payload["items"][0]["condition_confirmed"] = True
    payload["items"][1]["text"] = "old battery"
    with pytest.raises(RoutingError, match="specialist guidance"):
        planner.plan(TripRequest.model_validate(payload))
    assert calls == []


GLASS = "empty_glass_packaging"
PAPER = "clean_paper"


def request(mode="walking", kinds=(GLASS, PAPER)):
    return TripRequest(
        origin={"latitude": 42, "longitude": 21.4},
        mode=mode,
        items=[
            {
                "text": "a jar" if kind == GLASS else "paper",
                "manual_kind": kind,
                "condition_confirmed": True,
            }
            for kind in kinds
        ],
        share_coordinates=True,
    )


def site(identifier, kinds, longitude=21.401, status="unknown"):
    template = api.route_service.snapshot.sites[0]
    asset = template.assets[0].model_copy(
        update={
            "id": identifier + "-asset",
            "name": identifier,
            "asset_type": "recycling_container",
            "collection_mode": "drop_off_container",
            "source_materials": ("glass",),
            "operational_status": status,
            "acceptance": Acceptance(
                profile_id="test",
                accepted_item_kinds=tuple(kinds),
                evidence_ids=("test",),
                limits="Empty/clean only",
            ),
        }
    )
    return template.model_copy(
        update={"id": identifier, "latitude": 42, "longitude": longitude, "assets": (asset,)}
    )


def provider(handler=None):
    calls = []

    def respond(req):
        payload = json.loads(req.content)
        calls.append((req.url.path, payload, req.headers["Accept"]))
        if handler:
            return handler(req, payload)
        points = payload.get("locations", payload.get("coordinates"))
        if "/matrix/" in req.url.path:
            n = len(points)
            return httpx.Response(
                200,
                json={
                    "durations": [[abs(i - j) * 10 for j in range(n)] for i in range(n)],
                    "sources": [{"location": p} for p in points],
                    "destinations": [{"location": p} for p in points],
                },
            )
        return httpx.Response(200, json=direction_body(points))

    return ORSProvider("test-secret", httpx.MockTransport(respond)), calls


def direction_body(points):
    return {
        "features": [
            {
                "geometry": {"type": "LineString", "coordinates": points},
                "properties": {
                    "way_points": list(range(len(points))),
                    "segments": [{}] * (len(points) - 1),
                    "summary": {"distance": 200, "duration": 100},
                },
            }
        ]
    }


def service(sites):
    adapter, calls = provider()
    snapshot = api.route_service.snapshot.model_copy(update={"sites": tuple(sites)})
    return RoutingService(snapshot, api.classifier, adapter), calls


def test_directed_optimum_ends_at_last_stop_without_return():
    durations = [[0, 1, 9, 5], [None, 0, 1, 6], [None, 50, 0, 6], [None, 6, 6, 0]]
    assert solve([1, 2, 3], durations, 3) == [0, 1]
    assert solve([3, 3], [[0, 3, 4], [9, 0, 1], [9, 1, 0]], 3) == [0]


def test_solver_matches_exhaustive_shortest_path_fixture():
    durations = [
        [0, 4, 3, 8, 10],
        [8, 0, 2, 2, 5],
        [3, 6, 0, 1, 7],
        [9, 3, 5, 0, 4],
        [5, 4, 1, 2, 0],
    ]
    for k, i, j in itertools.product(range(5), repeat=3):
        durations[i][j] = min(durations[i][j], durations[i][k] + durations[k][j])
    masks = [1, 2, 4, 3]
    choices = []
    for size in range(1, 5):
        for order in itertools.permutations(range(4), size):
            covered = 0
            for index in order:
                covered |= masks[index]
            if covered == 7:
                nodes = [0, *[index + 1 for index in order]]
                choices.append(
                    sum(durations[a][b] for a, b in zip(nodes[:-1], nodes[1:], strict=True))
                )
    selected = solve(masks, durations, 7)
    nodes = [0, *[index + 1 for index in selected]]
    assert sum(durations[a][b] for a, b in zip(nodes[:-1], nodes[1:], strict=True)) == min(choices)


def test_shortlist_is_bounded_per_kind_and_budget_limits_requests():
    planner, calls = service(
        [site(f"site-{i}", (GLASS, PAPER), 21.401 + i / 1000) for i in range(8)]
    )
    assert len(shortlist(planner.snapshot.sites, (GLASS, PAPER), request().origin)) == 3
    planner._active = 2
    with pytest.raises(RoutingError) as failure:
        planner.plan(request())
    assert failure.value.code == "busy"
    assert calls == []


def test_unreachable_kind_is_not_silently_dropped():
    with pytest.raises(RoutingError, match="No connected trip"):
        solve([1, 2], [[0, 1, None], [None, 0, None], [None, None, 0]], 3)


def test_matching_uses_asset_acceptance_not_site_category_and_excludes_closed():
    candidate = site("narrow-vending", ("empty_beverage_can",))
    closed = site("closed", (GLASS,), status="closed")
    with pytest.raises(RoutingError, match="No explicitly accepting"):
        shortlist((candidate, closed), (GLASS,), Coordinates(latitude=42, longitude=21.4))


@pytest.mark.parametrize("mode,profile", [("walking", "foot-walking"), ("driving", "driving-car")])
def test_matching_deduplicates_stop_and_uses_correct_profile(mode, profile):
    planner, calls = service([site("combined", (GLASS, PAPER))])
    result = planner.plan(request(mode, (GLASS, PAPER, GLASS)))
    assert len(result.stops) == 1
    assert set(result.stops[0].item_kinds) == {GLASS, PAPER}
    assert result.stops[0].asset_ids == ["combined-asset"]
    assert len(calls) == 2
    assert all(profile in path for path, _, _ in calls)
    assert calls[1][2] == "application/geo+json"
    assert calls[1][1]["continue_straight"] == (mode == "driving")
    assert len(calls[1][1]["coordinates"]) == 2
    assert "text" not in json.dumps([payload for _, payload, _ in calls])


@pytest.mark.parametrize("text", ["old battery", "paint can", "greasy cardboard"])
def test_hazard_or_held_item_cannot_be_overridden_and_never_contacts_provider(text):
    planner, calls = service([site("recycling", (GLASS, PAPER))])
    payload = request()
    payload.items[0].text = text
    with pytest.raises(RoutingError, match="specialist guidance"):
        planner.plan(payload)
    assert calls == []


def test_unconfirmed_item_and_missing_consent_block_provider():
    planner, calls = service([site("recycling", (GLASS, PAPER))])
    payload = request()
    payload.share_coordinates = False
    with pytest.raises(RoutingError, match="sharing"):
        planner.plan(payload)
    payload.share_coordinates = True
    payload.items[0].condition_confirmed = False
    with pytest.raises(RoutingError, match="confirmation"):
        planner.plan(payload)
    assert calls == []


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_auth"),
        (403, "provider_auth"),
        (429, "provider_limit"),
        (503, "provider_unavailable"),
        (404, "provider_no_route"),
    ],
)
def test_provider_failures_are_actionable_and_do_not_echo_sensitive_bodies(status, code):
    adapter, _ = provider(lambda req, body: httpx.Response(status, text="test-secret sensitive"))
    with pytest.raises(RoutingError) as failure:
        adapter.matrix("walking", [[21.4, 42]])
    assert failure.value.code == code
    assert "secret" not in failure.value.message


def test_missing_key_and_timeout_do_not_fabricate_routes():
    with pytest.raises(RoutingError) as failure:
        ORSProvider("").matrix("walking", [[21.4, 42]])
    assert failure.value.code == "routing_not_configured"

    def timeout(req, body):
        raise httpx.ReadTimeout("private detail")

    adapter, _ = provider(timeout)
    with pytest.raises(RoutingError) as failure:
        adapter.matrix("driving", [[21.4, 42]])
    assert failure.value.code == "provider_timeout"


@pytest.mark.parametrize("change", ["shape", "nonfinite", "distant_origin"])
def test_bad_matrix_and_excessive_snapping_are_rejected(change):
    def response(req, body):
        data = {
            "durations": [[0]],
            "sources": [{"location": [21.4, 42]}],
            "destinations": [{"location": [21.4, 42]}],
        }
        if change == "shape":
            data["durations"] = []
        elif change == "nonfinite":
            return httpx.Response(200, content=json.dumps({**data, "durations": [[math.nan]]}))
        else:
            data["sources"][0]["location"] = [22, 43]
        return httpx.Response(200, json=data)

    adapter, _ = provider(response)
    with pytest.raises(RoutingError):
        adapter.matrix("walking", [[21.4, 42]])


@pytest.mark.parametrize("change", ["missing_stop", "skipped_segment", "malformed_warning", "gap"])
def test_incomplete_or_unsafe_provider_geometry_is_rejected(change):
    def response(req, body):
        data = direction_body(body["coordinates"])
        properties = data["features"][0]["properties"]
        if change == "missing_stop":
            properties["way_points"] = [0]
        elif change == "skipped_segment":
            properties["warnings"] = [{"code": 3}]
        elif change == "malformed_warning":
            properties["warnings"] = ["bad"]
        else:
            data["features"][0]["geometry"]["coordinates"][1] = [23, 43]
        return httpx.Response(200, json=data)

    adapter, _ = provider(response)
    with pytest.raises(RoutingError):
        adapter.directions("walking", [[21.4, 42], [21.401, 42]])


def test_extra_metadata_warning_is_exposed_without_discarding_valid_route():
    def response(req, body):
        data = direction_body(body["coordinates"])
        data["features"][0]["properties"]["warnings"] = [{"code": 4}]
        return httpx.Response(200, json=data)

    adapter, _ = provider(response)
    assert adapter.directions("walking", [[21.4, 42], [21.401, 42]]).warnings


def test_api_validation_and_no_store(monkeypatch):
    planner, _ = service([site("combined", (GLASS, PAPER))])
    monkeypatch.setattr(api, "route_service", planner)
    client = TestClient(api.app)
    payload = request().model_dump()
    response = client.post("/api/v1/trips", json=payload)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    for change in [
        {"items": []},
        {"mode": "cycling"},
        {"items": payload["items"] * 4},
        {"origin": {"latitude": 91, "longitude": 21.4}},
        {"share_coordinates": "yes"},
    ]:
        invalid = client.post("/api/v1/trips", json={**payload, **change})
        assert invalid.status_code == 422
        assert invalid.headers["cache-control"] == "no-store"
    response = client.post("/api/v1/trips", json={**payload, "share_coordinates": False})
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
