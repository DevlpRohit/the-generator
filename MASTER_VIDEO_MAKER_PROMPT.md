# Master Prompt: Free AI Video Maker for Faceless YouTube Channel

> **How to use:** Paste the entire contents of this file into a new Claude Code session inside an empty project folder (e.g. `D:\VideoMaker`). Claude Code will build the full application step by step.

---

## YOUR TASK

Build a complete **"Master AI Video Maker"** web application — a locally running tool for creating faceless YouTube videos with voiceover audio, thumbnails, SEO metadata, and Excel project logging. Everything must be **100% free**, work offline (except trending research), and run on Windows 10/11 with Python 3.10+.

---

## TECH STACK — FREE ONLY

| Purpose | Library | Cost |
|---|---|---|
| Backend server | Flask | Free |
| Video assembly | MoviePy + ffmpeg | Free |
| Image/frame creation | Pillow (PIL) | Free |
| Text-to-speech voice | edge-tts (Microsoft free TTS) | Free |
| Offline fallback TTS | pyttsx3 | Free |
| Trending research | pytrends + BeautifulSoup | Free |
| Background tones | numpy + scipy (sine wave generator) | Free |
| Excel logging | openpyxl | Free |
| Frontend | Plain HTML + CSS + JavaScript | Free |

**No OpenAI. No paid APIs. No subscriptions. No cloud services.**

---

## PROJECT FOLDER STRUCTURE TO CREATE

```
VideoMaker/
├── app.py                  ← Flask main server
├── requirements.txt        ← all pip dependencies
├── setup.bat               ← one-click install + launch (Windows)
├── run.bat                 ← one-click start server
├── config.py               ← all default settings in one place
├── modules/
│   ├── __init__.py
│   ├── script_generator.py     ← template-based script writer
│   ├── audio_generator.py      ← edge-tts voice synthesis
│   ├── scene_generator.py      ← Pillow image scene creator
│   ├── video_assembler.py      ← MoviePy video builder
│   ├── thumbnail_generator.py  ← YouTube thumbnail creator
│   ├── metadata_generator.py   ← title, description, tags writer
│   ├── trend_researcher.py     ← pytrends + YouTube scraper
│   └── excel_logger.py         ← openpyxl project logger
├── templates/
│   ├── index.html          ← main video creator form
│   ├── projects.html       ← all past projects table
│   └── research.html       ← trending topics explorer
├── static/
│   ├── style.css           ← dark YouTube-like theme
│   └── app.js              ← form handling + progress polling
└── projects/               ← auto-created, one subfolder per video
```

---

## WEBPAGE CONTROLS (All on the Main Page as Dropdowns/Inputs)

Build the main form at route `/` with these exact controls:

```
1.  Topic / Subject Line        → text input (required)
2.  Video Quality               → 360p | 480p | 720p | 1080p | 4K
3.  Video Duration              → 30s | 60s | 2min | 5min | 10min
4.  Aspect Ratio                → 16:9 Landscape | 9:16 Shorts | 1:1 Square | 4:3 Classic
5.  Content Type                → Storytelling | Sci-Fi | Educational | Horror |
                                   Motivational | Mystery | Documentary | History | Comedy
6.  Video Style                 → Cinematic | Ghibli-Inspired | Minimalist |
                                   Cyberpunk/Neon | Vintage | Comic Book | Nature & Calm
7.  Voice                       → Male US | Female US | Male UK | Female UK |
                                   Male AU | Female AU | Neutral/Soft
8.  Animation                   → Ken Burns (zoom+pan) | Fade Transitions |
                                   Glitch Effect | Typewriter Text | Slide In | Static
9.  Background Music Mood       → None | Epic/Dramatic | Calm/Peaceful |
                                   Dark/Suspense | Uplifting | Mystery
10. Auto-Research Mode          → toggle ON/OFF
    (when ON: ignores topic field, finds trending topic automatically)
```

**Buttons on the page:**
- `[Research Trending Topics]` — shows top 10 trending suggestions below the form
- `[Generate Video]` — triggers the full pipeline
- `[View All Projects]` — link to `/projects`
- `[Explore Trends]` — link to `/research`

---

## VIDEO GENERATION PIPELINE (in order)

### Step 1 — Trending Research (if Auto-Research ON or button clicked)
- Use `pytrends` (`TrendReq`) to get rising/top topics related to the subject
- Scrape `https://www.youtube.com/feed/trending` with BeautifulSoup to extract video titles
- Return top 10 suggestions + 5 trending-style title rewrites per topic
- If offline or scrape fails, fall back to a local trending templates list

### Step 2 — Script Generation (modules/script_generator.py)
- NO AI API. Use template-based generation only.
- Each content type has its own narrative template:
  - `Storytelling`: Hook → Setup → Rising action → Climax → Resolution → CTA
  - `Sci-Fi`: Discovery → Technical exposition → Conflict → Resolution → Future implication
  - `Educational`: Question hook → Context → 3-5 key facts → Summary → CTA
  - `Horror`: Unsettling hook → Build tension → Reveal → Aftermath → Warning CTA
  - `Motivational`: Pain point → Story → Lesson → Action steps → CTA
  - `Mystery`: Strange fact hook → Background → Clues → Theory → Unresolved ending
  - `Documentary`: Historical context → Key figures → Events → Impact → Today
  - `History`: Era setup → Key event → Cause & effect → Legacy → Lesson
- Script length is controlled by duration setting:
  - 30s = ~75 words, 60s = ~150 words, 2min = ~300 words, 5min = ~750 words, 10min = ~1500 words
- Split script into scenes at paragraph breaks (each paragraph = one visual scene)
- Save script to `script.txt` in the project folder

### Step 3 — Audio Generation (modules/audio_generator.py)
- Use `edge-tts` as primary TTS engine (free Microsoft voices, internet needed)
- Voice mapping:
  ```python
  voices = {
      "Male US":    "en-US-GuyNeural",
      "Female US":  "en-US-JennyNeural",
      "Male UK":    "en-GB-RyanNeural",
      "Female UK":  "en-GB-SoniaNeural",
      "Male AU":    "en-AU-WilliamNeural",
      "Female AU":  "en-AU-NatashaNeural",
      "Neutral":    "en-US-AriaNeural"
  }
  ```
- If edge-tts fails (offline), fall back to `pyttsx3`
- Save audio as `audio_narration.mp3` in project folder
- **CRITICAL**: Verify audio file exists and duration > 0 before continuing
- Log audio duration in seconds — this controls video length

### Step 4 — Background Music Generation (modules/audio_generator.py)
- Generate music using `numpy` + `scipy` sine/square wave synthesis (no files needed)
- Mood presets:
  - `Epic`: layered low drones + slow build (40Hz base + harmonics)
  - `Calm`: soft sine wave at 432Hz, slow fade in/out
  - `Dark/Suspense`: dissonant intervals, minor key tones
  - `Uplifting`: major key arpeggios at medium tempo
  - `Mystery`: binaural-style slow oscillation
  - `None`: skip this step
- Mix music at 20% volume under narration using MoviePy's `CompositeAudioClip`
- Save as `background_music.mp3`

### Step 5 — Scene/Frame Generation (modules/scene_generator.py)
- One image per script paragraph/scene using Pillow only
- Resolution based on quality + ratio:
  ```
  16:9  → 1280x720 (720p), 1920x1080 (1080p), 3840x2160 (4K)
  9:16  → 720x1280 (720p), 1080x1920 (1080p)
  1:1   → 720x720 (720p), 1080x1080 (1080p)
  4:3   → 960x720 (720p), 1440x1080 (1080p)
  ```
- Style-based color palettes:
  ```python
  palettes = {
      "Cinematic":      {"bg": "#0a0a1a", "accent": "#c8a94e", "text": "#e8e8e8"},
      "Ghibli-Inspired":{"bg": "#d4e8c2", "accent": "#7ba05b", "text": "#2c1810"},
      "Minimalist":     {"bg": "#f5f5f0", "accent": "#333333", "text": "#111111"},
      "Cyberpunk/Neon": {"bg": "#0d0d0d", "accent": "#ff006e", "text": "#00f5ff"},
      "Vintage":        {"bg": "#d4a853", "accent": "#8b4513", "text": "#2c1810"},
      "Comic Book":     {"bg": "#fffde7", "accent": "#e53935", "text": "#1a1a1a"},
      "Nature & Calm":  {"bg": "#1a3a2a", "accent": "#4caf50", "text": "#e8f5e9"}
  }
  ```
- Draw scene text centered with word-wrap using Pillow's `ImageDraw` + `ImageFont`
- Add scene number overlay (subtle, bottom right corner)
- Apply gradient overlay for depth
- Save as `scene_01.png`, `scene_02.png`, etc.

### Step 6 — Animation Effect Application (modules/scene_generator.py)
Apply animation by generating multiple frames per scene or using MoviePy effects:
- `Ken Burns`: use `clip.resize(lambda t: 1 + 0.04*t).set_position(('center','center'))`
- `Fade Transitions`: `clip.crossfadein(0.5)` between scenes
- `Glitch Effect`: randomize small pixel offsets using numpy on a few frames
- `Typewriter Text`: reveal text character by character across the clip duration
- `Slide In`: use `clip.set_position(lambda t: (max(0, -W + W*t/0.5), 'center'))` for first 0.5s
- `Static`: no animation, just hold the image

### Step 7 — Video Assembly (modules/video_assembler.py)
```python
from moviepy.editor import *

# Load scene images
clips = []
for scene_img, scene_text, duration in zip(scene_images, scene_texts, scene_durations):
    img_clip = ImageClip(scene_img).set_duration(duration)
    img_clip = apply_animation(img_clip, animation_style)
    clips.append(img_clip)

# Concatenate all scenes
video = concatenate_videoclips(clips, method="compose")

# CRITICAL: Attach audio — this fixes the no-sound bug
narration = AudioFileClip("audio_narration.mp3")

if background_music_mood != "None":
    music = AudioFileClip("background_music.mp3").volumex(0.2)
    music = music.subclip(0, narration.duration).audio_fadeout(2)
    final_audio = CompositeAudioClip([narration, music])
else:
    final_audio = narration

video = video.set_audio(final_audio)

# Verify audio is attached
assert video.audio is not None, "AUDIO NOT ATTACHED — aborting"

# Export with audio
video.write_videofile(
    "final_video.mp4",
    fps=24,
    codec="libx264",
    audio_codec="aac",
    audio_bitrate="192k",
    threads=4
)
```
- Always verify `video.audio is not None` before export
- Log the output file size and duration to confirm success

### Step 8 — Thumbnail Generation (modules/thumbnail_generator.py)
- Always 1280x720 for landscape, 1080x1920 for 9:16 Shorts
- Use Pillow to build:
  - Styled background matching the video style palette
  - Large bold title text (split into 2 lines max)
  - Subtle gradient overlay (bottom-to-top dark fade)
  - Optional: a simple icon/emoji rendered as text in a contrasting circle
  - Channel-name-style small text at the bottom
- Save as `thumbnail.png`

### Step 9 — Metadata Generation (modules/metadata_generator.py)
Generate all YouTube upload metadata using templates (no AI API):

**Titles** — generate 5 options using trending title patterns:
```
Pattern 1: "The [Shocking/Hidden/Real] Truth About [TOPIC] (Most People Don't Know This)"
Pattern 2: "[TOPIC] Explained in [DURATION] — You Won't Believe #[NUMBER]"
Pattern 3: "Why [TOPIC] Is Changing Everything in [CURRENT_YEAR]"
Pattern 4: "I Studied [TOPIC] for [TIME] — Here's What I Found"
Pattern 5: "[NUMBER] Things About [TOPIC] That Will Blow Your Mind"
```

**Description** — 400-word SEO template:
- Hook paragraph (repeat best title)
- 3-paragraph content summary from script
- Timestamps if duration > 2 min
- 5 related topic suggestions
- CTA: "Like, Subscribe, Turn on Notifications"
- 10 hashtags at the bottom

**Tags** — 30 tags:
- 10 broad tags (e.g., "facts", "educational", "top 10")
- 10 topic-specific tags derived from the subject line words
- 10 trending tags pulled from pytrends for the topic

Save all metadata to `metadata.json` in the project folder.

---

## FILE STORAGE — ONE FOLDER PER VIDEO

Every project saves to: `./projects/{safe_topic_name}_{YYYYMMDD_HHMMSS}/`

```
projects/
└── why_black_holes_exist_20260530_143022/
    ├── final_video.mp4        ← final video WITH audio (always check this plays)
    ├── thumbnail.png          ← 1280x720 YouTube thumbnail
    ├── audio_narration.mp3    ← voice narration
    ├── background_music.mp3   ← generated background music (if selected)
    ├── script.txt             ← full narration script
    ├── metadata.json          ← all YouTube metadata
    ├── settings.json          ← exact settings used to make this video
    ├── scene_01.png
    ├── scene_02.png
    └── ...
```

Folder naming rules:
- Lowercase, underscores only, max 50 characters
- `re.sub(r'[^a-z0-9_]', '_', topic.lower().strip())[:50]`

---

## EXCEL PROJECT LOG

File: `./video_log.xlsx` — auto-created on first run, appended on each new video.

**Columns:**
| # | Column Name | Source |
|---|---|---|
| A | Date Created | auto |
| B | Topic | user input |
| C | Best Title (used) | metadata_generator |
| D | Duration | settings |
| E | Quality | settings |
| F | Style | settings |
| G | Voice | settings |
| H | Content Type | settings |
| I | Video File Path | file system |
| J | Thumbnail Path | file system |
| K | Tags (comma-separated) | metadata_generator |
| L | Description (first 200 chars) | metadata_generator |
| M | Upload Status | **manual** — leave blank |
| N | YouTube URL | **manual** — leave blank |
| O | Views (7-day) | **manual** — leave blank |
| P | Revenue ($) | **manual** — leave blank |

- Sort: most recent at top (row 2, header is row 1)
- After saving, auto-open the Excel file: `os.startfile(os.path.abspath("video_log.xlsx"))`
- Bold + freeze the header row
- Auto-fit column widths

---

## ROUTES TO BUILD

| Route | Purpose |
|---|---|
| `GET /` | Main video creator form |
| `POST /generate` | Trigger video generation pipeline |
| `GET /progress/<job_id>` | SSE stream for progress updates |
| `GET /projects` | Table of all past projects |
| `GET /projects/<folder_name>` | Single project detail + video player |
| `GET /research` | Trending topic explorer |
| `POST /research/fetch` | AJAX: fetch trending topics for a keyword |
| `GET /video/<folder>/<filename>` | Serve video/thumbnail files |

---

## PROGRESS TRACKING

- Use Flask Server-Sent Events (SSE) at `/progress/<job_id>` 
- Frontend polls this endpoint and updates a progress bar
- Steps to report:
  1. "Researching trends..." (10%)
  2. "Writing script..." (20%)
  3. "Generating voice audio..." (35%)
  4. "Creating scene images..." (55%)
  5. "Generating background music..." (65%)
  6. "Assembling video..." (80%)
  7. "Creating thumbnail..." (90%)
  8. "Generating metadata + logging to Excel..." (95%)
  9. "Done!" (100%)

---

## UI DESIGN REQUIREMENTS

- **Theme**: Dark background `#0f0f0f`, card background `#1a1a1a`, accent `#ff0000` (YouTube red)
- **Font**: System font stack — no Google Fonts (works offline)
- **Layout**: Single-column centered form, max-width 800px
- **After generation**: Show a result card with:
  - Embedded `<video>` player for the final video
  - Thumbnail preview image
  - Copy buttons for: Title, Description, Tags
  - "Open Project Folder" button (calls a `/open_folder` endpoint)
  - "Add to Excel Log" button (if not auto-logged)
- **Responsive**: Works on 1920x1080 and 1366x768

---

## SETUP FILES TO CREATE

### requirements.txt
```
flask
moviepy
Pillow
edge-tts
pyttsx3
pytrends
beautifulsoup4
requests
numpy
scipy
openpyxl
imageio
imageio-ffmpeg
```

### setup.bat
```bat
@echo off
echo Installing VideoMaker...
python -m venv venv
call venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
echo Setup complete! Starting app...
python app.py
```

### run.bat
```bat
@echo off
call venv\Scripts\activate
python app.py
```

---

## BUG FIXES REQUIRED (from previous broken version)

1. **No Sound Bug** — MUST FIX:
   - Always generate `audio_narration.mp3` BEFORE assembling video
   - Always call `.set_audio(AudioFileClip(...))` on the final video clip
   - Always export with `audio_codec="aac"`
   - Assert `video.audio is not None` before writing file
   - Test: after export, check file size > 500KB and duration matches audio

2. **ffmpeg not found** — Handle gracefully:
   - `imageio-ffmpeg` provides a bundled ffmpeg
   - Set: `import imageio_ffmpeg; os.environ["FFMPEG_BINARY"] = imageio_ffmpeg.get_ffmpeg_exe()`
   - Do this at the top of `app.py` before any MoviePy import

3. **edge-tts async** — edge-tts uses asyncio:
   - Wrap calls with `asyncio.run(generate_audio(...))` or use `nest_asyncio` if inside Flask

---

## IMPLEMENTATION ORDER

Build in this exact order so each piece can be tested before moving on:

1. Project folder structure + `requirements.txt` + `setup.bat` + `run.bat`
2. `config.py` with all constants and palette definitions
3. `modules/audio_generator.py` — test that a WAV/MP3 file is created with sound
4. `modules/scene_generator.py` — test that PNG images are created with text
5. `modules/video_assembler.py` — test that `final_video.mp4` has audio (open in VLC)
6. `modules/thumbnail_generator.py`
7. `modules/script_generator.py` with all content type templates
8. `modules/metadata_generator.py`
9. `modules/trend_researcher.py`
10. `modules/excel_logger.py`
11. `app.py` — Flask routes wiring all modules together
12. `templates/index.html` with all form controls
13. `templates/projects.html`
14. `templates/research.html`
15. `static/style.css` dark theme
16. `static/app.js` progress bar + AJAX

After step 5, run a smoke test: generate a 30-second video and confirm it plays with audio in Windows Media Player before continuing.

---

## FINAL CHECKLIST

Before reporting the application as complete, verify:

- [ ] `setup.bat` installs everything without errors
- [ ] `run.bat` starts the Flask server
- [ ] Browser opens to the form page with all dropdowns populated
- [ ] Generating a 30s video creates the project folder with all files
- [ ] `final_video.mp4` plays WITH audio (not silent)
- [ ] `thumbnail.png` is created and visually matches the style
- [ ] `metadata.json` contains title options, description, and 30 tags
- [ ] `video_log.xlsx` is created/updated and opens automatically
- [ ] `/projects` page shows the completed project
- [ ] `/research` page returns trending topics
- [ ] No crashes on all 9 content types and all 7 video styles
```
