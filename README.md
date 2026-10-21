#  TaskFlow Prep

### Plan Smarter. Prepare Consistently. Land Your Next Tech Role.

**TaskFlow Prep** is a full-stack technical interview preparation and job-tracking platform that brings study planning, deadline reminders, job discovery, resume matching, and application management into one workspace.

Instead of juggling multiple tools, developers can organize their preparation, stay on top of deadlines, discover relevant opportunities, and track their progress from a single application.

---

## 🎯 1. The Problem We're Solving

Preparing for a software engineering role is more than solving DSA questions. It involves balancing study schedules, development projects, revision, applications, and interview preparation.

| The challenge | How TaskFlow Prep helps |
|---|---|
| 📚 Disorganized preparation | Organizes learning into preparation tracks and actionable tasks |
| ⏰ Forgotten deadlines | Schedules persistent reminder jobs and generates in-app notifications |
| 📉 Inconsistent study habits | Provides a calendar to review completed study tasks |
| 🔎 Scattered job searches | Searches configured public Greenhouse and Lever job boards |
| 📄 Unclear skill alignment | Compares resume keywords with job-description keywords |
| 📋 Lost application details | Tracks applications and role-specific interview practice notes |

**The goal:** Turn interview preparation from a collection of scattered activities into an organized, trackable workflow.

---

## 🖥️ 2. Product Overview

TaskFlow Prep is organized around six key areas.

| Module | What it does |
|---|---|
| **Overview** | Provides a central entry point for preparation activities |
| **Preparation Tracks** | Groups study goals into manageable preparation tracks |
| **Study Tasks** | Creates tasks with deadlines, completion status, and history |
| **Job Search** | Finds listings from supported public job boards |
| **Application Tracker** | Organizes applications and interview practice notes |
| **Consistency & Notifications** | Displays study activity and in-app reminders |

### Core capabilities

- 🔐 Secure, user-specific accounts and sessions
- 📝 Persistent study tasks and preparation tracks
- ⚙️ Database-backed background job processing
- 🔔 Duplicate-safe in-app deadline notifications
- 📄 Private resume uploads and keyword-based matching
- 💼 Job application and interview practice management
- 📅 Study activity and completion calendar

---

## 🏗️ 3. System Architecture

TaskFlow Prep separates the user interface, API, database, and background processing into distinct components. This keeps user-facing requests separate from scheduled work and provides a foundation for future scaling.

```mermaid
flowchart TB
    U["👤 User"]
    FE["React + Vite<br/>Frontend"]
    API["FastAPI<br/>REST API"]
    AUTH["Authentication<br/>Sessions + CSRF"]
    DB[("PostgreSQL 17<br/>Users · Tasks · Jobs · Notifications")]
    WORKER["Python Background Worker"]
    HANDLER["Task Handler Registry"]
    RETRY["Leases · Bounded Retries<br/>Idempotency"]
    NOTIF["In-App Notifications"]
    BOARDS["Public Greenhouse / Lever APIs"]
    RESUME["Private Resume Storage<br/>PDF · DOCX · TXT"]

    U --> FE
    FE -->|"Same-origin /api proxy"| API
    API --> AUTH
    AUTH --> DB
    API -->|"Create reminder jobs"| DB
    WORKER -->|"Claim due jobs<br/>with SKIP LOCKED"| DB
    WORKER --> HANDLER
    HANDLER --> RETRY
    RETRY -->|"Commit notification"| DB
    DB --> NOTIF
    API -->|"Configured board requests"| BOARDS
    API --> RESUME

    classDef frontend fill:#252525,stroke:#ef4444,color:#ffffff
    classDef backend fill:#321b1b,stroke:#ef4444,color:#ffffff
    classDef storage fill:#202b3b,stroke:#60a5fa,color:#ffffff
    class FE frontend
    class API,AUTH,WORKER,HANDLER,RETRY backend
    class DB,NOTIF,RESUME storage
```

### How the components work together

**1. Frontend — React + Vite**

Users manage study tasks, preparation tracks, job applications, and notifications through the web interface. Requests to `/api` are proxied to the backend during local development.

**2. API — FastAPI**

The API handles authentication, validates requests, enforces user-level data access, and coordinates database operations. Creating a task with a deadline also creates its associated reminder job.

**3. Database — PostgreSQL**

PostgreSQL stores application data, including users, tasks, background jobs, and notifications. Job records are persisted rather than existing only in application memory.

**4. Background worker — Python**

A separate worker claims due jobs using database locking, dispatches them through an explicit task-handler registry, and applies bounded retries and lease-based recovery.

**5. Notification delivery — In-app**

When a reminder job succeeds, its notification is committed to the database. Deterministic notification keys help prevent duplicate records when a job is retried or replayed.

**6. External integrations and file storage**

The application queries supported public Greenhouse and Lever boards and stores uploaded resumes in private storage. Unsupported job platforms are saved as outbound search links instead of being fetched by the server.

---

## ⚙️ 4. How Reliable Reminders Work

A deadline reminder is more than a scheduled function. The system must preserve the job, handle failures, and avoid creating duplicate notifications.

```mermaid
flowchart TD
    A["User creates a task<br/>with a timezone-aware deadline"]
    B["API saves task and reminder job"]
    C["Worker claims a due job<br/>using a database lease"]
    D{"Handler succeeds?"}
    E["Commit notification<br/>with deterministic key"]
    F{"Retry attempts remaining?"}
    G["Schedule bounded retry"]
    H["Mark job failed<br/>after retry limit"]
    I["User sees in-app notification"]

    A --> B --> C --> D
    D -->|Yes| E --> I
    D -->|No| F
    F -->|Yes| G --> C
    F -->|No| H

    classDef success fill:#173b2b,stroke:#34d399,color:#ffffff
    classDef process fill:#252525,stroke:#ef4444,color:#ffffff
    classDef failure fill:#3b2525,stroke:#f87171,color:#ffffff
    class A,B,C,D,F,G process
    class E,I success
    class H failure
```

### Reliability mechanisms

- **Persistent jobs:** Reminder jobs survive API and worker restarts because they are stored in the database.
- **Concurrent job claiming:** PostgreSQL `SKIP LOCKED` supports multiple workers claiming different eligible jobs.
- **Bounded retries:** Failed jobs can be retried without retrying indefinitely.
- **Database leases:** Leases support recovery when a worker stops processing a claimed job.
- **Idempotent notifications:** Deterministic keys help prevent duplicate notification records during reprocessing.
- **Transactional persistence:** Job and notification records are stored in the same database, enabling consistent transactional operations.

These mechanisms improve reliability, but they do not eliminate every possible failure. Production guarantees depend on transaction boundaries, lease recovery behavior, and concurrency and crash-recovery testing.

---

## 🧰 5. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React, Vite | Interactive web application |
| Backend | Python, FastAPI | REST API and business logic |
| Database | PostgreSQL 17 | Persistent application and job storage |
| ORM | SQLAlchemy | Database models and queries |
| Migrations | Alembic | Version-controlled schema changes |
| Background processing | Python worker | Deadline processing and retries |
| Authentication | Argon2, session cookies | Password hashing and session management |
| Security | CSRF protection, user-scoped queries | Request protection and data isolation |
| File processing | PDF, DOCX, UTF-8 TXT | Private resume uploads and text extraction |
| Integrations | Greenhouse, Lever | Supported public job-board searches |
| Testing | pytest, frontend test suite | Automated behavior validation |
| Code quality | Ruff | Python linting |
| Infrastructure | Docker Compose | Containerized local development |
| API documentation | OpenAPI, Swagger UI | Interactive API exploration |

---

## 🔒 6. Security and Data Privacy

Security is built into the application architecture rather than treated as an afterthought.

- **Password protection:** Passwords are hashed using Argon2.
- **Session security:** Random session identifiers are issued through HttpOnly cookies, with only SHA-256 digests stored in the database.
- **CSRF protection:** Mutating authenticated requests require a CSRF token.
- **User-level isolation:** Private queries are scoped to the authenticated user.
- **Private resume storage:** Resume files are stored outside source control in a dedicated upload directory with owner-only filesystem permissions.
- **Input constraints:** Resume uploads are limited to supported formats and a maximum size of 8 MB.
- **Timezone-aware deadlines:** Task deadlines require an explicit timezone offset, and API timestamps are returned in UTC.

**Current limitation:** Authentication rate limiting, account recovery, configurable notification preferences, and external notification delivery are not yet implemented.

---

## 🧪 7. Testing and Quality Assurance

The project includes automated tests for important application workflows and development checks.

The core lifecycle test covers:

1. Registering a user.
2. Creating a task with a deadline.
3. Running its persisted reminder job.
4. Verifying the unread notification count.
5. Marking the notification as read.
6. Replaying the job and checking that no duplicate notification is inserted.

### Local validation

The latest reported local validation passed:

| Check | Result |
|---|---|
| Backend tests | 22 passed |
| Frontend tests | 5 passed |
| Ruff linting | Passed |
| Production frontend build | Passed |
| Alembic SQLite model-drift check | Passed |

**Important:** PostgreSQL was unavailable in the original implementation environment. The dedicated two-worker PostgreSQL locking test remains unverified locally and is configured to run in CI when `TEST_POSTGRES_URL` is provided.

### Run the checks

```bash
cd backend
pytest
ruff check app tests

cd ../frontend
npm test
npm run build
```

---

## 🚀 8. Getting Started

### Prerequisites

- Python 3.11+
- Node.js 22+
- PostgreSQL 17
- Git
- Docker Compose (optional)

### Step 1 — Clone the repository

```bash
git clone <your-repository-url>
cd TaskFlow-Prep
```

Replace `<your-repository-url>` with your actual GitHub repository URL.

### Step 2 — Configure environment variables

Copy `.env.example` to `.env` and configure:

```dotenv
SESSION_SECRET=replace-with-a-long-random-secret
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/taskflow
```

Use a strong, unique secret and your actual PostgreSQL credentials. Never commit `.env` or production secrets.

### Step 3 — Install backend dependencies and migrate

```bash
cd backend

python -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/alembic upgrade head
```

### Step 4 — Start the API

From the `backend` directory:

```bash
../.venv/bin/uvicorn app.main:app --reload
```

### Step 5 — Start the background worker

In a separate terminal:

```bash
cd backend
../.venv/bin/python -m app.worker
```

### Step 6 — Start the frontend

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

The Vite development server proxies `/api` requests to `http://localhost:8000`.

### Step 7 — Explore the API

Open the FastAPI interactive documentation at:

`http://localhost:8000/docs`

### Optional: Docker Compose

After configuring `.env`:

```bash
docker compose up --build
```

The containerized setup applies database migrations before API startup, and the worker waits for API readiness.

---

## 💡 9. Market Prospects

TaskFlow Prep is designed for computer science students, fresh graduates, and early-career developers who want a more organized way to prepare for technical interviews while managing active job applications.

### Why it could be useful

- **One preparation workspace:** Combines study organization and job application tracking.
- **Actionable deadlines:** Connects preparation tasks with persistent background processing.
- **Practical job discovery:** Connects configured public job boards with a personal application workflow.
- **Transparent skill matching:** Helps users identify overlapping resume and job-description keywords.
- **Room to grow:** Provides a foundation for future personalized roadmaps, company-specific practice, and preparation analytics.

Its commercial potential would need to be validated through user interviews, adoption metrics, retention, and competitive research. The initial focus is on solving a practical developer workflow problem.

---

## 🏁 10. Final Note

TaskFlow Prep is built to demonstrate practical software engineering beyond basic CRUD operations.

It brings together full-stack development, secure authentication, relational data modeling, persistent background jobs, retry handling, idempotent notifications, external integrations, file processing, and automated testing in one cohesive application.

The central engineering objective is simple: **make preparation organized for the user and dependable behind the scenes.**

The current milestone establishes the foundation. Future development will focus on stronger operational guarantees, richer preparation workflows, and a more personalized interview-preparation experience.

**Built with ❤️ and a focus on reliability, security, and maintainable engineering.**
