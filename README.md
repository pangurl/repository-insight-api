# Repository Insight API

FastAPI service for turning public GitHub repository data into cached, source-derived engineering signals. It provides repository metadata, language distribution, recent Issue summaries, transparent difficulty signals, and bounded learning tasks.

## Why it exists

Developer tools often need GitHub data but should not pass raw upstream responses directly to a UI. This service creates a stable API contract, persists analysis snapshots, avoids repeated upstream calls with a TTL cache, and exposes explicit failures for unavailable repositories, timeouts, and rate limits.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health check. |
| `POST /repositories/{owner}/{repo}/analyze` | Fetch, analyze, and persist a repository snapshot. |
| `GET /repositories/{owner}/{repo}` | Read cached repository metadata. |
| `GET /repositories/{owner}/{repo}/insights` | Read the latest cached analysis. |

Interactive OpenAPI documentation is available at `/docs`.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:DATABASE_URL="sqlite:///./repository_insight.db"
uvicorn app.main:app --reload
```

Then call `POST http://localhost:8000/repositories/fastapi/fastapi/analyze` and inspect `GET /repositories/fastapi/fastapi/insights`.

## Containerized runtime

```bash
docker compose up --build
```

Compose starts FastAPI with PostgreSQL. Add `GITHUB_TOKEN` to your environment for higher GitHub API limits; it is never persisted.

## Engineering choices

- **FastAPI + Pydantic:** typed API contracts and generated OpenAPI documentation.
- **SQLAlchemy:** SQLite for fast local tests and PostgreSQL for the containerized service path.
- **Explicit GitHub adapter:** bounded timeouts, PR filtering, rate-limit translation, and no hidden scraping.
- **Snapshot cache:** avoids repeated GitHub calls and keeps a reproducible record of analysis outputs.
- **Docker + CI:** Docker Compose supports service-level integration; GitHub Actions runs pytest on every push and pull request.

Difficulty signals are transparent engineering heuristics, not claims about contributor skill or commercial potential.
