import os

os.environ["AGENTX_DRY_RUN"] = "1"

from fastapi.testclient import TestClient
from backend.server import app
from backend import server


def fake_agent(message, history=None, dry_run=False):
    return {
        "answer": "Demo healthcare navigation response",
        "trace": [
            {
                "tool": "list_files",
                "args": {},
                "observation": "Demo files found"
            }
        ]
    }


def test_home():
    with TestClient(app) as client:
        response = client.get("/")

        assert response.status_code == 200
        assert response.json()["status"] == "running"


def test_chat(monkeypatch):

    monkeypatch.setattr(
        server,
        "execute_agent",
        fake_agent
    )

    with TestClient(app) as client:

        response = client.post(
            "/api/chat",
            json={
                "message": "Hello",
                "dry_run": True
            }
        )

        assert response.status_code == 200

        data = response.json()

        assert "session_id" in data
        assert "response" in data


def test_session(monkeypatch):

    monkeypatch.setattr(
        server,
        "execute_agent",
        fake_agent
    )

    with TestClient(app) as client:

        chat_response = client.post(
            "/api/chat",
            json={"message": "Hello"}
        )

        session_id = chat_response.json()["session_id"]

        response = client.get(
            f"/api/session/{session_id}"
        )

        assert response.status_code == 200
        assert len(response.json()["messages"]) == 2


def test_appointment(monkeypatch):

    monkeypatch.setattr(
        server,
        "execute_agent",
        fake_agent
    )

    with TestClient(app) as client:

        chat_response = client.post(
            "/api/chat",
            json={"message": "Book appointment"}
        )

        session_id = chat_response.json()["session_id"]

        response = client.post(
            "/api/appointments/book",
            json={
                "session_id": session_id,
                "doctor_id": 101,
                "appointment_date": "2026-11-02",
                "appointment_time": "10:30",
                "confirmed_by_user": True
            }
        )

        assert response.status_code == 200

        assert (
            response.json()["status"]
            == "demo_confirmed"
        )


def test_stream(monkeypatch):

    monkeypatch.setattr(
        server,
        "execute_agent",
        fake_agent
    )

    with TestClient(app) as client:

        response = client.post(
            "/api/chat/stream",
            json={"message": "Hello"}
        )

        assert response.status_code == 200
        assert "final_response" in response.text


def test_websocket(monkeypatch):

    monkeypatch.setattr(
        server,
        "execute_agent",
        fake_agent
    )

    with TestClient(app) as client:

        with client.websocket_connect("/ws/chat") as ws:

            ws.send_json({
                "message": "Hello"
            })

            first = ws.receive_json()
            second = ws.receive_json()
            third = ws.receive_json()

            assert first["event"] == "thinking"
            assert second["event"] == "tool_completed"
            assert third["event"] == "final_response"
            