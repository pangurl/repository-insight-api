"""FastAPI entry point for Repository Insight API."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Database
from app.github_client import GitHubClient, GitHubClientError
from app.schemas import HealthResponse, InsightResponse, RepositoryResponse
from app.services import RepositoryService


def create_app(settings: Settings | None = None, github_client: GitHubClient | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    database = Database(settings.database_url)
    client = github_client or GitHubClient(settings.github_token)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.create_schema()
        yield
        client.close()

    app = FastAPI(
        title="Repository Insight API",
        version="0.1.0",
        description="Source-linked repository metadata, issue signals, and scoped learning tasks.",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.github_client = client
    app.state.settings = settings

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        return response

    @app.exception_handler(GitHubClientError)
    async def github_error(_: Request, error: GitHubClientError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": str(error)})

    def session_dependency(request: Request):
        yield from request.app.state.database.sessions()

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/repositories/{owner}/{repo}", response_model=RepositoryResponse, tags=["repositories"])
    def repository(owner: str, repo: str, session: Session = Depends(session_dependency)) -> RepositoryResponse:
        cached = RepositoryService(session, settings.cache_ttl_minutes).cached_insight(f"{owner}/{repo}")
        if cached is None:
            raise HTTPException(status_code=404, detail="Repository has not been analyzed yet. Call POST /analyze first.")
        return cached.repository

    @app.get("/repositories/{owner}/{repo}/insights", response_model=InsightResponse, tags=["repositories"])
    def insights(owner: str, repo: str, session: Session = Depends(session_dependency)) -> InsightResponse:
        cached = RepositoryService(session, settings.cache_ttl_minutes).cached_insight(f"{owner}/{repo}")
        if cached is None:
            raise HTTPException(status_code=404, detail="Repository has not been analyzed yet. Call POST /analyze first.")
        return cached

    @app.post("/repositories/{owner}/{repo}/analyze", response_model=InsightResponse, tags=["repositories"])
    def analyze(owner: str, repo: str, refresh: bool = False, session: Session = Depends(session_dependency)) -> InsightResponse:
        service = RepositoryService(session, settings.cache_ttl_minutes)
        cached = service.cached_insight(f"{owner}/{repo}")
        if cached and not refresh:
            fetched_at = cached.fetched_at
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if fetched_at >= datetime.now(timezone.utc) - service.cache_ttl:
                return cached
        bundle = client.fetch_bundle(owner, repo)
        return service.analyze(owner, repo, bundle, refresh=refresh)

    return app


app = create_app()
