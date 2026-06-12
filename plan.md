# AutoVideo AI — Development Plan

## What We Are Building

A locally-run web application (`http://localhost:8000`) that takes a video topic and
produces a complete faceless YouTube video — script, voiceover, AI visuals, subtitles,
and thumbnail — using only free tools, no GPU required.

> **Design principle (added 2026-06-09):** The tool must produce videos that are
> **eligible for YouTube monetization under the current AI-content rules**, not just
> "videos that play." Pure auto-generated AI narration over AI slideshows is exactly
> the pattern YouTube demonetizes. Every feature below is now framed around keeping a
> **human in the loop**, **varying** output between uploads, and **disclosing** AI use
> correctly. See *YouTube AI Monetization Policy* below.

---

## YouTube AI Monetization Policy — What We Must Comply With

*Last verified 2026-06-09. Two independent rule-sets apply; we must pass BOTH.*

### Rule-set A — "Inauthentic Content" (YPP update, July 15 2025)

Renamed/replaced the old "Repetitious Content" policy. It **demonetizes** content that is:
mass-produced, templated, highly repetitive, or **AI-generated without meaningful human
input** ("AI slop"). **Risk: a few inauthentic videos can demonetize the entire channel.**

AI is *allowed* and monetizable when used **as a tool** — "like Photoshop" — as long as
the video adds **original human value**:
- Human narration, commentary, editing, or analysis
- A unique perspective / angle per video (not a reused template)
- Videos that are **visually and structurally distinct** from each other
- Not robotic narration over a generic slideshow with no added insight
- Not AI avatars presenting fake/derivative "news" or documentary

### Rule-set B — AI Disclosure ("altered or synthetic content")

Separate from monetization. Creators **must disclose** (a toggle in YouTube Studio /
upload flow) when AI is used to make **realistic** content a viewer could mistake for
real people, real events, or real voices.
- **Disclosure REQUIRED:** photorealistic AI footage depicting real-looking people/places/
  events; voice clones of real people; realistic "this really happened" reenactments.
- **Disclosure NOT required:** clearly stylized/animated art (Ghibli, comic, abstract,
  obvious illustration); AI used only for *production assistance* — scripts, ideas,
  editing, thumbnails, captions, our neural TTS.
- Proper disclosure does **not** reduce reach or ad eligibility. *Failure* to disclose
  when required is what triggers penalties.
- From ~**May 2026**, YouTube auto-detects photorealistic AI and may apply the label
  itself; a high-confidence auto-label cannot be removed.

### Rule-set C — YPP baseline (unchanged, still required)

1,000 subscribers **+** 4,000 valid public watch-hours in 12 months (or 10M Shorts views
in 90 days); original content; advertiser-friendly (no gore/hate/medical-misinfo/etc.);
correct "Made for Kids" status; reused-content policy.

> **Implication for this app:** our default pipeline (Gemini script → AI images → TTS →
> auto metadata, fully automated) is the *highest-risk* profile under Rule-set A. The
> features below convert it into a compliant, human-supervised, varied, disclosed workflow.

---

## Architecture at a Glance

```
Browser UI (HTML/CSS/JS)
        │  POST /api/generate
        ▼
FastAPI Backend (main.py)
        │  asyncio.create_task()
        ▼
Async Pipeline
  ├── 1. Script Gen  ──► Pollinations.ai text API (free, no key)
  ├── 2. TTS         ──► edge-tts (Microsoft Neural, free, offline-capable)
  ├── 3. Images      ──► Pollinations.ai image API (Flux model, free, no key)
  ├── 4. Video       ──► MoviePy 1.0.3 + FFmpeg (local)
  └── 5. Subtitles   ──► SRT from script timing + FFmpeg burn-in

projects/{job_id}/
  ├── script.json
  ├── audio_hook.mp3, audio_section_0.mp3 ...
  ├── image_hook.jpg, image_section_0.jpg ...
  ├── raw_video.mp4
  ├── subtitles.srt
  ├── final_video.mp4
  └── thumbnail.jpg
```

---

## Technology Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Python 3.13 + FastAPI | Async-native, already installed |
| Frontend | Vanilla HTML/CSS/JS | Zero build step, instant dev |
| Job queue | asyncio.create_task | No Redis needed for single-user |
| Video assembly | MoviePy 1.0.3 | Already installed |
| Video encoding | FFmpeg 8.1 | Already installed |
| TTS | edge-tts | Already installed, 400+ voices |
| Script AI | Pollinations.ai text API | Free, no key, OpenAI-compatible |
| Image AI | Pollinations.ai image API (Flux) | Free, no key, 1920×1080 |
| Image processing | Pillow | Already installed |
| HTTP client | httpx | Already installed, async |

---

## Milestones

### Milestone 1 — Core Pipeline ✅ (Current)
**Goal:** Topic → complete video, end to end.

- [x] FastAPI backend with job management
- [x] Pollinations.ai script generation with JSON mode
- [x] edge-tts voiceover per script section
- [x] Pollinations.ai Flux image generation (1920×1080)
- [x] MoviePy video assembly (images + audio)
- [x] SRT subtitle generation from word timings
- [x] FFmpeg subtitle burn-in
- [x] Thumbnail generation
- [x] Dark-theme web UI with real-time progress polling
- [x] Projects gallery with video playback

**Estimated time:** 3–5 min per video (CPU only)

---

### Milestone 2 — Visual Quality Upgrade
**Goal:** Better-looking videos with motion and music.

- [ ] Ken Burns zoom/pan effect on images via MoviePy
- [ ] Background music mixing (YouTube Audio Library tracks)
- [ ] Audio ducking (music quieter under voiceover)
- [ ] Transition effects between sections (crossfade)
- [ ] Pexels/Pixabay B-roll video clips (free API)
- [ ] Thumbnail text overlay with Pillow

---

### Milestone 3 — Monetization Compliance Layer ⭐ (priority)
**Goal:** Every exported video passes YouTube's *Inauthentic Content* + *AI Disclosure*
rules. This is the difference between a channel that earns and one that gets demonetized.
Tasks map to real modules in `auto_video/`.

#### 3A — Human value (beats Rule-set A "inauthentic")
- [x] **"Monetization-Safe Mode" toggle** (default ON) — *done.* Form toggle (checked by
      default) forces the review checkpoint: `run_pipeline` pauses when `safe_mode` OR
      `pause_review` is on. Stored on the job.
- [x] **Mandatory script review + edit** — *done.* On resume, the script is hashed against
      the AI draft; if unchanged under Safe Mode the `/job/<id>/resume` route returns
      `needs_confirmation` (the UI shows a "you haven't edited it — continue anyway?" prompt)
      and the pipeline stays paused until the user edits or explicitly forces. `edited_by_human`
      is recorded on the job and saved into `settings.json`.
- [x] **Original-commentary field** — *done.* Form textarea (`commentary`) is injected as a
      scene right after the hook (`run_pipeline`), saved to `script_history.json`, and counts
      toward the gate's `human_input` check.
- [x] **Human voiceover option** — *done.* Form file input (`voiceover`, mp3/wav/m4a/…) is
      saved at `/generate`, then `audio_generator.prepare_human_voiceover()` slices it per
      paragraph (weighted by word count) to fit the existing assembler; TTS remains the
      default. Sets `human_voiceover` → strongest `human_input` signal.

#### 3B — Variation engine (beats "mass-produced / templated")
- [x] **De-template titles** — *done.* `metadata_generator.py` now uses Gemini topic-specific
      titles as primary; the fallback patterns were de-clickbaited (no more "You Won't Believe
      Number {num}") and are **rotated** via `.title_pattern_history.json` so recent uploads
      don't share a pattern.
- [ ] **Cross-video variation check** — before export, compare new title/structure/visual
      style against the last N projects in `projects/`; warn if too similar (templated).
- [ ] **Vary structure & style** — rotate intro style, pacing, palette, animation, voice
      across uploads instead of one fixed recipe.

#### 3C — AI disclosure (Rule-set B)
- [x] **Disclosure decision logic** — *done.* `requires_ai_disclosure(style)` classifies
      stylized palettes (Ghibli/Comic/Cyberpunk/Vintage/Minimalist/Nature) as not needing
      the label; realistic/unknown styles default to True (safe). Stored as
      `requires_ai_disclosure` in `metadata.json`.
- [x] **Description disclosure line** — *done.* `_with_disclosure()` auto-injects a single
      AI-disclosure sentence into the description (applied to both Gemini and template
      output) when disclosure is recommended.
- [x] **Studio reminder on upload** — *done.* `youtube_uploader.upload_video()` returns a
      `disclosure_reminder` (exact Studio path to the "Altered or synthetic content" toggle)
      when the flag is set; `app.py` reads `requires_ai_disclosure` from metadata and passes
      it through. (Data API v3 can't set the toggle, so Studio is the only path.)

#### 3D — Quality / safety gates (Rule-set A & C)
*All implemented as checks in `modules/compliance.py` (see 3E).*
- [x] **Word-count gate** — *done.* Critical check: ≥ 55% of the duration's target word count.
- [x] **Originality score** — *done.* Warn check: distinct-trigram ratio (< 85% flags repetition).
- [x] **Unique-images gate** — *done.* Warn check: counts content-distinct `scene_*.png` (≥ 4).
- [x] **Niche risk flags** — *done.* `config.py` `RISKY_NICHES` + `niche_risk()`; the index
      form tags risky niches with `data-risk` + a ⚠ marker and a live amber warning banner
      (`#niche-warning`). Also a warn check in the gate.
- [~] **Made-for-Kids + advertiser-friendly** — niche risk surfaced in the gate;
      `selfDeclaredMadeForKids=False` is set on upload. A user-facing MFK confirm is still TODO.

#### 3E — Pre-publish compliance gate (final blocker)
- [x] **Compliance checklist + gate** — *done.* `modules/compliance.py` `evaluate(folder)`
      scores 8 checks (3 critical: human input, length, valid metadata; 5 warn: image
      variety, originality, AI disclosure, duplicate title, niche risk). `GET /compliance/<folder>`
      returns the report; the result card renders it (`#compliance-panel`). The upload route
      **blocks on any critical failure** (`needs_force`) — the UI lists the failures and lets
      the user override (`force:true`). Verified: old un-edited project → 1 critical → upload
      blocked; `force` bypasses the gate.

---

### Milestone 4 — UX Polish & Calendar
**Goal:** Full production-ready tool.

- [ ] Content calendar — batch-schedule 7-day topic queue
- [ ] Export metadata pack (title, description, tags, thumbnail as ZIP)
- [ ] Groq API integration (optional, faster script generation)
- [ ] Ollama/local LLM integration (fully offline option)
- [ ] Settings page (voice default, style default, output directory)
- [ ] Whisper-based accurate subtitle timing

---

## Free Tools Used — Limits & Fallbacks

| Tool | Free Limit | Fallback |
|------|-----------|---------|
| Pollinations text | Unlimited (shared server) | Hardcoded template script |
| Pollinations images | Unlimited (shared server) | Pillow gradient placeholder |
| edge-tts | Unlimited (uses MS servers) | pyttsx3 (offline, lower quality) |
| MoviePy | Local, no limits | — |
| FFmpeg | Local, no limits | Skip subtitle burn |

---

## YouTube Policy Compliance Strategy

How each policy rule is satisfied by a concrete feature:

| Policy rule | How we comply |
|-------------|---------------|
| **Inauthentic / AI-slop (Jul 2025)** | Monetization-Safe Mode forces human review + edit; original-commentary field; optional human voiceover; output not shipped raw from AI |
| **Mass-produced / templated** | De-templated Gemini titles; cross-video similarity check vs `projects/`; rotated structure / palette / voice / animation |
| **AI disclosure (realistic content)** | Disclosure-decision logic per video; auto description line when required; Studio "altered content" toggle reminder on upload |
| **Original value** | Script prompt forces unique angle; user adds personal take; originality (n-gram) score |
| **Not spam / thin** | Word-count gate per duration; ≥ 4 unique images; no slideshow loops |
| **Advertiser-friendly + Made-for-Kids** | Niche risk flags on Conspiracy/True-Crime; MFK + ad-friendly checklist before upload |
| **Reused-content** | Fresh images seeded per job; variation engine prevents near-duplicate uploads |

---

## Pre-Publish Compliance Gate

Export / Upload stays disabled until **all** of these pass (Milestone 3E):

- [ ] **Human input confirmed** — script reviewed & edited, OR a human voiceover supplied
- [ ] **Original take present** — commentary/angle field is non-empty
- [ ] **Length OK** — script meets the minimum word count for its duration
- [ ] **Originality OK** — n-gram uniqueness above threshold
- [ ] **Visual variety OK** — ≥ 4 distinct scene images
- [ ] **Not templated** — title/structure not near-identical to recent uploads
- [ ] **AI disclosure resolved** — either "not required (stylized)" or description line added
      **and** Studio toggle reminder shown
- [ ] **Niche/ad-safety acknowledged** — risky niche warning accepted; Made-for-Kids set
- [ ] **Metadata sane** — title ≤ 100 chars, description present, tags ≤ 500

> Failing items are shown with the exact fix. This gate is the single most important
> monetization safeguard — it stops the tool from ever producing demonetizable "AI slop".

---

## File Structure

```
auto_video/
├── plan.md              ← this file
├── prompt.md            ← master spec prompt for LLMs
├── requirements.txt     ← pip dependencies
├── run.bat              ← double-click launcher (Windows)
├── main.py              ← FastAPI app + pipeline orchestration
├── config.py            ← constants (paths, voices, styles)
├── pipeline/
│   ├── __init__.py
│   ├── script_gen.py    ← Pollinations.ai text generation
│   ├── tts.py           ← edge-tts voiceover
│   ├── image_gen.py     ← Pollinations.ai image generation
│   └── video_assembly.py ← MoviePy + FFmpeg assembly
├── static/
│   ├── index.html       ← single-page UI
│   ├── style.css        ← dark theme styles
│   └── app.js           ← frontend logic + polling
└── projects/            ← auto-created, stores all generated assets
    └── {job_id}/
        ├── script.json
        ├── audio_*.mp3
        ├── image_*.jpg
        ├── raw_video.mp4
        ├── subtitles.srt
        ├── final_video.mp4
        └── thumbnail.jpg
```

---

## How to Run

```bat
cd auto_video
run.bat
```

Then open: `http://localhost:8000`

---

## Anticipated Challenges & Solutions

| Challenge | Solution |
|-----------|---------|
| Pollinations slow / down | 3-attempt retry with 5s backoff; gradient placeholder for images |
| MoviePy Python 3.13 compat | Tested — works with v1.0.3 |
| FFmpeg subtitle path on Windows | Drive colon escaped (`D\:/path`) in filter string |
| Long generation time (3-5 min) | Real-time progress bar via `/api/status` polling every 2s |
| edge-tts needs internet | Fallback note in UI; pyttsx3 planned for Milestone 2 |
| ImageMagick not installed | No TextClip used — subtitles via FFmpeg only |

---

## Next Actions

**Monetization-compliance work (Milestone 3 — do first, highest impact):**

- [x] AI-disclosure line in `metadata_generator.py` (single injection point, both paths)
- [x] De-templated + rotated fallback titles
- [x] Studio "altered content" disclosure reminder in `youtube_uploader.py` (wired through `app.py`)
- [x] Risky-niche backend (`RISKY_NICHES` / `niche_risk`) **+ UI** (⚠ marker + live warning banner)
- [x] **Monetization-Safe Mode** (default-ON toggle) — forces review; resume nudges when the
      script is unedited; `edited_by_human` tracked → `settings.json`
- [x] Per-video disclosure note in the result card (shown only for realistic styles; updated
      with the Studio reminder after upload)
- [x] **Pre-Publish Compliance Gate** — `modules/compliance.py` + `GET /compliance/<folder>`;
      result-card checklist; upload route blocks critical failures with `force` override
- [x] **Quality gates** — word-count, originality (n-gram), ≥ 4 unique images (gate checks)

- [x] **Original-commentary field** + **human-voiceover upload** — both feed the `human_input`
      gate check (commentary injected as a scene; voiceover sliced per paragraph)

Remaining (optional polish):

1. **Cross-video variation check** vs recent `projects/` (gate has duplicate-title; extend to
   structure/visual style)
2. **Made-for-Kids confirm** in the UI before upload

**Smoke-test the existing pipeline:**

1. Run `run.bat` (Flask app on `http://127.0.0.1:5000`)
2. Enter topic: **"5 Mind-Blowing Facts About the Human Brain"**, Style **Cinematic**, Voice **Male US**
3. Generate, then **review & edit the script** at the pause checkpoint (don't ship raw AI)
4. Review output, then upload as Private draft and set disclosure in Studio if visuals are realistic

> Note: this plan's Architecture section describes the original FastAPI design; the shipped
> app is **Flask** (`app.py`, `modules/`, port 5000). Compliance tasks above reference the
> real modules.
