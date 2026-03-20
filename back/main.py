from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from back.auth import create_access_token, require_auth, verify_password
from back.bootstrap import initialize_runtime
from back.celery_app import celery_app
from back.config import settings
from back.database import Database
from back.schemas import (
    CarDetailResponse,
    CarListResponse,
    LoginRequest,
    SessionResponse,
    SortBy,
    SortOrder,
    SyncMetaResponse,
    SyncResponse,
    TokenResponse,
)


database = Database(settings.database_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_runtime(database)
    if settings.startup_sync_enabled:
        try:
            celery_app.send_task("back.tasks.ensure_sync_due")
        except Exception:
            pass
    yield
    await database.engine.dispose()


app = FastAPI(title=settings.api_title, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def healthcheck() -> dict[str, str | int | None]:
    meta = await database.get_sync_meta()
    return {"status": "ok", **meta}


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest, response: Response) -> TokenResponse:
    user = await database.get_user(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = create_access_token(payload.username)
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return TokenResponse(
        expires_in=settings.token_expire_minutes * 60,
    )


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
async def logout(response: Response) -> Response:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )
    return response


@app.get("/auth/session", response_model=SessionResponse, tags=["auth"])
async def auth_session(username: str = Depends(require_auth)) -> SessionResponse:
    return SessionResponse(authenticated=True, username=username)


@app.get("/cars", response_model=CarListResponse, tags=["cars"], dependencies=[Depends(require_auth)])
async def list_cars(
    lang: str = Query("en", pattern="^(ja|en|ru)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    query: str | None = None,
    make: str | None = None,
    body_type: str | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    drive_type: str | None = None,
    location: str | None = None,
    color: str | None = None,
    min_year: int | None = Query(None, ge=1900, le=2100),
    max_year: int | None = Query(None, ge=1900, le=2100),
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    min_mileage: int | None = Query(None, ge=0),
    max_mileage: int | None = Query(None, ge=0),
    sort_by: SortBy = "synced_at",
    sort_order: SortOrder = "desc",
) -> CarListResponse:
    payload = await database.list_cars(
        lang=lang,
        page=page,
        page_size=page_size,
        filters={
            "query": query,
            "make": make,
            "body_type": body_type,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "drive_type": drive_type,
            "location": location,
            "color": color,
            "min_year": min_year,
            "max_year": max_year,
            "min_price": min_price,
            "max_price": max_price,
            "min_mileage": min_mileage,
            "max_mileage": max_mileage,
        },
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return CarListResponse.model_validate(payload)


@app.get("/cars/{listing_id}", response_model=CarDetailResponse, tags=["cars"], dependencies=[Depends(require_auth)])
async def get_car(
    listing_id: str,
    lang: str = Query("en", pattern="^(ja|en|ru)$"),
) -> CarDetailResponse:
    item = await database.get_car(listing_id, lang)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return CarDetailResponse(item=item)


@app.post("/sync", response_model=SyncResponse, tags=["system"], dependencies=[Depends(require_auth)])
async def sync_now() -> SyncResponse:
    task = celery_app.send_task("back.tasks.sync_cars_now")
    return SyncResponse(queued=True, task_id=task.id)


@app.get("/sync/meta", response_model=SyncMetaResponse, tags=["system"], dependencies=[Depends(require_auth)])
async def sync_meta() -> SyncMetaResponse:
    return SyncMetaResponse.model_validate(await database.get_sync_meta())
