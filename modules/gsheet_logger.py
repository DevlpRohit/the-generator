"""Google Sheets project logger (gspread + a Google service account).

ONE-TIME SETUP
  1. Google Cloud Console (console.cloud.google.com) -> create/pick a project.
  2. APIs & Services -> Library -> enable **Google Sheets API** (and Google Drive API).
  3. APIs & Services -> Credentials -> Create credentials -> **Service account**.
     Then on that service account: Keys -> Add key -> JSON -> download it.
  4. Save that file as  auto_video/gsheets_credentials.json  (next to app.py).
  5. Create a Google Sheet. Open the JSON and copy the "client_email"
     (looks like name@project.iam.gserviceaccount.com) and **Share** the sheet
     with that email as **Editor**.
  6. Put the sheet ID in auto_video/.env :   GSHEET_ID=<the long id from the URL>
     (URL form  https://docs.google.com/spreadsheets/d/<THIS_PART>/edit  — or set
     GSHEET_URL to the full URL and the id is parsed out).

The app uses Google Sheets when this is configured, and falls back to Excel otherwise.
"""
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_CREDS_PATH = Path(__file__).parent.parent / "gsheets_credentials.json"

# Same columns as the Excel log, so the two are interchangeable.
HEADERS = [
    "Date Created", "Topic", "Best Title", "Duration", "Quality",
    "Style", "Voice", "Content Type", "Video File Path", "Thumbnail Path",
    "Tags (CSV)", "Description (200 chars)", "Upload Status",
    "YouTube URL", "Views (7-day)", "Revenue ($)",
]


def _sheet_id() -> str:
    sid = os.environ.get("GSHEET_ID", "").strip()
    if sid:
        return sid
    url = os.environ.get("GSHEET_URL", "").strip()
    if "/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return url  # allow a bare id in GSHEET_URL too


def is_available() -> bool:
    """True only when both the service-account file and a sheet id are present."""
    return _CREDS_PATH.exists() and bool(_sheet_id())


def status() -> dict:
    return {
        "credentials": _CREDS_PATH.exists(),
        "sheet_id": bool(_sheet_id()),
        "ready": is_available(),
    }


def _worksheet():
    import gspread
    gc = gspread.service_account(filename=str(_CREDS_PATH))
    ws = gc.open_by_key(_sheet_id()).sheet1
    # Ensure a header row exists once.
    try:
        if not ws.row_values(1):
            ws.append_row(HEADERS)
    except Exception:
        pass
    return ws


def log_project(project: dict) -> bool:
    """Append one video's row to the Google Sheet (newest first). Returns True on
    success, False if not configured or on error (caller can fall back to Excel)."""
    if not is_available():
        return False
    try:
        ws = _worksheet()
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            project.get("topic", ""),
            project.get("best_title", ""),
            project.get("duration", ""),
            project.get("quality", ""),
            project.get("style", ""),
            project.get("voice", ""),
            project.get("content_type", ""),
            project.get("video_path", ""),
            project.get("thumbnail_path", ""),
            ", ".join(project.get("tags", [])[:20]),
            (project.get("description", ""))[:200],
            "", "", "", "",   # Upload Status / URL / Views / Revenue — manual
        ]
        ws.insert_row(row, index=2, value_input_option="USER_ENTERED")
        logger.info("Logged project to Google Sheet")
        return True
    except Exception as e:
        logger.warning("Google Sheets log failed: %s", e)
        return False
