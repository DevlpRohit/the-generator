# The Generator — AI Faceless Video Maker

A locally-running web app that generates complete faceless YouTube videos from a topic — script, voiceover, AI scene images, subtitles, thumbnail, and SEO metadata — all free, no OpenAI or paid APIs required.

---

## What Is This?

It is a **local web app** that runs on your computer. You open it in a browser like a website, but it is not on the internet — it runs on `http://127.0.0.1:5000` (your own machine).

You give it a topic and it automatically:

1. Writes a script (via Google Gemini AI)
2. Generates voiceover audio (Microsoft Edge TTS — free)
3. Creates AI scene images (Pollinations.ai — free)
4. Assembles everything into an MP4 video with animated subtitles
5. Generates a thumbnail + YouTube title / description / tags

All video files are saved in the `projects/` folder on your computer.

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
| Excel Logging | openpyxl |
| Google Sheets | gspread |
| Trend Research | pytrends + BeautifulSoup |
| Cloud Storage | Supabase (optional) |
| YouTube Upload | Google API Python client |

---

## How to Install on Another Computer

### Requirements

- Windows 10 or 11
- Python 3.10 or newer — [python.org/downloads](https://python.org/downloads)
- Git (optional, for cloning) — [git-scm.com](https://git-scm.com)

---

### Step 1 — Get the Code

**Option A — Clone from GitHub (recommended):**
```powershell
git clone https://github.com/DevlpRohit/the-generator.git
cd the-generator
```

**Option B — Download ZIP from GitHub:**

Go to `github.com/DevlpRohit/the-generator` → click **Code → Download ZIP** → extract the folder

**Option C — Copy the folder:**

Copy the project folder directly via USB drive or Google Drive to the new computer

---

### Step 2 — Install Dependencies

```powershell
cd the-generator
pip install -r requirements.txt
```

Or simply double-click **`setup.bat`** — it installs everything automatically.

---

### Step 3 — Add Your API Keys

Create a file called `.env` inside the project folder and paste your keys:

```
GEMINI_API_KEY=your_gemini_key_here
PEXELS_API_KEY=your_pexels_key_here
```

- **Gemini API key** — free at [aistudio.google.com](https://aistudio.google.com) (required)
- **Pexels API key** — free at [pexels.com/api](https://www.pexels.com/api/) (optional, for real video B-roll footage)

You can also enter these keys directly from the **Settings page** in the app after launch — no need to create the `.env` file manually.

> **Important:** Never share your `.env` file with anyone. It contains your private API keys. Each person needs their own free Gemini key.

---

### Step 4 — Run the App

```powershell
python app.py
```

Or double-click **`run.bat`**

Then open your browser and go to: **http://127.0.0.1:5000**

---

## How to Make a Video

1. Open the app in your browser at `http://127.0.0.1:5000`
2. Type your video topic (e.g. *"The Science of Black Holes"*)
3. Choose your settings — voice, style, duration, aspect ratio, music mood
4. Click **Generate**
5. Watch the progress bar — takes 2–10 minutes depending on length
6. Download your finished MP4, thumbnail, and metadata

---

## How to Share This App

| Method | Best For |
|---|---|
| GitHub link (`DevlpRohit/the-generator`) | Anyone technical |
| Download ZIP from GitHub | Non-technical users |
| USB / Google Drive (copy folder) | Offline sharing |
| Zip the folder and send via WhatsApp / email | Quick sharing |

Each person who installs it needs their own Gemini API key (free). The app itself costs nothing.

---

## Project Structure

```
the-generator/
├── app.py                   # Flask server + pipeline orchestration
├── config.py                # Voices, styles, resolutions, niches
├── requirements.txt
├── setup.bat                # One-click install (Windows)
├── run.bat                  # One-click start server (Windows)
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
└── projects/                # Generated videos (gitignored, stays local)
```

---

## Output Per Video

Each generated video produces a folder inside `projects/` containing:

| File | Description |
|---|---|
| `final_video.mp4` | The finished video |
| `shorts_video.mp4` | 9:16 vertical version (if enabled) |
| `thumbnail.png` | YouTube thumbnail |
| `script.txt` | Full narration script |
| `script_history.json` | Version snapshots (Gemini draft → your edits) |
| `metadata.json` | Titles, description, tags |
| `settings.json` | Exact settings used (for one-click regeneration) |

---

## Optional Integrations

| Feature | How to Set Up |
|---|---|
| Pexels B-roll footage | Add `PEXELS_API_KEY` in Settings or `.env` |
| Google Sheets log | Place `gsheets_credentials.json` in project root |
| YouTube upload | Place `client_secrets.json` (OAuth) in project root |
| Supabase cloud sync | Add `SUPABASE_URL` + `SUPABASE_KEY` in `.env` |

---

## Monetization-Safe Mode

Enable in the UI to force a human-review checkpoint before rendering. The pipeline pauses after the AI writes the script so you can edit it in your own words — the key safeguard against YouTube's "inauthentic content" policy for AI-generated videos.

---

## Quick Reference

```
Install  →  pip install -r requirements.txt
Run      →  python app.py
Open     →  http://127.0.0.1:5000
Videos   →  projects/ folder
Keys     →  .env file or Settings page in app
```

---

## Troubleshooting

### App won't start
- Make sure Python 3.10+ is installed: `python --version`
- Run `pip install -r requirements.txt` again to ensure all packages are present
- Check that you are inside the project folder before running `python app.py`

### "No module named flask" or similar error
```powershell
pip install -r requirements.txt
```
If that fails, try:
```powershell
python -m pip install -r requirements.txt
```

### Video generation fails at "Writing script"
- Your Gemini API key is missing or wrong — open the app → Settings → paste your key
- Check your internet connection (Gemini requires internet)
- Get a free key at [aistudio.google.com](https://aistudio.google.com)

### Video generation fails at "Encoding final video"
- ffmpeg is not installed. Fix:
```powershell
pip install imageio-ffmpeg
```
- Try lowering the quality to 480p or 720p in the settings

### No audio / silent video
- `edge-tts` requires an internet connection to Microsoft's servers
- Check your firewall is not blocking Python
- Fallback: the app will try `pyttsx3` (offline TTS) automatically

### App opens but shows a blank page
- Clear your browser cache
- Try a different browser (Chrome or Edge recommended)
- Make sure the terminal running `python app.py` shows no errors

### "Address already in use" / port 5000 error
Another process is using port 5000. Either close that app or run on a different port:
```powershell
python app.py --port 5001
```
Then open `http://127.0.0.1:5001`

### Images not generating
- Pollinations.ai requires internet access — check your connection
- If using Pexels, make sure `PEXELS_API_KEY` is set in `.env` or Settings
- Try switching Image Provider to `pollinations` in the generation form

### Projects not showing in the Projects page
- The `projects/` folder may be empty if no videos have completed yet
- If using Supabase, check that `SUPABASE_URL` and `SUPABASE_KEY` are correct in `.env`

### Windows: "python is not recognized"
During Python installation, check the box **"Add Python to PATH"** and reinstall.

### pip install fails on Windows
Run PowerShell as Administrator, then:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## License

MIT
