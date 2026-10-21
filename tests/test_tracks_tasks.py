from datetime import UTC, datetime, timedelta

from tests.conftest import csrf_headers, register


def test_registration_seeds_track_catalog(client):
    register(client)
    response = client.get("/api/v1/tracks")
    assert response.status_code == 200
    names = {track["name"] for track in response.json()}
    assert {"Data Structures & Algorithms", "Operating Systems", "System Design"} <= names
    assert len(names) == 10


def test_custom_track_can_be_edited_archived_and_restored(client):
    register(client)
    headers = csrf_headers(client)
    created = client.post(
        "/api/v1/tracks",
        json={"name": "Distributed Systems", "description": "Consensus and scale"},
        headers=headers,
    )
    assert created.status_code == 201
    track_id = created.json()["id"]

    renamed = client.patch(
        f"/api/v1/tracks/{track_id}",
        json={"name": "Distributed systems", "sort_order": 30},
        headers=headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Distributed systems"
    assert renamed.json()["sort_order"] == 30

    assert client.post(f"/api/v1/tracks/{track_id}/archive", headers=headers).status_code == 200
    assert track_id not in {track["id"] for track in client.get("/api/v1/tracks").json()}
    assert track_id in {
        track["id"] for track in client.get("/api/v1/tracks?include_archived=true").json()
    }
    assert (
        client.post(f"/api/v1/tracks/{track_id}/restore", headers=headers).json()["archived_at"]
        is None
    )


def test_archiving_track_preserves_tasks_and_history(client, lifecycle):
    headers = lifecycle["headers"]
    track = client.post(
        "/api/v1/tracks",
        json={"name": "Interview prep"},
        headers=headers,
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "Practice indexing",
            "due_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            "remind_before_minutes": 60,
            "track_id": track["id"],
            "priority": "high",
            "estimated_duration_minutes": 45,
            "notes": "Compare B-tree and hash indexes",
        },
        headers=headers,
    )
    assert task.status_code == 201, task.text
    assert task.json()["track_id"] == track["id"]
    assert task.json()["priority"] == "high"
    assert task.json()["estimated_duration_minutes"] == 45

    assert client.post(f"/api/v1/tracks/{track['id']}/archive", headers=headers).status_code == 200
    persisted_task = client.get(f"/api/v1/tasks/{task.json()['id']}")
    assert persisted_task.status_code == 200
    assert persisted_task.json()["track_id"] == track["id"]

    history = client.get(f"/api/v1/tasks/{task.json()['id']}/history")
    assert history.status_code == 200
    assert [item["event_type"] for item in history.json()] == ["task_created"]


def test_task_status_changes_are_persisted_in_history(client, lifecycle):
    task_id = lifecycle["task"]["id"]
    headers = lifecycle["headers"]
    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "in_progress", "priority": "high"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"
    assert updated.json()["priority"] == "high"

    completed = client.patch(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None
    history = client.get(f"/api/v1/tasks/{task_id}/history").json()
    assert [entry["event_type"] for entry in history] == [
        "status_changed",
        "task_updated",
        "status_changed",
        "task_created",
    ]
    assert history[0]["previous_status"] == "in_progress"
    assert history[0]["new_status"] == "completed"


def test_archived_track_cannot_receive_new_task_and_foreign_track_is_hidden(client, lifecycle):
    headers = lifecycle["headers"]
    track = client.post(
        "/api/v1/tracks",
        json={"name": "Archive check"},
        headers=headers,
    ).json()
    client.post(f"/api/v1/tracks/{track['id']}/archive", headers=headers)
    due_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    response = client.post(
        "/api/v1/tasks",
        json={"title": "Invalid assignment", "due_at": due_at, "track_id": track["id"]},
        headers=headers,
    )
    assert response.status_code == 422

    client.post("/api/v1/auth/logout", headers=headers)
    register(client, "second@example.com")
    assert (
        client.patch(
            f"/api/v1/tracks/{track['id']}",
            json={"name": "Try to rename another user's track"},
            headers=csrf_headers(client),
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/tasks/{lifecycle['task']['id']}/history").status_code == 404


def test_duplicate_track_names_are_rejected_case_insensitively(client):
    register(client)
    headers = csrf_headers(client)
    assert (
        client.post("/api/v1/tracks", json={"name": "My Track"}, headers=headers).status_code == 201
    )
    duplicate = client.post(
        "/api/v1/tracks",
        json={"name": "my track"},
        headers=headers,
    )
    assert duplicate.status_code == 409
