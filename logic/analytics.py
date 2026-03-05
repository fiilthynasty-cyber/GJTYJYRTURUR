# logic/analytics.py
#
# Aggregate stats over scored leads, pipeline runs, and outreach data.
# All functions are pure (no DB writes) unless noted.
#
# Usage:
#   from logic.analytics import summarise_leads, top_sources, intent_breakdown
#   summary = summarise_leads(lead_dicts)

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Lead-level aggregation (works on a list of ScoredLead.to_dict() or raw dicts)
# ---------------------------------------------------------------------------

def summarise_leads(leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns a summary dict for a batch of leads.
    """
    if not leads:
        return {
            "total": 0,
            "avg_score": 0.0,
            "hot": 0,
            "intent": {},
            "sources": {},
            "score_histogram": {},
        }

    scores = [int(l.get("score") or 0) for l in leads]
    total = len(leads)
    avg = round(sum(scores) / total, 1)
    hot = sum(1 for s in scores if s >= 70)

    intent_counts: Counter = Counter(l.get("intent") or "low" for l in leads)
    source_counts: Counter = Counter(l.get("source") or "unknown" for l in leads)

    histogram: Dict[str, int] = {}
    for s in scores:
        bucket = f"{(s // 10) * 10}-{(s // 10) * 10 + 9}"
        histogram[bucket] = histogram.get(bucket, 0) + 1

    return {
        "total": total,
        "avg_score": avg,
        "hot": hot,
        "intent": dict(intent_counts),
        "sources": dict(source_counts),
        "score_histogram": histogram,
    }


def top_sources(leads: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
    """
    Returns ranked source list with lead count and average score.
    """
    buckets: Dict[str, List[int]] = {}
    for lead in leads:
        src = lead.get("source") or "unknown"
        score = int(lead.get("score") or 0)
        buckets.setdefault(src, []).append(score)

    result = []
    for src, scores in buckets.items():
        result.append({
            "source": src,
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 1),
            "hot_count": sum(1 for s in scores if s >= 70),
        })

    result.sort(key=lambda x: (x["avg_score"], x["count"]), reverse=True)
    return result[:top_n]


def intent_breakdown(leads: List[Dict[str, Any]]) -> Dict[str, int]:
    counter: Counter = Counter(l.get("intent") or "low" for l in leads)
    return {"high": counter["high"], "medium": counter["medium"], "low": counter["low"]}


def top_pain_points(leads: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Aggregates pain-point phrases across all lead reasons.
    """
    counter: Counter = Counter()
    for lead in leads:
        reasons = lead.get("reasons") or {}
        pains = reasons.get("pain_points") or []
        for p in pains:
            counter[p] += 1
    return [{"phrase": k, "count": v} for k, v in counter.most_common(top_n)]


def top_buying_signals(leads: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for lead in leads:
        reasons = lead.get("reasons") or {}
        signals = reasons.get("buying_signals") or []
        for s in signals:
            counter[s] += 1
    return [{"phrase": k, "count": v} for k, v in counter.most_common(top_n)]


def freshness_distribution(leads: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Bucket leads by age: <1h, <6h, <24h, <3d, <7d, older.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    buckets = {"<1h": 0, "<6h": 0, "<24h": 0, "<3d": 0, "<7d": 0, "older": 0}

    for lead in leads:
        dt = _parse_iso(lead.get("created_at_iso"))
        if dt is None:
            buckets["older"] += 1
            continue
        age = now - dt
        if age <= timedelta(hours=1):
            buckets["<1h"] += 1
        elif age <= timedelta(hours=6):
            buckets["<6h"] += 1
        elif age <= timedelta(hours=24):
            buckets["<24h"] += 1
        elif age <= timedelta(days=3):
            buckets["<3d"] += 1
        elif age <= timedelta(days=7):
            buckets["<7d"] += 1
        else:
            buckets["older"] += 1

    return buckets


def full_report(leads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    One-shot full analytics report over a lead batch.
    """
    return {
        "summary": summarise_leads(leads),
        "top_sources": top_sources(leads),
        "intent_breakdown": intent_breakdown(leads),
        "top_pain_points": top_pain_points(leads),
        "top_buying_signals": top_buying_signals(leads),
        "freshness_distribution": freshness_distribution(leads),
    }
