"""Cookie-based local account boundary. Reviewer authority stays entirely separate."""

import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from smart_recycling.accounts import SESSION_SECONDS, Accounts
from smart_recycling.community import AllowanceExceeded

COOKIE = "sra_session"


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, Field(min_length=3, max_length=24, pattern=r"^[a-z0-9_]+$")]
    password: Annotated[SecretStr, Field(min_length=15, max_length=128)]

    @field_validator("username", mode="before")
    @classmethod
    def normalize(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class DeleteAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: Annotated[SecretStr, Field(min_length=15, max_length=128)]


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: Annotated[str, Field(min_length=1, max_length=2048)]


def account_write(request: Request):
    # Browsers cannot send this custom header cross-origin without a CORS preflight;
    # the app grants no cross-origin access. Origin validation is also applied globally.
    # Keep the previous header working for already-open clients during the rename.
    action = any(
        request.headers.get(name) == "1" for name in ("x-najdi-frli-action", "x-goodsort-action")
    )
    if request.method != "GET" and not action:
        raise HTTPException(403, "Reload the page and try again.")


def router(accounts: Accounts) -> APIRouter:
    result = APIRouter(prefix="/api/v1/account", dependencies=[Depends(account_write)])
    slots = threading.BoundedSemaphore(2)

    def require_user(request):
        user = accounts.user(request.cookies.get(COOKIE, ""))
        if not user:
            raise HTTPException(401, "Sign in again. Your drop-off has not been saved.")
        return user

    def allowance(request, service="account", limits=(500, 60, 20)):
        try:
            accounts.store.reserve(service, request.state.quota_client, *limits)
        except AllowanceExceeded:
            raise HTTPException(
                429, "Too many attempts. Try again later.", headers={"Retry-After": "3600"}
            ) from None

    def login_response(user_id, request, response):
        token = accounts.start_session(user_id, request.cookies.get(COOKIE, ""))
        response.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_SECONDS,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
        )
        return accounts.summary(accounts.user(token))

    def credentials_action(payload, request, response, register=False):
        allowance(request)
        if register:
            allowance(request, "registration", (100, 10, 5))
        if not slots.acquire(blocking=False):
            raise HTTPException(429, "Sign-in is busy. Retry shortly.")
        try:
            operation = accounts.register if register else accounts.authenticate
            user_id = operation(payload.username, payload.password.get_secret_value())
        finally:
            slots.release()
        if not user_id:
            raise HTTPException(
                409 if register else 401,
                "Username unavailable." if register else "Username or password incorrect.",
            )
        return login_response(user_id, request, response)

    @result.post("/register", status_code=201)
    def register(payload: Credentials, request: Request, response: Response):
        return credentials_action(payload, request, response, register=True)

    @result.post("/login")
    def login(payload: Credentials, request: Request, response: Response):
        return credentials_action(payload, request, response)

    @result.get("/me")
    def me(request: Request):
        user = accounts.user(request.cookies.get(COOKIE, ""))
        return accounts.summary(user) if user else {"user": None}

    @result.post("/logout", status_code=204)
    def logout(request: Request, response: Response):
        accounts.logout(request.cookies.get(COOKIE, ""))
        response.delete_cookie(
            COOKIE, httponly=True, samesite="strict", secure=request.url.scheme == "https"
        )

    @result.delete("", status_code=204)
    def delete(payload: DeleteAccount, request: Request, response: Response):
        user = require_user(request)
        allowance(request)
        if not slots.acquire(blocking=False):
            raise HTTPException(429, "Account service is busy. Retry shortly.")
        try:
            valid = accounts.authenticate(user["username"], payload.password.get_secret_value())
        finally:
            slots.release()
        if not valid:
            raise HTTPException(401, "Password incorrect.")
        accounts.delete(user["id"])
        response.delete_cookie(
            COOKIE, httponly=True, samesite="strict", secure=request.url.scheme == "https"
        )

    @result.post("/dropoffs")
    def complete(payload: Completion, request: Request):
        user = require_user(request)
        allowance(request, "dropoff", (1000, 100, 40))
        try:
            created = accounts.complete(user["id"], payload.ticket)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        return dict(accounts.summary(user), recorded=created)

    return result
