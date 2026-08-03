"""Google Drive integration using OAuth "sign in as a user" credentials.

Uploads agreement files into a single shared Drive folder (folder ID comes
from GOOGLE_DRIVE_FOLDER_ID in .env). Run `python google_oauth_setup.py`
once to open a browser, sign in, and create token.json — after that this
module refreshes the token automatically and never needs a browser again.
"""

from __future__ import annotations

import io
import time
from functools import lru_cache

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.config import get_settings
from app.errors import AppError

SCOPES = ["https://www.googleapis.com/auth/drive"]
MAX_RETRIES = 3


class DriveNotConfigured(AppError):
    def __init__(self, reason: str | None = None) -> None:
        message = reason or (
            "Google Drive is not configured. Set GOOGLE_OAUTH_CREDENTIALS_FILE and "
            "GOOGLE_DRIVE_FOLDER_ID in your .env file, then run "
            "`python google_oauth_setup.py` once to sign in."
        )
        super().__init__(message, status_code=500)


def _load_credentials() -> Credentials:
    settings = get_settings()
    if not settings.google_oauth_credentials_file or not settings.google_drive_folder_id:
        raise DriveNotConfigured()

    from pathlib import Path

    token_path = Path(settings.google_oauth_token_file)
    if not token_path.exists():
        raise DriveNotConfigured(
            "Google Drive isn't connected yet. Run `python google_oauth_setup.py` "
            "once (locally, with a browser) to sign in and create token.json."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        else:
            raise DriveNotConfigured(
                "Your Google Drive sign-in has expired or was revoked. Run "
                "`python google_oauth_setup.py` again to reconnect."
            )

    return creds


@lru_cache(maxsize=1)
def _get_service():
    credentials = _load_credentials()
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _with_retries(fn, *args, **kwargs):
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except HttpError as exc:  # noqa: PERF203 - retry loop is intentional
            last_error = exc
            # 4xx errors (not found, forbidden, bad request, ...) are permanent —
            # retrying them 3 times just delays a clear error unnecessarily.
            status = getattr(exc, "status_code", None) or getattr(exc.resp, "status", None)
            if status and 400 <= int(status) < 500:
                break
            if attempt < MAX_RETRIES:
                time.sleep(attempt * 0.6)
    if last_error is not None and getattr(last_error, "resp", None) is not None and last_error.resp.status == 404:
        raise AppError(
            "Google Drive folder not found. Check that GOOGLE_DRIVE_FOLDER_ID in .env "
            "is correct, and that the Google account you signed in with "
            "(google_oauth_setup.py) actually has access to that folder — "
            "open the folder's sharing settings and confirm, or share it with that account."
        )
    raise AppError(f"Google Drive request failed after {MAX_RETRIES} attempts: {last_error}")


def upload_bytes(content: bytes, filename: str, mime_type: str) -> dict:
    """Upload a file into the configured Drive folder and return id + link."""
    settings = get_settings()
    service = _get_service()

    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False)
    metadata = {"name": filename, "parents": [settings.google_drive_folder_id]}

    file = _with_retries(
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,webViewLink,webContentLink",
            supportsAllDrives=True,
        )
        .execute
    )

    file_id = file["id"]

    # Make the file viewable by anyone with the link so it can be opened /
    # downloaded from the app without asking every tenant to sign in with Google.
    try:
        _with_retries(
            service.permissions()
            .create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
                supportsAllDrives=True,
            )
            .execute
        )
    except AppError:
        pass  # sharing is best-effort; the file still exists and is owner-accessible

    link = file.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
    return {"drive_file_id": file_id, "drive_link": link}


def delete_file(file_id: str) -> None:
    if not file_id:
        return
    service = _get_service()
    try:
        _with_retries(service.files().delete(fileId=file_id, supportsAllDrives=True).execute)
    except AppError:
        pass  # if it's already gone (or inaccessible), don't block the DB delete


def download_bytes(file_id: str) -> tuple[bytes, str]:
    """Return (file_bytes, mime_type) for proxying a download through our server."""
    service = _get_service()
    meta = _with_retries(
        service.files().get(fileId=file_id, fields="mimeType,name", supportsAllDrives=True).execute
    )
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue(), meta.get("mimeType", "application/octet-stream")