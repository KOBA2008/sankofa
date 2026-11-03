"""Configuration centrale : chemins, clés et noms de modèles."""
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
PLACES_DIR = DATA / "places"
RUNS_DIR = DATA / "runs"
UPLOADS_DIR = DATA / "uploads"
CACHE_DIR = DATA / "cache"
for d in (PLACES_DIR, RUNS_DIR, UPLOADS_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

META_API_KEY = os.getenv("META_API_KEY", "").strip()
META_BASE_URL = os.getenv("META_BASE_URL", "https://api.meta.ai/v1").strip()
MODEL_TEXT = os.getenv("META_MODEL_TEXT", "muse-spark-1.3")
MODEL_IMAGE = os.getenv("META_MODEL_IMAGE", "muse-image-1.0")
MODEL_SEGMENT = os.getenv("META_MODEL_SEGMENT", "sam-3.1")
MODEL_TRANSCRIBE = os.getenv("META_MODEL_TRANSCRIBE", "muse-voice-transcribe-1.0")

# Baseten : modèles open weights de Meta (Llama) derrière une API compatible OpenAI
BASETEN_API_KEY = os.getenv("BASETEN_API_KEY", "").strip()
BASETEN_BASE_URL = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1").strip()
BASETEN_MODEL = os.getenv("BASETEN_MODEL", "").strip()  # vide : choisi automatiquement parmi les modèles Llama

# Wikimedia demande un User-Agent qui identifie l'outil
USER_AGENT = "SankofaBot/0.1 (heritage research prototype; +https://github.com/) python-httpx"
