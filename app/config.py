"""Environment-backed application settings."""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./repository_insight.db"
    github_token: str | None = None
    cache_ttl_minutes: int = 60

    @classmethod
    def from_environment(cls) -> "Settings":
        ttl = os.getenv("CACHE_TTL_MINUTES", "60")
        try:
            cache_ttl_minutes = max(1, int(ttl))
        except ValueError:
            cache_ttl_minutes = 60
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            github_token=os.getenv("GITHUB_TOKEN") or None,
            cache_ttl_minutes=cache_ttl_minutes,
        )

