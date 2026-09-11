"""Tests for internal bearer-token protection on /chat."""

import unittest

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


class InternalAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.original_token = settings.ai_service_internal_token
        self.payload = {
            "user_id": 1,
            "session_id": 1,
            "message": "hello",
        }

    def tearDown(self):
        settings.ai_service_internal_token = self.original_token

    def test_missing_token_returns_401_when_configured(self):
        settings.ai_service_internal_token = "test-secret"

        response = self.client.post("/chat", json=self.payload)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Unauthorized internal service request")

    def test_wrong_token_returns_401(self):
        settings.ai_service_internal_token = "test-secret"

        response = self.client.post(
            "/chat",
            json=self.payload,
            headers={"Authorization": "Bearer wrong-secret"},
        )

        self.assertEqual(response.status_code, 401)

    def test_correct_token_returns_200(self):
        settings.ai_service_internal_token = "test-secret"

        response = self.client.post(
            "/chat",
            json=self.payload,
            headers={"Authorization": "Bearer test-secret"},
        )

        self.assertEqual(response.status_code, 200)

    def test_empty_configured_token_allows_local_request(self):
        settings.ai_service_internal_token = ""

        response = self.client.post("/chat", json=self.payload)

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
