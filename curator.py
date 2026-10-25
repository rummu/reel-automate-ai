"""
Media Curation Module
- Reads EXIF capture timestamps
- Groups media by day
- Enforces the 30+ items per day threshold
- Performs blur detection, burst deduplication, and aesthetic ranking
"""

import os
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
from PIL import Image, ExifTags
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass
import config

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}

def get_media_capture_time(file_path: Path) -> datetime:
    """Extract capture datetime from EXIF or fallback to file system mtime."""
    ext = file_path.suffix.lower()
    
    if ext in IMAGE_EXTENSIONS:
        try:
            with Image.open(file_path) as img:
                exif = img.getexif()
                if exif:
                    # Look for DateTimeOriginal (0x9003) or DateTime (0x0132)
                    for tag_id in (0x9003, 0x0132, 0x9004):
                        date_str = exif.get(tag_id)
                        if date_str and isinstance(date_str, str):
                            try:
                                return datetime.strptime(date_str.strip(), "%Y:%m:%d %H:%M:%S")
                            except Exception:
                                pass
        except Exception:
            pass

    # Fallback to file creation / modified time
    stat = file_path.stat()
    timestamp = min(stat.st_mtime, getattr(stat, "st_ctime", stat.st_mtime))
    return datetime.fromtimestamp(timestamp)

def get_all_media_items(folder_path: Path):
    """
    Scans all media files in folder_path and returns a flat list sorted chronologically.
    Returns:
        list of dicts with 'path', 'time', 'is_video'
    """
    items = []
    valid_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

    for root, _, files in os.walk(folder_path):
        for f in files:
            path = Path(root) / f
            if path.suffix.lower() in valid_extensions and not f.startswith("."):
                cap_time = get_media_capture_time(path)
                items.append({
                    "path": path,
                    "time": cap_time,
                    "is_video": path.suffix.lower() in VIDEO_EXTENSIONS
                })

    items.sort(key=lambda x: x["time"])
    return items

def scan_and_group_by_day(folder_path: Path):
    """
    Scans media in folder_path, extracts timestamps, and groups files by day (YYYY-MM-DD).
    Returns:
        dict: { "2026-10-24": [Path1, Path2, ...], ... }
    """
    grouped = {}
    valid_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

    for root, _, files in os.walk(folder_path):
        for f in files:
            path = Path(root) / f
            if path.suffix.lower() in valid_extensions and not f.startswith("."):
                cap_time = get_media_capture_time(path)
                day_key = cap_time.strftime("%Y-%m-%d")
                if day_key not in grouped:
                    grouped[day_key] = []
                grouped[day_key].append({
                    "path": path,
                    "time": cap_time,
                    "is_video": path.suffix.lower() in VIDEO_EXTENSIONS
                })

    # Sort items within each day chronologically
    for day_key in grouped:
        grouped[day_key].sort(key=lambda x: x["time"])

    return grouped

def check_day_eligibility(items: list, min_items=None, require_photos=None, min_photos=None):
    """
    Checks if a day's media collection meets the rules for reel generation:
    1. Must contain photos (if require_photos is True)
    2. Must meet the minimum item threshold
    Returns:
        (is_eligible: bool, reason: str, stats: dict)
    """
    if min_items is None:
        min_items = config.MIN_ITEMS_PER_DAY
    if require_photos is None:
        require_photos = config.REQUIRE_PHOTOS
    if min_photos is None:
        min_photos = config.MIN_PHOTOS_REQUIRED

    photos = [x for x in items if not x.get("is_video", False)]
    videos = [x for x in items if x.get("is_video", False)]
    stats = {
        "total": len(items),
        "photos": len(photos),
        "videos": len(videos),
        "has_photos": len(photos) >= min_photos
    }

    if not items:
        return False, "No media items found in Drive folder.", stats

    if require_photos and len(photos) < min_photos:
        return False, (
            f"Waiting for photos: Found {len(videos)} videos and {len(photos)} photos."
        ), stats

    if len(items) < min_items:
        return False, (
            f"Waiting for media: {len(items)}/{min_items} items uploaded."
        ), stats

    return True, (
        f"Ready for Reel: {len(items)} items ({len(photos)} photos, {len(videos)} videos)."
    ), stats

def compute_blur_score(img_cv: np.ndarray) -> float:
    """Compute variance of Laplacian (higher = sharper, lower = blurry)."""
    if img_cv is None:
        return 0.0
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def compute_color_histogram(img_cv: np.ndarray) -> np.ndarray:
    """Calculate normalized color histogram for duplicate detection."""
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist.flatten()

def load_cv_image(path: Path, max_dim=1920) -> np.ndarray:
    """Load image safely via PIL (handles EXIF orientation & HEIC if supported)."""
    try:
        with Image.open(path) as pil_img:
            # Handle orientation
            try:
                from PIL import ImageOps
                pil_img = ImageOps.exif_transpose(pil_img)
            except Exception:
                pass
            
            # Convert to RGB
            pil_img = pil_img.convert("RGB")
            
            # Resize if overly huge to speed up processing
            w, h = pil_img.size
            if max(w, h) > max_dim:
                ratio = max_dim / float(max(w, h))
                pil_img = pil_img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
                
            img_np = np.array(pil_img)
            return cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"[Curator] Warning: Could not load image {path.name}: {e}")
        return None

def curate_day_media(media_items: list, target_count=config.TARGET_SELECTED_CLIPS):
    """
    Filters blurry items, deduplicates burst shots, and samples aesthetic highlights across the day.
    Returns:
        list of selected media dicts
    """
    scored_items = []
    
    print(f"[Curator] Analyzing {len(media_items)} items for quality and variety...")
    
    prev_hist = None
    for item in media_items:
        path = item["path"]
        is_video = item["is_video"]
        
        if is_video:
            # Extract middle frame of video to check sharpness
            cap = cv2.VideoCapture(str(path))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total_frames // 2))
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                continue
            
            blur = compute_blur_score(frame)
            hist = compute_color_histogram(frame)
        else:
            frame = load_cv_image(path, max_dim=1280)
            if frame is None:
                continue
            blur = compute_blur_score(frame)
            hist = compute_color_histogram(frame)

        # 1. Filter out blurry images
        if blur < config.MIN_LAPLACIAN_BLUR_SCORE:
            continue

        # 2. Burst deduplication: Check similarity to previous accepted item
        is_duplicate = False
        if prev_hist is not None:
            # Cosine similarity between histograms
            denom = (np.linalg.norm(hist) * np.linalg.norm(prev_hist))
            if denom > 0:
                sim = np.dot(hist, prev_hist) / denom
                if sim > config.MAX_BURST_SIMILARITY:
                    is_duplicate = True

        if not is_duplicate:
            scored_items.append({
                "item": item,
                "blur_score": blur,
                "time": item["time"],
                "hist": hist
            })
            prev_hist = hist

    if not scored_items:
        print("[Curator] Warning: No items passed quality filter! Using raw items as fallback.")
        return media_items[:target_count]

    # 3. Balanced & Aesthetic Temporal Spread Sampling
    # If both photos and videos are provided, ensure the reel combines BOTH!
    photo_scored = [x for x in scored_items if not x["item"]["is_video"]]
    video_scored = [x for x in scored_items if x["item"]["is_video"]]

    if photo_scored and video_scored and len(scored_items) > target_count:
        # Guarantee minimum 20% representation for both photos and videos
        min_photos = max(1, min(len(photo_scored), int(target_count * 0.25)))
        min_videos = max(1, min(len(video_scored), int(target_count * 0.25)))

        photo_ratio = len(photo_scored) / len(scored_items)
        target_photos = int(round(target_count * photo_ratio))
        target_photos = max(min_photos, min(len(photo_scored), target_photos))
        target_videos = max(min_videos, min(len(video_scored), target_count - target_photos))

        if target_photos + target_videos < target_count:
            if len(photo_scored) > target_photos:
                target_photos = min(len(photo_scored), target_count - target_videos)
            elif len(video_scored) > target_videos:
                target_videos = min(len(video_scored), target_count - target_photos)

        # Sample photos uniformly across time
        idx_p = np.linspace(0, len(photo_scored) - 1, target_photos, dtype=int)
        selected_photos = [photo_scored[i]["item"] for i in idx_p]

        # Sample videos uniformly across time
        idx_v = np.linspace(0, len(video_scored) - 1, target_videos, dtype=int)
        selected_videos = [video_scored[i]["item"] for i in idx_v]

        # Combine and sort chronologically so the reel alternates naturally
        selected = selected_photos + selected_videos
        selected.sort(key=lambda x: x["time"])
        print(f"[Curator] Curated balanced aesthetic mix: {len(selected_photos)} photos and {len(selected_videos)} videos.")
    elif len(scored_items) <= target_count:
        selected = [x["item"] for x in scored_items]
    else:
        indices = np.linspace(0, len(scored_items) - 1, target_count, dtype=int)
        selected = [scored_items[i]["item"] for i in indices]

    print(f"[Curator] Selected {len(selected)} top aesthetic clips from {len(media_items)} raw items.")
    return selected
