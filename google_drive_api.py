"""
Google Drive Cloud API & Web URL Handler
- Extracts Google Drive folder IDs from URLs
- Supports downloading media from shared cloud folders via gdown / Drive API
- Supports uploading rendered reels directly to Google Drive output folder
"""

import os
import re
import sys
from pathlib import Path

def extract_folder_id(url_or_id: str) -> str:
    """Extracts Google Drive folder ID from URL or raw ID."""
    if not url_or_id:
        return ""
    url_or_id = str(url_or_id).strip()
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    match_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url_or_id)
    if match_id:
        return match_id.group(1)
    if len(url_or_id) > 20 and "/" not in url_or_id:
        return url_or_id
    return ""

def is_google_drive_url(path_or_url: str) -> bool:
    """Returns True if the string is a Google Drive web URL."""
    return "drive.google.com" in str(path_or_url)

def ensure_cloud_credentials():
    """Restores token.json and client_secret.json from cloud environment variables if running in Docker/Cloud."""
    token_file = Path("token.json")
    if not token_file.exists() and os.getenv("GOOGLE_TOKEN_JSON"):
        try:
            with open(token_file, "w") as f:
                f.write(os.getenv("GOOGLE_TOKEN_JSON"))
            print("[Drive Cloud] Restored token.json from GOOGLE_TOKEN_JSON environment variable.", flush=True)
        except Exception as e:
            print(f"[Drive Cloud] Could not restore token.json: {e}", flush=True)

    client_secret_file = Path("client_secret.json")
    if not client_secret_file.exists() and os.getenv("GOOGLE_CLIENT_SECRET_JSON"):
        try:
            with open(client_secret_file, "w") as f:
                f.write(os.getenv("GOOGLE_CLIENT_SECRET_JSON"))
        except Exception:
            pass

ensure_cloud_credentials()

def download_folder_from_cloud(url_or_id: str, destination_dir: Path):
    """
    Downloads media files from a shared Google Drive folder URL to a local cache directory.
    Uses authenticated Google Drive API (token.json) for high-speed, direct sync if available.
    Falls back to gdown if no token is present.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    folder_id = extract_folder_id(url_or_id)
    
    if not folder_id:
        print(f"[Drive Cloud] Error: Invalid Google Drive folder URL: {url_or_id}", flush=True)
        return False

    token_file = Path("token.json")
    if token_file.exists():
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload

            creds = Credentials.from_authorized_user_file(str(token_file), scopes=["https://www.googleapis.com/auth/drive"])
            service = build("drive", "v3", credentials=creds)

            q = f"'{folder_id}' in parents and trashed = false"
            res = service.files().list(q=q, fields="files(id, name, mimeType, size, modifiedTime)").execute()
            remote_files = res.get("files", [])

            remote_names = {f["name"] for f in remote_files}

            # Clean up local cache if files were removed from Google Drive
            for local_file in destination_dir.glob("*"):
                if local_file.is_file() and local_file.name not in remote_names:
                    try:
                        local_file.unlink()
                        print(f"[Drive Cloud] Removed obsolete file: {local_file.name}", flush=True)
                    except Exception:
                        pass

            new_downloaded = 0
            for f in remote_files:
                name = f["name"]
                fid = f["id"]
                target_path = destination_dir / name
                expected_size = int(f.get("size", 0))

                if target_path.exists() and expected_size > 0 and target_path.stat().st_size == expected_size:
                    continue

                size_mb = round(expected_size / (1024 * 1024), 1)
                print(f"[Drive Cloud] Syncing incoming file: {name} ({size_mb} MB)...", flush=True)
                req = service.files().get_media(fileId=fid)
                with open(target_path, "wb") as out_f:
                    downloader = MediaIoBaseDownload(out_f, req, chunksize=10*1024*1024)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                new_downloaded += 1

            if new_downloaded > 0:
                print(f"[Drive Cloud] Synced {new_downloaded} new files from Google Drive.", flush=True)
            return True
        except Exception as e:
            print(f"[Drive Cloud] Direct API sync note: {e}, checking gdown fallback...", flush=True)

    print(f"\n[Drive Cloud] Syncing from Google Drive folder ID: {folder_id}...")
    try:
        import gdown
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        gdown.download_folder(url=folder_url, output=str(destination_dir), quiet=False, use_cookies=False)
        print(f"[Drive Cloud] Download completed to: {destination_dir}", flush=True)
        return True
    except ImportError:
        print("[Drive Cloud] Note: 'gdown' is not installed yet. Run: pip install gdown", flush=True)
        return False
    except Exception as e:
        print(f"[Drive Cloud] Error downloading folder: {e}", flush=True)
        return False

def upload_reel_to_cloud(local_reel_file: Path, output_url_or_id: str):
    """
    Uploads the rendered reel to Google Drive using google-api-python-client.
    If credentials.json or token.json is configured, uploads directly.
    Otherwise, returns status and direct browser upload link.
    """
    folder_id = extract_folder_id(output_url_or_id)
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else str(output_url_or_id)
    print(f"\n[Drive Cloud] Finished reel ready: {local_reel_file.name}")
    print(f"[Drive Cloud] Target Google Drive Folder: {folder_url}")

    # Check for Google Drive OAuth token or Service Account credentials
    creds_file = Path("credentials.json")
    token_file = Path("token.json")
    creds = None

    if token_file.exists():
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(str(token_file), scopes=["https://www.googleapis.com/auth/drive"])
        except Exception as e:
            print(f"[Drive Cloud] Error loading token.json: {e}")

    if not creds and creds_file.exists():
        try:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                str(creds_file), scopes=["https://www.googleapis.com/auth/drive"]
            )
        except Exception as e:
            print(f"[Drive Cloud] Error loading credentials.json: {e}")

    if creds:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            service = build("drive", "v3", credentials=creds)

            file_metadata = {
                "name": local_reel_file.name,
                "parents": [folder_id] if folder_id else []
            }
            media = MediaFileUpload(str(local_reel_file), mimetype="video/mp4", resumable=True, chunksize=10*1024*1024)
            request = service.files().create(body=file_metadata, media_body=media, fields="id")
            
            print(f"[Drive Cloud] Starting upload for {local_reel_file.name} to folder {folder_id}...", flush=True)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f"[Drive Cloud] Upload progress: {pct}%", flush=True)

            file_id = response.get('id')
            print(f"[Drive Cloud] SUCCESS! Uploaded to Google Drive. File ID: {file_id}", flush=True)
            return {
                "success": True,
                "file_id": file_id,
                "folder_url": folder_url,
                "message": f"Successfully uploaded {local_reel_file.name} to Google Drive!"
            }
        except Exception as e:
            print(f"[Drive Cloud] Note on API upload: {e}", flush=True)
            return {
                "success": False,
                "folder_url": folder_url,
                "message": f"API upload failed: {e}"
            }

    print("[Drive Cloud] Note: Direct Google Drive cloud upload requires Google authentication (credentials.json).")
    print(f"[Drive Cloud] Output folder URL: {folder_url}")
    return {
        "success": False,
        "folder_url": folder_url,
        "needs_creds": True,
        "message": "Cloud upload requires Google credentials. You can upload directly via browser or download."
    }
