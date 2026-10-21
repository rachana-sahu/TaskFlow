import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app import opportunities
from app.models import JobApplication, ResumeDocument
from tests.conftest import csrf_headers, register


def _source(client, provider="greenhouse", **overrides):
    body = {
        "provider": provider,
        "company_name": "Example Labs",
        "board_slug": "example-labs",
        "search_url": None,
        **overrides,
    }
    response = client.post("/api/v1/job-sources", json=body, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_resume_job_matching_filters_and_application_practice(client, app, monkeypatch):
    register(client)
    app.state.upload_dir = Path(app.state.engine.url.database + "-private-resumes")
    headers = csrf_headers(client)
    source = _source(client)

    upload = client.post(
        "/api/v1/resume",
        files={"file": ("resume.txt", b"Python SQL and Docker engineer", "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    with app.state.session_factory() as db:
        resume = db.query(ResumeDocument).one()
        assert resume.filename == "resume.txt"
        resume_path = app.state.upload_dir / resume.storage_key
        assert resume_path.read_bytes().startswith(b"Python")
        assert stat.S_IMODE(resume_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(app.state.upload_dir.stat().st_mode) == 0o700

    monkeypatch.setattr(
        opportunities,
        "_greenhouse_jobs",
        lambda board: [
            {
                "provider": "greenhouse",
                "company_name": board.company_name,
                "title": "Senior Python Engineer",
                "location": "Remote",
                "job_url": "https://jobs.example.test/python",
                "description": "Build services with Python, SQL, Docker, and Java.",
            }
        ],
    )
    filters = client.put(
        "/api/v1/job-search/filters",
        json={
            "keywords": "Senior, Python",
            "location": "Remote",
            "work_mode": "remote",
            "minimum_match": 60,
        },
        headers=headers,
    )
    assert filters.status_code == 200
    results = client.get("/api/v1/job-search")
    assert results.status_code == 200, results.text
    payload = results.json()
    assert payload["resume_uploaded"] is True
    assert payload["listing_count"] == 1
    assert payload["results"][0]["match_score"] == 75
    assert payload["results"][0]["matched_keywords"] == ["docker", "python", "sql"]
    assert payload["results"][0]["missing_keywords"] == ["java"]

    saved = client.post(
        "/api/v1/job-applications",
        json={
            key: payload["results"][0][key]
            for key in (
                "provider",
                "title",
                "company_name",
                "location",
                "job_url",
                "description",
            )
        },
        headers=headers,
    )
    assert saved.status_code == 201, saved.text
    application_id = saved.json()["id"]
    assert saved.json()["match_score"] == 75
    updated = client.patch(
        f"/api/v1/job-applications/{application_id}",
        json={
            "status": "applied",
            "company_rating": 4,
            "company_notes": "Friendly interview process",
            "company_review_url": "https://www.ambitionbox.com/reviews/example",
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "applied"
    assert updated.json()["company_rating"] == 4

    practice = client.post(
        f"/api/v1/job-applications/{application_id}/practice",
        json={
            "year": 2024,
            "category": "Backend",
            "prompt": "Explain how you would design a resilient API.",
            "review_notes": "Practice a clear trade-off discussion.",
            "source_url": "https://www.ambitionbox.com/interviews/example",
        },
        headers=headers,
    )
    assert practice.status_code == 201, practice.text
    practice_id = practice.json()["id"]
    assert practice.json()["year"] == 2024
    assert (
        client.patch(
            f"/api/v1/job-applications/{application_id}/practice/{practice_id}",
            json={"rating": 5, "review_notes": "Good second attempt."},
            headers=headers,
        ).json()["rating"]
        == 5
    )
    assert len(client.get(f"/api/v1/job-applications/{application_id}/practice").json()) == 1
    assert (
        client.patch(
            f"/api/v1/job-applications/{application_id}",
            json={"company_review_url": "https://example.test/reviews"},
            headers=headers,
        ).status_code
        == 422
    )
    assert client.get("/api/v1/job-sources").json()[0]["id"] == source["id"]
    assert client.delete("/api/v1/resume", headers=headers).status_code == 204
    assert not resume_path.exists()
    assert client.get("/api/v1/job-applications").json()[0]["match_score"] is None
    register(client, "another@example.com")
    assert client.get("/api/v1/resume").status_code == 404


def test_job_sources_and_applications_are_private_and_validated(client):
    register(client)
    headers = csrf_headers(client)
    assert (
        client.post(
            "/api/v1/job-sources",
            json={
                "provider": "greenhouse",
                "company_name": "No board ID",
                "board_slug": None,
            },
            headers=headers,
        ).status_code
        == 422
    )
    source = _source(
        client,
        "link_only",
        board_slug=None,
        search_url="https://www.linkedin.com/jobs/search/?keywords=python",
    )
    assert client.get("/api/v1/job-search").json()["listing_count"] == 0

    owner_application = client.post(
        "/api/v1/job-applications",
        json={
            "provider": "link_only",
            "title": "Backend Engineer",
            "company_name": "Example",
            "job_url": "https://jobs.example.test/backend",
        },
        headers=headers,
    )
    assert owner_application.status_code == 201
    register(client, "second@example.com")
    assert client.get("/api/v1/job-applications").json() == []
    assert (
        client.delete(
            f"/api/v1/job-sources/{source['id']}", headers=csrf_headers(client)
        ).status_code
        == 404
    )
    assert client.get("/api/v1/job-applications").json() == []


def test_calendar_counts_completed_days_and_practice_is_owner_scoped(client, app):
    register(client)
    headers = csrf_headers(client)
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "Complete a practice task",
            "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
        headers=headers,
    ).json()
    completed = client.patch(
        f"/api/v1/tasks/{task['id']}/complete",
        headers=headers,
    )
    assert completed.status_code == 200
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    activity = client.get(f"/api/v1/calendar/activity?year={today.year}&month={today.month}")
    assert activity.status_code == 200, activity.text
    assert activity.json()["completed_tasks"] == 1
    assert sum(activity.json()["active_days"].values()) == 1

    application = client.post(
        "/api/v1/job-applications",
        json={
            "provider": "link_only",
            "title": "Backend Engineer",
            "company_name": "Example",
            "job_url": "https://jobs.example.test/private",
        },
        headers=headers,
    ).json()
    register(client, "other@example.com")
    assert client.get(f"/api/v1/job-applications/{application['id']}/practice").status_code == 404
    with app.state.session_factory() as db:
        assert db.query(JobApplication).count() == 1
