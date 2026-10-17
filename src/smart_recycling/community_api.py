"""Community HTTP boundary: no public identities or unreviewed photos."""

import asyncio
import io
import os
import secrets
import threading
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from smart_recycling.community import AllowanceExceeded, CommunityStore
from smart_recycling.settings import PROJECT_ROOT


class ContainerReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: Annotated[str, Field(min_length=1, max_length=160)]
    condition: Literal["available", "full", "inaccessible", "damaged"]


class DumpingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: Annotated[float, Field(ge=41.8, le=42.2, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=21.2, le=21.7, allow_inf_nan=False)]
    description: Annotated[str, Field(min_length=3, max_length=500)]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["approved", "rejected", "cleared", "duplicate"]


def peer_key(store: CommunityStore, request: Request):
    return request.state.community_client


def review_access(request: Request):
    secret = os.getenv("SRA_REVIEW_TOKEN", "")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
    if len(secret) < 32 or not secrets.compare_digest(secret.encode(), supplied.encode()):
        raise HTTPException(401, "Reviewer access required")


def router(store: CommunityStore, assets: dict) -> APIRouter:
    result = APIRouter()
    photo_slots = threading.BoundedSemaphore(2)

    def reserve(request):
        client = peer_key(store, request)
        try:
            store.reserve("report", request.state.quota_client, 500, 30, 10)
        except AllowanceExceeded:
            raise HTTPException(
                429, "Report limit reached. Try again later.", headers={"Retry-After": "3600"}
            ) from None
        return client

    @result.get("/api/v1/container-statuses")
    def statuses(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        values, rechecks, version = store.status_snapshot(peer_key(store, request))
        return {"statuses": values, "rechecks": rechecks, "version": version}

    @result.post("/api/v1/container-reports", status_code=201)
    def container(payload: ContainerReport, request: Request):
        if payload.asset_id not in assets:
            raise HTTPException(404, "Unknown container")
        return store.submit("container", reserve(request), **payload.model_dump())

    @result.post("/api/v1/dumping-reports", status_code=201)
    def dumping(payload: DumpingReport, request: Request):
        if len(payload.description.strip()) < 3:
            raise HTTPException(422, "Add a short description")
        return store.submit("dumping", reserve(request), **payload.model_dump())

    @result.get("/api/v1/dumping-reports")
    def dumping_list(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"reports": store.reports()}

    @result.post("/api/v1/dumping-reports/{identifier}/photo", status_code=204)
    async def upload(identifier: str, request: Request):
        if not photo_slots.acquire(blocking=False):
            raise HTTPException(429, "Photo uploads are busy. Retry shortly.")
        try:
            return await asyncio.wait_for(upload_photo(identifier, request), timeout=20)
        except TimeoutError:
            raise HTTPException(408, "Photo upload timed out. Retry.") from None
        finally:
            photo_slots.release()

    async def upload_photo(identifier: str, request: Request):
        client = await run_in_threadpool(reserve, request)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 5 * 1024 * 1024:
                raise HTTPException(413, "Photo must be 5 MB or smaller")
        photo = await run_in_threadpool(sanitize_photo, bytes(raw))
        try:
            if not await run_in_threadpool(store.attach_photo, identifier, client, photo):
                raise HTTPException(404, "Pending report not found")
        except AllowanceExceeded:
            raise HTTPException(507, "Photo storage is full. Your text report is saved.") from None
        return Response(status_code=204)

    @result.get("/review", include_in_schema=False)
    def review_page():
        return FileResponse(
            PROJECT_ROOT / "web" / "review.html", headers={"Cache-Control": "no-store"}
        )

    @result.get("/api/v1/review/reports", dependencies=[Depends(review_access)])
    def review_reports(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"reports": store.reports(review=True)}

    @result.patch("/api/v1/review/reports/{identifier}", dependencies=[Depends(review_access)])
    def update(identifier: str, payload: Review):
        if not store.moderate(identifier, payload.state):
            raise HTTPException(404, "Report not found or invalid action")
        return {"state": payload.state}

    @result.get("/api/v1/review/reports/{identifier}/photo", dependencies=[Depends(review_access)])
    def review_photo(identifier: str):
        photo = store.photo(identifier)
        if not photo:
            raise HTTPException(404, "Photo not found")
        return Response(
            photo,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    return result


def sanitize_photo(raw: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if (
                source.format not in {"JPEG", "PNG", "WEBP"}
                or source.width * source.height > 16_000_000
            ):
                raise ValueError
            picture = ImageOps.exif_transpose(source).convert("RGB")
            picture.thumbnail((1280, 1280))
            clean = Image.new("RGB", picture.size)
            clean.paste(picture)
            output = io.BytesIO()
            clean.save(output, format="JPEG", quality=80)
            return output.getvalue()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(422, "Use a JPEG, PNG or WebP photo up to 16 megapixels") from None
