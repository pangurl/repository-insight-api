"""Persistence models for cached repository analysis."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    html_url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255))
    stargazers_count: Mapped[int] = mapped_column(Integer, default=0)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    primary_language: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    snapshots: Mapped[list["AnalysisSnapshot"]] = relationship(back_populates="repository", cascade="all, delete-orphan")


class AnalysisSnapshot(Base):
    __tablename__ = "analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    activity_score: Mapped[int] = mapped_column(Integer, default=0)
    difficulty_score: Mapped[int] = mapped_column(Integer, default=0)
    difficulty_signals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    learning_tasks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    issue_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    languages: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    repository: Mapped[Repository] = relationship(back_populates="snapshots")
