from datetime import UTC, timedelta

import pytest
from sqlalchemy import select

from app.jobs import (
    HANDLERS,
    process_due_jobs_once,
    retry_delay,
    transition_job,
)
from app.models import BackgroundJob, JobAttempt, User, utcnow
from tests.conftest import register


def test_worker_processes_due_job_and_records_attempt(client, app, lifecycle):
    assert process_due_jobs_once(
        app.state.session_factory,
        worker_id="test-worker",
        now=lifecycle["due_at"] + timedelta(seconds=1),
    )
    job = client.get("/api/v1/jobs").json()[0]
    assert job["status"] == "succeeded"
    assert job["attempt_count"] == 1


def test_unsupported_jobs_fail_and_keep_attempt_history(client, app):
    user = register(client)
    with app.state.session_factory.begin() as db:
        job = BackgroundJob(
            user_id=user["id"],
            task_type="not_registered",
            payload={},
            idempotency_key="unsupported-job",
            scheduled_at=utcnow() - timedelta(seconds=1),
            max_attempts=1,
        )
        db.add(job)
    assert process_due_jobs_once(app.state.session_factory, worker_id="test-worker")
    job = client.get("/api/v1/jobs").json()[0]
    assert job["status"] == "failed"
    assert job["attempt_count"] == 1
    assert "Unregistered task type" in job["error_message"]


def test_retry_backoff_is_bounded():
    assert retry_delay(1) == 30
    assert retry_delay(3) == 120
    assert retry_delay(100) == 3600


def test_invalid_state_transition_is_rejected():
    job = BackgroundJob(status="succeeded")
    with pytest.raises(ValueError, match="Invalid job state transition"):
        transition_job(job, "running")


def test_handler_retry_succeeds_without_losing_attempt_history(client, app, monkeypatch):
    user = register(client)
    now = utcnow()
    calls = 0

    def fail_once(_db, _job):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")

    monkeypatch.setitem(HANDLERS, "test_retry", fail_once)
    with app.state.session_factory.begin() as db:
        job = BackgroundJob(
            user_id=user["id"],
            task_type="test_retry",
            payload={},
            idempotency_key="retry-once",
            scheduled_at=now - timedelta(seconds=1),
            max_attempts=2,
        )
        db.add(job)
    assert process_due_jobs_once(app.state.session_factory, worker_id="worker-a", now=now)
    with app.state.session_factory() as db:
        job = db.scalar(select(BackgroundJob).where(BackgroundJob.idempotency_key == "retry-once"))
        first_scheduled = job.scheduled_at
        if first_scheduled.tzinfo is None:
            first_scheduled = first_scheduled.replace(tzinfo=UTC)
        assert job.status == "retrying"
        assert now + timedelta(seconds=24) <= first_scheduled <= now + timedelta(seconds=36)
        job_id = job.id

    assert process_due_jobs_once(
        app.state.session_factory,
        worker_id="worker-b",
        now=first_scheduled + timedelta(seconds=1),
    )
    with app.state.session_factory() as db:
        attempts = list(
            db.scalars(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id)
                .order_by(JobAttempt.attempt_number)
            )
        )
        job = db.get(BackgroundJob, job_id)
        assert job.status == "succeeded"
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]


def test_expired_worker_lease_is_recovered(app, monkeypatch):
    now = utcnow()
    with app.state.session_factory.begin() as db:
        user = User(email="lease@example.com", password_hash="not-used")
        db.add(user)
        db.flush()
        job = BackgroundJob(
            user_id=user.id,
            task_type="lease_recovery",
            payload={},
            idempotency_key="lease-recovery",
            status="running",
            attempt_count=1,
            max_attempts=2,
            scheduled_at=now - timedelta(minutes=5),
            started_at=now - timedelta(minutes=5),
            lease_expires_at=now - timedelta(minutes=3),
            worker_id="dead-worker",
        )
        db.add(job)
        db.flush()
        job_id = job.id
        db.add(JobAttempt(job_id=job.id, attempt_number=1, status="running"))
    monkeypatch.setitem(HANDLERS, "lease_recovery", lambda _db, _job: None)

    assert process_due_jobs_once(app.state.session_factory, worker_id="recovery", now=now)
    with app.state.session_factory() as db:
        job = db.get(BackgroundJob, job_id)
        attempts = list(
            db.scalars(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id)
                .order_by(JobAttempt.attempt_number)
            )
        )
        assert job.status == "succeeded"
        assert job.attempt_count == 2
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]
