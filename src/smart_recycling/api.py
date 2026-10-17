"""HTTP adapter for the Smart Recycling Access domain."""

import logging
import os
import threading
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from smart_recycling.accounts import Accounts
from smart_recycling.accounts_api import router as accounts_router
from smart_recycling.clothes import add_clothing_sites
from smart_recycling.community import AllowanceExceeded, CommunityStore
from smart_recycling.community_api import router as community_router
from smart_recycling.coverage import load_coverage
from smart_recycling.coverage_models import CoverageReport
from smart_recycling.domain import Site, WasteCategory
from smart_recycling.electronics import citizen_snapshot
from smart_recycling.geo import nearest_site
from smart_recycling.guidance import MODEL_VERSION, GuidanceResponse, ItemKind, load_classifier
from smart_recycling.infrastructure import load_infrastructure
from smart_recycling.infrastructure_models import Scope, SiteSnapshot
from smart_recycling.localization import (
    guidance_translation,
    language_from_header,
    request_language,
    translate,
)
from smart_recycling.minilm import MiniLMError
from smart_recycling.multilingual import BilingualSuggester, suggestion_language
from smart_recycling.object_models import load_object_suggester
from smart_recycling.ors import ORSProvider
from smart_recycling.parking import ParkingPlanner
from smart_recycling.parking_data import ParkingCatalog
from smart_recycling.repository import load_sites
from smart_recycling.routing import RoutingService
from smart_recycling.routing_models import RoutingError, TripRequest, TripResponse
from smart_recycling.settings import PROJECT_ROOT, Settings
from smart_recycling.transit import TransitPlanner
from smart_recycling.transit_feed import TransitFeedStore
from smart_recycling.upgrades import Material, load_upgrades, payload
from smart_recycling.vision import (
    MAX_UPLOAD_BYTES,
    OpenAIVisionProvider,
    PhotoSuggestionsResponse,
    VisionError,
    VisionService,
)

logger = logging.getLogger(__name__)
settings = Settings.from_env()
try:
    text_suggester = (
        load_object_suggester(PROJECT_ROOT, "en", settings.minilm_model_path)
        if settings.minilm_suggestions_enabled
        else None
    )
except MiniLMError:
    logger.exception("MiniLM category suggestions are unavailable; rules remain active")
    text_suggester = None
english_suggester = text_suggester
multilingual_suggester = None
if settings.minilm_suggestions_enabled:
    try:
        configured = os.getenv("SRA_MULTILINGUAL_MODEL_PATH", "").strip()
        model_path = (
            (PROJECT_ROOT / configured).resolve()
            if configured
            else PROJECT_ROOT / "models/multilingual-minilm"
        )
        multilingual_suggester = load_object_suggester(
            PROJECT_ROOT, "mk", model_path if configured or model_path.exists() else None
        )
    except MiniLMError:
        logger.exception("Macedonian model unavailable; bilingual policy rules remain active")
    if multilingual_suggester or text_suggester:
        text_suggester = BilingualSuggester(text_suggester, multilingual_suggester)
classifier = load_classifier(
    settings.classifier_path,
    settings.guidance_policy_path,
    category_suggester=text_suggester,
)
sites = load_sites(settings.sites_data_path)
snapshots = load_infrastructure(settings.infrastructure_path, settings.policy_path)
snapshots["citizen"] = citizen_snapshot(
    SiteSnapshot.model_validate_json(snapshots["city"].body),
    PROJECT_ROOT / "data/infrastructure/electronics-2026-09-22",
    settings.guidance_policy_path,
)
snapshots["citizen"] = add_clothing_sites(
    SiteSnapshot.model_validate_json(snapshots["citizen"].body),
    PROJECT_ROOT / "data/infrastructure/clothes-2026-09-22",
    settings.guidance_policy_path,
)
parking_catalog = ParkingCatalog(PROJECT_ROOT / "data/parking/skopje-v1/parking.json")
route_service = RoutingService(
    SiteSnapshot.model_validate_json(snapshots["citizen"].body),
    classifier,
    ORSProvider(settings.ors_api_key),
    transit=TransitPlanner(
        TransitFeedStore(PROJECT_ROOT / "runtime/jsp-gtfs.zip"), ORSProvider(settings.ors_api_key)
    ),
    parking=ParkingPlanner(parking_catalog, ORSProvider(settings.ors_api_key)),
)
vision_service = VisionService(
    OpenAIVisionProvider(settings.openai_api_key, settings.openai_vision_model),
    classifier.policy["version"],
)

try:
    coverage_snapshot = load_coverage(settings.coverage_path, snapshots["city"].body)
except (OSError, ValueError):
    coverage_snapshot = None  # City endpoint fails explicitly; citizen guidance remains usable.

try:
    upgrade_report = (
        load_upgrades(settings.upgrades_path, coverage_snapshot.body, snapshots["city"].body)
        if coverage_snapshot
        else None
    )
except (OSError, ValueError):
    upgrade_report = None

app = FastAPI(title="Smart Recycling Access", version="0.1.0")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "web"), name="static")
community_store = CommunityStore(
    Path(os.getenv("SRA_COMMUNITY_DB", PROJECT_ROOT / "runtime/community.sqlite3"))
)
community_assets = {
    asset.id: asset for site in route_service.snapshot.sites for asset in site.assets
}
app.include_router(community_router(community_store, community_assets))
accounts = Accounts(community_store)
app.include_router(accounts_router(accounts))
vision_slots = threading.BoundedSemaphore(2)


@app.exception_handler(StarletteHTTPException)
async def localized_http_error(request: Request, error: StarletteHTTPException):
    detail = error.detail
    if isinstance(detail, str):
        detail = translate(detail)
    elif isinstance(detail, dict) and isinstance(detail.get("message"), str):
        detail = {**detail, "message": translate(detail["message"])}
    return JSONResponse({"detail": detail}, status_code=error.status_code, headers=error.headers)


@app.exception_handler(RequestValidationError)
async def private_account_validation(request: Request, error: RequestValidationError):
    if request.url.path.startswith("/api/v1/account"):
        # Standard validation errors may echo submitted password strings.
        return JSONResponse(
            {
                "detail": translate(
                    "Check your input: username 3–24 letters, digits or _; "
                    "password 15–128 characters."
                )
            },
            status_code=422,
        )
    return await request_validation_exception_handler(request, error)


@app.middleware("http")
async def community_boundary(request: Request, call_next):
    """Bound writes before parsing. Cookie identity and network quotas are separate."""
    path = request.url.path
    if not (path.startswith("/api/") or path in {"/", "/city", "/review"}):
        return await call_next(request)
    client, cookie = await run_in_threadpool(
        community_store.visitor, request.cookies.get("sra_visitor", "")
    )
    request.state.community_client = client
    request.state.quota_client = await run_in_threadpool(
        community_store.client_key, request.client.host if request.client else "unknown"
    )
    if request.method in {"POST", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(
                {"detail": translate("Cross-origin writes are not allowed")}, status_code=403
            )
        # Stream uploads have their own byte limit; JSON needs one before validation.
        if path != "/api/v1/photo-suggestions" and not path.endswith("/photo"):
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 16384:
                    return JSONResponse({"detail": translate("Request too large")}, status_code=413)
            request._body = bytes(raw)
    response = await call_next(request)
    if request.cookies.get("sra_visitor") != cookie:
        response.set_cookie(
            "sra_visitor",
            cookie,
            max_age=86400,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
    if path.startswith(
        ("/api/v1/container", "/api/v1/dumping", "/api/v1/review", "/api/v1/account")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


def reserve_provider(request: Request, service: str):
    defaults = {"vision": (100, 10, 5), "routing": (500, 100, 30)}
    daily, personal, hourly = defaults[service]
    try:
        community_store.reserve(
            service,
            request.state.quota_client,
            int(os.getenv(f"SRA_{service.upper()}_DAILY_LIMIT", daily)),
            int(os.getenv(f"SRA_{service.upper()}_CLIENT_DAILY_LIMIT", personal)),
            int(os.getenv(f"SRA_{service.upper()}_CLIENT_HOURLY_LIMIT", hourly)),
        )
    except AllowanceExceeded:
        raise HTTPException(
            429,
            detail={
                "code": "usage_limit",
                "message": "Usage limit reached. Try later; manual selection remains available.",
            },
            headers={"Retry-After": "3600"},
        ) from None


@app.middleware("http")
async def private_trip_responses(request: Request, call_next):
    """Validation failures may echo submitted coordinates; never cache those either."""
    response = await call_next(request)
    if request.url.path in {"/api/v1/trips", "/api/v1/photo-suggestions"}:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def response_language(request: Request, call_next):
    language = language_from_header(request.headers.get("accept-language", "en"))
    token = request_language.set(language)
    try:
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Vary"] = ", ".join(
                filter(None, [response.headers.get("Vary"), "Accept-Language"])
            )
        return response
    finally:
        request_language.reset(token)


class ClassificationRequest(BaseModel):
    language: Literal["en", "mk"] | None = None
    text: Annotated[str, Field(min_length=1, max_length=200)]
    manual_kind: ItemKind | None = None
    condition_confirmed: StrictBool = False


class NearestRequest(BaseModel):
    material: WasteCategory
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]


class SiteResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    materials: list[WasteCategory]

    @classmethod
    def from_domain(cls, site: Site) -> "SiteResponse":
        return cls(
            id=site.site_id,
            name=site.name,
            latitude=site.latitude,
            longitude=site.longitude,
            materials=sorted(site.materials, key=lambda item: item.value),
        )


class NearestResponse(BaseModel):
    site: SiteResponse
    distance_m: float
    synthetic: bool = True


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "web" / "index.html")


@app.get("/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "text_suggestion_model": english_suggester.model_version
        if english_suggester
        else "unavailable",
        "macedonian_suggestion_model": multilingual_suggester.model_version
        if multilingual_suggester
        else "unavailable",
        "supported_languages": "en,mk",
        "site_count": snapshots["city"].site_count,
        "asset_count": snapshots["city"].asset_count,
        "legacy_seed_site_count": len(sites),
        "nearest_data_source": "synthetic",
    }


@app.get("/api/v1/sites", response_model=SiteSnapshot)
def site_snapshot(request: Request, scope: Scope = "city") -> Response:
    """Download the real map dataset; matching ETags avoid retransmitting it."""
    snapshot = snapshots[scope]
    headers = {
        "ETag": snapshot.etag,
        "Cache-Control": "private, max-age=300, must-revalidate",
        "X-Content-Type-Options": "nosniff",
    }
    validators = request.headers.get("if-none-match", "").split(",")
    for validator in validators:
        candidate = validator.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate in {"*", snapshot.etag}:
            return Response(status_code=304, headers=headers)
    return Response(snapshot.body, media_type="application/json", headers=headers)


@app.post("/api/v1/classify", response_model=GuidanceResponse)
def classify(payload: ClassificationRequest) -> GuidanceResponse:
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="text must not be blank")
    if payload.condition_confirmed and payload.manual_kind is None:
        raise HTTPException(
            status_code=422, detail="confirmation requires an explicit item selection"
        )
    language = payload.language or request_language.get()
    token = suggestion_language.set(language)
    try:
        answer = classifier.decide(payload.text, payload.manual_kind, payload.condition_confirmed)
    finally:
        suggestion_language.reset(token)
    return guidance_translation(answer, language)


@app.post(
    "/api/v1/photo-suggestions",
    response_model=PhotoSuggestionsResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                content_type: {"schema": {"type": "string", "format": "binary"}}
                for content_type in ("image/jpeg", "image/png", "image/webp")
            },
        }
    },
)
async def photo_suggestions(
    request: Request,
    response: Response,
) -> PhotoSuggestionsResponse:
    """Return model suggestions only; the existing confirmation flow remains authoritative."""
    response.headers["Cache-Control"] = "no-store"
    if not vision_service.configured:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "vision_not_configured",
                "message": "Photo suggestions are unavailable until OPENAI_API_KEY is configured.",
            },
            headers={"Cache-Control": "no-store"},
        )
    declared_content_type = request.headers.get("content-type", "").partition(";")[0].strip()
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "image_too_large", "message": "The photo must be 8 MB or smaller."},
                headers={"Cache-Control": "no-store"},
            )
    try:
        if not vision_slots.acquire(blocking=False):
            raise HTTPException(
                429,
                detail={"code": "busy", "message": "Photo analysis is busy. Try again shortly."},
                headers={"Retry-After": "10"},
            )
        try:
            await run_in_threadpool(reserve_provider, request, "vision")
            return await vision_service.suggest(bytes(raw), declared_content_type)
        finally:
            vision_slots.release()
    except VisionError as error:
        raise HTTPException(
            status_code=error.status,
            detail={"code": error.code, "message": error.message},
            headers={"Cache-Control": "no-store"},
        ) from error


@app.post("/api/v1/nearest", response_model=NearestResponse)
def nearest(payload: NearestRequest) -> NearestResponse:
    if payload.material is WasteCategory.SPECIAL_UNSUPPORTED:
        raise HTTPException(
            status_code=422,
            detail="special_unsupported requires disposal guidance, not a collection site",
        )

    result = nearest_site(sites, payload.material, (payload.latitude, payload.longitude))
    if result is None:
        raise HTTPException(status_code=404, detail="no compatible site found")
    return NearestResponse(
        site=SiteResponse.from_domain(result.site),
        distance_m=round(result.distance_m, 1),
    )


@app.get("/api/v1/routing")
def routing_status() -> dict:
    """Report configuration without exposing provider credentials."""
    return {
        "configured": bool(settings.ors_api_key),
        "max_items": 6,
        "modes": ["walking", "driving", "transit"],
        "provider": "openrouteservice",
    }


@app.post("/api/v1/trips", response_model=TripResponse)
def plan_trip(payload: TripRequest, response: Response, request: Request) -> TripResponse:
    """Coordinate-bearing results must not be cached by browsers or intermediaries."""
    response.headers["Cache-Control"] = "no-store"
    try:
        reserve_provider(request, "routing")
        client = request.state.community_client
        statuses, version = community_store.statuses(client)
        result = route_service.plan(payload, statuses=statuses, status_version=version)
        fresh, _ = community_store.statuses(client)
        used = {asset for stop in result.stops for asset in stop.asset_ids}
        if any(statuses.get(asset) != fresh.get(asset) for asset in used):
            raise RoutingError(
                "status_changed", "A container changed while planning. Update your route.", 409
            )
        user = accounts.user(request.cookies.get("sra_session", ""))
        if user:
            for stop in result.stops:
                stop.completion_ticket = accounts.ticket(user["id"], stop.item_kinds)
        return result
    except RoutingError as error:
        raise HTTPException(
            status_code=error.status,
            detail={"code": error.code, "message": error.message},
            headers={"Cache-Control": "no-store"},
        ) from error


@app.get("/api/v1/parking")
def parking_snapshot(response: Response):
    """Redistributable ODbL-derived parking database, with provenance and no live occupancy."""
    try:
        snapshot = parking_catalog.get()
    except RoutingError as error:
        raise HTTPException(
            status_code=error.status, detail={"code": error.code, "message": error.message}
        ) from error
    response.headers["Cache-Control"] = "public, max-age=3600"
    return snapshot


@app.get("/city", include_in_schema=False)
def city_page() -> FileResponse:
    """City analysis is separate from the citizen trip flow."""
    return FileResponse(PROJECT_ROOT / "web" / "city.html")


@app.get("/api/v1/coverage", response_model=CoverageReport)
def city_coverage(request: Request) -> Response:
    """Return a prepared population-weighted network approximation, never a fallback."""
    if coverage_snapshot is None:
        raise HTTPException(
            status_code=503,
            detail="City coverage is unavailable. The prepared "
            "population/network/acceptance report is missing, invalid or stale.",
        )
    headers = {
        "ETag": coverage_snapshot.etag,
        "Cache-Control": "public, max-age=300, must-revalidate",
    }
    validators = request.headers.get("if-none-match", "").split(",")
    if any(v.strip().removeprefix("W/") in {"*", coverage_snapshot.etag} for v in validators):
        return Response(status_code=304, headers=headers)
    return Response(coverage_snapshot.body, media_type="application/json", headers=headers)


@app.get("/api/v1/upgrades")
def city_upgrades(material: Material, n: Annotated[int, Query(ge=0, le=100)] = 5) -> dict:
    """Return one prepared additive upgrade scenario without live routing calls."""
    if upgrade_report is None:
        raise HTTPException(
            503, "Upgrade recommendations unavailable; rebuild the prepared report."
        )
    if n > upgrade_report.max_upgrades:
        raise HTTPException(422, f"Prepared upgrade budget is 0..{upgrade_report.max_upgrades}.")
    plan = next(
        p for p in upgrade_report.plans if p.material == material and p.requested_upgrades == n
    )
    return payload(upgrade_report, plan)
