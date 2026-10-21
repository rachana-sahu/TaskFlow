# API contract (v1)

All endpoints use `/api/v1`. Authenticated routes use the `taskflow_session` cookie. Mutations require `X-CSRF-Token`, matching the `taskflow_csrf` cookie and the active server-side session.

## Create a study task

```http
POST /api/v1/tasks
Content-Type: application/json
X-CSRF-Token: <token>

{"title":"Review graph traversal","due_at":"2026-10-15T09:30:00+05:30","remind_before_minutes":60}
```

Returns `201` with `{ "id", "title", "due_at", "status" }` and atomically schedules one `task_deadline_reminder` job. The deadline must be timezone-aware; it is normalized to UTC. Duplicate task creation is not implicitly deduplicated.
Optional task fields include `track_id`, `priority` (`low`, `normal`, or `high`), `estimated_duration_minutes` (1–1440), and `notes`.

## Preparation tracks and task history

- `GET /api/v1/tracks` returns active tracks; `?include_archived=true` includes archived tracks.
- `POST /api/v1/tracks` creates a user-owned custom track. Registration seeds ten editable starter tracks.
- `PATCH /api/v1/tracks/{id}` updates name, description, or ordering.
- `POST /api/v1/tracks/{id}/archive` / `restore` soft-archive or restore a track. Existing tasks/history remain intact.
- `PATCH /api/v1/tasks/{id}` updates supported task metadata/status and records changes.
- `GET /api/v1/tasks/{id}/history` returns only history for a task owned by the current user.

## Read notification state

- `GET /api/v1/notifications` returns up to 100 newest notifications owned by the session user.
- `GET /api/v1/notifications/unread-count` returns `{ "count": 0 }` when none are unread.
- `POST /api/v1/notifications/{id}/read` sets `read_at` once and returns the persisted record.
- `POST /api/v1/notifications/read-all` marks all of the current user's unread records read.

## Job state

`GET /api/v1/jobs` and `GET /api/v1/jobs/{id}` expose only the authenticated user's job records. Jobs move through `queued → running → succeeded`, or `queued → running → retrying → running → succeeded|failed`. Automatic retries use capped exponential delay. Manual retry is not yet exposed.

## Career search and applications

- Connect a public board with `POST /api/v1/job-sources` using `provider` (`greenhouse` or `lever`), company name, and its public board ID. `link_only` sources require a user-provided `search_url`; those links are never fetched by the API.
- `PUT /api/v1/job-search/filters` persists comma-separated keywords, location, work mode, and minimum resume keyword match for the signed-in user. `GET /api/v1/job-search` reads connected public boards and returns matching listings, source errors, and keyword comparisons.
- `POST /api/v1/resume` accepts a private PDF, DOCX, or UTF-8 TXT upload (maximum 8 MB). `GET /api/v1/resume` returns metadata only; `DELETE /api/v1/resume` removes the stored file and extracted text. The match score is a deterministic keyword overlap, not an AI or hiring prediction.
- `POST /api/v1/job-applications` saves a listing. Application status, personal company notes, a 1–5 rating, and an optional AmbitionBox review URL are persisted per user.
- `/api/v1/job-applications/{id}/practice` stores user-authored prompts, year/topic, personal review notes, ratings, and optional AmbitionBox links. The service does not scrape or reproduce AmbitionBox content.

## Consistency calendar

`GET /api/v1/calendar/activity?year=2026&month=10` aggregates completion history for tasks owned by the signed-in user, interpreted in that user's configured timezone. A calendar day is active when at least one task was marked complete that local day.

## Health checks

- `GET /api/v1/health/live` reports process liveness.
- `GET /api/v1/health/ready` executes a database query and reports readiness only when it succeeds.
