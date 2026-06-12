---
title: Auto Video Maker
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Auto Video Maker

AI-powered faceless YouTube video generator. Enter a topic, choose a style and voice, and the app writes the script, generates visuals, adds narration, and assembles the final video — ready to download or upload to YouTube.

## Features
- Script generation via Google Gemini
- 7 visual styles with animations
- Edge-TTS narration (400+ voices)
- Background music synthesis
- YouTube monetization compliance gate
- Cloud storage via Supabase (videos available from any device)

## Required Secrets
Set these in the Space **Settings → Variables and secrets**:

| Secret | Required |
|--------|----------|
| `GEMINI_API_KEY` | Yes |
| `SUPABASE_URL` | Yes |
| `SUPABASE_KEY` | Yes |
| `PEXELS_API_KEY` | Optional (for B-roll footage) |
