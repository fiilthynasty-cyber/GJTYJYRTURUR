from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from flask import Flask, jsonify, request
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



def _success(payload: dict[str, Any], status_code: int = 200):
    """Return a standard success response envelope."""
    return jsonify({"status": "success", **payload}), status_code



def _error(message: str, status_code: int = 400):
    """Return a standard error response envelope."""
    return jsonify({"status": "error", "message": message}), status_code



def _parse_limit(raw_limit: Any) -> int | None:
    if raw_limit is None:
        return None
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None
    if limit < 1:
        return None
    return min(limit, 100)



def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)

    @app.get("/")
    def home():
        return _success({"message": "Backend is live!"})

    @app.get("/api/hello")
    def hello():
        return _success({"message": "Hello from backend!"})

    @app.route("/api/getLeads", methods=["GET", "POST"])
    def get_leads():
        """Return stub lead records; supports optional `limit` for quick local filtering."""
        payload = request.get_json(silent=True) if request.method == "POST" else None
        limit = _parse_limit((payload or {}).get("limit"))

        if request.method == "POST" and (payload or {}).get("limit") is not None and limit is None:
            return _error("`limit` must be a positive integer.")

        leads = [deepcopy(DEFAULT_LEAD) for _ in range(limit or 1)]
        return _success({"leads": leads, "count": len(leads)})

    @app.post("/api/analyzeLead")
    def analyze_lead():
        return _success({"analysis": deepcopy(DEFAULT_ANALYSIS)})

    @app.post("/api/updateLead")
    def update_lead():
        return _success({"message": "Lead updated successfully"})

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
