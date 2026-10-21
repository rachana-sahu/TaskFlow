import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import BackgroundJob, JobAttempt, Notification, Task, utcnow

LEASE_FOR = timedelta(minutes=2)
MAX_BACKOFF_SECONDS = 3600
VALID_TRANSITIONS = {
    "queued": {"running"},
    "running": {"running", "retrying", "succeeded", "failed"},
    "retrying": {"running"},
    "succeeded": set(),
    "failed": set(),
}


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def enqueue_task_reminder(
    db: Session,
    *,
    user_id: str,
    task_id: str,
    due_at: datetime,
    remind_before_minutes: int,
    now: datetime | None = None,
) -> BackgroundJob:
    scheduled_at = due_at - timedelta(minutes=remind_before_minutes)
    scheduled_at = max(scheduled_at, utc(now or utcnow()))
    idempotency_key = f"task-deadline:{user_id}:{task_id}:{due_at.isoformat()}"
    job = BackgroundJob(
        user_id=user_id,
        task_type="task_deadline_reminder",
        payload={"task_id": task_id},
        idempotency_key=idempotency_key,
        scheduled_at=scheduled_at,
    )
    db.add(job)
    return job


def create_task_reminder(db: Session, job: BackgroundJob) -> None:
    task_id = job.payload.get("task_id")
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == job.user_id))
    if task is None or task.status in {"completed", "archived"}:
        return

    existing = db.scalar(
        select(Notification.id).where(Notification.idempotency_key == job.idempotency_key)
    )
    if existing is not None:
        return

    db.add(
        Notification(
            user_id=job.user_id,
            notification_type="upcoming_deadline",
            title="Study task deadline",
            body=f'"{task.title}" is approaching its deadline.',
            related_resource_type="task",
            related_resource_id=task.id,
            scheduled_at=job.scheduled_at,
            idempotency_key=job.idempotency_key,
        )
    )


HANDLERS: dict[str, Callable[[Session, BackgroundJob], None]] = {
    "task_deadline_reminder": create_task_reminder,
}


def retry_delay(attempt_count: int) -> int:
    return min(30 * (2 ** max(attempt_count - 1, 0)), MAX_BACKOFF_SECONDS)


def transition_job(job: BackgroundJob, next_status: str) -> None:
    if next_status not in VALID_TRANSITIONS.get(job.status, set()):
        raise ValueError(f"Invalid job state transition: {job.status} -> {next_status}")
    job.status = next_status


def process_due_jobs_once(
    session_factory: sessionmaker,
    *,
    worker_id: str | None = None,
    now: datetime | None = None,
) -> bool:
    current_time = utc(now or utcnow())
    worker_id = worker_id or f"worker-{uuid4()}"
    claimed_job_id: str | None = None
    claimed_attempt = 0
    recovered_lease = False

    with session_factory.begin() as db:
        exhausted_leases = db.scalars(
            select(BackgroundJob)
            .where(
                BackgroundJob.status == "running",
                BackgroundJob.lease_expires_at <= current_time,
                BackgroundJob.attempt_count >= BackgroundJob.max_attempts,
            )
            .with_for_update(skip_locked=True)
        )
        for exhausted_job in exhausted_leases:
            attempt = db.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == exhausted_job.id,
                    JobAttempt.attempt_number == exhausted_job.attempt_count,
                )
            )
            if attempt is not None:
                attempt.status = "failed"
                attempt.error_message = "Worker lease expired after final attempt"
                attempt.completed_at = current_time
            transition_job(exhausted_job, "failed")
            exhausted_job.completed_at = current_time
            exhausted_job.lease_expires_at = None
            exhausted_job.error_message = "Worker lease expired after final attempt"
            recovered_lease = True

        eligible = or_(
            (
                BackgroundJob.status.in_(("queued", "retrying"))
                & (BackgroundJob.scheduled_at <= current_time)
            ),
            (
                (BackgroundJob.status == "running")
                & (BackgroundJob.lease_expires_at <= current_time)
            ),
        )
        job = db.scalar(
            select(BackgroundJob)
            .where(eligible, BackgroundJob.attempt_count < BackgroundJob.max_attempts)
            .order_by(BackgroundJob.priority.desc(), BackgroundJob.scheduled_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return recovered_lease
        if job.status == "running":
            previous_attempt = db.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.attempt_number == job.attempt_count,
                )
            )
            if previous_attempt is not None:
                previous_attempt.status = "failed"
                previous_attempt.error_message = "Worker lease expired"
                previous_attempt.completed_at = current_time
        transition_job(job, "running")
        job.attempt_count += 1
        job.started_at = current_time
        job.lease_expires_at = current_time + LEASE_FOR
        job.worker_id = worker_id
        job.error_message = None
        claimed_job_id = job.id
        claimed_attempt = job.attempt_count
        db.add(
            JobAttempt(
                job_id=job.id,
                attempt_number=claimed_attempt,
                status="running",
                started_at=current_time,
            )
        )

    try:
        with session_factory.begin() as db:
            job = db.scalar(
                select(BackgroundJob).where(BackgroundJob.id == claimed_job_id).with_for_update()
            )
            if job is None or job.status != "running" or job.worker_id != worker_id:
                return True
            handler = HANDLERS.get(job.task_type)
            if handler is None:
                raise ValueError(f"Unregistered task type: {job.task_type}")
            handler(db, job)
            transition_job(job, "succeeded")
            job.completed_at = current_time
            job.lease_expires_at = None
            attempt = db.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.attempt_number == claimed_attempt,
                )
            )
            if attempt is not None:
                attempt.status = "succeeded"
                attempt.completed_at = current_time
        return True
    except Exception as exc:
        with session_factory.begin() as db:
            job = db.scalar(
                select(BackgroundJob).where(BackgroundJob.id == claimed_job_id).with_for_update()
            )
            if job is None or job.status != "running" or job.worker_id != worker_id:
                return True
            job.error_message = str(exc)[:2000]
            job.lease_expires_at = None
            transition_job(
                job,
                "retrying" if job.attempt_count < job.max_attempts else "failed",
            )
            if job.status == "retrying":
                delay = retry_delay(job.attempt_count)
                jittered_delay = random.uniform(delay * 0.8, delay * 1.2)
                job.scheduled_at = current_time + timedelta(
                    seconds=min(jittered_delay, MAX_BACKOFF_SECONDS)
                )
            else:
                job.completed_at = current_time
            attempt = db.scalar(
                select(JobAttempt).where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.attempt_number == claimed_attempt,
                )
            )
            if attempt is not None:
                attempt.status = "failed"
                attempt.error_message = job.error_message
                attempt.completed_at = current_time
        return True
