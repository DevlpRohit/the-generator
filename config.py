import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# ── Resolution map ─────────────────────────────────────────────
RESOLUTIONS = {
    "16:9": {
        "360p": (640, 360), "480p": (854, 480), "720p": (1280, 720),
        "1080p": (1920, 1080), "4K": (3840, 2160),
    },
    "9:16": {
        "360p": (360, 640), "480p": (480, 854), "720p": (720, 1280),
        "1080p": (1080, 1920), "4K": (2160, 3840),
    },
    "1:1": {
        "360p": (360, 360), "480p": (480, 480), "720p": (720, 720),
        "1080p": (1080, 1080), "4K": (2160, 2160),
    },
    "4:3": {
        "360p": (480, 360), "480p": (640, 480), "720p": (960, 720),
        "1080p": (1440, 1080), "4K": (2880, 2160),
    },
}

# ── Duration → target word count ───────────────────────────────
DURATION_WORDS = {
    "30s": 75, "60s": 150, "2min": 300, "5min": 750, "10min": 1500,
}

DURATION_SECONDS = {
    "30s": 30, "60s": 60, "2min": 120, "5min": 300, "10min": 600,
}

# ── Voice map ──────────────────────────────────────────────────
VOICES = {
    "Male US":     "en-US-GuyNeural",
    "Female US":   "en-US-JennyNeural",
    "Male UK":     "en-GB-RyanNeural",
    "Female UK":   "en-GB-SoniaNeural",
    "Male AU":     "en-AU-WilliamNeural",
    "Female AU":   "en-AU-NatashaNeural",
    "Neutral/Soft": "en-US-AriaNeural",
}

# ── Cloned voice (commercial-safe Chatterbox) ─────────────────
# When this voice is selected, narration is generated in the user's own cloned
# voice from the reference recording below (MIT-licensed engine, monetizable).
CLONED_VOICE_LABEL = "My Cloned Voice"
VOICE_PROFILE_PATH = BASE_DIR / "voice_profiles" / "my_voice.wav"

# ── Style colour palettes ──────────────────────────────────────
PALETTES = {
    "Cinematic":      {"bg": "#0a0a1a", "accent": "#c8a94e", "text": "#e8e8e8", "sub": "#888888"},
    "Ghibli-Inspired":{"bg": "#d4e8c2", "accent": "#7ba05b", "text": "#2c1810", "sub": "#556b2f"},
    "Minimalist":     {"bg": "#f5f5f0", "accent": "#333333", "text": "#111111", "sub": "#777777"},
    "Cyberpunk/Neon": {"bg": "#0d0d0d", "accent": "#ff006e", "text": "#00f5ff", "sub": "#9900ff"},
    "Vintage":        {"bg": "#d4a853", "accent": "#8b4513", "text": "#2c1810", "sub": "#704214"},
    "Comic Book":     {"bg": "#fffde7", "accent": "#e53935", "text": "#1a1a1a", "sub": "#333333"},
    "Nature & Calm":  {"bg": "#1a3a2a", "accent": "#4caf50", "text": "#e8f5e9", "sub": "#81c784"},
}

# ── Content types ──────────────────────────────────────────────
CONTENT_TYPES = [
    "Storytelling", "Sci-Fi", "Educational", "Horror",
    "Motivational", "Mystery", "Documentary", "History", "Comedy",
]

# ── Animation types ────────────────────────────────────────────
ANIMATIONS = [
    "Auto (Varied Motion)",      # rotates motion per scene — avoids the static-slideshow look
    "Ken Burns", "Fade Transitions", "Glitch Effect",
    "Typewriter Text", "Slide In", "Static",
]

# ── Music moods ────────────────────────────────────────────────
MUSIC_MOODS = ["Auto (AI Picks)", "None", "Epic/Dramatic", "Calm/Peaceful", "Dark/Suspense", "Uplifting", "Mystery"]

# ── Faceless YouTube niches (used by trend research) ──────────
NICHES = [
    "Psychology & Mind",
    "History & Mysteries",
    "Science & Space",
    "Self-Improvement",
    "Money & Finance",
    "Health & Nutrition",
    "Technology & AI",
    "Conspiracy Theories",
    "True Crime",
    "Philosophy",
    "Business & Entrepreneurship",
    "Motivation & Success",
    "Spirituality",
    "Relationships & Dating",
    "Pop Culture",
    "Education & Learning",
    "Nature & Animals",
    "Travel & Adventure",
    "Food & Cooking",
    "Gaming",
    "Sports & Fitness",
    "Movies & Entertainment",
]

# ── Sub-niches (cascading from each parent niche) ─────────────
SUB_NICHES: dict[str, list[str]] = {
    "Psychology & Mind": [
        "Cognitive Biases", "Dream Science", "Manipulation & Persuasion",
        "Memory & Learning", "Mental Health", "Neuroscience",
        "Human Behavior", "Emotional Intelligence", "Social Psychology",
        "Dark Psychology", "Addiction & Habits", "IQ & Intelligence",
    ],
    "History & Mysteries": [
        "Ancient Civilizations", "World Wars", "Lost Civilizations",
        "Historical Figures", "Unsolved Mysteries", "Secret Societies",
        "Archaeological Discoveries", "Medieval History", "Cold War",
        "Historical Crimes", "Forgotten Empires", "Historical Hoaxes",
    ],
    "Science & Space": [
        "Black Holes", "Quantum Physics", "Mars & Planets",
        "Dark Matter & Energy", "Multiverse Theory", "Alien Life",
        "Space Exploration", "Physics Experiments", "Astronomy",
        "Climate Science", "Biology & Evolution", "Chemistry Secrets",
    ],
    "Self-Improvement": [
        "Morning Routines", "Productivity Hacks", "Discipline & Habits",
        "Mindset & Focus", "Time Management", "Stoicism",
        "Reading & Learning", "Social Skills", "Goal Setting",
        "Overcoming Fear", "Confidence Building", "Decluttering & Simplicity",
    ],
    "Money & Finance": [
        "Investing for Beginners", "Passive Income", "Crypto & Blockchain",
        "Stock Market", "Real Estate", "Financial Freedom",
        "Side Hustles", "Budgeting & Saving", "Wealth Building",
        "Economic Collapse", "Debt & Credit", "Taxes & Loopholes",
    ],
    "Health & Nutrition": [
        "Intermittent Fasting", "Brain Foods", "Sleep Science",
        "Exercise Science", "Anti-Aging", "Mental Health & Diet",
        "Gut Health", "Vitamins & Supplements", "Cancer Prevention",
        "Longevity", "Detox & Cleansing", "Weight Loss Science",
    ],
    "Technology & AI": [
        "Artificial Intelligence", "ChatGPT & LLMs", "Robotics",
        "Cybersecurity", "Quantum Computing", "Future of Work",
        "Surveillance Tech", "Neural Interfaces", "Automation",
        "Tech Giants & Ethics", "Space Tech", "Biotech & Gene Editing",
    ],
    "Conspiracy Theories": [
        "Government Secrets", "Moon Landing", "Area 51",
        "Illuminati", "Deep State", "Big Pharma",
        "Media Manipulation", "Secret Experiments", "UFO Cover-ups",
        "New World Order", "False Flags", "Ancient Aliens",
    ],
    "True Crime": [
        "Serial Killers", "Cold Cases", "Heists & Scams",
        "Cults", "Missing Persons", "Prison Stories",
        "Hitmen & Assassins", "White-Collar Crime", "Forensics",
        "Infamous Trials", "Kidnappings", "Unsolved Murders",
    ],
    "Philosophy": [
        "Stoicism", "Existentialism", "Ethics & Morality",
        "Free Will", "Simulation Theory", "Nihilism",
        "Eastern Philosophy", "Plato & Aristotle", "Death & Meaning",
        "Political Philosophy", "Logic & Reasoning", "Consciousness",
    ],
    "Business & Entrepreneurship": [
        "Startup Stories", "Billionaire Habits", "Business Failures",
        "Marketing Secrets", "Leadership", "E-commerce",
        "Personal Branding", "Sales Psychology", "Dropshipping",
        "Amazon FBA", "Building an Audience", "Franchise Models",
    ],
    "Motivation & Success": [
        "Success Stories", "Overcoming Failure", "Grit & Resilience",
        "Daily Disciplines", "Visualization", "Flow State",
        "Champions Mindset", "Rise & Grind", "Comebacks",
        "Underdog Stories", "Work Ethic Secrets", "Olympic Mindset",
    ],
    "Spirituality": [
        "Law of Attraction", "Meditation", "Near-Death Experiences",
        "Astral Projection", "Ancient Wisdom", "Manifestation",
        "Religion & Science", "Sacred Geometry", "Energy & Chakras",
        "Afterlife", "Lucid Dreaming", "Synchronicity",
    ],
    "Relationships & Dating": [
        "Attachment Styles", "Dating Psychology", "Breakups & Healing",
        "Red Flags & Narcissism", "Body Language", "Attraction Science",
        "Long-Distance Relationships", "Toxic Relationships",
        "Marriage & Divorce", "Loneliness & Connection", "Cheating & Trust",
        "Friendship & Loyalty",
    ],
    "Pop Culture": [
        "Celebrity Drama", "Movie Theories", "Music Industry Secrets",
        "Internet Trends", "Fashion History", "Viral Moments",
        "TV Show Analysis", "Comic Book Culture", "Awards & Scandals",
        "Social Media Stars", "Influencer Culture", "Brand Stories",
    ],
    "Education & Learning": [
        "Study Techniques", "Speed Reading", "Language Learning",
        "Memory Palaces", "Online Learning", "Gifted Kids",
        "History of Education", "IQ & Intelligence", "Skill Mastery",
        "Learning Disabilities", "Schools Around the World", "Future of Education",
    ],
    "Nature & Animals": [
        "Ocean Mysteries", "Predators & Prey", "Animal Intelligence",
        "Endangered Species", "Insect World", "Evolution",
        "Natural Disasters", "Rainforest Secrets", "Migration",
        "Bizarre Creatures", "Deep Sea Life", "Animal Communication",
    ],
    "Travel & Adventure": [
        "Forbidden Places", "Underground Cities", "Ghost Towns",
        "Extreme Environments", "Lost Islands", "Abandoned Places",
        "World Wonders", "Dangerous Countries", "Solo Travel",
        "Budget Travel Hacks", "Hidden Gems", "Cultural Secrets",
    ],
    "Food & Cooking": [
        "Food Science", "Street Food World", "Cooking Hacks",
        "Food History", "Bizarre Foods", "Diet Comparison",
        "Restaurant Secrets", "Fermentation", "Superfoods",
        "Food Psychology", "Michelin Star Secrets", "Food Fraud",
    ],
    "Gaming": [
        "Game Lore & Stories", "Game Development Secrets", "Speedrunning",
        "Retro Games", "Esports", "Game Psychology",
        "Hidden Easter Eggs", "Gaming Addiction", "Open World Secrets",
        "Game Theories", "Game Industry Drama", "Modding Culture",
    ],
    "Sports & Fitness": [
        "Athlete Mindset", "Training Science", "Sports Psychology",
        "Doping & Scandals", "Underdog Athletes", "Nutrition for Athletes",
        "World Records", "Combat Sports", "Sports Injuries",
        "Greatest Comebacks", "Coaching Secrets", "Sports Betting",
    ],
    "Movies & Entertainment": [
        "Behind the Scenes", "Movie Theories", "Deleted Scenes",
        "Box Office Flops", "Director Styles", "Hidden Symbolism",
        "Sequel Failures", "Cult Classics", "Documentary Picks",
        "Studio Secrets", "Casting Controversies", "Remakes vs Originals",
    ],
}

# ── Monetization-risk niches ───────────────────────────────────
# Advertiser-unfriendly or misinformation-prone niches that pair badly with the
# AI-faceless format under YouTube's Inauthentic Content + advertiser-friendly rules.
# Surface the caution in the UI and steer defaults toward safer niches.
RISKY_NICHES = {
    "Conspiracy Theories": "Misinformation risk — frequently advertiser-unfriendly and "
                           "prone to being flagged as inauthentic. Hard to monetize.",
    "True Crime":          "Graphic/sensitive content — often limited or no ads, and "
                           "AI reenactments may need disclosure. Handle carefully.",
}


def niche_risk(niche: str) -> str:
    """Return a monetization-caution note for a niche, or '' if it's considered safe."""
    return RISKY_NICHES.get(niche, "")


# ── Thumbnail size ─────────────────────────────────────────────
THUMB_SIZE_LANDSCAPE = (1280, 720)
THUMB_SIZE_PORTRAIT  = (1080, 1920)

# ── Voice speeds ──────────────────────────────────────────────
VOICE_SPEEDS = {
    "Slow (-20%)":   "-20%",
    "Normal":        "+0%",
    "Fast (+15%)":   "+15%",
}

# ── Subtitle style presets ─────────────────────────────────────
SUBTITLE_STYLES = [
    "Auto (AI Picks)",  # content_analyzer selects automatically based on topic/tone
    "Clean White",      # white text, black stroke, accent on last word
    "Bold Yellow",      # TikTok-style bright yellow
    "Neon Glow",        # white text with coloured glow
    "Minimal",          # small clean centered, no highlight
]

# ── Flask secret key ───────────────────────────────────────────
SECRET_KEY = "autovideo-secret-2026"
