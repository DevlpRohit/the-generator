# The Generator — AI Faceless Video Maker

A locally-running web app that generates complete faceless YouTube videos from a topic — script, voiceover, AI scene images, subtitles, thumbnail, and SEO metadata — all free, no OpenAI or paid APIs required.

---

## Features

- **AI Script Generation** — Gemini-powered scripts with hook, sections, and outro
- **Text-to-Speech** — Microsoft Edge TTS (7 voice options) with adjustable speed
- **Voice Cloning** — Record your own voice; narration generated in your voice (Chatterbox, MIT-licensed)
- **Human Voiceover** — Upload your own MP3/WAV to replace TTS entirely
- **AI Scene Images** — Pollinations.ai or Pexels B-roll video as visuals
- **Animated Subtitles** — Word-level sync with 4 style presets (Clean White, Bold Yellow, Neon Glow, Minimal)
- **Background Music** — Procedurally generated for 6 moods (Epic, Calm, Dark, Uplifting, Mystery, None)
- **YouTube Shorts** — Auto center-crop to 9:16 on the same pass
- **Thumbnail Generator** — Custom styled thumbnails per video
- **SEO Metadata** — AI-generated titles (3 options), description, and tags
- **Script Review Pause** — Human-edit checkpoint before rendering; Monetization-Safe Mode enforces it
- **Job Queue** — Run videos back-to-back without overlap
- **Supabase Cloud Sync** — Optional; persists projects across restarts for shared/hosted use
- **YouTube Upload** — One-click private draft upload with compliance pre-check
- **Google Sheets + Excel Logging** — Automatic project log after each completed video
- **Trend Research** — pytrends + YouTube scraper for viral topic ideas

---

## Tech Stack (100% Free)

| Purpose | Library |
|---|---|
| Backend | Flask |
| AI Script | Google Gemini (`google-genai`) |
| Text-to-Speech | `edge-tts` (Microsoft free) + `pyttsx3` fallback |
| Voice Cloning | Chatterbox (MIT) |
| Video Assembly | MoviePy + ffmpeg |
| Images | Pillow · Pollinations.ai · Pexels API |
| Music | numpy + scipy (sine wave generator) |
| Subtitles | Pillow word-level burn-in |
| Excel | openpyxl |
| Google Sheets | gspread |
| Trend Research | pytrends + BeautifulSoup |
| Cloud Storage | Supabase (optional) |
| YouTube Upload | Google API Python client |

---

## Quick Start (Windows)

```bash
# 1. Clone the repo
git clone https://github.com/rohitbhutta/the-generator.git
cd the-generator

# 2. Install dependencies (one-click)
setup.bat

# 3. Add your Gemini API key
# Either paste it in the Settings page after launch, or create a .env file:
echo GEMINI_API_KEY=your_key_here > .env

# 4. Run
run.bat
# Open http://127.0.0.1:5000
```

> **Python 3.10+ required.** ffmpeg is bundled via `imageio-ffmpeg`.

---

## Project Structure

```
the-generator/
├── app.py                   # Flask server + pipeline orchestration
├── config.py                # Voices, styles, resolutions, niches
├── requirements.txt
├── setup.bat / run.bat      # Windows launchers
├── modules/
│   ├── script_generator.py  # Gemini script writer
│   ├── audio_generator.py   # TTS, voice clone, human voiceover
│   ├── scene_generator.py   # AI images + Pexels B-roll
│   ├── video_assembler.py   # MoviePy assembly + subtitle burn-in
│   ├── thumbnail_generator.py
│   ├── metadata_generator.py
│   ├── trend_researcher.py  # pytrends + YouTube scraper
│   ├── compliance.py        # Pre-publish monetization checklist
│   ├── excel_logger.py
│   ├── gsheet_logger.py
│   ├── supabase_client.py
│   ├── youtube_uploader.py
│   ├── voice_clone.py
│   └── job_store.py         # SQLite job persistence
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS, JS, assets
└── projects/                # Generated videos (gitignored)
```

---

## Optional Integrations

| Feature | Setup |
|---|---|
| Pexels B-roll | Add `PEXELS_API_KEY` in Settings or `.env` |
| Google Sheets log | Place `gsheets_credentials.json` in root |
| YouTube upload | Place `client_secrets.json` (OAuth) in root |
| Supabase sync | Add `SUPABASE_URL` + `SUPABASE_KEY` in `.env` |

---

## Output Per Video

Each generated video produces a folder under `projects/` containing:

- `final_video.mp4` — the finished video
- `shorts_video.mp4` — 9:16 version (if enabled)
- `thumbnail.png`
- `script.txt`
- `script_history.json` — version snapshots (Gemini draft → human edits)
- `metadata.json` — titles, description, tags
- `settings.json` — exact settings used (for one-click regeneration)
- Individual scene images and audio clips

---

## Monetization-Safe Mode

Enable in the UI to force a human-review checkpoint before rendering. The pipeline pauses after the AI writes the script so you can edit it in your own words — the key safeguard against YouTube's "inauthentic content" policy for AI-generated videos.

---

## License

MIT
