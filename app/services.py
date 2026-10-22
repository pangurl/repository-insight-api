"""Repository analysis, caching, and persistence rules."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.github_client import RepositoryBundle
from app.models import AnalysisSnapshot, Repository
from app.schemas import InsightResponse, RepositoryResponse


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _issues_summary(issues: list[dict], excluded: int) -> dict:
    comments = [int(item.get("comments", 0)) for item in issues]
    labels = [label.get("name", "") for item in issues for label in item.get("labels", [])]
    top_labels = sorted({label for label in labels if label})[:5]
    return {
        "open_issues_sampled": len(issues),
        "pull_requests_excluded": excluded,
        "median_comments": int(median(comments)) if comments else 0,
        "top_labels": top_labels,
    }


def _signals(metadata: dict, languages: dict[str, int], summary: dict) -> tuple[int, int, list[dict], list[dict]]:
    now = datetime.now(timezone.utc)
    pushed_at = _timestamp(metadata.get("pushed_at"))
    push_age = (now - pushed_at).days if pushed_at else 365
    activity = max(10, min(100, 100 - push_age * 2 + min(summary["open_issues_sampled"], 15)))
    signals: list[dict] = []
    if len(languages) >= 4:
        signals.append({"label": "Polyglot codebase", "score": 70, "reason": f"The repository uses {len(languages)} languages, increasing setup and integration surface."})
    if summary["open_issues_sampled"] >= 15:
        signals.append({"label": "Active issue queue", "score": 65, "reason": "The latest 30 records contain a substantial open-Issue sample."})
    if summary["median_comments"] >= 3:
        signals.append({"label": "Discussion-heavy issues", "score": 60, "reason": "Recent issues have repeated discussion, suggesting investigation before implementation."})
    if push_age <= 14:
        signals.append({"label": "Recently maintained", "score": 45, "reason": f"The latest push was {push_age} days ago; changes may move quickly."})
    if not signals:
        signals.append({"label": "Limited sampled complexity", "score": 30, "reason": "The sampled repository signals do not indicate a high-complexity first contribution."})
    difficulty = min(100, max(signal["score"] for signal in signals) + max(0, len(signals) - 1) * 5)
    tasks = [
        {"title": "Map one repository workflow", "scope": "Read the README and trace one public API or CLI path end-to-end.", "rationale": "Creates a bounded baseline before choosing a contribution."},
        {"title": "Reproduce one sampled Issue", "scope": "Select a recent non-PR Issue and write a minimal reproduction or diagnostic note.", "rationale": "Tests local setup and turns issue evidence into an engineering artifact."},
    ]
    if languages:
        primary = max(languages, key=languages.get)
        tasks.append({"title": f"Build a {primary} inspection script", "scope": "Extract one repository metric or validate one configuration assumption.", "rationale": "Practises the dominant language with a bounded deliverable."})
    return activity, difficulty, signals, tasks


def _repository_response(repository: Repository) -> RepositoryResponse:
    return RepositoryResponse.model_validate(repository)


def to_response(repository: Repository, snapshot: AnalysisSnapshot, cache_hit: bool) -> InsightResponse:
    return InsightResponse(
        repository=_repository_response(repository),
        languages=snapshot.languages,
        issue_summary=snapshot.issue_summary,
        activity_score=snapshot.activity_score,
        difficulty_score=snapshot.difficulty_score,
        difficulty_signals=snapshot.difficulty_signals,
        learning_tasks=snapshot.learning_tasks,
        fetched_at=snapshot.fetched_at,
        cache_hit=cache_hit,
    )


class RepositoryService:
    def __init__(self, session: Session, cache_ttl_minutes: int) -> None:
        self.session = session
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)

    def cached_insight(self, full_name: str) -> InsightResponse | None:
        statement = select(Repository).where(Repository.full_name == full_name).options(selectinload(Repository.snapshots))
        repository = self.session.scalar(statement)
        if not repository or not repository.snapshots:
            return None
        snapshot = max(repository.snapshots, key=lambda item: item.fetched_at)
        return to_response(repository, snapshot, cache_hit=True)

    def analyze(self, owner: str, repo: str, bundle: RepositoryBundle, refresh: bool = False) -> InsightResponse:
        full_name = f"{owner}/{repo}"
        cached = self.cached_insight(full_name)
        if cached and not refresh and cached.fetched_at >= datetime.now(timezone.utc) - self.cache_ttl:
            return cached

        data = bundle.metadata
        repository = self.session.scalar(select(Repository).where(Repository.full_name == full_name))
        if repository is None:
            repository = Repository(full_name=full_name, owner=owner, name=repo, html_url=data["html_url"], description=data.get("description"), default_branch=data.get("default_branch", "main"))
            self.session.add(repository)
        repository.html_url = data["html_url"]
        repository.description = data.get("description")
        repository.default_branch = data.get("default_branch", "main")
        repository.stargazers_count = int(data.get("stargazers_count", 0))
        repository.forks_count = int(data.get("forks_count", 0))
        repository.open_issues_count = int(data.get("open_issues_count", 0))
        repository.primary_language = data.get("language")
        repository.pushed_at = _timestamp(data.get("pushed_at"))
        repository.last_fetched_at = datetime.now(timezone.utc)

        summary = _issues_summary(bundle.issues, bundle.pull_requests_excluded)
        activity, difficulty, signals, tasks = _signals(data, bundle.languages, summary)
        snapshot = AnalysisSnapshot(issue_count=len(bundle.issues), activity_score=activity, difficulty_score=difficulty, difficulty_signals=signals, learning_tasks=tasks, issue_summary=summary, languages=bundle.languages)
        repository.snapshots.append(snapshot)
        self.session.commit()
        self.session.refresh(repository)
        self.session.refresh(snapshot)
        return to_response(repository, snapshot, cache_hit=False)
