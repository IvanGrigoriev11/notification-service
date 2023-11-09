import json
import time
from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notification_service.db import (
    Database,
    InvalidParameters,
    Notification,
    NotificationNotFound,
)
from notification_service.service import make_app
from notification_service.smtp import SmtpRequest, SmtpService


@dataclass(frozen=True)
class FakeDb(Database):
    documents: list[Notification] = field(default_factory=list)

    async def get_notification(
        self, user_id: str, notification_id: str
    ) -> Notification:
        user_records = self._get_user(user_id)
        for record in user_records:
            if record.id == notification_id:
                return record

        raise NotificationNotFound()

    async def get_notifications(
        self, user_id: str, skip: int, limit: int
    ) -> list[Notification]:
        user = self._get_user(user_id)
        if 0 <= skip < len(user) and limit > 0:
            return user[skip : skip + limit]
        raise InvalidParameters()

    async def save_notification(self, notification: Notification):
        self.documents.append(notification)

    def _get_user(self, user_id: str) -> list[Notification]:
        user_records = []
        for notification in self.documents:
            if notification.user_id == user_id:
                user_records.append(notification)
        return user_records


@dataclass(frozen=True)
class FakeSmtp(SmtpService):
    requests: list[SmtpRequest] = field(default_factory=list)

    async def send_email(self, request: SmtpRequest):
        self.requests.append(request)


class TestApp:
    db: FakeDb
    smtp: FakeSmtp
    app: FastAPI
    client: TestClient

    def setup_method(self):
        self.db = FakeDb()
        self.smtp = FakeSmtp()
        self.app = make_app(self.db, self.smtp)
        self.client = TestClient(self.app)

    def test_create_notification_registration(self):
        payload = {
            "user_id": "x" * 24,
            "key": "registration",
            "target_email": "reciever@mail.ru",
        }
        response = self.client.post("/create", json=payload)
        assert response.status_code == 201
        assert len(self.smtp.requests) == 1
        assert self.smtp.requests[0] == SmtpRequest(
            "reciever@mail.ru",
            payload["key"],
        )
        assert json.loads(response.text)["success"]

    @pytest.mark.parametrize(
        "user_id, key",
        [
            ("x" * 24, "invalid"),
            ("x" * 23, "invalid"),
        ],
    )
    def test_create_notification_invalid_payload(self, user_id, key):
        payload = {
            "user_id": user_id,
            "key": key,
        }
        response = self.client.post("/create", json=payload)
        assert response.status_code == 400
        assert json.loads(response.text)["success"] == False

    @pytest.mark.parametrize(
        "user_id, key",
        [
            ("x" * 24, "new_message"),
            ("x" * 24, "new_login"),
        ],
    )
    def test_create_notification_new_message(self, user_id, key):
        payload = {
            "user_id": user_id,
            "key": key,
        }
        response = self.client.post("/create", json=payload)
        assert response.status_code == 201
        assert json.loads(response.text)["success"] == True
        if key == "new_message":
            assert (
                len(self.db._get_user("x" * 24)) == 1 and len(self.smtp.requests) == 0
            )
        elif key == "new_login":
            assert len(self.smtp.requests) == 1 and len(self.db.documents) == 1

    def test_read_correct_notification(self):
        payload = {
            "user_id": "x" * 24,
            "key": "new_message",
            "is_new": True,
            "notification_id": "6542f4be6a594321f98f444e",
        }
        self.client.post("/create", json=payload)
        first_record = self.db.documents[0]
        assert first_record.is_new == True
        response = self.client.post(
            "/read", params={"user_id": "x" * 24, "notification_id": first_record.id}
        )
        assert response.status_code == 200
        second_record = self.db.documents[1]
        assert second_record.is_new == False
        assert json.loads(response.text)["success"] == True

    def test_read_not_found(self):
        payload = {
            "user_id": "x" * 24,
            "key": "new_message",
            "is_new": True,
        }
        self.client.post("/create", json=payload)
        response = self.client.post(
            "/read",
            params={"user_id": "y" * 24, "notification_id": self.db.documents[0].id},
        )
        assert response.status_code == 404
        assert json.loads(response.text)["error"] == "Notification not found"

    def test_get_list_notifications(self):
        payload = {
            "user_id": "x" * 24,
            "key": "new_message",
            "is_new": True,  #
        }
        for _ in range(3):
            self.client.post("/create", json=payload)
            time.sleep(0.05)
        response = self.client.get(
            "/list", params={"user_id": "x" * 24, "skip": 1, "limit": 1}
        )
        assert response.status_code == 200
        data = json.loads(response.text)["data"]
        assert len(data) == 1

    def test_get_list_notifications_error(self):
        payload = {
            "user_id": "x" * 24,
            "key": "new_message",
            "is_new": True,
        }
        for _ in range(3):
            self.client.post("/create", json=payload)
            time.sleep(0.05)
        response = self.client.get(
            "/list", params={"user_id": "x" * 24, "skip": 3, "limit": 1}
        )
        assert response.status_code == 400
        assert json.loads(response.text)["error"] == "Invalid parameters"
