"""Supabase client — singleton, Storage uploads, and projects table helpers.

Required env vars (set in HF Space secrets):
    SUPABASE_URL  — e.g. https://xxxx.supabase.co
    SUPABASE_KEY  — service role key (has full storage + table access)

Supabase setup (run once in the SQL Editor):
    create table if not exists jobs (
        id          text primary key,
        status      text not null default 'running',
        progress    integer default 0,
        step        text default '',
        data        jsonb default '{}',
        created_at  timestamptz default now(),
        updated_at  timestamptz default now()
    );

    create table if not exists projects (
        folder_name text primary key,
        title       text,
        topic       text,
        duration    text,
        style       text,
        created_at  timestamptz default now(),
        video_url   text,
        thumb_url   text,
        tags        text[],
        description text
    );

    -- Create the 'videos' storage bucket (public so URLs work without auth)
    insert into storage.buckets (id, name, public)
    values ('videos', 'videos', true)
    on conflict (id) do update set public = true;
"""
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client():
    """Return a Supabase client if SUPABASE_URL + SUPABASE_KEY are set, else None."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        logger.warning("Supabase client init failed: %s", exc)
        return None


# ── Storage ───────────────────────────────────────────────────

def upload_to_storage(local_path: str, remote_path: str, content_type: str = "video/mp4") -> str | None:
    """Upload a file to the 'videos' bucket. Returns its public URL, or None on failure."""
    sb = get_client()
    if not sb:
        return None
    try:
        with open(local_path, "rb") as fh:
            sb.storage.from_("videos").upload(
                path=remote_path,
                file=fh,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        return sb.storage.from_("videos").get_public_url(remote_path)
    except Exception as exc:
        logger.warning("Storage upload failed [%s]: %s", remote_path, exc)
        return None


# ── Projects table ────────────────────────────────────────────

def save_project(row: dict) -> bool:
    """Upsert a project record into the projects table. Returns True on success."""
    sb = get_client()
    if not sb:
        return False
    try:
        tags = row.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        sb.table("projects").upsert({**row, "tags": tags}).execute()
        return True
    except Exception as exc:
        logger.warning("Supabase save_project failed: %s", exc)
        return False


def load_projects() -> list[dict]:
    """Return all project records ordered newest first. Empty list if not configured."""
    sb = get_client()
    if not sb:
        return []
    try:
        resp = sb.table("projects").select("*").order("created_at", desc=True).execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("Supabase load_projects failed: %s", exc)
        return []


def delete_project_data(folder_name: str) -> None:
    """Remove the project row and its Storage files (video + thumbnail)."""
    sb = get_client()
    if not sb:
        return
    try:
        sb.table("projects").delete().eq("folder_name", folder_name).execute()
    except Exception as exc:
        logger.warning("Supabase delete project row failed: %s", exc)
    for fname in ("final_video.mp4", "thumbnail.png"):
        try:
            sb.storage.from_("videos").remove([f"{folder_name}/{fname}"])
        except Exception as exc:
            logger.warning("Storage delete failed [%s/%s]: %s", folder_name, fname, exc)
