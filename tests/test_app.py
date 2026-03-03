import unittest

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
        self.assertEqual(len(payload["leads"]), 3)

    def test_get_leads_post_with_bad_limit(self):
        response = self.client.post("/api/getLeads", json={"limit": 0})
        payload = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["status"], "error")
        self.assertIn("positive integer", payload["message"])

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
        self.assertIn("updated successfully", payload["message"])


if __name__ == "__main__":
    unittest.main()
