# AutoVideo AI — Master Specification Prompt

> **Purpose:** Paste this prompt into any capable LLM (Claude Opus, GPT-4o, Gemini 1.5 Pro)
> to generate a full specification and development plan for the AutoVideo AI application.

---

```
You are a senior full-stack developer and AI integration architect. Your task is to
produce a complete, actionable specification and development plan for a locally-run
web application that generates faceless YouTube videos using only free AI tools and
services. The output must be structured, detailed, and immediately usable by a
developer with intermediate web development experience.

---

## CONTEXT

The target user runs a USA-based faceless YouTube channel and wants to automate
"insane" (highly creative, attention-grabbing, unique) video production entirely
on their local machine. "Insane" means: unexpected angles, strong hooks, tight
pacing, original framing of ideas — NOT low-effort slideshow content. Every
output must be structured to qualify for YouTube monetization under their
AI-generated content policies, which require demonstrated human creative oversight,
sufficient original value, and clear disclosure where required.

---

## DELIVERABLE STRUCTURE

Produce the full specification as a single structured document with the following
sections. Use H2 headings, bullet points, code blocks, and tables where appropriate.

---

### SECTION 1 — Executive Summary

Write a 3-paragraph overview covering:
- What the application does end-to-end
- Why the chosen architecture suits local, free-tier operation
- What differentiates this from commodity AI video tools

---

### SECTION 2 — Technology Stack

Provide a complete technology stack recommendation. For each layer, specify:
- The chosen technology and exact version (where relevant)
- Why it was chosen over alternatives
- Any local installation or setup requirements

Layers to cover:
- Backend runtime and framework (e.g., Python/FastAPI, Node/Express)
- Frontend framework (e.g., React, Svelte, plain HTML/JS)
- Local database or state store (e.g., SQLite, TinyDB, JSON flat files)
- Task queue / background job system for long-running generation jobs
- Video processing library (e.g., MoviePy, FFmpeg via subprocess)
- Audio processing library
- Local model runtime if any local models are used (e.g., Ollama)
- Packaging / local server launcher (so a non-developer user can start the app)

---

### SECTION 3 — AI Tool Integration Strategy

For EACH stage of video production below, provide:
1. The specific free tool or service recommended (with URL)
2. How it is accessed (API, local model, CLI, Python library, browser automation)
3. Exact free-tier limits and how the application stays within them
4. A fallback option if the primary tool hits rate limits or goes offline
5. Any disclosure or attribution requirements imposed by the tool's license/ToS

Stages:
A. Script Generation
   — Primary: a locally-run LLM via Ollama (specify recommended model, e.g.,
     Mistral 7B, LLaMA 3 8B). Explain the exact prompting strategy for
     generating hooks, story beats, CTAs, and YouTube-policy-safe narration.
   — Fallback: Groq free API (llama3-8b-8192 endpoint, 14,400 req/day free).

B. Text-to-Speech (Voiceover)
   — Primary: Coqui TTS or Piper TTS (local, fully offline).
   — Fallback: Edge-TTS (Microsoft, free unofficial library, no API key needed).
   — Describe how to select voice, adjust speed/pitch for a compelling narration
     style, and export WAV/MP3.

C. Background Music / Sound Effects
   — Specify royalty-free sources compatible with YouTube monetization
     (e.g., YouTube Audio Library, Pixabay Music, ccMixter).
   — Describe how the application will auto-select and auto-trim tracks to match
     video duration, including ducking under voiceover.

D. Visual Asset Generation (Images / Short Clips)
   — Primary: Stable Diffusion locally via ComfyUI or AUTOMATIC1111
     (free, offline, no API cost). Specify recommended model weights
     (e.g., SDXL Turbo, Realistic Vision) and settings for high-quality
     16:9 frames suitable for YouTube.
   — Secondary: Pollinations.ai (free image API, no key required) as a
     lightweight fallback.
   — For motion / B-roll: Pexels API (free tier) and Pixabay API (free tier)
     for stock video clips. Describe how to search by keyword and cache results.

E. Subtitles / Captions
   — Use OpenAI Whisper (local, free, open-source) to transcribe generated
     audio and produce timed SRT files.
   — Describe how FFmpeg burns subtitles into the final video with a styled
     font suitable for mobile viewing.

F. Thumbnail Generation
   — Stable Diffusion (same local instance) with a specific thumbnail-optimized
     prompt template. Include text overlay via Pillow (Python library).
   — Describe the composition rules (face-equivalent focal point, high contrast,
     large readable text).

---

### SECTION 4 — Application Workflow Design

Describe the complete user journey and internal pipeline as two sub-sections:

#### 4A — User Input Interface
List every input field the user sees on the main "Create Video" form:
- Topic / title seed
- Target audience (age range, interest tags)
- Video length target (short: 3-5 min, standard: 8-15 min)
- Visual style selector (cinematic, minimalist, documentary, cyberpunk, etc.)
- Narration voice selector (list available TTS voices)
- Monetization-mode toggle (enables extra policy-safe structure: intro, value
  section, CTA, outro)
- Advanced options panel: custom script override, manual image prompts,
  music mood selector

#### 4B — Internal Generation Pipeline
Map out the sequential and parallel steps as a numbered pipeline with
estimated processing time per step on a mid-range consumer laptop (no GPU
vs. GPU-accelerated). Use this structure:

Step 1 — Script Generation [~15s CPU / ~8s GPU]
Step 2 — Script Review Screen (human-in-the-loop checkpoint — REQUIRED) [user]
Step 3 — TTS Voiceover Rendering [~30s]
Step 4 — Audio Post-Processing (normalization, noise reduction, music mix) [~20s]
Step 5 — Image Prompt Extraction from Script [~5s]
Step 6 — Visual Asset Generation / Fetch [~2-10 min depending on GPU]
Step 7 — Subtitle Generation via Whisper [~30s]
Step 8 — Video Assembly via FFmpeg/MoviePy [~1-3 min]
Step 9 — Thumbnail Generation [~30s]
Step 10 — Final Preview + Export Screen [user]

For each step specify: inputs, outputs (file types, location in a local
/projects/{video_id}/ directory), error handling, and retry behavior.

---

### SECTION 5 — YouTube Policy Compliance Architecture

This section is critical. Address each requirement explicitly:

#### 5A — AI Disclosure Compliance
- Describe exactly where and how the application inserts YouTube's required
  AI disclosure label (automated via YouTube Data API v3 or manual checklist).
- Explain how the app generates a description-box disclosure statement.

#### 5B — Human Creative Oversight (the monetization gatekeeper)
- Explain the mandatory human review checkpoints built into the pipeline
  (minimum: script review at Step 2, final video review at Step 10).
- Describe the "originality scoring" UI element that evaluates the script for:
  - Unique angle / hook score
  - Factual claim density (too many unverified facts = risk)
  - Similarity to existing content (use local TF-IDF or simple n-gram check)
- Explain how these checkpoints create an auditable record that demonstrates
  human involvement if YouTube reviews the channel.

#### 5C — Value-Add Content Structures
Describe 5 specific content templates the application offers, each with a
"value justification" (why this format earns monetization approval):
1. Educational explainer with original commentary
2. Ranked listicle with sourced, fact-checked claims
3. Narrative storytelling (true events, public domain stories)
4. Trend analysis / opinion piece with clear human editorial stance
5. Tutorial / how-to with demonstrated steps

For each template, specify the script structure (intro hook, sections,
CTA, outro) and the visual rhythm pattern (cuts per minute, B-roll ratio).

#### 5D — Spam and Low-Quality Content Avoidance
- Minimum quality gates the app enforces before allowing export:
  - Script word count floor
  - Unique sentence ratio (deduplication check)
  - Audio clarity score
  - Visual variety check (no identical frames repeated > N times)
- Describe how the app flags or blocks export if gates are not met.

---

### SECTION 6 — Monetization Strategy Integration

#### 6A — Niche Selection Guidance
Recommend 8 high-CPM, faceless-channel-friendly niches suitable for a USA
audience. For each niche provide:
- Niche name
- Estimated CPM range (USD)
- Content difficulty (Easy / Medium / Hard to produce with this app)
- YouTube search demand (High / Medium / Low)
- Monetization risk level (Low / Medium — based on policy sensitivity)

Format as a markdown table.

#### 6B — Video Structure for Watch Time
Explain how the app's default script template is engineered for retention:
- Hook formula for the first 30 seconds
- Pattern interrupt placements (visual/audio change every 45-90s)
- Mid-video re-engagement technique
- End-screen CTA structure to drive subscribe + next-video watch

#### 6C — Upload Cadence Automation
Describe an optional "Content Calendar" feature that:
- Schedules video topics across a week
- Batches generation jobs overnight
- Produces a weekly upload queue with metadata (title, description, tags,
  thumbnail) ready for manual upload or YouTube Data API v3 upload

---

### SECTION 7 — UI / UX Specification

Describe the application's interface across these screens:

1. **Dashboard** — active projects, generation queue status, recent exports
2. **Create Video** — the main input form (described in Section 4A)
3. **Script Editor** — full script display with inline edit, section labels,
   word count, originality score, and approve/regenerate controls
4. **Asset Manager** — grid view of generated images, ability to regenerate
   individual frames, swap stock footage, upload custom assets
5. **Video Preview** — browser-based video player with timeline, subtitle
   overlay toggle, audio waveform, and export button
6. **Settings** — API keys (for optional paid upgrades), local model paths,
   default voice, default visual style, output directory

For each screen, describe: layout (sidebar/main/panel), key interactive
elements, and any real-time feedback (progress bars, live preview updates).

---

### SECTION 8 — Challenges and Mitigations

Identify and solve at least 10 specific technical and operational challenges.
Format each as:

**Challenge:** [description]
**Impact:** [what breaks if unsolved]
**Solution:** [specific, implementable fix with technology named]
**Residual Risk:** [what cannot be fully mitigated]

Include challenges covering:
- GPU memory limits for local Stable Diffusion
- Free API rate limits mid-generation
- Lip-sync / audio-visual timing drift in long videos
- Whisper transcription errors causing subtitle misalignment
- ComfyUI/A1111 version incompatibilities on user machines
- YouTube policy changes invalidating compliance logic
- Content ID claims on AI-generated visuals that resemble copyrighted work
- Local storage consumption from large video projects
- Cross-platform compatibility (Windows / macOS / Linux)
- Long generation times degrading user experience

---

### SECTION 9 — Implementation Roadmap

Break development into 4 milestones. For each milestone provide:
- Milestone name and goal
- List of features delivered
- Estimated developer hours (solo intermediate developer)
- Testable acceptance criteria

Milestone 1: Core Pipeline (text → voice → basic slideshow video)
Milestone 2: Visual Intelligence (SD integration, asset manager, thumbnails)
Milestone 3: Policy & Quality Layer (compliance gates, human checkpoints, scoring)
Milestone 4: UX Polish & Calendar (full UI, batch generation, upload metadata)

---

### SECTION 10 — File and Directory Structure

Provide the recommended project directory tree for the application repository,
annotated with a one-line description of each directory's purpose. Include
where generated project files (scripts, audio, images, final videos) are stored
relative to the app root.

---

### SECTION 11 — Quick-Start Setup Instructions

Write step-by-step setup instructions for a Windows 11 user with Python 3.11
and Node.js 20 already installed. Cover:
1. Cloning/downloading the repo
2. Creating a Python virtual environment and installing dependencies
3. Installing and configuring Ollama with the recommended model
4. Installing ComfyUI or AUTOMATIC1111 and pointing the app at it
5. Running the local dev server
6. Opening the app in a browser and generating the first test video

---

END OF PROMPT
```

---

## How to Use This Prompt

Paste the block above (between the triple backticks) into any of these models:

| Model | Notes |
|-------|-------|
| Claude Opus 4 | Best detail, longest output |
| GPT-4o | Good structure, fast |
| Gemini 1.5 Pro | Good for long documents |

To narrow the output, append a constraint before submitting:
> *"Focus only on Sections 2–5 for now"*

To get code instead of a plan:
> *"Skip the plan — implement Section 4B as working Python code"*
