# Architecture notes

## Current vertical slice

- React + TypeScript + Vite provide the same-origin client; Vite proxies `/api` to FastAPI.
- FastAPI owns identity, task ownership, scheduling, and persisted notification read state. The browser is not an authorization boundary.
- SQLAlchemy 2.x models the user, revocable session, task, reminder job, per-attempt history, notification, notification preferences, job sources/filters, private resume metadata, applications, and practice reviews.
- A separately runnable worker polls PostgreSQL and uses `SELECT ... FOR UPDATE SKIP LOCKED` to claim due jobs. Its registered handler checks current task status before it creates a notification.
- A unique deterministic key on notifications makes processing replays idempotent. Notification and job success updates are committed within the same transaction.
- SQLite is available for focused local tests; PostgreSQL remains the production and concurrency-test database.

## Security decisions

- Password hashing uses Argon2.
- Session cookies are HttpOnly, SameSite=Lax, have a finite lifetime, and are revocable in the database. The CSRF token is stored server-side and compared with both a readable cookie and request header for mutations.
- Every task, job, and notification query filters by authenticated `user_id`; missing and non-owned identifiers return the same 404 response.
- Career sources, filters, resume records, and applications are account-scoped. Practice items are reached through an owner-checked application. Resume binaries use random storage keys, an owner-only upload directory, and owner-only file permissions; the public API returns metadata, never the binary or extracted text.
- Job discovery fetches only fixed Greenhouse/Lever public-board endpoints. User-defined custom platform URLs are outbound links and are never server-fetched, avoiding arbitrary URL/SSRF behavior.
- Resume matching compares a bounded set of role keywords with extracted resume text and reports matched/missing terms. It is deterministic and should not be treated as an employment prediction.
- Interview prompts and ratings are original user input. AmbitionBox is link-only; the service does not scrape or reproduce third-party question/review text.
- Consistency activity is derived from persisted task status history and grouped by the account timezone.
- Database credentials and session settings are environment-configured.

## Deferred decisions

The current milestone does not provide account recovery/rate limiting, email or push delivery, scheduled daily summaries, rich preference management, or administrative operations. The schema reserves preferences, but only the task-deadline in-app reminder is connected end-to-end. Career search is not a universal aggregator; platforms without supported public APIs are links only.
