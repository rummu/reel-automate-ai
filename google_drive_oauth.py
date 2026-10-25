"""
Google Drive OAuth Login Helper
- Authorizes your personal Google Drive account
- Generates token.json so reels upload directly to your personal Google Drive
"""
import os
import sys
import json
from pathlib import Path

# Force UTF-8 encoding on Windows to prevent charmap crashes
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file"
]

def main():
    client_secret_file = Path("client_secret.json")
    token_file = Path("token.json")

    if not client_secret_file.exists():
        print("\n[OAuth] ERROR: client_secret.json not found!", flush=True)
        return False

    print("\n" + "=" * 60, flush=True)
    print("  GOOGLE DRIVE ONE-TIME ACCOUNT AUTHORIZATION", flush=True)
    print("=" * 60, flush=True)
    print("[OAuth] Starting local authorization listener on port 8085...", flush=True)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_file), 
        scopes=SCOPES
    )

    prompt_msg = (
        "\nPLEASE VISIT THIS URL IN YOUR BROWSER TO AUTHORIZE:\n"
        "{url}\n\n"
        "Waiting for you to sign in and click 'Allow' in your browser...\n"
    )

    creds = flow.run_local_server(
        port=8085,
        prompt='consent',
        access_type='offline',
        open_browser=True,
        authorization_prompt_message=prompt_msg,
        success_message="Authentication successful! Reel Automate AI is now authorized. You can close this window."
    )

    with open(token_file, "w") as f:
        f.write(creds.to_json())

    print("\n" + "=" * 60, flush=True)
    print("  SUCCESS: token.json CREATED SUCCESSFULLY!", flush=True)
    print("  Automated Google Drive uploads are now fully enabled!", flush=True)
    print("=======================================================\n", flush=True)
    return True

if __name__ == "__main__":
    main()
