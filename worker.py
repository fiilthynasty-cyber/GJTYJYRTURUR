import os
import time
import socket
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# =============================
# CONFIG
# =============================

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
NOW = lambda: datetime.now(timezone.utc)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "10"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "5"))
LOCK_TTL_MINUTES = int(os.environ.get("LOCK_TTL_MINUTES", "10"))

sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# =============================
# JOB CLAIMING
# =============================

def pick_jobs(limit=5):
    lock_expired_before = (NOW() - timedelta(minutes=LOCK_TTL_MINUTES)).isoformat()

    candidates = (
        sb.table("jobs")
        .select("*")
        .eq("status", "queued")
        .lte("run_at", NOW().isoformat())
        .or_(f"locked_at.is.null,locked_at.lt.{lock_expired_before}")
        .order("run_at", desc=False)
        .limit(limit)
        .execute()
        .data
    )

    picked = []

    for job in candidates:
        updated = (
            sb.table("jobs")
            .update({
                "status": "processing",
                "locked_at": NOW().isoformat(),
                "locked_by": WORKER_ID,
                "attempts": (job.get("attempts") or 0) + 1,
            })
            .eq("id", job["id"])
            .eq("status", "queued")
            .execute()
            .data
        )

        if updated:
            picked.append(updated[0])

    return picked


# =============================
# STATE TRANSITIONS
# =============================

def mark_done(job_id):
    sb.table("jobs").update({
        "status": "done",
        "locked_at": None,
        "locked_by": None,
        "last_error": None,
    }).eq("id", job_id).execute()


def mark_failed(job, err):
    attempts = job.get("attempts") or 1

    if attempts >= MAX_ATTEMPTS:
        sb.table("jobs").update({
            "status": "dead",
            "locked_at": None,
            "locked_by": None,
            "last_error": str(err),
        }).eq("id", job["id"]).execute()
        return

    delay = min(60, 2 ** attempts)  # exponential backoff
    next_run = (NOW() + timedelta(minutes=delay)).isoformat()

    sb.table("jobs").update({
        "status": "queued",
        "run_at": next_run,
        "locked_at": None,
        "locked_by": None,
        "last_error": str(err),
    }).eq("id", job["id"]).execute()


# =============================
# FIILTHY BUSINESS LOGIC
# =============================

def handle_job(job):
    job_type = job.get("type")
    payload = job.get("payload") or {}

    if job_type == "ping":
        print("PONG")
        return

    elif job_type == "scan_site":
        scan_site(payload)

    elif job_type == "find_intent":
        find_intent(payload)

    elif job_type == "match_leads":
        match_leads(payload)

    elif job_type == "send_outreach":
        send_outreach(payload)

    else:
        raise ValueError(f"Unknown job type: {job_type}")


# =============================
# MODULE LOGIC
# =============================

def scan_site(payload):
    site_id = payload["site_id"]

    sb.table("sites").update({
        "scanned_at": NOW().isoformat(),
        "score": 75,
        "keywords": ["saas", "automation"],
        "niche": "b2b",
    }).eq("id", site_id).execute()

    enqueue_job("find_intent", {"site_id": site_id})
    enqueue_job("match_leads", {"site_id": site_id})


def find_intent(payload):
    site_id = payload["site_id"]

    sb.table("intent_events").insert({
        "site_id": site_id,
        "source": "stub",
        "intent_score": 0.71,
        "created_at": NOW().isoformat(),
    }).execute()


def match_leads(payload):
    site_id = payload["site_id"]

    inserted = sb.table("leads").insert({
        "site_id": site_id,
        "handle": "example_user",
        "platform": "reddit",
        "intent_score": 0.8,
        "created_at": NOW().isoformat(),
    }).execute().data

    if inserted:
        enqueue_job("send_outreach", {
            "site_id": site_id,
            "lead_id": inserted[0]["id"]
        })


def send_outreach(payload):
    sb.table("posts").insert({
        "site_id": payload["site_id"],
        "lead_id": payload["lead_id"],
        "content": "Hey! Quick question about your project…",
        "status": "sent_stub",
        "created_at": NOW().isoformat(),
    }).execute()


# =============================
# ENQUEUE HELPER
# =============================

def enqueue_job(job_type, payload, delay_minutes=0):
    sb.table("jobs").insert({
        "status": "queued",
        "type": job_type,
        "payload": payload,
        "attempts": 0,
        "max_attempts": MAX_ATTEMPTS,
        "run_at": (NOW() + timedelta(minutes=delay_minutes)).isoformat(),
    }).execute()


# =============================
# MAIN LOOP
# =============================

def run_forever():
    print(f"[{WORKER_ID}] FIILTHY worker online")

    while True:
        jobs = pick_jobs(limit=BATCH_SIZE)

        for job in jobs:
            try:
                handle_job(job)
                mark_done(job["id"])
            except Exception as e:
                print("Job failed:", e)
                mark_failed(job, e)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_forever()
