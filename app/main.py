from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import SessionLocal, engine, get_db, make_engine
from app.jobs import enqueue_task_reminder, utc
from app.models import (
    AuthSession,
    BackgroundJob,
    Base,
    Notification,
    NotificationPreference,
    PreparationTrack,
    Task,
    TaskHistory,
    User,
    utcnow,
)
from app.opportunities import router as opportunities_router
from app.schemas import (
    Credentials,
    JobResponse,
    NotificationResponse,
    TaskCreate,
    TaskHistoryResponse,
    TaskResponse,
    TaskUpdate,
    TrackCreate,
    TrackResponse,
    TrackUpdate,
    UserResponse,
)
from app.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    create_session,
    current_user,
    hash_password,
    require_csrf,
    validate_timezone,
    verify_password,
)

DEFAULT_TRACKS = (
    (
        "Data Structures & Algorithms",
        "Build problem-solving fluency across core data structures and algorithms.",
    ),
    ("Operating Systems", "Review processes, memory, concurrency, and scheduling."),
    ("Databases", "Study relational modeling, transactions, indexing, and query design."),
    ("Object-Oriented Design", "Practice modeling maintainable object-oriented systems."),
    ("Computer Networks", "Review protocols, networking layers, and web fundamentals."),
    ("Aptitude", "Keep quantitative reasoning and problem-solving practice on track."),
    ("System Design", "Build system design knowledge through focused study tasks."),
    ("SQL", "Practice querying and reasoning about relational data."),
    ("Coding Practice", "Organize implementation drills and timed practice."),
    ("Behavioral Interviews", "Prepare clear, specific stories about your experience."),
)


def _record_task_history(
    db: Session,
    task: Task,
    event_type: str,
    *,
    previous_status: str | None = None,
    new_status: str | None = None,
    details: str | None = None,
) -> None:
    db.add(
        TaskHistory(
            task_id=task.id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            details=details,
        )
    )


def create_app(
    database_url: str | None = None,
    *,
    create_schema: bool = False,
) -> FastAPI:
    app = FastAPI(title="TaskFlow Prep API", version="1.0.0")
    configured_engine = make_engine(database_url) if database_url else engine
    session_factory: sessionmaker = (
        SessionLocal
        if database_url is None
        else sessionmaker(bind=configured_engine, expire_on_commit=False)
    )
    if create_schema:
        Base.metadata.create_all(configured_engine)

    def app_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = app_db
    app.include_router(opportunities_router)
    settings = get_settings()
    app.state.engine = configured_engine
    app.state.session_factory = session_factory
    app.state.upload_dir = settings.upload_dir
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.get("/api/v1/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/api/v1/health/ready")
    def ready(db: Session = Depends(app_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.post("/api/v1/auth/register", response_model=UserResponse, status_code=201)
    def register(body: Credentials, response: Response, db: Session = Depends(app_db)):
        validate_timezone(body.timezone)
        email = body.email.lower()
        if db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        user = User(email=email, password_hash=hash_password(body.password), timezone=body.timezone)
        db.add(user)
        db.flush()
        db.add(NotificationPreference(user_id=user.id))
        db.add_all(
            PreparationTrack(
                user_id=user.id,
                name=name,
                description=description,
                sort_order=position,
            )
            for position, (name, description) in enumerate(DEFAULT_TRACKS)
        )
        create_session(db, user, response)
        db.commit()
        db.refresh(user)
        return user

    @app.post("/api/v1/auth/login", response_model=UserResponse)
    def login(body: Credentials, response: Response, db: Session = Depends(app_db)):
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Email or password is incorrect")
        create_session(db, user, response)
        db.commit()
        return user

    @app.get("/api/v1/auth/me", response_model=UserResponse)
    def me(user: Annotated[User, Depends(current_user)]):
        return user

    @app.get("/api/v1/auth/csrf")
    def csrf(
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
        session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        if session_cookie is None:
            raise HTTPException(status_code=401, detail="Sign in required")
        session_id = sha256(session_cookie.encode()).hexdigest()
        auth_session = db.get(AuthSession, session_id)
        if auth_session is None or auth_session.user_id != user.id:
            raise HTTPException(status_code=401, detail="Session expired")
        return {"csrf_token": auth_session.csrf_token}

    @app.post("/api/v1/auth/logout", status_code=204, dependencies=[Depends(require_csrf)])
    def logout(
        response: Response,
        db: Session = Depends(app_db),
        session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        if session_cookie:
            auth_session = db.get(AuthSession, sha256(session_cookie.encode()).hexdigest())
            if auth_session is not None:
                db.delete(auth_session)
            db.commit()
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        response.status_code = 204
        return response

    @app.get("/api/v1/tracks", response_model=list[TrackResponse])
    def list_tracks(
        user: Annotated[User, Depends(current_user)],
        include_archived: bool = False,
        db: Session = Depends(app_db),
    ):
        query = select(PreparationTrack).where(PreparationTrack.user_id == user.id)
        if not include_archived:
            query = query.where(PreparationTrack.archived_at.is_(None))
        return list(db.scalars(query.order_by(PreparationTrack.sort_order, PreparationTrack.name)))

    @app.post(
        "/api/v1/tracks",
        response_model=TrackResponse,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    def create_track(
        body: TrackCreate,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Track name cannot be blank")
        duplicate = db.scalar(
            select(PreparationTrack.id).where(
                PreparationTrack.user_id == user.id,
                func.lower(PreparationTrack.name) == name.lower(),
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="A track with this name already exists")
        max_order = db.scalar(
            select(func.max(PreparationTrack.sort_order)).where(PreparationTrack.user_id == user.id)
        )
        track = PreparationTrack(
            user_id=user.id,
            name=name,
            description=body.description.strip(),
            sort_order=(max_order or 0) + 1,
        )
        db.add(track)
        db.commit()
        db.refresh(track)
        return track

    @app.patch(
        "/api/v1/tracks/{track_id}",
        response_model=TrackResponse,
        dependencies=[Depends(require_csrf)],
    )
    def update_track(
        track_id: str,
        body: TrackUpdate,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        track = db.scalar(
            select(PreparationTrack).where(
                PreparationTrack.id == track_id,
                PreparationTrack.user_id == user.id,
            )
        )
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(
                status_code=422, detail="Provide at least one track field to update"
            )
        if any(value is None for value in changes.values()):
            raise HTTPException(status_code=422, detail="Track fields cannot be null")
        if "name" in changes:
            name = (changes["name"] or "").strip()
            if not name:
                raise HTTPException(status_code=422, detail="Track name cannot be blank")
            duplicate = db.scalar(
                select(PreparationTrack.id).where(
                    PreparationTrack.user_id == user.id,
                    func.lower(PreparationTrack.name) == name.lower(),
                    PreparationTrack.id != track.id,
                )
            )
            if duplicate:
                raise HTTPException(status_code=409, detail="A track with this name already exists")
            changes["name"] = name
        for field, value in changes.items():
            setattr(track, field, value.strip() if field == "description" and value else value)
        db.commit()
        db.refresh(track)
        return track

    def set_track_archived(track_id: str, user: User, db: Session, archived: bool):
        track = db.scalar(
            select(PreparationTrack).where(
                PreparationTrack.id == track_id,
                PreparationTrack.user_id == user.id,
            )
        )
        if track is None:
            raise HTTPException(status_code=404, detail="Track not found")
        track.archived_at = utcnow() if archived else None
        db.commit()
        db.refresh(track)
        return track

    @app.post(
        "/api/v1/tracks/{track_id}/archive",
        response_model=TrackResponse,
        dependencies=[Depends(require_csrf)],
    )
    def archive_track(
        track_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        return set_track_archived(track_id, user, db, True)

    @app.post(
        "/api/v1/tracks/{track_id}/restore",
        response_model=TrackResponse,
        dependencies=[Depends(require_csrf)],
    )
    def restore_track(
        track_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        return set_track_archived(track_id, user, db, False)

    @app.get("/api/v1/tasks", response_model=list[TaskResponse])
    def list_tasks(user: Annotated[User, Depends(current_user)], db: Session = Depends(app_db)):
        return list(
            db.scalars(
                select(Task).where(Task.user_id == user.id).order_by(Task.due_at, Task.created_at)
            )
        )

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
    def get_task(
        task_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get(
        "/api/v1/tasks/{task_id}/history",
        response_model=list[TaskHistoryResponse],
    )
    def task_history(
        task_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        task_exists = db.scalar(select(Task.id).where(Task.id == task_id, Task.user_id == user.id))
        if task_exists is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return list(
            db.scalars(
                select(TaskHistory)
                .where(TaskHistory.task_id == task_id)
                .order_by(TaskHistory.occurred_at.desc())
            )
        )

    @app.post(
        "/api/v1/tasks",
        response_model=TaskResponse,
        status_code=201,
        dependencies=[Depends(require_csrf)],
    )
    def create_task(
        body: TaskCreate,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Task title cannot be blank")
        if body.track_id is not None:
            track_exists = db.scalar(
                select(PreparationTrack.id).where(
                    PreparationTrack.id == body.track_id,
                    PreparationTrack.user_id == user.id,
                    PreparationTrack.archived_at.is_(None),
                )
            )
            if track_exists is None:
                raise HTTPException(
                    status_code=422, detail="Choose an active track in your workspace"
                )
        task = Task(
            user_id=user.id,
            track_id=body.track_id,
            title=title,
            due_at=body.due_at,
            priority=body.priority,
            estimated_duration_minutes=body.estimated_duration_minutes,
            notes=body.notes,
        )
        db.add(task)
        db.flush()
        _record_task_history(
            db,
            task,
            "task_created",
            new_status=task.status,
            details="Task added to the study plan.",
        )
        enqueue_task_reminder(
            db,
            user_id=user.id,
            task_id=task.id,
            due_at=utc(task.due_at),
            remind_before_minutes=body.remind_before_minutes,
        )
        db.commit()
        db.refresh(task)
        return task

    @app.patch(
        "/api/v1/tasks/{task_id}",
        response_model=TaskResponse,
        dependencies=[Depends(require_csrf)],
    )
    def update_task(
        task_id: str,
        body: TaskUpdate,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=422, detail="Provide at least one task field to update")
        if "title" in changes:
            title = (changes["title"] or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail="Task title cannot be blank")
            changes["title"] = title
        if "track_id" in changes and changes["track_id"] is not None:
            track_exists = db.scalar(
                select(PreparationTrack.id).where(
                    PreparationTrack.id == changes["track_id"],
                    PreparationTrack.user_id == user.id,
                    PreparationTrack.archived_at.is_(None),
                )
            )
            if track_exists is None:
                raise HTTPException(
                    status_code=422, detail="Choose an active track in your workspace"
                )
        for field in ("status", "priority"):
            if field in changes and changes[field] is None:
                raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        previous_status = task.status
        for field, value in changes.items():
            setattr(task, field, value)
        if "status" in changes and changes["status"] != previous_status:
            task.completed_at = utcnow() if changes["status"] == "completed" else None
            _record_task_history(
                db,
                task,
                "status_changed",
                previous_status=previous_status,
                new_status=changes["status"],
            )
        other_fields = set(changes) - {"status"}
        if other_fields:
            _record_task_history(
                db,
                task,
                "task_updated",
                details=f"Updated: {', '.join(sorted(other_fields))}.",
            )
        db.commit()
        db.refresh(task)
        return task

    @app.patch(
        "/api/v1/tasks/{task_id}/complete",
        response_model=TaskResponse,
        dependencies=[Depends(require_csrf)],
    )
    def complete_task(
        task_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != "completed":
            previous_status = task.status
            task.status = "completed"
            task.completed_at = utcnow()
            _record_task_history(
                db,
                task,
                "status_changed",
                previous_status=previous_status,
                new_status="completed",
            )
        db.commit()
        db.refresh(task)
        return task

    @app.get("/api/v1/notifications", response_model=list[NotificationResponse])
    def list_notifications(
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        return list(
            db.scalars(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at.desc())
                .limit(100)
            )
        )

    @app.get("/api/v1/notifications/unread-count")
    def unread_count(user: Annotated[User, Depends(current_user)], db: Session = Depends(app_db)):
        count = db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        )
        return {"count": count or 0}

    @app.post(
        "/api/v1/notifications/{notification_id}/read",
        response_model=NotificationResponse,
        dependencies=[Depends(require_csrf)],
    )
    def mark_notification_read(
        notification_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        notification = db.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user.id
            )
        )
        if notification is None:
            raise HTTPException(status_code=404, detail="Notification not found")
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            db.commit()
            db.refresh(notification)
        return notification

    @app.post(
        "/api/v1/notifications/read-all",
        status_code=204,
        dependencies=[Depends(require_csrf)],
    )
    def mark_all_read(user: Annotated[User, Depends(current_user)], db: Session = Depends(app_db)):
        db.query(Notification).filter(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        ).update({Notification.read_at: datetime.now(UTC)})
        db.commit()
        return Response(status_code=204)

    @app.get("/api/v1/jobs", response_model=list[JobResponse])
    def list_jobs(user: Annotated[User, Depends(current_user)], db: Session = Depends(app_db)):
        return list(
            db.scalars(
                select(BackgroundJob)
                .where(BackgroundJob.user_id == user.id)
                .order_by(BackgroundJob.created_at.desc())
                .limit(100)
            )
        )

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
    def get_job(
        job_id: str,
        user: Annotated[User, Depends(current_user)],
        db: Session = Depends(app_db),
    ):
        job = db.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user.id
            )
        )
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    return app


app = create_app()
