"""Narrow GitHub REST adapter with explicit upstream failures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class GitHubClientError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(detail)


@dataclass(frozen=True)
class RepositoryBundle:
    metadata: dict[str, Any]
    languages: dict[str, int]
    issues: list[dict[str, Any]]
    pull_requests_excluded: int


class GitHubClient:
    api_root = "https://api.github.com"

    def __init__(self, token: str | None = None, timeout_seconds: float = 12) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Repository-Insight-API",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(headers=headers, timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[dict[str, Any]]:
        try:
            response = self.client.get(f"{self.api_root}{path}", params=params)
        except httpx.TimeoutException as error:
            raise GitHubClientError(504, "GitHub request timed out. Retry shortly.") from error
        except httpx.HTTPError as error:
            raise GitHubClientError(502, "GitHub is temporarily unavailable.") from error

        if response.status_code == 404:
            raise GitHubClientError(404, "Repository not found or unavailable.")
        if response.status_code in {401, 403}:
            remaining = response.headers.get("x-ratelimit-remaining")
            detail = "GitHub authentication or rate limit prevented this scan."
            if remaining == "0":
                detail = "GitHub API rate limit reached. Add a token or retry after reset."
            raise GitHubClientError(429, detail)
        if response.status_code >= 500:
            raise GitHubClientError(502, "GitHub is temporarily unavailable. Retry shortly.")
        if response.status_code >= 400:
            raise GitHubClientError(502, "GitHub rejected the repository request.")
        return response.json()

    def fetch_bundle(self, owner: str, repo: str) -> RepositoryBundle:
        metadata = self._get(f"/repos/{owner}/{repo}")
        languages = self._get(f"/repos/{owner}/{repo}/languages")
        records = self._get(
            f"/repos/{owner}/{repo}/issues",
            {"state": "open", "per_page": 30, "sort": "updated", "direction": "desc"},
        )
        assert isinstance(metadata, dict) and isinstance(languages, dict) and isinstance(records, list)
        issues = [item for item in records if "pull_request" not in item]
        return RepositoryBundle(
            metadata=metadata,
            languages={str(key): int(value) for key, value in languages.items()},
            issues=issues,
            pull_requests_excluded=len(records) - len(issues),
        )
