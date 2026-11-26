import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

WORK_DIR = BASE_DIR / "workspace"
OUTPUT_DIR = BASE_DIR / "outputs"
MODEL_DIR = BASE_DIR / "models"

for d in (WORK_DIR, OUTPUT_DIR, MODEL_DIR):
    d.mkdir(parents=True, exist_ok=True)


def init_ffmpeg() -> bool:
    """Ensure ffmpeg and ffprobe are available on PATH via static-ffmpeg if missing."""
    import shutil

    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
        return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    except Exception:
        return False


def get_gemini_api_key(override: str | None = None) -> str | None:
    if override and override.strip():
        return override.strip()
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    return env_key or None
