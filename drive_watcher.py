"""
Google Drive Watcher & Synchronization Engine
- Watches input folder for incoming photos/videos from iPhone / Google Drive
- Automatically detects days reaching 30+ items
- Triggers reel generation and copies the finished aesthetic video directly into Google Drive 'reel' folder
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import shutil
import argparse
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
import curator
import reel_generator

class ReelMediaDropHandler(FileSystemEventHandler):
    """Watches for file drops into the Google Drive input directory."""
    def __init__(self, debounce_sec=5.0):
        super().__init__()
        self.debounce_sec = debounce_sec
        self.last_triggered = 0.0

    def on_any_event(self, event):
        if event.is_directory:
            return
        
        # Check if modified or created file has valid media extension
        ext = Path(event.src_path).suffix.lower()
        if ext in (curator.IMAGE_EXTENSIONS | curator.VIDEO_EXTENSIONS):
            current_time = time.time()
            if current_time - self.last_triggered > self.debounce_sec:
                self.last_triggered = current_time
                file_name = Path(event.src_path).name
                is_photo = ext in curator.IMAGE_EXTENSIONS
                if is_photo:
                    print(f"\n[Drive Watcher] 📸 Photo added to Drive: {file_name}")
                    print("[Drive Watcher] Checking if ready to generate reel from videos and photos...")
                else:
                    print(f"\n[Drive Watcher] 🎥 Video added to Drive: {file_name}")
                    print("[Drive Watcher] Note: Reel creation is on standby until photos are added to Drive.")
                # Allow a short settling window for multi-file paste
                time.sleep(2.0)
                scan_and_process_pending_days()

import google_drive_api

def sync_reel_to_google_drive(rendered_reel_path: Path):
    """Copies the completed reel into Google Drive 'reel' folder (local or cloud)."""
    if config.IS_CLOUD_OUTPUT:
        print(f"[Drive Sync] Syncing reel to Google Drive cloud URL...")
        return google_drive_api.upload_reel_to_cloud(rendered_reel_path, config.CLOUD_OUTPUT_URL)
    else:
        target_drive_folder = Path(config.GOOGLE_DRIVE_OUTPUT_FOLDER)
        target_drive_folder.mkdir(parents=True, exist_ok=True)
        dest_file = target_drive_folder / rendered_reel_path.name
        try:
            shutil.copy2(str(rendered_reel_path), str(dest_file))
            print(f"[Drive Sync] SUCCESS! Reel synced to Google Drive:\n  -> {dest_file}")
            return {"success": True, "local_dest": str(dest_file)}
        except Exception as e:
            print(f"[Drive Sync] Note on copying to drive folder: {e}")
            return {"success": False, "error": str(e)}

import hashlib
import json

STATE_FILE = config.DATA_DIR / "watcher_state.json"

def load_processed_fingerprints():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return set(json.load(f).get("processed_fingerprints", []))
        except Exception:
            return set()
    return set()

def save_processed_fingerprint(fp: str):
    fps = load_processed_fingerprints()
    fps.add(fp)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"processed_fingerprints": list(fps)}, f, indent=2)
    except Exception:
        pass

def compute_media_fingerprint(items: list) -> str:
    parts = []
    for it in sorted(items, key=lambda x: str(x["path"].name)):
        p = it["path"]
        try:
            stat = p.stat()
            parts.append(f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}")
        except Exception:
            parts.append(str(p.name))
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()

BATCH_SETTLING_STATE = {
    "last_fp": None,
    "first_seen_time": None,
    "settle_seconds": 20.0
}

def scan_and_process_pending_days():
    """Scans the configured input folder (or cloud URL) and runs reel generator automatically when new media arrives."""
    if config.IS_CLOUD_INPUT:
        google_drive_api.download_folder_from_cloud(config.CLOUD_INPUT_URL, config.GOOGLE_DRIVE_INPUT_FOLDER)

    input_folder = Path(config.GOOGLE_DRIVE_INPUT_FOLDER)
    if not input_folder.exists():
        print(f"[Drive Watcher] Notice: Input folder '{input_folder}' does not exist yet.", flush=True)
        try:
            input_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[Drive Watcher] Warning: Could not create folder '{input_folder}': {e}", flush=True)
            return

    processed = load_processed_fingerprints()

    all_items = curator.get_all_media_items(input_folder)
    all_eligible, all_reason, all_stats = curator.check_day_eligibility(all_items)
    
    if all_eligible:
        all_fp = f"all_{compute_media_fingerprint(all_items)}"
        if all_fp in processed:
            BATCH_SETTLING_STATE["last_fp"] = None
            print(f"[Drive Watcher] Current batch ({all_stats['total']} items) already processed. Standing by for new uploads...", flush=True)
            return

        # Check if this batch is newly detected or if it is still settling
        if all_fp != BATCH_SETTLING_STATE["last_fp"]:
            BATCH_SETTLING_STATE["last_fp"] = all_fp
            BATCH_SETTLING_STATE["first_seen_time"] = time.time()
            print(f"[Drive Watcher] 📥 Upload in progress ({all_stats['total']} items so far). Waiting 20s for folder to settle...", flush=True)
            return

        elapsed = time.time() - (BATCH_SETTLING_STATE["first_seen_time"] or time.time())
        if elapsed < BATCH_SETTLING_STATE["settle_seconds"]:
            remaining = int(BATCH_SETTLING_STATE["settle_seconds"] - elapsed)
            print(f"[Drive Watcher] ⏳ Batch settling ({all_stats['total']} items, {remaining}s remaining before auto-rendering)...", flush=True)
            return

        # Settling period complete! Trigger automated reel creation
        print(f"\n[Drive Watcher] 🚀 UPLOAD COMPLETE! {all_stats['total']} items settled. Starting Reel Generation...", flush=True)
        reel_file = reel_generator.render_reel_for_day("All_Media", all_items)
        if reel_file:
            save_processed_fingerprint(all_fp)
            sync_reel_to_google_drive(reel_file)
            print(f"\n[Drive Watcher] ✅ Reel successfully generated and uploaded to Google Drive!", flush=True)
            BATCH_SETTLING_STATE["last_fp"] = None
        return

    # 2. Otherwise check day by day
    grouped_days = curator.scan_and_group_by_day(input_folder)
    for day_str, items in grouped_days.items():
        is_eligible, reason, stats = curator.check_day_eligibility(items)
        if is_eligible:
            day_fp = f"{day_str}_{compute_media_fingerprint(items)}"
            if day_fp in processed:
                continue

            print(f"\n[Drive Watcher] 🚀 NEW DAY READY: {day_str} ({stats['total']} items). Generating reel...", flush=True)
            reel_file = reel_generator.render_reel_for_day(day_str, items)
            if reel_file:
                save_processed_fingerprint(day_fp)
                sync_reel_to_google_drive(reel_file)
                print(f"[Drive Watcher] ✅ Reel for {day_str} saved to Google Drive!", flush=True)
        else:
            pass

def start_continuous_watcher():
    """Starts background file watcher on the Google Drive input folder."""
    watch_path = Path(config.GOOGLE_DRIVE_INPUT_FOLDER)
    try:
        watch_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[Drive Watcher] Notice: Could not access '{watch_path}': {e}")
        print(f"[Drive Watcher] Please ensure Google Drive desktop app is running.")
    
    print("\n=======================================================")
    print("      AI REEL MAKER - GOOGLE DRIVE AUTO-WATCHER        ")
    print("=======================================================")
    print(f"Watching Google Drive Input Folder:\n  -> {watch_path}")
    print(f"Outputting Reels to:\n  -> {config.GOOGLE_DRIVE_OUTPUT_FOLDER}")
    print(f"Rule: Only generates reel when photos are added to Drive (>= {config.MIN_ITEMS_PER_DAY} total items).")
    print("Drop your iPhone photos/videos into Google Drive anytime!\n")

    # Initial scan on startup
    scan_and_process_pending_days()

    event_handler = ReelMediaDropHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()

    try:
        last_cloud_sync = time.time()
        while True:
            time.sleep(1)
            # Periodic cloud sync every 15 seconds for cloud Google Drive folders
            if config.IS_CLOUD_INPUT and (time.time() - last_cloud_sync > 15):
                last_cloud_sync = time.time()
                scan_and_process_pending_days()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Drive Reel Watcher")
    parser.add_argument("--watch", action="store_true", help="Start continuous background folder watcher")
    parser.add_argument("--run-now", action="store_true", help="Run scan and edit immediately")
    parser.add_argument("--set-input-path", type=str, help="Set your local Google Drive input folder path")
    parser.add_argument("--set-output-path", type=str, help="Set your local Google Drive reel folder path")
    args = parser.parse_args()

    if args.set_input_path:
        config.GOOGLE_DRIVE_INPUT_FOLDER = Path(args.set_input_path)
        print(f"Updated Google Drive Input Folder to: {config.GOOGLE_DRIVE_INPUT_FOLDER}")

    if args.set_output_path:
        config.GOOGLE_DRIVE_OUTPUT_FOLDER = Path(args.set_output_path)
        print(f"Updated Google Drive Output Folder to: {config.GOOGLE_DRIVE_OUTPUT_FOLDER}")

    if args.watch:
        start_continuous_watcher()
    else:
        scan_and_process_pending_days()
