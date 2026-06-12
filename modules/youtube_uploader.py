"""YouTube Data API v3 uploader — uploads finished videos as Private drafts.

Free tier: unlimited uploads (subject to daily quota of 10,000 units; one upload ≈ 1600 units).
Requires one-time OAuth consent. After first run, token is cached in projects/yt_token.json.

Setup:
  1. Go to console.cloud.google.com → APIs & Services → Credentials
  2. Create OAuth 2.0 Client ID → Desktop app
  3. Download client_secrets.json and place it next to app.py
  4. First upload opens a browser window for consent; token auto-refreshes after that.
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SECRETS_PATH = Path(__file__).parent.parent / "client_secrets.json"
_TOKEN_PATH   = Path(__file__).parent.parent / "projects" / "yt_token.json"
_SCOPES       = ["https://www.googleapis.com/auth/youtube.upload"]


def is_available() -> bool:
    """True if client_secrets.json exists (key is configured)."""
    return _SECRETS_PATH.exists()


def _get_credentials():
    """Load or refresh OAuth credentials. Opens browser on first run."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError(
            "Missing packages. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )

    creds = None
    if _TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_SECRETS_PATH), _SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_PATH.parent.mkdir(exist_ok=True)
        _TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: str = "",
    privacy: str = "private",
    requires_ai_disclosure: bool = False,
) -> dict:
    """Upload video to YouTube as a Private draft.

    Returns dict with 'video_id' and 'url' on success. When ``requires_ai_disclosure``
    is true, the result also includes a 'disclosure_reminder' — the Data API v3 does NOT
    expose the "altered or synthetic content" toggle, so it must be set in YouTube Studio
    before publishing.

    Raises RuntimeError on failure.
    """
    if not is_available():
        raise RuntimeError("client_secrets.json not found — YouTube upload not configured")

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise RuntimeError(
            "Missing packages. Run: pip install google-api-python-client"
        )

    creds = _get_credentials()

    try:
        youtube = build("youtube", "v3", credentials=creds)
    except Exception as e:
        raise RuntimeError(f"Failed to build YouTube client: {e}")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description[:5000],
            "tags":        tags[:500],
            "categoryId":  "27",  # Education
        },
        "status": {
            "privacyStatus":          privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,  # 5 MB chunks
    )

    logger.info("Uploading to YouTube: %s", title[:60])
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("Upload progress: %d%%", int(status.progress() * 100))

    video_id = response.get("id", "")
    logger.info("Upload complete: video_id=%s", video_id)

    # Set thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path) and video_id:
        try:
            from googleapiclient.http import MediaFileUpload as MFU
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MFU(thumbnail_path, mimetype="image/png"),
            ).execute()
            logger.info("Thumbnail set for video_id=%s", video_id)
        except Exception as e:
            logger.warning("Thumbnail upload failed: %s", e)

    result = {
        "video_id": video_id,
        "url":      f"https://www.youtube.com/watch?v={video_id}",
        "status":   privacy,
    }

    if requires_ai_disclosure:
        result["disclosure_reminder"] = (
            "AI disclosure needed: this video's visuals look realistic. Before publishing, "
            "open YouTube Studio -> Content -> this video -> Details -> Show more -> "
            "'Altered or synthetic content', and set it to YES."
        )
        logger.info("AI disclosure reminder attached for video_id=%s", video_id)

    return result
