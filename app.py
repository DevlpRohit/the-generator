"""Master AI Video Maker — Flask application."""
import io
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

# UTF-8 safe output on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

# Load .env so GEMINI_API_KEY (and any future keys) are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from flask import (
    Flask, render_template, request, jsonify,
    Response, send_file, abort,
)

from config import (
    BASE_DIR, PROJECTS_DIR, VOICES, PALETTES,
    CONTENT_TYPES, ANIMATIONS, MUSIC_MOODS, NICHES, RISKY_NICHES,
    RESOLUTIONS, SECRET_KEY,
    VOICE_SPEEDS, SUBTITLE_STYLES,
    CLONED_VOICE_LABEL, VOICE_PROFILE_PATH,
    SUB_NICHES,
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialise SQLite job store
from modules.job_store import init_db, create_job, update_job, get_job, sanitize_job
init_db()


# ── Helpers ───────────────────────────────────────────────────

def _safe_folder(topic: str) -> str:
    safe = re.sub(r"[^a-z0-9_]", "_", topic.lower().strip())[:50]
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe}_{ts}"


def _upd(job_id: str, **kw) -> None:
    update_job(job_id, **kw)


class JobCancelled(Exception):
    """Raised inside the pipeline when the user cancels the job."""


def _check_cancel(job_id: str) -> None:
    """Call between pipeline steps. Raises JobCancelled if the user hit Stop."""
    job = get_job(job_id)
    if job and job.get("cancel_event") and job["cancel_event"].is_set():
        raise JobCancelled()


# ── Pipeline helpers ──────────────────────────────────────────

def _save_script_history(project_dir, version_name: str, paragraphs: list[str]) -> None:
    """Append a script version snapshot to script_history.json."""
    history_path = Path(project_dir) / "script_history.json"
    try:
        history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    except Exception:
        history = []
    history.append({
        "version":    version_name,
        "timestamp":  datetime.now().isoformat(),
        "paragraphs": paragraphs,
    })
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def _make_shorts_version(input_path: str, output_path: str) -> None:
    """Center-crop a landscape MP4 to 9:16 for YouTube Shorts using MoviePy."""
    try:
        import imageio_ffmpeg
        os.environ.setdefault("FFMPEG_BINARY", imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(input_path)
    w, h = clip.w, clip.h
    # For 16:9 → 9:16: crop to a 9:16 window centered horizontally
    target_w = int(h * 9 / 16)
    if target_w > w:
        # Already portrait-ish — just export as-is resized
        target_w = w
    x1 = (w - target_w) // 2
    cropped = clip.crop(x1=x1, x2=x1 + target_w)
    # Resize to standard Shorts resolution 1080x1920
    from moviepy.editor import vfx
    final = cropped.resize((1080, 1920))
    final.write_videofile(
        output_path, fps=30, codec="libx264",
        audio_codec="aac", bitrate="6M", preset="medium",
        verbose=False, logger=None,
    )
    clip.close()
    cropped.close()
    final.close()


def _split_long_paragraphs(
    paragraphs: list[str],
    visual_plan: list[str],
    word_threshold: int = 45,
) -> tuple[list[str], list[str]]:
    """Split paragraphs longer than word_threshold at a sentence boundary.
    Each half gets its own scene image and audio clip, keeping visual variety high.
    """
    import re
    out_paras: list[str] = []
    out_plan:  list[str] = []

    for i, para in enumerate(paragraphs):
        words = para.split()
        hint  = visual_plan[i] if i < len(visual_plan) else ""
        if len(words) <= word_threshold:
            out_paras.append(para)
            out_plan.append(hint)
            continue

        # Split at nearest sentence boundary to mid-point
        mid = len(words) // 2
        sentences = re.split(r"(?<=[.!?])\s+", para)
        if len(sentences) < 2:
            # No sentence boundary — force split at word mid
            out_paras.extend([
                " ".join(words[:mid]),
                " ".join(words[mid:]),
            ])
            out_plan.extend([hint, hint])
        else:
            # Find sentence split closest to mid
            best_split = 1
            best_dist  = abs(len(" ".join(sentences[:1]).split()) - mid)
            for s in range(2, len(sentences)):
                dist = abs(len(" ".join(sentences[:s]).split()) - mid)
                if dist < best_dist:
                    best_dist, best_split = dist, s
            out_paras.extend([
                " ".join(sentences[:best_split]),
                " ".join(sentences[best_split:]),
            ])
            out_plan.extend([hint, hint])

    return out_paras, out_plan


# ── Pipeline ──────────────────────────────────────────────────

def run_pipeline(job_id: str, settings: dict) -> None:
    topic        = settings["topic"]
    quality      = settings.get("quality", "720p")
    dur_min      = max(0, int(settings.get("duration_min", 2) or 2))
    dur_sec      = max(0, min(59, int(settings.get("duration_sec", 0) or 0)))
    total_secs   = max(10, dur_min * 60 + dur_sec)
    target_words = max(20, round(total_secs * 2.5))
    duration_label = f"{dur_min}m{dur_sec:02d}s"
    aspect_ratio = settings.get("aspect_ratio", "16:9")
    content_type = settings.get("content_type", "Educational")
    style        = settings.get("style", "Cinematic")
    voice        = settings.get("voice", "Male US")
    animation    = settings.get("animation", "Fade Transitions")
    music_mood   = settings.get("music_mood", "None")
    image_provider  = settings.get("image_provider", "pollinations")
    voice_rate      = VOICE_SPEEDS.get(settings.get("voice_speed", "Normal"), "+0%")
    subtitle_preset = settings.get("subtitle_preset", "Clean White")

    folder_name  = _safe_folder(topic)
    project_dir  = PROJECTS_DIR / folder_name
    project_dir.mkdir(parents=True, exist_ok=True)

    _upd(job_id, project_dir=str(project_dir), folder_name=folder_name)

    try:
        # 1 ── Research (optional)
        _check_cancel(job_id)
        _upd(job_id, step="Researching trends...", progress=10)
        research_data = {}
        viral_context: dict | None = None
        if settings.get("auto_research") == "on":
            try:
                from modules.trend_researcher import research_topic
                research_data = research_topic(topic)
                if research_data.get("trending_topics"):
                    topic = research_data["trending_topics"][0]
                    _upd(job_id, topic=topic)
                # Pick viral hook for the chosen topic
                hooks = research_data.get("viral_hooks", [])
                if hooks and isinstance(hooks, list):
                    viral_context = hooks[0] if isinstance(hooks[0], dict) else None
            except Exception as e:
                logging.warning("Trend research failed: %s", e)

        # 2 ── Script
        _check_cancel(job_id)
        _upd(job_id, step="Writing script...", progress=20)
        from modules.script_generator import generate_script
        script_text, paragraphs, visual_plan = generate_script(
            topic, content_type, total_secs, target_words, duration_label,
            viral_context=viral_context,
        )
        (project_dir / "script.txt").write_text(script_text, encoding="utf-8")

        # Save Gemini draft to script history
        _save_script_history(project_dir, "gemini_draft", paragraphs)

        # 2a ── Inject the user's own commentary as a scene (human perspective) ──
        commentary = (settings.get("commentary") or "").strip()
        if commentary:
            pos = 1 if len(paragraphs) >= 1 else 0   # right after the hook
            paragraphs.insert(pos, commentary)
            hint = " ".join(commentary.split()[:6]) or f"{topic} personal reflection"
            visual_plan.insert(pos, hint)
            _save_script_history(project_dir, "human_commentary", paragraphs)

        # Split long paragraphs into sub-scenes for visual variety (>40 words)
        paragraphs, visual_plan = _split_long_paragraphs(paragraphs, visual_plan)

        # 2b ── Review/edit pause (mandatory under Monetization-Safe Mode) ──────
        # Safe Mode forces the human-review checkpoint so videos aren't shipped raw
        # from the AI — the key safeguard against YouTube's "inauthentic content" rule.
        safe_mode = settings.get("safe_mode") == "on"
        settings["edited_by_human"] = False
        if settings.get("pause_review") == "on" or safe_mode:
            import hashlib
            orig_hash = hashlib.md5(
                "\n".join(p.strip() for p in paragraphs).encode("utf-8")
            ).hexdigest()
            _upd(job_id, status="paused_script",
                 step="Paused — review and edit the script below, then click Continue.",
                 progress=25,
                 paragraphs=list(paragraphs),
                 orig_hash=orig_hash,
                 safe_mode=safe_mode)
            job_now = get_job(job_id)
            resume_event = job_now.get("resume_event") if job_now else None
            if resume_event:
                # Wait, checking cancel every 0.5s
                while not resume_event.wait(timeout=0.5):
                    _check_cancel(job_id)
                _check_cancel(job_id)
                # Caller has overwritten paragraphs in the job store
                job_now = get_job(job_id)
                edited = (job_now.get("paragraphs") if job_now else None) or paragraphs
                if edited and isinstance(edited, list):
                    paragraphs = [p.strip() for p in edited if p and str(p).strip()]
                    script_text = "\n\n".join(paragraphs)
                    (project_dir / "script.txt").write_text(script_text, encoding="utf-8")
                    # Trim visual_plan to match edited paragraph count
                    visual_plan = visual_plan[:len(paragraphs)]
                    # Save user-edited version to history
                    _save_script_history(project_dir, "user_edited", paragraphs)
                settings["edited_by_human"] = bool(job_now.get("edited_by_human")) if job_now else False
            _upd(job_id, status="running",
                 step="Continuing with edited script...", progress=28)

        # 2c ── Content analysis — auto-select voice pacing, subtitle style, music
        _check_cancel(job_id)
        _upd(job_id, step="Analysing content tone and pacing...", progress=29)
        from modules.content_analyzer import analyze_content
        content_analysis = analyze_content(
            topic=topic,
            content_type=content_type,
            style=style,
            paragraphs=paragraphs,
            current_music_mood=music_mood,
        )
        voice_rates_per_para = content_analysis["voice_rate_per_paragraph"]

        # Auto subtitle: override if user left it on "Auto (AI Picks)"
        if subtitle_preset in ("Auto (AI Picks)", "Auto", ""):
            subtitle_preset = content_analysis["subtitle_preset"]
            _upd(job_id, subtitle_preset=subtitle_preset)

        # Auto music: override if user left it on "None" or "Auto"
        if music_mood in ("None", "Auto", ""):
            music_mood = content_analysis["music_mood"]

        logging.info(
            "Content analysis — subtitle=%s, music=%s, rates=%s",
            subtitle_preset, music_mood, voice_rates_per_para,
        )

        # 3 ── Audio narration (parallel with images) — 30-45%
        # Audio runs in a background thread; images run sequentially in main thread.
        # Both finish before assembly. Cuts ~30-40% off total time on longer videos.
        _check_cancel(job_id)
        # Human voiceover (if uploaded) replaces TTS — strongest human-input signal.
        voiceover_path = settings.get("voiceover_path") or ""
        use_voiceover  = bool(voiceover_path) and os.path.exists(voiceover_path)
        settings["human_voiceover"] = use_voiceover

        # Cloned voice (the user's own voice via Chatterbox) — commercial-safe.
        use_cloned = False
        if not use_voiceover and voice == CLONED_VOICE_LABEL:
            from modules import voice_clone
            if voice_clone.is_available() and VOICE_PROFILE_PATH.exists():
                use_cloned = True
            else:
                logging.warning("Cloned voice selected but engine/profile missing — using TTS.")
        settings["cloned_voice"] = use_cloned

        _upd(job_id, step="Cloning your voice..." if use_cloned
                          else "Preparing your voiceover..." if use_voiceover
                          else "Generating voice audio...", progress=30)
        from modules.audio_generator import (
            generate_narration_per_paragraph, prepare_human_voiceover,
            generate_cloned_narration_per_paragraph,
        )

        _audio_result: dict = {}
        _audio_exc: list = []

        def _audio_thread():
            def _audio_cb(done, total, label):
                pct = 30 + int(12 * done / max(total, 1))
                _upd(job_id, step=label, progress=pct)

            try:
                if use_voiceover:
                    result = prepare_human_voiceover(
                        voiceover_path, paragraphs, str(project_dir),
                        progress_cb=_audio_cb,
                    )
                elif use_cloned:
                    result = generate_cloned_narration_per_paragraph(
                        paragraphs, str(VOICE_PROFILE_PATH), str(project_dir),
                        progress_cb=_audio_cb,
                    )
                else:
                    result = generate_narration_per_paragraph(
                        paragraphs, voice, str(project_dir),
                        progress_cb=_audio_cb,
                        voice_rate=voice_rate,
                        voice_rates=voice_rates_per_para,
                    )
                _audio_result["value"] = result
            except Exception as exc:
                _audio_exc.append(exc)

        audio_thread = threading.Thread(target=_audio_thread, daemon=True)
        audio_thread.start()

        _check_cancel(job_id)
        # 4 ── Scene images (sequential, Pollinations rate-limited) — 42-78%
        _upd(job_id, step="Creating AI scene images...", progress=42)
        from modules.scene_generator import generate_scenes

        def _scene_cb(done, total, label):
            _check_cancel(job_id)
            pct = 42 + int(36 * done / max(total, 1))
            _upd(job_id, step=label, progress=pct)

        # Hybrid visuals: real Pexels VIDEO B-roll (when "Pexels" source is chosen)
        # else cinematic AI images. Falls back to AI image per-scene when no clip fits.
        from modules.scene_generator import generate_scene_assets
        scene_paths = generate_scene_assets(
            paragraphs, style, aspect_ratio, quality, topic, str(project_dir),
            image_provider=image_provider,
            visual_plan=visual_plan,
            progress_cb=_scene_cb,
            use_broll=(image_provider == "pexels"),
        )

        # Wait for audio thread to finish before assembly
        _upd(job_id, step="Waiting for audio to complete...", progress=79)
        audio_thread.join()
        if _audio_exc:
            raise _audio_exc[0]

        narration_path, scene_audio_paths, scene_durations, word_timings = _audio_result["value"]
        audio_duration = sum(scene_durations)

        _check_cancel(job_id)
        # 4b ── Background music — 80%
        _upd(job_id, step="Generating background music...", progress=80)
        music_path = ""
        if music_mood != "None":
            from modules.audio_generator import generate_music
            music_path = str(project_dir / "background_music.mp3")
            generate_music(music_mood, audio_duration, music_path)

        _check_cancel(job_id)
        # 6 ── Assemble video (one audio clip per image, perfect sync)
        _upd(job_id, step="Encoding final video (this is the longest step)...",
             progress=83)
        from modules.video_assembler import assemble_video
        video_path = str(project_dir / "final_video.mp4")

        # Step-level retry: try up to 2 times on assembly failure
        for _attempt in range(2):
            try:
                assemble_video(
                    scene_paths, scene_audio_paths, music_path,
                    animation, video_path,
                    word_timings=word_timings,
                    style=style,
                    subtitle_preset=subtitle_preset,
                    paragraphs=paragraphs,
                    target_size=RESOLUTIONS.get(aspect_ratio, {}).get(quality),
                )
                break
            except Exception as e:
                if _attempt == 0:
                    logging.warning("Assembly attempt 1 failed (%s), retrying without subtitles", e)
                    word_timings = None  # retry without subtitle burn to avoid fl() issues
                else:
                    raise

        # 6b ── Shorts auto-resize (optional) — 89%
        shorts_url = ""
        if settings.get("generate_shorts") == "on" and aspect_ratio != "9:16":
            _upd(job_id, step="Creating YouTube Shorts version (9:16)...", progress=88)
            try:
                shorts_path = str(project_dir / "shorts_video.mp4")
                _make_shorts_version(video_path, shorts_path)
                if os.path.exists(shorts_path) and os.path.getsize(shorts_path) > 50_000:
                    shorts_url = f"/video/{folder_name}/shorts_video.mp4"
                    logging.info("Shorts version created: %s", shorts_path)
            except Exception as e:
                logging.warning("Shorts resize failed: %s", e)

        # 7 ── Thumbnail
        _upd(job_id, step="Creating thumbnail...", progress=90)
        from modules.thumbnail_generator import generate_thumbnail
        thumb_path = str(project_dir / "thumbnail.png")
        # Thumbnail needs a still: prefer an image scene; if all scenes are B-roll
        # video, grab a frame from the first clip.
        first_scene = next((p for p in scene_paths if not p.lower().endswith(".mp4")), "")
        if not first_scene and scene_paths:
            try:
                from moviepy.editor import VideoFileClip
                frame_png = str(project_dir / "_thumb_frame.png")
                vc = VideoFileClip(scene_paths[0], audio=False)
                vc.save_frame(frame_png, t=min(1.0, (vc.duration or 1) / 2))
                vc.close()
                first_scene = frame_png
            except Exception as e:
                logging.warning("Thumbnail frame grab failed: %s", e)
        generate_thumbnail(topic, style, aspect_ratio, thumb_path,
                           scene_image_path=first_scene)

        # 8 ── Metadata
        _upd(job_id, step="Generating metadata + logging to Excel...", progress=95)
        from modules.metadata_generator import generate_metadata
        meta = generate_metadata(
            topic, paragraphs,
            str(project_dir / "metadata.json"),
            total_seconds=total_secs,
            duration_label=duration_label,
            style=style,
            synthetic_voice=settings.get("cloned_voice", False),
        )

        # Save settings (drop the staging path; keep the human_voiceover flag) and
        # clean up the staged upload now that audio_narration.mp3 is the canonical copy.
        staged = settings.pop("voiceover_path", "")
        if staged:
            try:
                os.remove(staged)
            except Exception:
                pass
        (project_dir / "settings.json").write_text(
            json.dumps({**settings, "topic": topic}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 9 ── Upload video + thumbnail to Supabase Storage (cloud download for any user)
        _upd(job_id, step="Uploading to cloud storage...", progress=96)
        from modules.supabase_client import upload_to_storage, save_project
        final_video_url = f"/video/{folder_name}/final_video.mp4"
        final_thumb_url = f"/video/{folder_name}/thumbnail.png"

        sb_video = upload_to_storage(
            video_path, f"{folder_name}/final_video.mp4", "video/mp4"
        )
        if sb_video:
            final_video_url = sb_video

        sb_thumb = upload_to_storage(
            thumb_path, f"{folder_name}/thumbnail.png", "image/png"
        )
        if sb_thumb:
            final_thumb_url = sb_thumb

        # 10 ── Save project metadata to Supabase (persists across server restarts)
        save_project({
            "folder_name": folder_name,
            "title":       meta["best_title"],
            "topic":       topic,
            "duration":    duration_label,
            "style":       style,
            "video_url":   final_video_url,
            "thumb_url":   final_thumb_url,
            "tags":        meta.get("tags", []),
            "description": meta.get("description", ""),
        })

        # 11 ── Log the project — Google Sheets if configured, else Excel
        log_row = {
            "topic":          topic,
            "best_title":     meta["best_title"],
            "duration":       duration_label,
            "quality":        quality,
            "style":          style,
            "voice":          voice,
            "content_type":   content_type,
            "video_path":     final_video_url,
            "thumbnail_path": final_thumb_url,
            "tags":           meta["tags"],
            "description":    meta["description"],
        }
        logged = False
        try:
            from modules.gsheet_logger import log_project as gsheet_log
            logged = gsheet_log(log_row)
        except Exception as e:
            logging.warning("Google Sheets log error: %s", e)
        if not logged:
            try:
                from modules.excel_logger import log_project as excel_log
                excel_log(log_row)
            except Exception as e:
                logging.warning("Excel log failed: %s", e)

        _upd(
            job_id,
            status="done", step="Done!", progress=100,
            video_url=final_video_url,
            thumbnail_url=final_thumb_url,
            shorts_url=shorts_url,
            title=meta["best_title"],
            title_options=meta["title_options"],
            description=meta["description"],
            tags=meta["tags"],
            folder_name=folder_name,
            requires_ai_disclosure=meta.get("requires_ai_disclosure", True),
        )

    except JobCancelled:
        logging.info("Pipeline cancelled by user: job=%s", job_id)
        _upd(job_id, status="cancelled", step="Cancelled by user", progress=0)
    except Exception as exc:
        import traceback
        logging.error("Pipeline error job=%s\n%s", job_id, traceback.format_exc())
        _upd(job_id, status="error", step="Failed", error=str(exc))


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    # Offer the cloned voice only when the engine is installed and a profile exists.
    voice_list = list(VOICES.keys())
    try:
        from modules import voice_clone
        if voice_clone.is_available() and VOICE_PROFILE_PATH.exists():
            voice_list = [CLONED_VOICE_LABEL] + voice_list
    except Exception:
        pass
    return render_template(
        "index.html",
        voices=voice_list,
        voice_speed_options=[
            ("Slow (-20%)", "Slow (-20%) — Documentary"),
            ("Normal", "Normal"),
            ("Fast (+15%)", "Fast (+15%)"),
        ],
        subtitle_preset_options=[
            ("Auto (AI Picks)", "Auto (AI Picks) — recommended"),
            ("Clean White", "Clean White"),
            ("Bold Yellow", "Bold Yellow (TikTok Style)"),
            ("Neon Glow", "Neon Glow"),
            ("Minimal", "Minimal"),
        ],
        styles=list(PALETTES.keys()),
        content_types=CONTENT_TYPES,
        animations=ANIMATIONS,
        music_moods=MUSIC_MOODS,
        aspect_ratios=list(RESOLUTIONS.keys()),
        qualities=["360p", "480p", "720p", "1080p", "4K"],
        niches=NICHES,
        risky_niches=RISKY_NICHES,
        sub_niches=SUB_NICHES,
        pexels_configured=bool(os.environ.get("PEXELS_API_KEY", "").strip()),
        gemini_configured=bool(os.environ.get("GEMINI_API_KEY", "").strip()),
    )


_QUEUE: list[dict] = []   # [{"job_id": ..., "settings": ...}]
_QUEUE_LOCK = threading.Lock()
_QUEUE_RUNNING = threading.Event()


def _queue_worker():
    """Background thread: drain the job queue one job at a time."""
    while True:
        with _QUEUE_LOCK:
            if not _QUEUE:
                _QUEUE_RUNNING.clear()
                return
            item = _QUEUE.pop(0)

        _QUEUE_RUNNING.set()
        run_pipeline(item["job_id"], item["settings"])

        with _QUEUE_LOCK:
            if not _QUEUE:
                _QUEUE_RUNNING.clear()
                return


def _enqueue(job_id: str, settings: dict) -> None:
    """Add job to queue and start the worker thread if not already running."""
    with _QUEUE_LOCK:
        _QUEUE.append({"job_id": job_id, "settings": settings})

    if not _QUEUE_RUNNING.is_set():
        _QUEUE_RUNNING.set()
        t = threading.Thread(target=_queue_worker, daemon=True)
        t.start()


@app.route("/generate", methods=["POST"])
def generate():
    job_id   = str(uuid.uuid4())[:8]
    settings = request.form.to_dict()

    # Optional human voiceover upload (strongest human-input signal). Saved to a
    # staging path now because the pipeline runs in a thread after the request ends.
    vf = request.files.get("voiceover")
    if vf and vf.filename:
        ext = os.path.splitext(vf.filename)[1].lower()
        if ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"):
            updir = PROJECTS_DIR / "_uploads"
            updir.mkdir(exist_ok=True)
            dest = updir / f"{job_id}{ext}"
            try:
                vf.save(str(dest))
                settings["voiceover_path"] = str(dest)
            except Exception as e:
                logging.warning("Voiceover upload failed to save: %s", e)
        else:
            return jsonify({"error": f"Unsupported audio format '{ext}'. Use mp3, wav, m4a, aac, ogg, or flac."}), 400

    if not settings.get("topic", "").strip() and settings.get("auto_research") != "on":
        return jsonify({"error": "Topic is required"}), 400

    if not settings.get("topic", "").strip():
        settings["topic"] = "trending topic"

    queue_mode = settings.get("queue_mode") == "on"

    create_job(job_id, {
        "status":   "queued" if (queue_mode and _QUEUE_RUNNING.is_set()) else "running",
        "progress": 0,
        "step":     "Queued — waiting for current video to finish..." if (queue_mode and _QUEUE_RUNNING.is_set()) else "Starting pipeline...",
        "error":    None,
        "topic":    settings["topic"],
        "resume_event": threading.Event(),
        "cancel_event": threading.Event(),
        "paragraphs": [],
    })

    if queue_mode:
        _enqueue(job_id, settings)
    else:
        t = threading.Thread(target=run_pipeline, args=(job_id, settings), daemon=True)
        t.start()

    queue_pos = len(_QUEUE) if queue_mode else 0
    return jsonify({"job_id": job_id, "queue_position": queue_pos})


@app.route("/queue")
def queue_status():
    """Return current queue contents."""
    with _QUEUE_LOCK:
        items = [{"job_id": q["job_id"], "topic": q["settings"].get("topic", "")}
                 for q in _QUEUE]
    return jsonify({"queue": items, "running": _QUEUE_RUNNING.is_set()})


@app.route("/job/<job_id>/resume", methods=["POST"])
def job_resume(job_id: str):
    """Resume a paused job with edited paragraphs."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    if job.get("status") != "paused_script":
        return jsonify({"error": f"job is not paused (status={job.get('status')})"}), 400

    body  = request.json or {}
    edits = body.get("paragraphs")
    force = bool(body.get("force"))
    cleaned = ([str(p).strip() for p in edits if str(p or "").strip()]
               if isinstance(edits, list) else [])

    # Did the human actually change the AI draft? Compare against the hash saved at pause.
    import hashlib
    new_hash  = hashlib.md5("\n".join(cleaned).encode("utf-8")).hexdigest() if cleaned else ""
    unchanged = bool(job.get("orig_hash")) and new_hash == job.get("orig_hash")

    # Monetization-Safe Mode: nudge for original input before shipping a raw AI script.
    if job.get("safe_mode") and unchanged and not force:
        return jsonify({
            "needs_confirmation": True,
            "message": ("Monetization-Safe Mode: you haven't changed the AI-written script. "
                        "YouTube can demonetize videos that show no meaningful human input. "
                        "Edit at least one paragraph in your own words — or continue anyway."),
        }), 200

    if cleaned:
        update_job(job_id, paragraphs=cleaned, edited_by_human=(not unchanged))

    ev = job.get("resume_event")
    if ev:
        ev.set()
    return jsonify({"ok": True})


@app.route("/job/<job_id>/cancel", methods=["POST"])
def job_cancel(job_id: str):
    """Signal the pipeline to abort at the next checkpoint."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    ev = job.get("cancel_event")
    if ev:
        ev.set()
    rev = job.get("resume_event")
    if rev:
        rev.set()
    return jsonify({"ok": True})


@app.route("/progress/<job_id>")
def progress(job_id: str):
    def generate():
        while True:
            job = get_job(job_id) or {"status": "not_found"}
            yield f"data: {json.dumps(sanitize_job(job))}\n\n"
            if job.get("status") in ("done", "error", "not_found", "cancelled"):
                break
            time.sleep(1)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _load_project_items() -> list[dict]:
    # Try Supabase first — persists across server restarts for any user
    try:
        from modules.supabase_client import load_projects
        sb_items = load_projects()
        if sb_items:
            # Normalise field names to match what the template expects
            result = []
            for r in sb_items:
                result.append({
                    "folder":      r.get("folder_name", ""),
                    "title":       r.get("title", ""),
                    "topic":       r.get("topic", ""),
                    "duration":    r.get("duration", ""),
                    "style":       r.get("style", ""),
                    "created":     (r.get("created_at") or "")[:16].replace("T", " "),
                    "video_url":   r.get("video_url", ""),
                    "thumb_url":   r.get("thumb_url", ""),
                    "tags":        r.get("tags") or [],
                    "description": r.get("description", ""),
                })
            return result
    except Exception:
        pass

    # Fall back to local filesystem scan (local dev without Supabase)
    items = []
    for folder in sorted(PROJECTS_DIR.iterdir(), reverse=True):
        if not folder.is_dir() or folder.name.startswith("_"):
            continue
        video_path = folder / "final_video.mp4"
        thumb_path = folder / "thumbnail.png"
        if not video_path.exists():
            continue
        meta, settings_data = {}, {}
        try:
            meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        try:
            settings_data = json.loads((folder / "settings.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        items.append({
            "folder":   folder.name,
            "title":    meta.get("best_title") or settings_data.get("topic", folder.name),
            "topic":    meta.get("topic") or settings_data.get("topic", ""),
            "duration": settings_data.get("duration", ""),
            "style":    settings_data.get("style", ""),
            "created":  folder.name[-15:].replace("_", " "),
            "video_url": f"/video/{folder.name}/final_video.mp4",
            "thumb_url": f"/video/{folder.name}/thumbnail.png" if thumb_path.exists() else "",
            "tags":     meta.get("tags", []),
            "description": meta.get("description", ""),
        })
    return items


@app.route("/projects")
def projects():
    return render_template("projects.html", projects=_load_project_items(),
                           styles=list(PALETTES.keys()))


@app.route("/delete_project/<folder_name>", methods=["POST"])
def delete_project(folder_name: str):
    import shutil
    # Remove from Supabase (table row + storage files)
    try:
        from modules.supabase_client import delete_project_data
        delete_project_data(folder_name)
    except Exception as e:
        logging.warning("Supabase delete failed: %s", e)
    folder = PROJECTS_DIR / folder_name
    if folder.exists():
        try:
            shutil.rmtree(str(folder))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})


@app.route("/export_csv")
def export_csv():
    import csv
    import io as _io
    items = _load_project_items()
    buf = _io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["folder", "title", "topic", "duration",
                                         "style", "created", "video_url"])
    w.writeheader()
    for item in items:
        w.writerow({k: item.get(k, "") for k in w.fieldnames})
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=projects.csv"},
    )


@app.route("/regenerate/<folder_name>", methods=["POST"])
def regenerate(folder_name: str):
    folder = PROJECTS_DIR / folder_name
    settings_path = folder / "settings.json"
    if not settings_path.exists():
        return jsonify({"error": "Settings not found"}), 404
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    job_id = str(uuid.uuid4())[:8]
    create_job(job_id, {
        "status": "running", "progress": 0,
        "step": "Starting regeneration...", "error": None,
        "topic": settings.get("topic", ""),
        "resume_event": threading.Event(),
        "cancel_event": threading.Event(),
        "paragraphs": [],
    })
    t = threading.Thread(target=run_pipeline, args=(job_id, settings), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/projects/<folder_name>")
def project_detail(folder_name: str):
    folder = PROJECTS_DIR / folder_name
    if not folder.exists():
        abort(404)

    meta = {}
    settings_data = {}
    script_text = ""

    try:
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        settings_data = json.loads((folder / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        script_text = (folder / "script.txt").read_text(encoding="utf-8")
    except Exception:
        pass

    return render_template(
        "project_detail.html",
        folder=folder_name,
        meta=meta,
        settings=settings_data,
        script=script_text,
        video_url=f"/video/{folder_name}/final_video.mp4",
        thumb_url=f"/video/{folder_name}/thumbnail.png",
    )


@app.route("/research")
def research_page():
    return render_template("research.html", niches=NICHES, sub_niches=SUB_NICHES)


@app.route("/research/fetch", methods=["POST"])
def research_fetch():
    body      = request.json or {}
    keyword   = (body.get("keyword") or "").strip()
    niche     = (body.get("niche") or "").strip()
    sub_niche = (body.get("sub_niche") or "").strip()
    # Priority: explicit keyword > sub-niche > niche
    query = keyword or sub_niche or niche
    if not query:
        return jsonify({"error": "keyword or niche required"}), 400
    try:
        from modules.trend_researcher import research_topic
        return jsonify(research_topic(query, niche=sub_niche or niche))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/video/<folder>/<filename>")
def serve_video(folder: str, filename: str):
    path = PROJECTS_DIR / folder / filename
    if not path.exists():
        abort(404)
    mime = "video/mp4" if filename.endswith(".mp4") else "image/png"
    return send_file(str(path), mimetype=mime)


@app.route("/open_folder/<folder_name>")
def open_folder(folder_name: str):
    folder = PROJECTS_DIR / folder_name
    if folder.exists():
        try:
            os.startfile(str(folder))
        except Exception:
            pass
    return jsonify({"ok": True})


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    env_path = BASE_DIR / ".env"

    def _read_keys() -> dict:
        keys = {"GEMINI_API_KEY": "", "PEXELS_API_KEY": ""}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    k = k.strip()
                    if k in keys:
                        keys[k] = v.strip()
        return keys

    if request.method == "POST":
        data = request.form.to_dict()
        keys = _read_keys()
        for k in ("GEMINI_API_KEY", "PEXELS_API_KEY"):
            if k in data:
                keys[k] = data[k].strip()
        # Write back
        try:
            lines = [f"{k}={v}" for k, v in keys.items()]
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            # Reload env vars
            os.environ.update({k: v for k, v in keys.items() if v})
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    keys = _read_keys()
    yt_configured = (BASE_DIR / "client_secrets.json").exists()
    return render_template("settings.html", keys=keys, yt_configured=yt_configured)


@app.route("/settings/test/<service>", methods=["POST"])
def settings_test(service: str):
    body = request.json or {}
    key  = (body.get("key") or "").strip()
    if service == "gemini":
        if not key:
            return jsonify({"error": "No key provided"}), 400
        try:
            import google.genai as genai
            c = genai.Client(api_key=key)
            c.models.generate_content(model="gemini-flash-latest", contents="Hello")
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 400
    elif service == "pexels":
        if not key:
            return jsonify({"error": "No key provided"}), 400
        try:
            import requests as req
            r = req.get("https://api.pexels.com/v1/search",
                        headers={"Authorization": key},
                        params={"query": "nature", "per_page": 1},
                        timeout=8)
            if r.status_code == 200:
                return jsonify({"ok": True})
            return jsonify({"error": f"HTTP {r.status_code}"}), 400
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 400
    return jsonify({"error": "Unknown service"}), 400


@app.route("/compliance/<folder_name>")
def compliance_report(folder_name: str):
    """Pre-publish monetization compliance checklist for a finished project."""
    if not (PROJECTS_DIR / folder_name).exists():
        return jsonify({"error": "Project not found"}), 404
    from modules.compliance import evaluate
    return jsonify(evaluate(folder_name))


@app.route("/upload_youtube/<folder_name>", methods=["POST"])
def upload_youtube(folder_name: str):
    """Upload a completed project to YouTube as a Private draft."""
    folder = PROJECTS_DIR / folder_name
    if not folder.exists():
        return jsonify({"error": "Project not found"}), 404

    video_path = folder / "final_video.mp4"
    thumb_path = folder / "thumbnail.png"
    if not video_path.exists():
        return jsonify({"error": "Video file not found"}), 404

    # ── Pre-publish compliance gate ──────────────────────────────
    # Block upload on critical failures unless the user explicitly overrides.
    force = bool((request.get_json(silent=True) or {}).get("force"))
    from modules.compliance import evaluate
    report = evaluate(folder_name)
    if not report["ok_to_publish"] and not force:
        return jsonify({
            "needs_force": True,
            "compliance":  report,
            "error":       "Compliance gate: resolve the critical issues, or override to upload anyway.",
        }), 200

    try:
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}

    title       = meta.get("best_title") or folder_name
    description = meta.get("description", "")
    tags        = meta.get("tags", [])
    needs_disclosure = bool(meta.get("requires_ai_disclosure", True))

    try:
        from modules.youtube_uploader import is_available, upload_video
        if not is_available():
            return jsonify({"error": "YouTube upload not configured — add client_secrets.json"}), 400

        result = upload_video(
            str(video_path), title, description, tags,
            thumbnail_path=str(thumb_path) if thumb_path.exists() else "",
            requires_ai_disclosure=needs_disclosure,
        )
        return jsonify(result)
    except Exception as e:
        logging.error("YouTube upload failed: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/admin/restart", methods=["POST"])
def admin_restart():
    """Pull latest code from GitHub then restart the server process."""
    import subprocess

    def _pull_and_restart():
        time.sleep(0.6)   # let the HTTP response reach the browser first
        try:
            result = subprocess.run(
                ["git", "pull", "github", "main"],
                cwd=str(BASE_DIR),
                capture_output=True, text=True, timeout=30,
            )
            logging.info("git pull: %s %s", result.stdout.strip(), result.stderr.strip())
        except Exception as e:
            logging.warning("git pull failed: %s", e)
        # Replace current process with a fresh one — same args, fresh modules
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_pull_and_restart, daemon=False).start()
    return jsonify({"ok": True, "message": "Pulling latest code and restarting…"})


if __name__ == "__main__":
    print("\n  The Generator — Local Video Maker")
    print("  Open: http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
