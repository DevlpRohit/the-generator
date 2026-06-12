"""Job store: Supabase when SUPABASE_URL/KEY are set, SQLite fallback for local dev.

The public API (init_db, create_job, update_job, get_job, sanitize_job,
list_recent_jobs) is identical to the old SQLite-only version so nothing
else in the codebase needs to change.

threading.Event objects (resume_event, cancel_event) are never persisted —
they live in the in-memory _EVENTS dict regardless of backend.
"""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "projects" / "jobs.db"
_lock = threading.Lock()
_EVENTS: dict[str, dict] = {}


def _sb():
    try:
        from modules.supabase_client import get_client
        return get_client()
    except Exception:
        return None


# ── SQLite helpers ────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _sql_init() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                status      TEXT NOT NULL DEFAULT 'running',
                progress    INTEGER DEFAULT 0,
                step        TEXT DEFAULT '',
                data        TEXT DEFAULT '{}',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.commit()


def _sql_create(job_id, status, progress, step, data):
    now = datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO jobs "
            "(id, status, progress, step, data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, status, progress, step,
             json.dumps(data, ensure_ascii=False), now, now),
        )
        conn.commit()


def _sql_update(job_id, status, progress, step, extra):
    now = datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return
        cur = json.loads(row["data"] or "{}")
        cur.update(extra)
        conn.execute(
            "UPDATE jobs SET status=?, progress=?, step=?, data=?, updated_at=? WHERE id=?",
            (
                status   if status   is not None else row["status"],
                progress if progress is not None else row["progress"],
                step     if step     is not None else row["step"],
                json.dumps(cur, ensure_ascii=False), now, job_id,
            ),
        )
        conn.commit()


def _sql_get(job_id) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d.update(json.loads(d.pop("data", "{}") or "{}"))
    return d


def _sql_list(limit) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d.update(json.loads(d.pop("data", "{}") or "{}"))
        result.append(d)
    return result


# ── Supabase helpers ──────────────────────────────────────────

def _sb_create(job_id, status, progress, step, data):
    now = datetime.now(timezone.utc).isoformat()
    _sb().table("jobs").upsert({
        "id": job_id, "status": status, "progress": progress,
        "step": step, "data": data, "created_at": now, "updated_at": now,
    }).execute()


def _sb_update(job_id, status, progress, step, extra):
    sb = _sb()
    now = datetime.now(timezone.utc).isoformat()
    resp = sb.table("jobs").select("data").eq("id", job_id).maybe_single().execute()
    if not resp or not resp.data:
        return
    cur = resp.data.get("data") or {}
    if isinstance(cur, str):
        cur = json.loads(cur)
    cur.update(extra)
    patch = {"data": cur, "updated_at": now}
    if status   is not None: patch["status"]   = status
    if progress is not None: patch["progress"] = progress
    if step     is not None: patch["step"]     = step
    sb.table("jobs").update(patch).eq("id", job_id).execute()


def _sb_get(job_id) -> dict | None:
    resp = _sb().table("jobs").select("*").eq("id", job_id).maybe_single().execute()
    if not resp or not resp.data:
        return None
    d = dict(resp.data)
    raw = d.pop("data", {}) or {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    d.update(raw)
    return d


def _sb_list(limit) -> list[dict]:
    resp = _sb().table("jobs").select("*").order("updated_at", desc=True).limit(limit).execute()
    result = []
    for row in (resp.data or []):
        d = dict(row)
        raw = d.pop("data", {}) or {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        d.update(raw)
        result.append(d)
    return result


# ── Public API ────────────────────────────────────────────────

def init_db() -> None:
    if not _sb():
        _sql_init()


def create_job(job_id: str, initial: dict) -> None:
    events, clean = {}, {}
    for k, v in initial.items():
        (events if isinstance(v, threading.Event) else clean)[k] = v
    with _lock:
        _EVENTS[job_id] = events

    status   = clean.pop("status",   "running")
    progress = clean.pop("progress", 0)
    step     = clean.pop("step",     "")

    try:
        if _sb():
            _sb_create(job_id, status, progress, step, clean)
        else:
            _sql_create(job_id, status, progress, step, clean)
    except Exception:
        pass


def update_job(job_id: str, **kwargs) -> None:
    status   = kwargs.pop("status",   None)
    progress = kwargs.pop("progress", None)
    step     = kwargs.pop("step",     None)

    for k, v in list(kwargs.items()):
        if isinstance(v, threading.Event):
            with _lock:
                _EVENTS.setdefault(job_id, {})[k] = v
            del kwargs[k]

    try:
        if _sb():
            _sb_update(job_id, status, progress, step, kwargs)
        else:
            _sql_update(job_id, status, progress, step, kwargs)
    except Exception:
        pass


def get_job(job_id: str) -> dict | None:
    try:
        result = _sb_get(job_id) if _sb() else _sql_get(job_id)
    except Exception:
        result = None
    if result is None:
        return None
    with _lock:
        result.update(_EVENTS.get(job_id, {}))
    return result


def sanitize_job(job: dict) -> dict:
    skip = {"resume_event", "cancel_event", "created_at", "updated_at"}
    return {k: v for k, v in job.items()
            if k not in skip and not isinstance(v, threading.Event)}


def list_recent_jobs(limit: int = 50) -> list[dict]:
    try:
        return _sb_list(limit) if _sb() else _sql_list(limit)
    except Exception:
        return []
