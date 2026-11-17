"""
Application settings.

Every value is read from the .env file in the project root, so no secrets
live in the code. If a required value is missing, the app stops immediately
with a clear message instead of failing later in a confusing way.
"""
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing setting '{name}'. Open the .env file in the project root "
            f"and add it (see .env.example for a template)."
        )
    return value


def _text(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        raise RuntimeError(f"Setting '{name}' in .env must be a whole number.")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        raise RuntimeError(f"Setting '{name}' in .env must be a number.")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> List[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _floats(name: str, default: str) -> List[float]:
    try:
        return [float(item) for item in _list(name, default)]
    except ValueError:
        raise RuntimeError(f"Setting '{name}' in .env must be numbers separated by commas.")


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


class Settings:
    # --- Database ---
    DATABASE_URL: str = _required("DATABASE_URL")

    # --- Security ---
    SECRET_KEY: str = _required("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 480)
    ALLOWED_ORIGINS: List[str] = _list(
        "ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
    )

    # --- Administrator (created automatically on first start) ---
    ADMIN_NAME: str = _text("ADMIN_NAME", "System Administrator")
    ADMIN_EMAIL: str = _required("ADMIN_EMAIL").lower()
    ADMIN_PASSWORD: str = _required("ADMIN_PASSWORD")
    # Where "new doctor registration" alerts and the test email go. Defaults to the admin login email.
    ADMIN_NOTIFY_EMAIL: str = _text("ADMIN_NOTIFY_EMAIL", "") or ADMIN_EMAIL

    # --- Model ---
    # "auto" reads the architecture from the checkpoint. Only needed for plain state_dict files.
    MODEL_ARCH: str = _text("MODEL_ARCH", "auto").lower()
    MODEL_PATH: Path = _path(_text("MODEL_PATH", "app/weights/model.pth"))
    CLASS_NAMES: List[str] = _list("CLASS_NAMES", "glioma,meningioma,notumor,pituitary")
    IMAGE_SIZE: int = _int("IMAGE_SIZE", 224)
    USE_AUTOCONTRAST: bool = _bool("USE_AUTOCONTRAST", True)
    NORM_MEAN: List[float] = _floats("NORM_MEAN", "0.485,0.456,0.406")
    NORM_STD: List[float] = _floats("NORM_STD", "0.229,0.224,0.225")
    CONFIDENCE_THRESHOLD: float = _float("CONFIDENCE_THRESHOLD", 0.70)

    # Out-of-distribution checks (used when the checkpoint contains them, as MS-CBAM-Net's does).
    # Distance check: rejects images that do not look like the training MRIs.
    # In the training notebook it caught 100% of 'other' images with 5.5% false rejections.
    REJECT_ON_DISTANCE: bool = _bool("REJECT_ON_DISTANCE", True)
    # Confidence/entropy check: in the notebook it caught only 1.6% of 'other' images and wrongly
    # rejected 11% of real MRIs, so by default it only flags a scan for manual review.
    REJECT_ON_CONFIDENCE: bool = _bool("REJECT_ON_CONFIDENCE", False)

    # --- Login protection ---
    # After this many wrong passwords for one email from one address, login is blocked for a while.
    LOGIN_MAX_ATTEMPTS: int = _int("LOGIN_MAX_ATTEMPTS", 5)
    LOGIN_WINDOW_MINUTES: int = _int("LOGIN_WINDOW_MINUTES", 15)

    # --- Email (optional). Leave SMTP_HOST empty to print emails in the terminal instead. ---
    APP_BASE_URL: str = _text("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    SMTP_HOST: str = _text("SMTP_HOST", "")
    SMTP_PORT: int = _int("SMTP_PORT", 587)
    SMTP_USER: str = _text("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = _text("SMTP_FROM", "NeuroScan AI <no-reply@neuroscan.local>")
    SMTP_TLS: bool = _bool("SMTP_TLS", True)
    RESET_TOKEN_MINUTES: int = _int("RESET_TOKEN_MINUTES", 30)

    # --- Uploads and folders ---
    MAX_UPLOAD_MB: int = _int("MAX_UPLOAD_MB", 10)
    MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024
    STATIC_DIR: Path = BASE_DIR / "static"
    UPLOAD_DIR: Path = BASE_DIR / "static" / "uploads"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"


settings = Settings()

if len(settings.SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY in .env is too short. Use at least 32 characters. Generate one with: "
        'python -c "import secrets; print(secrets.token_hex(32))"'
    )
if len(settings.ADMIN_PASSWORD) < 8:
    raise RuntimeError("ADMIN_PASSWORD in .env must be at least 8 characters.")
if len(settings.CLASS_NAMES) < 2:
    raise RuntimeError("CLASS_NAMES in .env must list at least two classes.")
