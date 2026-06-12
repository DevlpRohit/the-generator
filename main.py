import asyncio
import io
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import logging

# Ensure UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import BASE_DIR, PROJECTS_DIR, VOICES, STYLES
from pipeline.script_gen import generate_script
from pipeline.tts import generate_tts
from pipeline.image_gen import generate_image
from pipeline.video_assembly import assemble_video, generate_srt, burn_subtitles

app = FastAPI(title="AutoVideo AI")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# In-memory job store  { job_id: { status, progress, step, ... } }
JOBS: dict = {}


# ── Models ──────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str
    style: str = "cinematic"
    voice: str = "en-US-GuyNeural"
    duration_minutes: int = 5


# ── Static routes ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))


@app.get("/videos/{job_id}/{filename}")
async def serve_video(job_id: str, filename: str):
    p = PROJECTS_DIR / job_id / filename
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(p), media_type="video/mp4")


@app.get("/thumbnails/{job_id}/{filename}")
async def serve_thumbnail(job_id: str, filename: str):
    p = PROJECTS_DIR / job_id / filename
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(p), media_type="image/jpeg")


# ── API routes ───────────────────────────────────────────────────────────────

@app.get("/api/voices")
async def list_voices():
    return VOICES


@app.get("/api/styles")
async def list_styles():
    return STYLES


@app.post("/api/generate")
async def start_generation(req: GenerateRequest):
    job_id = str(uuid.uuid4())[:8]
    job_dir = PROJECTS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    JOBS[job_id] = {
        "status": "running",
        "progress": 0,
        "step": "Starting pipeline...",
        "error": None,
        "video_url": None,
        "thumbnail_url": None,
        "title": None,
        "description": None,
        "tags": [],
        "topic": req.topic,
    }

    asyncio.create_task(_pipeline(job_id, req, job_dir))
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"status": "not_found"}, status_code=404)
    return job


@app.get("/api/projects")
async def list_projects():
    return [
        {
            "job_id": jid,
            "title": j.get("title") or j.get("topic", "Untitled"),
            "topic": j.get("topic"),
            "video_url": j.get("video_url"),
            "thumbnail_url": j.get("thumbnail_url"),
            "tags": j.get("tags", []),
        }
        for jid, j in JOBS.items()
        if j.get("status") == "done"
    ]


# ── Pipeline ─────────────────────────────────────────────────────────────────

def _upd(job_id: str, **kw):
    if job_id in JOBS:
        JOBS[job_id].update(kw)


async def _pipeline(job_id: str, req: GenerateRequest, job_dir: Path):
    loop = asyncio.get_event_loop()
    try:

        # 1 — Script
        _upd(job_id, step="Writing script with AI...", progress=5)
        script = await generate_script(req.topic, req.style, req.duration_minutes)
        (job_dir / "script.json").write_text(json.dumps(script, indent=2))
        _upd(job_id, step="Script complete", progress=15, title=script.get("title"))

        # 2 — Build narration segment list
        segs: list[tuple[str, str]] = []
        segs.append(("hook", script.get("hook_narration", "")))
        for i, sec in enumerate(script.get("sections", [])):
            segs.append((f"section_{i}", sec.get("narration", "")))
        outro = (script.get("outro_narration", "") + " " + script.get("cta", "")).strip()
        if outro:
            segs.append(("outro", outro))

        # 3 — TTS
        _upd(job_id, step="Generating voiceover...", progress=20)
        audio_map: dict = {}
        for seg_name, text in segs:
            if not text.strip():
                continue
            out = str(job_dir / f"audio_{seg_name}.mp3")
            dur = await generate_tts(text, req.voice, out)
            audio_map[seg_name] = {"path": out, "duration": dur, "text": text}
        _upd(job_id, step="Voiceover complete", progress=40)

        # 4 — Images
        _upd(job_id, step="Generating visuals...", progress=42)
        image_prompts: list[tuple[str, str]] = []
        image_prompts.append((
            "hook",
            f"{req.topic}, {req.style} style, cinematic establishing shot, dramatic, 8k"
        ))
        for i, sec in enumerate(script.get("sections", [])):
            p = sec.get("image_prompt") or f"{sec.get('heading', req.topic)}, {req.style}, cinematic, 8k"
            image_prompts.append((f"section_{i}", p))
        image_prompts.append((
            "outro",
            f"{req.topic}, inspiring wide shot, {req.style}, golden light, cinematic finale"
        ))

        image_map: dict = {}
        total_imgs = len(image_prompts)
        for idx, (seg_name, prompt) in enumerate(image_prompts):
            pct = 42 + int(idx / total_imgs * 28)
            _upd(job_id, step=f"Generating image {idx + 1}/{total_imgs}...", progress=pct)
            out = str(job_dir / f"image_{seg_name}.jpg")
            await generate_image(prompt, out, seed=idx + int(job_id, 16) % 1000)
            image_map[seg_name] = out
        _upd(job_id, step="All visuals ready", progress=70)

        # 5 — Build sections_data for assembly
        sections_data = []
        for seg_name, _ in segs:
            if seg_name not in audio_map:
                continue
            img = image_map.get(seg_name) or image_map.get("hook")
            if not img:
                continue
            sections_data.append({
                "image_path": img,
                "audio_path": audio_map[seg_name]["path"],
                "duration": audio_map[seg_name]["duration"],
                "narration": audio_map[seg_name]["text"],
            })

        # 6 — Assemble raw video
        _upd(job_id, step="Assembling video clips...", progress=72)
        raw_path = str(job_dir / "raw_video.mp4")
        await loop.run_in_executor(None, assemble_video, sections_data, raw_path)

        # 7 — Generate SRT
        _upd(job_id, step="Generating subtitles...", progress=87)
        srt_path = str(job_dir / "subtitles.srt")
        generate_srt(sections_data, srt_path)

        # 8 — Burn subtitles
        _upd(job_id, step="Burning subtitles into video...", progress=89)
        final_path = str(job_dir / "final_video.mp4")
        await loop.run_in_executor(None, burn_subtitles, raw_path, srt_path, final_path)

        # 9 — Thumbnail
        _upd(job_id, step="Generating thumbnail...", progress=95)
        thumb_path = str(job_dir / "thumbnail.jpg")
        thumb_prompt = (
            f"{script.get('title', req.topic)}, YouTube thumbnail, {req.style}, "
            "dramatic cinematic lighting, high contrast, no text overlay"
        )
        await generate_image(thumb_prompt, thumb_path, width=1280, height=720, seed=999)

        # Done!
        _upd(
            job_id,
            status="done",
            step="Done!",
            progress=100,
            video_url=f"/videos/{job_id}/final_video.mp4",
            thumbnail_url=f"/thumbnails/{job_id}/thumbnail.jpg",
            title=script.get("title", req.topic),
            description=script.get("description", ""),
            tags=script.get("tags", []),
            disclosure=script.get("disclosure", ""),
        )

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print(f"[Pipeline ERROR job={job_id}]\n{tb}")
        _upd(job_id, status="error", step="Pipeline failed", error=str(exc))


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
