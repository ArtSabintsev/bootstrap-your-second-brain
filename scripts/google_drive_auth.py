#!/usr/bin/env python3
"""One-time OAuth setup for Google Drive meeting-notes ingest.

Run this once interactively (it opens a browser for the operator to authorize).
Stores a refresh token at <secrets_dir>/google-drive/token.json — never in
the vault. The daily ingest script (google_drive_meetings_ingest.py) reuses
that token unattended, no browser needed after this.

Prerequisite (one-time, ~3 minutes, done once in Google Cloud Console):
  1. https://console.cloud.google.com/apis/library/drive.googleapis.com
     -> select/create a project -> Enable.
  2. https://console.cloud.google.com/apis/credentials
     -> Create Credentials -> OAuth client ID -> Application type: Desktop app.
  3. Download the JSON, save it as:
       <secrets_dir>/google-drive/client_secret.json
     (default secrets_dir is ~/Developer/helpers; see config.json)
  4. Run: python3 scripts/google_drive_auth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import secrets_dir  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main() -> int:
    creds_dir = secrets_dir() / "google-drive"
    client_secret = creds_dir / "client_secret.json"
    token_path = creds_dir / "token.json"

    if not client_secret.exists():
        print(f"Missing {client_secret}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0)

    creds_dir.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    token_path.chmod(0o600)
    print(f"Authorized. Refresh token saved to {token_path}")
    print("Daily ingest can now run unattended via google_drive_meetings_ingest.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
