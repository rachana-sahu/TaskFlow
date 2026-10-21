# TaskFlow Prep

A dark, red-accented workspace for planning technical interview study tasks and receiving reliable deadline reminders.

> **Current milestone:** authenticated study tasks and tracks, durable deadline reminders, a job search/application tracker with private resume keyword matching and role-specific practice notes, and a task-completion consistency calendar. Job listings are live only for connected public Greenhouse and Lever boards; custom platforms are saved as outbound search links. This repository started empty; broad preparation roadmaps, analytics, preferences, and the rest of the product architecture remain future work.

## Architecture

```text
React / Vite
    │ same-origin /api proxy
    ▼
FastAPI ─── SQLAlchemy ─── PostgreSQL 17
    │                         ▲
    └── creates reminder job  │ claims due work with SKIP LOCKED
                              │
                         Task worker
                              │
                              └── creates idempotent in-app notification
```

Jobs and notification records are committed to the same database. The worker uses an explicit task-handler registry, bounded retries, a database lease, and deterministic notification keys. Session cookies are HttpOnly, mutations require a CSRF token, and each private query scopes by the authenticated user.

## Requirements

- Python 3.11+
- Node.js 22+
- PostgreSQL 17 for normal operation and concurrency validation
- Docker Compose (optional convenience)

## Local setup

1. Copy `.env.example` to `.env`, set a long random `SESSION_SECRET`, and configure `DATABASE_URL`.
2. Create and migrate the database:

   ```sh
   cd backend
   python -m venv ../.venv
   ../.venv/bin/pip install -r requirements.txt
   ../.venv/bin/alembic upgrade head
   ```

3. In separate terminals, start the API, worker, and frontend:

   ```sh
   cd backend && ../.venv/bin/uvicorn app.main:app --reload
   cd backend && ../.venv/bin/python -m app.worker
   cd frontend && npm ci && npm run dev
   ```

   The frontend proxies `/api` to `http://localhost:8000`.

Resume files are stored in the private `UPLOAD_DIR` (default `backend/storage/resumes/`) with owner-only filesystem permissions. The uploaded binary and extracted matching text are not committed to source control. The API accepts PDF, DOCX, and UTF-8 TXT resumes up to 8 MB.

For a containerized setup, set `SESSION_SECRET` in `.env` and run `docker compose up --build`. The API applies Alembic migrations before it starts; the worker waits for API readiness.

## API

Interactive OpenAPI documentation is at `/docs`.

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`, `GET /api/v1/auth/csrf`
- `GET /api/v1/tracks`, `POST /api/v1/tracks`, `PATCH /api/v1/tracks/{track_id}`
- `POST /api/v1/tracks/{track_id}/archive`, `POST /api/v1/tracks/{track_id}/restore`
- `POST /api/v1/tasks`, `GET /api/v1/tasks`, `GET /api/v1/tasks/{task_id}`
- `PATCH /api/v1/tasks/{task_id}`, `PATCH /api/v1/tasks/{task_id}/complete`
- `GET /api/v1/tasks/{task_id}/history`
- `GET /api/v1/jobs`, `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/job-sources`, `POST /api/v1/job-sources`, `DELETE /api/v1/job-sources/{id}`
- `GET /api/v1/job-search/filters`, `PUT /api/v1/job-search/filters`, `GET /api/v1/job-search`
- `POST /api/v1/resume`, `GET /api/v1/resume`, `DELETE /api/v1/resume`
- `GET /api/v1/job-applications`, `POST /api/v1/job-applications`, `PATCH|DELETE /api/v1/job-applications/{id}`
- `GET|POST /api/v1/job-applications/{id}/practice` and item-level `PATCH|DELETE`
- `GET /api/v1/calendar/activity?year=2026&month=10`
- `GET /api/v1/notifications`, `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{notification_id}/read`, `POST /api/v1/notifications/read-all`
- `GET /api/v1/health/live`, `GET /api/v1/health/ready`

Mutating requests after login require the `X-CSRF-Token` obtained from `/api/v1/auth/csrf`. Task deadlines must include a timezone offset; API timestamps are returned in UTC.

## Tests and quality

```sh
cd backend && pytest
cd backend && ruff check app tests
cd frontend && npm test
cd frontend && npm run build
```

The automated lifecycle test registers a user, creates a deadline task, runs the persisted reminder job, checks the unread count, marks the notification read, and replays the job to verify no duplicate notification is inserted. SQLite-backed tests cover the transaction flow. A two-worker PostgreSQL lock test runs when `TEST_POSTGRES_URL` is configured; PostgreSQL was unavailable in the implementation environment, so that test remains skipped locally and is configured to run in CI. The latest local validation passed 22 backend tests, 5 frontend tests, Ruff, the production frontend build, and Alembic's SQLite model-drift check.

Job-board search calls only the public Greenhouse and Lever board endpoints configured by each user. Other sources are saved as links and are never fetched by the server. Resume matching is a transparent skills-keyword overlap heuristic, not an AI assessment or hiring prediction. Interview prompts, reviews, and ratings are user-authored; AmbitionBox pages can be linked, but their content is not scraped or reproduced.

## Security notes and known limits

- Passwords are Argon2-hashed. Session identifiers are random and only their SHA-256 digests are stored.
- Set `COOKIE_SECURE=true` behind HTTPS in production and supply a strong `SESSION_SECRET`.
- Authentication rate limiting, account recovery, admin authorization, external delivery channels, and configurable notification preferences are not implemented in this milestone.
- The worker is durable and retry-aware; PostgreSQL contention and process-crash integration tests have not been run locally.
- Job search is limited to user-configured public Greenhouse/Lever company boards; it is not a global cross-platform search. Job sites without supported public feeds remain external links.
- The interface currently covers Overview, Preparation tracks, Study tasks, Job search, Consistency, Notifications, and Job runs. Broader roadmaps/topics/planners, analytics, import/export, settings, and public marketing pages remain incomplete.
