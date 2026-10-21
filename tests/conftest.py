from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import BackgroundJob, Base, Notification, Task


@pytest.fixture
def app(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", create_schema=True)
    yield app
    Base.metadata.drop_all(app.state.engine)
    app.state.engine.dispose()


@pytest.fixture
def client(app):
    return TestClient(app)


def register(client: TestClient, email: str = "dev@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery", "timezone": "Asia/Kolkata"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.fixture
def lifecycle(client, app):
    user = register(client)
    headers = csrf_headers(client)
    due_at = datetime.now(UTC) + timedelta(minutes=10)
    task_response = client.post(
        "/api/v1/tasks",
        json={
            "title": "Review graph traversal",
            "due_at": due_at.isoformat(),
            "remind_before_minutes": 0,
        },
        headers=headers,
    )
    assert task_response.status_code == 201, task_response.text
    return {"user": user, "task": task_response.json(), "headers": headers, "due_at": due_at}


def task_and_job_counts(app) -> tuple[int, int, int]:
    with app.state.session_factory() as db:
        return (
            len(list(db.scalars(select(Task)))),
            len(list(db.scalars(select(BackgroundJob)))),
            len(list(db.scalars(select(Notification)))),
        )
