import copy

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def restore_activities_state():
    original_state = copy.deepcopy(activities)
    yield
    activities.clear()
    activities.update(original_state)


def test_root_redirects_to_static_index(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/static/index.html"


def test_get_activities_returns_activity_map(client):
    response = client.get("/activities")

    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, dict)
    assert "Chess Club" in payload


def test_get_activities_items_have_expected_fields(client):
    response = client.get("/activities")

    assert response.status_code == 200

    payload = response.json()
    for details in payload.values():
        assert "description" in details
        assert "schedule" in details
        assert "max_participants" in details
        assert "participants" in details
        assert isinstance(details["participants"], list)


def test_signup_adds_new_participant(client):
    activity_name = "Chess Club"
    new_email = "new.student@mergington.edu"

    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": new_email},
    )

    assert response.status_code == 200
    assert response.json()["message"] == f"Signed up {new_email} for {activity_name}"
    assert new_email in activities[activity_name]["participants"]


def test_signup_rejects_unknown_activity(client):
    response = client.post(
        "/activities/Unknown%20Club/signup",
        params={"email": "student@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_signup_rejects_duplicate_participant(client):
    activity_name = "Programming Class"
    existing_email = activities[activity_name]["participants"][0]

    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": existing_email},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"


def test_signup_allows_over_capacity_in_current_behavior(client):
    activity_name = "Art Studio"
    max_participants = activities[activity_name]["max_participants"]

    # Fill to capacity to validate current behavior (no max-participant enforcement).
    activities[activity_name]["participants"] = [
        f"student{i}@mergington.edu" for i in range(max_participants)
    ]

    overflow_email = "overflow.student@mergington.edu"
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": overflow_email},
    )

    assert response.status_code == 200
    assert overflow_email in activities[activity_name]["participants"]
    assert len(activities[activity_name]["participants"]) == max_participants + 1


def test_unregister_removes_existing_participant(client):
    activity_name = "Gym Class"
    existing_email = activities[activity_name]["participants"][0]

    response = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": existing_email},
    )

    assert response.status_code == 200
    assert response.json()["message"] == f"Unregistered {existing_email} from {activity_name}"
    assert existing_email not in activities[activity_name]["participants"]


def test_unregister_rejects_unknown_activity(client):
    response = client.delete(
        "/activities/Unknown%20Club/unregister",
        params={"email": "student@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_unregister_rejects_non_registered_participant(client):
    activity_name = "Debate Club"
    missing_email = "not.registered@mergington.edu"

    response = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": missing_email},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Student not registered for this activity"


def test_signup_then_unregister_restores_previous_state(client):
    activity_name = "Science Olympiad"
    email = "temp.student@mergington.edu"
    starting_participants = list(activities[activity_name]["participants"])

    signup_response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email},
    )
    assert signup_response.status_code == 200
    assert email in activities[activity_name]["participants"]

    unregister_response = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email},
    )
    assert unregister_response.status_code == 200
    assert activities[activity_name]["participants"] == starting_participants
