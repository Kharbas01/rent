"""Run this once to connect Google Drive (OAuth, not a service account).

What it does:
  1. Opens your browser and asks you to sign in with the Google account
     whose Drive you want agreements uploaded to.
  2. Saves the resulting token.json next to this file.
  3. app/google_drive.py then reuses/refreshes that token automatically —
     you never have to run this again unless you revoke access.

Prerequisites:
  - GOOGLE_OAUTH_CREDENTIALS_FILE in .env pointing at your OAuth client
    JSON (Google Cloud Console -> APIs & Services -> Credentials ->
    Create Credentials -> OAuth client ID -> Application type: Desktop app).
    Defaults to "credentials.json" in the project root.
  - GOOGLE_DRIVE_FOLDER_ID in .env set to the target Drive folder's ID
    (the long id in the folder's URL). The signed-in account must already
    have access to that folder (it's fine if it's the owner).

Usage:
    python google_oauth_setup.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> None:
    settings = get_settings()
    creds_path = Path(settings.google_oauth_credentials_file)
    token_path = Path(settings.google_oauth_token_file)

    if not creds_path.exists():
        print(f"Could not find OAuth credentials file at: {creds_path}")
        print(
            "Download it from Google Cloud Console (Credentials -> OAuth client ID, "
            "type = Desktop app), save it there, and set GOOGLE_OAUTH_CREDENTIALS_FILE "
            "in .env if you used a different name/path."
        )
        sys.exit(1)

    if not settings.google_drive_folder_id:
        print("GOOGLE_DRIVE_FOLDER_ID is not set in .env — set it before continuing.")
        sys.exit(1)

    print("Opening your browser to sign in to Google...")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json())
    print(f"\nSuccess! Saved {token_path}")
    print("Google Drive uploads will now work without any further sign-in.")


if __name__ == "__main__":
    main()
