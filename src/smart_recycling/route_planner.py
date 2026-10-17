"""Asset-scoped matching and exact coverage-path search over a bounded shortlist."""

import heapq
import math
from dataclasses import dataclass

from smart_recycling.geo import haversine_m
from smart_recycling.infrastructure_models import InfrastructureAsset, InfrastructureSite
from smart_recycling.routing_models import STREAM_KINDS, Coordinates, RoutingError


def accepts(asset: InfrastructureAsset, kind: str) -> bool:
    """Match full recycling capabilities or the explicitly requested general-bin type."""
    if kind in {"general", "ordinary_residual"}:
        # Navigation to a recorded bin type, not a disposal-policy acceptance claim.
        return (
            asset.operational_status in {"unknown", "operational", "open"}
            and asset.asset_type == "waste_container"
            and asset.collection_mode == "drop_off_container"
            and "mixed_municipal_waste" in asset.source_materials
        )
    return bool(
        asset.acceptance
        and asset.operational_status in {"unknown", "operational", "open"}
        and STREAM_KINDS.get(kind, frozenset({kind})) <= set(asset.acceptance.accepted_item_kinds)
    )


@dataclass(frozen=True)
class Candidate:
    """A source site and the required kinds explicitly supported by its assets."""

    site: InfrastructureSite
    kinds: frozenset[str]


def shortlist(
    sites: tuple[InfrastructureSite, ...], kinds: tuple[str, ...], origin: Coordinates
) -> list[Candidate]:
    """Retain three nearest sites per kind; this is a candidate heuristic, not a route."""
    candidates = []
    for site in sites:
        accepted = frozenset(
            kind for asset in site.assets for kind in kinds if accepts(asset, kind)
        )
        if accepted:
            candidates.append(Candidate(site, accepted))
    candidates.sort(
        key=lambda candidate: (
            haversine_m(
                (origin.latitude, origin.longitude),
                (candidate.site.latitude, candidate.site.longitude),
            ),
            candidate.site.id,
        )
    )
    selected: dict[str, Candidate] = {}
    for kind in kinds:
        eligible = [candidate for candidate in candidates if kind in candidate.kinds]
        if not eligible:
            raise RoutingError(
                "no_compatible_site",
                "No available recorded general-waste bin."
                if kind == "general"
                else f"No explicitly accepting City site for {kind}.",
            )
        for candidate in eligible[:3]:
            selected[candidate.site.id] = candidate
    return sorted(selected.values(), key=lambda candidate: candidate.site.id)


def solve(masks: list[int], durations: list[list[float | None]], target: int) -> list[int]:
    """Minimize directed network time from index 0, stopping when all kinds are covered.

    Candidate i is matrix index i+1. Every transition adds coverage, so revisits
    cannot help when matrix edges already represent shortest network paths.
    """
    queue = [(0.0, (), 0, 0)]
    best: dict[tuple[int, int], float] = {(0, 0): 0.0}
    while queue:
        cost, path, covered, last = heapq.heappop(queue)
        if cost != best.get((covered, last)):
            continue
        if covered == target:
            return list(path)
        for index, mask in enumerate(masks):
            next_covered = covered | mask
            edge = durations[last][index + 1]
            if next_covered == covered or edge is None or not math.isfinite(edge) or edge < 0:
                continue
            state = (next_covered, index + 1)
            next_cost = cost + edge
            if next_cost < best.get(state, math.inf):
                best[state] = next_cost
                heapq.heappush(queue, (next_cost, (*path, index), *state))
    raise RoutingError(
        "no_route",
        "No connected trip covers all items among the nearby candidates. "
        "Try another starting point or travel mode. No items were silently omitted.",
    )
