import unittest
from unittest.mock import patch

from app import create_app


class AppRoutesTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.testing = True
        self.client = app.test_client()

    def test_home_route(self):
        response = self.client.get("/")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIn("Backend is live", payload["message"])

    def test_hello_route(self):
        response = self.client.get("/api/hello")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIn("Hello from backend", payload["message"])

    def test_get_leads_get_route(self):
        response = self.client.get("/api/getLeads")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertGreaterEqual(len(payload["leads"]), 1)
        self.assertEqual(payload["count"], len(payload["leads"]))

    def test_get_leads_post_with_limit(self):
        response = self.client.post("/api/getLeads", json={"limit": 3})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["count"], 3)

    def test_get_leads_post_with_bad_limit(self):
        response = self.client.post("/api/getLeads", json={"limit": 0})
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["status"], "error")

    @patch("app.fetch_indiehackers_rss")
    @patch("app.fetch_hn")
    @patch("app.fetch_reddit")
    def test_generate_leads_route(self, mock_reddit, mock_hn, mock_ih):
        mock_reddit.return_value = [{
            "title": "Need a better lead gen tool",
            "url": "https://reddit.com/a",
            "deep_link": "https://reddit.com/a",
            "snippet": "Looking for options with pricing",
            "source": "reddit",
            "created_at_iso": "2025-01-01T00:00:00+00:00",
            "meta": {},
        }]
        mock_hn.return_value = []
        mock_ih.return_value = []

        response = self.client.post(
            "/api/generateLeads",
            json={"keywords": ["lead gen", "sales"], "max_queries": 1, "min_score": 1},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertGreaterEqual(payload["count"], 1)
        self.assertIn("source_counts", payload)
        self.assertEqual(payload["leads"][0]["source"], "reddit")

    def test_generate_leads_requires_keywords(self):
        response = self.client.post("/api/generateLeads", json={"keywords": []})
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["status"], "error")

    def test_analyze_route(self):
        response = self.client.post("/api/analyzeLead")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIn("analysis", payload)

    def test_update_route(self):
        response = self.client.post("/api/updateLead")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")


if __name__ == "__main__":
    unittest.main()
