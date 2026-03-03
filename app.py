from __future__ import annotations

import os
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

from logic.query_builder import CompanyProfile, build_queries
from logic.scoring import score_lead
from logic.sources import fetch_hn, fetch_indiehackers_rss, fetch_reddit

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

SUBSCRIBER_SIGNALS = {
    "subscribe": 14,
    "subscribers": 16,
    "newsletter": 12,
    "audience": 8,
    "followers": 9,
    "community": 8,
    "launch": 6,
    "waitlist": 10,
    "email list": 11,
    "creator": 8,
    "growth": 7,
}


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


def _subscriber_tier(score: int) -> str:
    if score >= 90:
        return "elite"
    if score >= 75:
        return "strong"
    if score >= 60:
        return "watch"
    return "low"


def _next_action_from_signals(signals: list[str]) -> str:
    lookup = {
        "newsletter": "Offer a fast newsletter growth teardown.",
        "waitlist": "Share a waitlist-to-customer conversion playbook.",
        "email list": "Lead with list cleaning + activation strategy.",
        "subscribers": "Pitch subscriber acquisition experiments.",
        "community": "Position around community-led onboarding loops.",
    }
    for signal in signals:
        if signal in lookup:
            return lookup[signal]
    return "Open with a short intent-based question and share one concrete growth idea."


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


def _score_subscriber_fit(lead: dict[str, Any]) -> tuple[int, list[str]]:
    text = " ".join([
        lead.get("title") or "",
        lead.get("summary") or "",
        " ".join(lead.get("reasons", {}).keys()),
    ]).lower()

    signal_points = 0
    matched_signals: list[str] = []
    for phrase, points in SUBSCRIBER_SIGNALS.items():
        if phrase in text:
            matched_signals.append(phrase)
            signal_points += points

    base = int(lead.get("score", 0))
    fit_score = min(100, max(0, base + signal_points))
    return fit_score, matched_signals


def _enrich_subscriber_lead(lead: dict[str, Any]) -> dict[str, Any]:
    fit_score, signals = _score_subscriber_fit(lead)
    return {
        **lead,
        "subscriber_fit_score": fit_score,
        "subscriber_tier": _subscriber_tier(fit_score),
        "subscriber_signals": signals,
        "next_action": _next_action_from_signals(signals),
    }


def _evolve_keywords(seed_keywords: list[str], leads: list[dict[str, Any]], cap: int = 12) -> list[str]:
    ranked = sorted(leads, key=lambda row: row.get("subscriber_fit_score", 0), reverse=True)
    output: list[str] = []
    seen: set[str] = set()

    def _add(keyword: str):
        cleaned = " ".join(keyword.lower().split())
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        output.append(cleaned)

    for kw in seed_keywords:
        _add(kw)

    for lead in ranked[:20]:
        for signal in lead.get("subscriber_signals", []):
            _add(signal)
            if len(output) >= cap:
                return output

    return output


def _balance_by_source(leads: list[dict[str, Any]], *, max_per_source: int, limit: int) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    output: list[dict[str, Any]] = []

    for lead in leads:
        source = lead.get("source") or "unknown"
        current = counts.get(source, 0)
        if current >= max_per_source:
            continue
        counts[source] = current + 1
        output.append(lead)
        if len(output) >= limit:
            break

    return output


def _top_signals(leads: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for lead in leads:
        counter.update(lead.get("subscriber_signals", []))
    return [{"signal": key, "count": value} for key, value in counter.most_common(limit)]


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


def run_autonomous_subscriber_engine(
    *,
    keywords: list[str],
    per_source_limit: int,
    max_queries: int,
    min_score: int,
    rounds: int,
    max_per_source: int,
    output_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rounds = max(1, min(5, rounds))

    keyword_plan = list(keywords)
    source_totals = {"reddit": 0, "hn": 0, "indiehackers": 0}
    errors: list[str] = []
    collected: dict[str, dict[str, Any]] = {}
    telemetry_rounds: list[dict[str, Any]] = []

    for cycle in range(1, rounds + 1):
        leads, source_counts, lead_errors = generate_ranked_leads(
            keywords=keyword_plan,
            per_source_limit=per_source_limit,
            max_queries=max_queries,
            min_score=min_score,
        )

        for key, value in source_counts.items():
            source_totals[key] += value
        errors.extend(lead_errors)

        for lead in leads:
            enriched = _enrich_subscriber_lead(lead)
            unique_key = enriched.get("post_url") or enriched.get("external_url") or enriched.get("title")
            existing = collected.get(unique_key)
            if not existing or enriched["subscriber_fit_score"] > existing.get("subscriber_fit_score", 0):
                collected[unique_key] = enriched

        round_leads = sorted(collected.values(), key=lambda row: row["subscriber_fit_score"], reverse=True)
        keyword_plan = _evolve_keywords(keyword_plan, round_leads)
        avg_fit = int(sum(row.get("subscriber_fit_score", 0) for row in round_leads) / len(round_leads)) if round_leads else 0

        telemetry_rounds.append({
            "round": cycle,
            "keywords": keyword_plan,
            "lead_pool": len(round_leads),
            "avg_fit_score": avg_fit,
            "top_signals": _top_signals(round_leads, limit=5),
        })

    final_ranked = sorted(collected.values(), key=lambda row: row["subscriber_fit_score"], reverse=True)
    balanced = _balance_by_source(final_ranked, max_per_source=max_per_source, limit=output_limit)

    telemetry = {
        "rounds": telemetry_rounds,
        "source_totals": source_totals,
        "errors": errors[:20],
        "keywords_final": keyword_plan,
        "top_signals": _top_signals(final_ranked),
    }
    return balanced, telemetry


def _read_generation_request() -> tuple[list[str], int, int, int, int | None]:
    payload = request.get_json(silent=True) or {}
    query_keywords = request.args.get("keywords")
    raw_keywords = payload.get("keywords") if payload else query_keywords
    keywords = _normalize_keywords(raw_keywords)

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

    @app.post("/api/subscriberEngine")
    def subscriber_engine():
        payload = request.get_json(silent=True) or {}
        keywords, per_source_limit, max_queries, min_score, limit = _read_generation_request()
        rounds = _parse_limit(payload.get("rounds"), max_value=5) or 3
        max_per_source = _parse_limit(
            payload.get("max_per_source") if payload.get("max_per_source") is not None else request.args.get("max_per_source"),
            max_value=50,
        ) or 10

        if not keywords:
            return _error("`keywords` must be a non-empty string array or comma-separated query string.")

        output_limit = limit or 30
        leads, telemetry = run_autonomous_subscriber_engine(
            keywords=keywords,
            per_source_limit=per_source_limit,
            max_queries=max_queries,
            min_score=min_score,
            rounds=rounds,
            max_per_source=max_per_source,
            output_limit=output_limit,
        )

        return _success({
            "engine": "autonomous_subscriber_engine",
            "rounds": rounds,
            "max_per_source": max_per_source,
            "count": len(leads),
            "telemetry": telemetry,
            "leads": leads,
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
