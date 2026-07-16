#!/usr/bin/env python3
"""Ingest Google Meet's auto-generated ("Notes by Gemini") meeting docs into
Sources/meeting-notes/.

Google Meet's "Take notes for me" feature drops a Google Doc per meeting into
a "Meet Recordings" folder in the operator's Drive. This script finds new docs
there since the last run, exports each as plain text, dedupes by file ID
against prior captures, and appends new ones to a dated capture file
(meeting-notes-YYYY-MM-DD.md).

Sources/ is immutable per AGENTS.md: this script only appends. Filing a
capture into the right Meetings/<project>.md (or Projects/ note) is the daily
Claude enrichment pass's job, same as bookmarks/podcasts.

Auth: reads a refresh token from <secrets_dir>/google-drive/token.json,
created once via `python3 scripts/google_drive_auth.py` (see that file's
docstring for the one-time Google Cloud Console setup). Never stored in the
vault.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import secrets_dir  # noqa: E402

VAULT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = VAULT / "Sources" / "meeting-notes"
TOKEN_PATH = secrets_dir() / "google-drive" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

FOLDER_NAME = "Meet Recordings"
TITLE_MARKER = "Notes by Gemini"


def _drive_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not TOKEN_PATH.exists():
        print(f"missing token: {TOKEN_PATH} (run scripts/google_drive_auth.py once)", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def known_ids() -> set[str]:
    ids: set[str] = set()
    for md in CAPTURE_DIR.glob("*.md"):
        ids.update(re.findall(r"<!-- gdrive:([a-zA-Z0-9_-]+) -->", md.read_text()))
    return ids


def find_meet_recordings_folder(svc) -> str | None:
    res = svc.files().list(
        q=f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)",
        pageSize=5,
    ).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def list_notes_docs(svc, folder_id: str) -> list[dict]:
    res = svc.files().list(
        q=(
            f"'{folder_id}' in parents and "
            "mimeType = 'application/vnd.google-apps.document' and trashed = false"
        ),
        fields="files(id, name, createdTime, modifiedTime, webViewLink)",
        pageSize=100,
        orderBy="createdTime desc",
    ).execute()
    return res.get("files", [])


def export_text(svc, file_id: str) -> str:
    data = svc.files().export(fileId=file_id, mimeType="text/plain").execute()
    return data.decode("utf-8") if isinstance(data, bytes) else data


def render(doc: dict, body: str) -> str:
    title = doc["name"]
    created = doc.get("createdTime", "")[:10]
    link = doc.get("webViewLink", f"https://docs.google.com/document/d/{doc['id']}/edit")
    return (
        f"\n## {title} <!-- gdrive:{doc['id']} -->\n"
        f"captured {created}\n\n"
        f"{body.strip()}\n\n"
        f"{link}\n"
    )


def main() -> int:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    svc = _drive_service()

    folder_id = find_meet_recordings_folder(svc)
    if not folder_id:
        print("google-drive-meetings: no 'Meet Recordings' folder found (no Meet notes yet?)")
        return 0

    docs = [d for d in list_notes_docs(svc, folder_id) if TITLE_MARKER in d["name"]]
    seen = known_ids()
    fresh = [d for d in docs if d["id"] not in seen]

    if not fresh:
        print(f"google-drive-meetings: no new meeting notes (tracking {len(seen)})")
        return 0

    today = date.today().isoformat()
    out = CAPTURE_DIR / f"meeting-notes-{today}.md"
    chunks = []
    if not out.exists():
        chunks.append(
            f"# Meeting notes captured {today}\n\n"
            "Automated capture via scripts/google_drive_meetings_ingest.py "
            "(Google Meet's Notes-by-Gemini docs). Immutable raw source; "
            "filed into the right Meetings/<project>.md on ingest.\n"
        )

    for doc in fresh:
        try:
            body = export_text(svc, doc["id"])
        except Exception as e:  # noqa: BLE001
            print(f"WARN: failed to export {doc['name']}: {e}", file=sys.stderr)
            continue
        chunks.append(render(doc, body))

    with out.open("a") as f:
        f.write("".join(chunks))

    print(f"google-drive-meetings: appended {len(fresh)} doc(s) to {out.relative_to(VAULT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
