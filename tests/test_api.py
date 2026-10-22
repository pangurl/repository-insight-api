from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import Settings
from app.github_client import RepositoryBundle
from app.main import create_app


class FakeGitHubClient:
    def __init__(self):
        self.calls = 0

    def close(self):
        pass

    def fetch_bundle(self, owner, repo):
        self.calls += 1
        return RepositoryBundle(
            metadata={"html_url": f"https://github.com/{owner}/{repo}", "description": "Test repository", "default_branch": "main", "stargazers_count": 10, "forks_count": 2, "open_issues_count": 3, "language": "Python", "pushed_at": datetime.now(timezone.utc).isoformat()},
            languages={"Python": 1000, "Dockerfile": 30},
            issues=[{"comments": 4, "labels": [{"name": "bug"}]}],
            pull_requests_excluded=1,
        )


def client(tmp_path):
    fake = FakeGitHubClient()
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", cache_ttl_minutes=60), fake)
    return TestClient(app), fake


def test_health(tmp_path):
    api, _ = client(tmp_path)
    with api:
        response = api.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_persists_and_caches(tmp_path):
    api, fake = client(tmp_path)
    with api:
        created = api.post("/repositories/acme/widget/analyze")
        cached = api.get("/repositories/acme/widget/insights")
        repeated = api.post("/repositories/acme/widget/analyze")
    assert created.status_code == 200
    assert created.json()["cache_hit"] is False
    assert cached.json()["repository"]["full_name"] == "acme/widget"
    assert repeated.json()["cache_hit"] is True
    assert fake.calls == 1


def test_unknown_repository_requires_analysis(tmp_path):
    api, _ = client(tmp_path)
    with api:
        response = api.get("/repositories/acme/missing")
    assert response.status_code == 404
