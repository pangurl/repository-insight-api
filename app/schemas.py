"""Public request and response contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "repository-insight-api"


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    html_url: str
    description: str | None
    default_branch: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    primary_language: str | None
    pushed_at: datetime | None
    last_fetched_at: datetime


class DifficultySignal(BaseModel):
    label: str
    score: int = Field(ge=0, le=100)
    reason: str


class LearningTask(BaseModel):
    title: str
    scope: str
    rationale: str


class IssueSummary(BaseModel):
    open_issues_sampled: int
    pull_requests_excluded: int
    median_comments: int
    top_labels: list[str]


class InsightResponse(BaseModel):
    repository: RepositoryResponse
    languages: dict[str, int]
    issue_summary: IssueSummary
    activity_score: int = Field(ge=0, le=100)
    difficulty_score: int = Field(ge=0, le=100)
    difficulty_signals: list[DifficultySignal]
    learning_tasks: list[LearningTask]
    fetched_at: datetime
    cache_hit: bool

