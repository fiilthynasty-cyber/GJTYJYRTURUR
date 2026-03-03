from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

from logic.query_builder import CompanyProfile, build_queries
from logic.scoring import score_lead
from logic.sources import fetch_hn, fetch_indiehackers_rss, fetch_reddit

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

DEFAULT_LEAD_KEYWORDS = [
    "saas",
    "automation",
    "sales",
    "lead generation",
]


def _success(payload: dict[str, Any], status_code: int = 200):
    return jsonify({"status": "success", **payload}), status_code


def _error(message: str, status_code: int = 400):
    return jsonify({"status": "error", "message": message}), status_code


def _parse_limit(raw_limit: Any, *, max_value: int = 100) -> int | None:
    if raw_limit is None:
        return None
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None
    if limit < 1:
        return None
    return min(limit, max_value)


def _normalize_keywords(raw_keywords: Any) -> list[str]:
    if raw_keywords is None:
        return DEFAULT_LEAD_KEYWORDS

    if isinstance(raw_keywords, str):
        raw_keywords = [piece.strip() for piece in raw_keywords.split(",")]

    if not isinstance(raw_keywords, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for item in raw_keywords:
        if not isinstance(item, str):
            continue
        kw = " ".join(item.strip().split())
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(kw)
    return out


def _bucket_intent(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lead_payload_from_source(item: dict[str, Any], *, score: int, reasons: dict[str, Any]) -> dict[str, Any]:
    direct_post_url = item.get("deep_link") or item.get("url") or ""
    return {
        "title": item.get("title") or "",
        "post_url": direct_post_url,
        "external_url": item.get("url") or direct_post_url,
        "source": item.get("source") or "",
        "author": (item.get("meta") or {}).get("author") or "",
        "summary": item.get("snippet") or "",
        "score": score,
        "intent": _bucket_intent(score),
        "reasons": reasons,
        "captured_at": _now_iso(),
    }


def generate_ranked_leads(
    *,
    keywords: list[str],
    per_source_limit: int,
    max_queries: int,
    min_score: int,
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    company = CompanyProfile(url="https://fiilthy.ai", keywords=tuple(keywords))
    queries = build_queries(company, max_queries=max_queries)

    source_counts = {"reddit": 0, "hn": 0, "indiehackers": 0}
    errors: list[str] = []
    deduped: dict[str, dict[str, Any]] = {}

    for query in queries:
        try:
            reddit_items = fetch_reddit(query, limit=per_source_limit)
            source_counts["reddit"] += len(reddit_items)
            for item in reddit_items:
                deduped[item["url"]] = item
        except Exception as exc:
            errors.append(f"reddit:{query}:{exc}")

        try:
            hn_items = fetch_hn(query, limit=per_source_limit)
            source_counts["hn"] += len(hn_items)
            for item in hn_items:
                deduped[item["url"]] = item
        except Exception as exc:
            errors.append(f"hn:{query}:{exc}")

    try:
        ih_items = fetch_indiehackers_rss(keywords, limit=per_source_limit * 2)
        source_counts["indiehackers"] += len(ih_items)
        for item in ih_items:
            deduped[item["url"]] = item
    except Exception as exc:
        errors.append(f"indiehackers:{exc}")

    ranked: list[dict[str, Any]] = []

    for item in deduped.values():
        score, _, reasons = score_lead(
            title=item.get("title") or "",
            content=item.get("snippet") or "",
            url=item.get("url") or "",
            source=item.get("source") or "",
            created_at_iso=item.get("created_at_iso"),
            meta=item.get("meta") or {},
        )

        if score < min_score:
            continue

        ranked.append(_lead_payload_from_source(item, score=score, reasons=reasons))

    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked, source_counts, errors


def _read_generation_request() -> tuple[list[str], int, int, int, int | None]:
    payload = request.get_json(silent=True) or {}
    query_keywords = request.args.get("keywords")
    raw_keywords = payload.get("keywords") if payload else query_keywords
    keywords = _normalize_keywords(raw_keywords)

    # POST body takes precedence over query args when provided.
    if payload.get("keywords") is not None:
        keywords = _normalize_keywords(payload.get("keywords"))

    per_source_limit = _parse_limit(
        payload.get("per_source_limit") if payload.get("per_source_limit") is not None else request.args.get("per_source_limit"),
        max_value=25,
    ) or 5
    max_queries = _parse_limit(
        payload.get("max_queries") if payload.get("max_queries") is not None else request.args.get("max_queries"),
        max_value=50,
    ) or 8
    min_score = _parse_limit(
        payload.get("min_score") if payload.get("min_score") is not None else request.args.get("min_score"),
        max_value=100,
    ) or 55

    limit_raw = payload.get("limit") if payload.get("limit") is not None else request.args.get("limit")
    limit = _parse_limit(limit_raw)

    return keywords, per_source_limit, max_queries, min_score, limit


def create_app() -> Flask:
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
        keywords, per_source_limit, max_queries, min_score, limit = _read_generation_request()

        if not keywords:
            return _error("`keywords` must be a non-empty string array or comma-separated query string.")

        leads, source_counts, errors = generate_ranked_leads(
            keywords=keywords,
            per_source_limit=per_source_limit,
            max_queries=max_queries,
            min_score=min_score,
        )

        if limit is not None:
            leads = leads[:limit]

        return _success({
            "keywords": keywords,
            "count": len(leads),
            "source_counts": source_counts,
            "errors": errors[:20],
            "leads": leads,
        })

    @app.post("/api/generateLeads")
    def generate_leads():
        keywords, per_source_limit, max_queries, min_score, limit = _read_generation_request()

        if not keywords:
            return _error("`keywords` must be a non-empty string array or comma-separated query string.")

        leads, source_counts, errors = generate_ranked_leads(
            keywords=keywords,
            per_source_limit=per_source_limit,
            max_queries=max_queries,
            min_score=min_score,
        )

        capped = leads[: min(100, limit or 100)]
        return _success({
            "keywords": keywords,
            "count": len(capped),
            "source_counts": source_counts,
            "errors": errors[:20],
            "leads": capped,
        })

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
