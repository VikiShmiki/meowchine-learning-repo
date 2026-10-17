"""Trip orchestration with authoritative item checks and bounded provider usage."""

import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from uuid import uuid4

from smart_recycling.guidance import GuidanceClassifier
from smart_recycling.infrastructure_models import SiteSnapshot
from smart_recycling.ors import PROFILES, ORSProvider
from smart_recycling.route_planner import accepts, shortlist, solve
from smart_recycling.routing_models import RoutingError, Stop, TripRequest, TripResponse, TripStream

logger = logging.getLogger(__name__)


class RoutingService:
    """A single-process demo service; never cache or log origins or descriptions."""

    def __init__(
        self,
        snapshot: SiteSnapshot,
        classifier: GuidanceClassifier,
        provider: ORSProvider,
        transit=None,
    ):
        self.snapshot, self.classifier, self.provider = snapshot, classifier, provider
        self.transit = transit
        self._lock = threading.Lock()
        self._started: deque[float] = deque()
        self._active = 0

    @contextmanager
    def _budget(self):
        with self._lock:
            now = time.monotonic()
            while self._started and self._started[0] < now - 60:
                self._started.popleft()
            if self._active >= 2 or len(self._started) >= 20:
                raise RoutingError("busy", "Routing is busy. Please retry in a minute.", 429)
            self._started.append(now)
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    def plan(self, request: TripRequest, *, statuses=None, status_version="") -> TripResponse:
        """Revalidate the entire basket; never silently route only a subset."""
        started, request_id = time.monotonic(), uuid4().hex
        outcome = "ok"
        try:
            return self._plan(request, statuses or {}, status_version)
        except RoutingError as error:
            outcome = error.code
            raise
        finally:
            logger.info(
                "routing request=%s mode=%s outcome=%s duration_ms=%.1f dataset=%s",
                request_id,
                request.mode,
                outcome,
                (time.monotonic() - started) * 1000,
                self.snapshot.dataset_version,
            )

    def _plan(self, request: TripRequest, statuses=None, status_version="") -> TripResponse:
        if not request.share_coordinates:
            raise RoutingError(
                "consent_required", "Confirm sharing your starting point with the routing provider."
            )
        for index, item in enumerate(request.items):
            if isinstance(item, TripStream):
                if item.material == "general" and not item.accept_unverified:
                    raise RoutingError(
                        "unverified_acceptance",
                        "General-waste bin acceptance is unverified. Acknowledge the warning "
                        "before requesting directions to recorded bins.",
                    )
                if not item.condition_confirmed:
                    raise RoutingError(
                        "item_not_confirmed",
                        "Confirm empty/clean items with no hazardous contents.",
                    )
                continue
            answer = self.classifier.decide(item.text, item.manual_kind, item.condition_confirmed)
            if not item.text.strip() or answer.status != "ready_for_site_matching":
                raise RoutingError(
                    "item_not_confirmed",
                    f"Item {index + 1} needs confirmation or specialist guidance. "
                    "No trip was requested.",
                )
        kinds = tuple(
            sorted(
                {
                    item.routing_kind if isinstance(item, TripStream) else item.manual_kind
                    for item in request.items
                }
            )
        )
        statuses = statuses or {}
        # Build a per-request view; never mutate the shared immutable source snapshot.
        effective_sites = tuple(
            site.model_copy(
                update={
                    "assets": tuple(
                        asset.model_copy(
                            update={"operational_status": statuses[asset.id]["condition"]}
                        )
                        if asset.id in statuses and statuses[asset.id]["condition"] != "available"
                        else asset
                        for asset in site.assets
                    )
                }
            )
            for site in self.snapshot.sites
        )
        candidates = shortlist(effective_sites, kinds, request.origin)
        points = [
            request.origin.lonlat(),
            *[[c.site.longitude, c.site.latitude] for c in candidates],
        ]
        masks = [sum(1 << i for i, kind in enumerate(kinds) if kind in c.kinds) for c in candidates]
        extra = {}
        with self._budget():
            if request.mode == "transit":
                if self.transit is None:
                    raise RoutingError(
                        "transit_unavailable", "JSP timetable is unavailable. Retry shortly.", 503
                    )
                indices, route, extra = self.transit.plan(request, candidates, kinds)
            else:
                durations = self.provider.matrix(request.mode, points)
                indices = solve(masks, durations, (1 << len(kinds)) - 1)
                route = self.provider.directions(
                    request.mode, [points[0], *[points[i + 1] for i in indices]]
                )
                extra["profile"] = PROFILES[request.mode]
        selected = [candidates[index] for index in indices]
        stops, remaining = [], set(kinds)
        for index, candidate in enumerate(selected):
            assigned = sorted(remaining & candidate.kinds)
            remaining.difference_update(assigned)
            assets = [
                asset
                for asset in candidate.site.assets
                if any(accepts(asset, kind) for kind in assigned)
            ]
            stops.append(
                Stop(
                    site_id=candidate.site.id,
                    name=assets[0].name,
                    latitude=candidate.site.latitude,
                    longitude=candidate.site.longitude,
                    item_kinds=assigned,
                    asset_ids=[asset.id for asset in assets],
                    arrival_notes=self.classifier.policy.get("arrival_notes", {}).get(
                        candidate.site.id, []
                    ),
                    acceptance_limits=sorted(
                        {asset.acceptance.limits for asset in assets if asset.acceptance}
                    ),
                    unverified_materials=["general"]
                    if {"general", "ordinary_residual"} & set(assigned)
                    else [],
                    network_access_gap_m=round(route.gaps_m[index + 1], 1),
                )
            )
        return TripResponse(
            status_version=status_version,
            mode=request.mode,
            distance_m=route.distance_m,
            duration_s=route.duration_s,
            geometry={"type": "LineString", "coordinates": route.geometry}
            if route.geometry
            else None,
            stops=stops,
            dataset_version=self.snapshot.dataset_version,
            policy_version=self.snapshot.policy_version,
            source_as_of=self.snapshot.as_of_date,
            candidate_count=len(candidates),
            warnings=[
                *(
                    [
                        "General-waste stops are recorded bin locations, not verified disposal "
                        "acceptance. Only ordinary non-hazardous household waste; follow bin "
                        "instructions. No batteries, electronics, chemicals, "
                        "medical or bulky waste."
                    ]
                    if {"general", "ordinary_residual"} & set(kinds)
                    else []
                ),
                *route.warnings,
                "Nearby shortlist: up to three source sites per item type. "
                "This is not a city-wide optimum.",
                "Network endpoints may be up to 100 m from recorded sites. "
                "Access connectors and entrances are unverified; "
                "do not cross barriers or private land.",
                *(
                    []
                    if request.mode == "transit"
                    else [
                        "Time and distance cover the routed network only, "
                        "excluding access gaps, disposal time, parking and live traffic."
                    ]
                ),
                "Site operation and local policy human review remain unverified. "
                "Check container instructions.",
            ],
            **extra,
        )
