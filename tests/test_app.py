import unittest

from app import create_app


class AppRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_home_route(self):
        response = self.client.get("/")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIn("Backend is live", payload["message"])

    def test_get_leads_route(self):
        response = self.client.get("/api/getLeads")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertGreaterEqual(len(payload["leads"]), 1)

    def test_analyze_route(self):
        response = self.client.post("/api/analyzeLead")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIn("analysis", payload)


if __name__ == "__main__":
    unittest.main()
