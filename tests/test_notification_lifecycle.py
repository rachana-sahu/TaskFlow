from datetime import timedelta

from sqlalchemy import select

from app.jobs import process_due_jobs_once
from app.models import BackgroundJob, utcnow
from tests.conftest import csrf_headers, register


def test_reminder_persists_once_across_retry_and_can_be_read(client, app, lifecycle):
    task_id = lifecycle["task"]["id"]
    jobs = client.get("/api/v1/jobs")
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1
    job_id = jobs.json()[0]["id"]
    scheduled_at = lifecycle["due_at"] + timedelta(seconds=1)

    assert process_due_jobs_once(app.state.session_factory, worker_id="worker-a", now=scheduled_at)
    notifications = client.get("/api/v1/notifications")
    assert notifications.status_code == 200
    assert len(notifications.json()) == 1
    notification = notifications.json()[0]
    assert notification["related_resource_id"] == task_id
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 1}
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "succeeded"

    with app.state.session_factory.begin() as db:
        job = db.get(BackgroundJob, job_id)
        job.status = "retrying"
        job.scheduled_at = utcnow() - timedelta(seconds=1)
    assert process_due_jobs_once(app.state.session_factory, worker_id="worker-b")
    assert len(client.get("/api/v1/notifications").json()) == 1

    mark_read = client.post(
        f"/api/v1/notifications/{notification['id']}/read",
        headers=lifecycle["headers"],
    )
    assert mark_read.status_code == 200
    assert mark_read.json()["read_at"] is not None
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 0}


def test_completed_task_does_not_create_reminder(client, app, lifecycle):
    task_id = lifecycle["task"]["id"]
    assert (
        client.patch(f"/api/v1/tasks/{task_id}/complete", headers=lifecycle["headers"]).status_code
        == 200
    )
    assert process_due_jobs_once(
        app.state.session_factory,
        worker_id="worker-a",
        now=lifecycle["due_at"] + timedelta(seconds=1),
    )
    assert client.get("/api/v1/notifications").json() == []


def test_in_progress_task_still_receives_deadline_reminder(client, app, lifecycle):
    assert (
        client.patch(
            f"/api/v1/tasks/{lifecycle['task']['id']}",
            json={"status": "in_progress"},
            headers=lifecycle["headers"],
        ).status_code
        == 200
    )
    assert process_due_jobs_once(
        app.state.session_factory,
        worker_id="worker-a",
        now=lifecycle["due_at"] + timedelta(seconds=1),
    )
    assert len(client.get("/api/v1/notifications").json()) == 1


def test_user_cannot_read_another_users_task_or_job(client, app, lifecycle):
    first_task_id = lifecycle["task"]["id"]
    first_job_id = client.get("/api/v1/jobs").json()[0]["id"]
    assert process_due_jobs_once(
        app.state.session_factory,
        worker_id="worker-a",
        now=lifecycle["due_at"] + timedelta(seconds=1),
    )
    first_notification_id = client.get("/api/v1/notifications").json()[0]["id"]
    assert (
        client.post(
            "/api/v1/auth/logout",
            headers=lifecycle["headers"],
        ).status_code
        == 204
    )
    register(client, "other@example.com")
    assert client.get(f"/api/v1/tasks/{first_task_id}").status_code == 404
    assert client.get(f"/api/v1/jobs/{first_job_id}").status_code == 404
    assert client.get("/api/v1/notifications").json() == []
    assert (
        client.post(
            f"/api/v1/notifications/{first_notification_id}/read",
            headers=csrf_headers(client),
        ).status_code
        == 404
    )
    assert client.get("/api/v1/notifications/unread-count").json() == {"count": 0}


def test_mutation_requires_csrf(client, lifecycle):
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "No CSRF",
            "due_at": lifecycle["due_at"].isoformat(),
            "remind_before_minutes": 0,
        },
    )
    assert response.status_code == 403


def test_reminder_job_has_deterministic_user_scoped_key(client, app, lifecycle):
    with app.state.session_factory() as db:
        jobs = list(db.scalars(select(BackgroundJob)))
    assert len(jobs) == 1
    assert jobs[0].idempotency_key.startswith("task-deadline:")
    assert jobs[0].user_id == lifecycle["user"]["id"]
