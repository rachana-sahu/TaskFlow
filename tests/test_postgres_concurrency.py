import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.jobs import process_due_jobs_once
from app.models import BackgroundJob, Notification, Task, User, utcnow

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set TEST_POSTGRES_URL to run PostgreSQL locking integration tests",
)


def test_concurrent_workers_claim_a_reminder_once():
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    user_id = str(uuid4())
    task_id = str(uuid4())
    job_id = str(uuid4())
    key = f"pg-concurrency-test:{uuid4()}"
    try:
        with factory.begin() as db:
            user = User(id=user_id, email=f"{user_id}@test.invalid", password_hash="not-used")
            db.add(user)
            db.flush()
            db.add(Task(id=task_id, user_id=user_id, title="Concurrency check", due_at=utcnow()))
            db.add(
                BackgroundJob(
                    id=job_id,
                    user_id=user_id,
                    task_type="task_deadline_reminder",
                    payload={"task_id": task_id},
                    idempotency_key=key,
                    scheduled_at=utcnow(),
                )
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(
                pool.map(
                    lambda worker: process_due_jobs_once(factory, worker_id=worker),
                    ("pg-worker-a", "pg-worker-b"),
                )
            )

        assert sum(outcomes) == 1
        with factory() as db:
            job = db.get(BackgroundJob, job_id)
            assert job is not None and job.status == "succeeded"
            assert job.attempt_count == 1
            assert (
                db.scalar(
                    select(func.count(Notification.id)).where(Notification.idempotency_key == key)
                )
                == 1
            )
    finally:
        with factory.begin() as db:
            user = db.get(User, user_id)
            if user is not None:
                db.delete(user)
        engine.dispose()
