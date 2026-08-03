"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Simple settings container (no external config library needed)."""

    def __init__(self) -> None:
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        self.supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "").strip()
        self.app_name: str = os.getenv("APP_NAME", "RentFlow").strip() or "RentFlow"
        self.host: str = os.getenv("HOST", "127.0.0.1").strip()
        self.port: int = int(os.getenv("PORT", "8000"))
        self.debug: bool = _as_bool(os.getenv("DEBUG"), True)
        self.cookie_secure: bool = _as_bool(os.getenv("COOKIE_SECURE"), False)
        self.allow_signup: bool = _as_bool(os.getenv("ALLOW_SIGNUP"), True)

        # Google Drive (agreement document storage) — OAuth "sign in as a user"
        # flow instead of a service account. credentials.json is the OAuth
        # client file downloaded from Google Cloud Console (Desktop app type).
        # token.json is created/refreshed automatically after the first
        # one-time browser consent (run google_oauth_setup.py once).
        raw_cred_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", "credentials.json").strip()
        cred_path = Path(raw_cred_path)
        self.google_oauth_credentials_file: str = (
            str(cred_path if cred_path.is_absolute() else BASE_DIR / cred_path)
        )

        raw_token_path = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json").strip()
        token_path = Path(raw_token_path)
        self.google_oauth_token_file: str = (
            str(token_path if token_path.is_absolute() else BASE_DIR / token_path)
        )

        self.google_drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        self.max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))

        self.base_dir: Path = BASE_DIR
        self.templates_dir: Path = TEMPLATES_DIR
        self.static_dir: Path = STATIC_DIR

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def drive_is_configured(self) -> bool:
        # "Configured" means the OAuth client file exists and a folder is set.
        # The user-consent token (token.json) is created separately by running
        # google_oauth_setup.py once; google_drive.py gives a clear error if
        # it's still missing when someone tries to actually upload a file.
        return bool(
            self.google_drive_folder_id and Path(self.google_oauth_credentials_file).exists()
        )

    def raise_if_unconfigured(self) -> None:
        if not self.is_configured:
            raise RuntimeError(
                "Supabase is not configured. Copy .env.example to .env and fill in "
                "SUPABASE_URL and SUPABASE_ANON_KEY."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()