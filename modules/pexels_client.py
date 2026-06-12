"""Pexels free stock video/photo client.

Free tier: 200 requests/hour, no watermark.
Get key at https://www.pexels.com/api/
Set PEXELS_API_KEY in .env or as env var.
"""
import logging
import os
import re
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

_PEXELS_VIDEO_API = "https://api.pexels.com/videos/search"
_PEXELS_PHOTO_API = "https://api.pexels.com/v1/search"


def _key() -> str:
    return os.environ.get("PEXELS_API_KEY", "")


def is_available() -> bool:
    return bool(_key())


def search_video(query: str, orientation: str = "landscape", per_page: int = 5) -> list[dict]:
    """Return list of video result dicts from Pexels."""
    k = _key()
    if not k:
        return []
    try:
        r = requests.get(
            _PEXELS_VIDEO_API,
            headers={"Authorization": k},
            params={"query": query[:100], "orientation": orientation,
                    "per_page": per_page, "size": "medium"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("videos", [])
        logger.warning("Pexels video search failed status=%d", r.status_code)
    except Exception as e:
        logger.warning("Pexels video search error: %s", e)
    return []


def download_video_clip(video: dict, output_path: str,
                        preferred_w: int = 1280, preferred_h: int = 720) -> bool:
    """Download best-matching video file from a Pexels video result dict."""
    files = video.get("video_files", [])
    if not files:
        return False

    # Pick closest resolution to preferred without going under (HD preferred)
    def score(f):
        fw = f.get("width", 0)
        fh = f.get("height", 0)
        diff = abs(fw - preferred_w) + abs(fh - preferred_h)
        return diff

    files_mp4 = [f for f in files if (f.get("file_type") or "").startswith("video/mp4")]
    if not files_mp4:
        files_mp4 = files
    best = min(files_mp4, key=score)

    url = best.get("link", "")
    if not url:
        return False

    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            size = os.path.getsize(output_path)
            if size > 10_000:
                logger.info("Pexels video OK: %s bytes=%d", Path(output_path).name, size)
                return True
            os.remove(output_path)
    except Exception as e:
        logger.warning("Pexels download error: %s", e)
        try: os.remove(output_path)
        except Exception: pass
    return False


def search_photo(query: str, orientation: str = "landscape") -> list[dict]:
    """Return list of photo result dicts from Pexels."""
    k = _key()
    if not k:
        return []
    try:
        r = requests.get(
            _PEXELS_PHOTO_API,
            headers={"Authorization": k},
            params={"query": query[:100], "orientation": orientation, "per_page": 5},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("photos", [])
        logger.warning("Pexels photo search failed status=%d", r.status_code)
    except Exception as e:
        logger.warning("Pexels photo search error: %s", e)
    return []


def download_photo(photo: dict, output_path: str, size: str = "large2x") -> bool:
    """Download a Pexels photo at requested size."""
    src = photo.get("src", {})
    url = src.get(size) or src.get("large") or src.get("medium") or ""
    if not url:
        return False
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and len(r.content) > 8000:
            with open(output_path, "wb") as f:
                f.write(r.content)
            from PIL import Image
            try:
                Image.open(output_path).verify()
                return True
            except Exception:
                try: os.remove(output_path)
                except Exception: pass
    except Exception as e:
        logger.warning("Pexels photo download error: %s", e)
    return False
