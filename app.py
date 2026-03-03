from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify
from flask_cors import CORS


DEFAULT_LEAD = {
    "id": 1,
    "title": "Example Lead",
    "content": "This is a test lead",
    "score": 85,
    "intent": "high",
}

DEFAULT_ANALYSIS = {
    "score": 92,
    "intent": "high",
    "reason": "Contains buying signals",
}


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)

    def success(payload: dict[str, Any], status_code: int = 200):
        return jsonify({"status": "success", **payload}), status_code

    @app.get("/")
    def home():
        return success({"message": "Backend is live!"})

    @app.get("/api/hello")
    def hello():
        return success({"message": "Hello from backend!"})

    @app.route("/api/getLeads", methods=["GET", "POST"])
    def get_leads():
        return success({"leads": [DEFAULT_LEAD]})

    @app.post("/api/analyzeLead")
    def analyze_lead():
        return success({"analysis": DEFAULT_ANALYSIS})

    @app.post("/api/updateLead")
    def update_lead():
        return success({"message": "Lead updated successfully"})

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
