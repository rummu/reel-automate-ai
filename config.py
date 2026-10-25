"""
Configuration settings for AI Aesthetic Reel Maker
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = BASE_DIR / "input_queue"
OUTPUT_DIR = BASE_DIR / "reels_output"
MUSIC_DIR = BASE_DIR / "music"
TEMP_DIR = BASE_DIR / "temp"

# Create directories if they don't exist
for d in [DATA_DIR, INPUT_DIR, OUTPUT_DIR, MUSIC_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except ImportError:
    pass

# Google Drive Integration Settings
env_input = os.getenv("GOOGLE_DRIVE_INPUT_FOLDER", "")
env_output = os.getenv("GOOGLE_DRIVE_OUTPUT_FOLDER", "")

IS_CLOUD_INPUT = "drive.google.com" in env_input
IS_CLOUD_OUTPUT = "drive.google.com" in env_output

CLOUD_INPUT_URL = env_input if IS_CLOUD_INPUT else ""
CLOUD_OUTPUT_URL = env_output if IS_CLOUD_OUTPUT else ""

# Local working directories
CLOUD_CACHE_DIR = BASE_DIR / "cloud_input_cache"
if IS_CLOUD_INPUT:
    CLOUD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    GOOGLE_DRIVE_INPUT_FOLDER = CLOUD_CACHE_DIR
else:
    GOOGLE_DRIVE_INPUT_FOLDER = Path(env_input) if env_input else INPUT_DIR

if IS_CLOUD_OUTPUT:
    GOOGLE_DRIVE_OUTPUT_FOLDER = OUTPUT_DIR
else:
    GOOGLE_DRIVE_OUTPUT_FOLDER = Path(env_output) if env_output else OUTPUT_DIR

# Reel Rules (Dynamic: supports 1 to 100+ items)
MIN_ITEMS_PER_DAY = int(os.getenv("MIN_ITEMS_PER_DAY", "1"))     # Dynamic minimum items (supports 1, 2, or 100+)
REQUIRE_PHOTOS = os.getenv("REQUIRE_PHOTOS", "false").lower() in ("true", "1", "yes") 
MIN_PHOTOS_REQUIRED = int(os.getenv("MIN_PHOTOS_REQUIRED", "0"))
TARGET_MIN_DURATION = 30.0      # Strictly enforced minimum reel length (30s)
TARGET_MAX_DURATION = 60.0      # Strictly enforced maximum reel length (60s)
REEL_WIDTH = 1080               # 9:16 1080x1920
REEL_HEIGHT = 1920
REEL_FPS = 30

# Curation and Quality Settings
MIN_LAPLACIAN_BLUR_SCORE = 65.0 # Lower values mean blurrier; filtered out
MAX_BURST_SIMILARITY = 0.92     # Skip near-duplicate burst shots
TARGET_SELECTED_CLIPS = 20      # Aim for 18-24 aesthetic shots per reel

# Motion & Pacing
PHOTO_CLIP_DURATION = 2.6       # Base duration per still image (adjusted to beats)
MIN_BEAT_INTERVAL = 1.4         # Fastest cut on beat
MAX_BEAT_INTERVAL = 4.5         # Slowest cut on beat
KEN_BURNS_ZOOM_RATIO = 1.12     # Subtle 12% zoom drift

# Aesthetic Color Presets
AESTHETIC_PRESET = "arif_cinematic" # Choices: 'arif_cinematic', 'golden_hour', 'moody_film'
ADD_FILM_GRAIN = True
GRAIN_INTENSITY = 0.04
ADD_VIGNETTE = True
VIGNETTE_STRENGTH = 0.25

# Typography
DEFAULT_LOCATION_NAME = "Germany"
SHOW_DATE_BADGE = True
SHOW_LOCATION_BADGE = True
FONT_FAMILY = "arial.ttf"       # Fallback to standard clean sans-serif
