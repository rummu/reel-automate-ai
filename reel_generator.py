"""
Master Reel Generator Engine
- Assembles curated photos and video snippets into an aesthetic 1080x1920 Instagram Reel
- Applies Ken Burns camera motion, beat-matched cuts, film color grading, and minimalist typography
- Muxes background music and exports directly to Google Drive output folder
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
import imageio_ffmpeg

import config
import curator
import motion_and_crop
import color_grade
import typography
import audio_sync

def get_ffmpeg_binary():
    """Returns path to static ffmpeg binary provided by imageio-ffmpeg."""
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def render_reel_for_day(day_date_str: str, day_media: list, location_name=config.DEFAULT_LOCATION_NAME, music_path: Path = None, force=False, progress_callback=None):
    """
    Renders a complete aesthetic reel for the specified day.
    
    Args:
        day_date_str: e.g. "2026-10-25"
        day_media: list of dicts with 'path', 'time', 'is_video'
        location_name: e.g. "Munich, Germany"
        music_path: optional custom MP3
        force: if True, skips the minimum item threshold (requires photos still)
        progress_callback: optional function(msg, percent)
    
    Returns:
        Path to generated .mp4 reel
    """
    print(f"\n=======================================================")
    print(f"[Reel Engine] Starting Reel Generation for {day_date_str}")
    print(f"[Reel Engine] Total items recorded for day: {len(day_media)}")
    print(f"=======================================================")

    # 1. Check Eligibility (Must have photos, and meets threshold unless force=True)
    is_eligible, reason, stats = curator.check_day_eligibility(day_media)
    if not stats["has_photos"] and config.REQUIRE_PHOTOS:
        print(f"[Reel Engine] Skip: No photos found for {day_date_str}. Reel creation requires photos.")
        return None
    if not is_eligible and not force:
        print(f"[Reel Engine] Skip: {reason}")
        return None

    # 2. Curate and deduplicate
    selected_items = curator.curate_day_media(day_media, target_count=config.TARGET_SELECTED_CLIPS)
    if not selected_items:
        print(f"[Reel Engine] Error: No valid items found for {day_date_str}.")
        return None

    # If small number of items (1 to 7 items), expand into multiple cinematic passes to ensure 30s-60s duration
    if len(selected_items) < 8:
        expanded_scenes = []
        target_scene_count = 10  # 10 scenes of ~3.2s = 32s reel
        while len(expanded_scenes) < target_scene_count:
            for item in selected_items:
                expanded_scenes.append(item)
                if len(expanded_scenes) >= target_scene_count:
                    break
        selected_items = expanded_scenes

    # 3. Audio & Beat Matching
    target_duration = min(config.TARGET_MAX_DURATION, max(config.TARGET_MIN_DURATION, len(selected_items) * config.PHOTO_CLIP_DURATION))
    soundtrack_path, beat_times = audio_sync.get_track_and_beat_timestamps(target_duration, music_path=music_path)
    clip_durations = audio_sync.calculate_clip_durations(len(selected_items), beat_times, target_total_duration=target_duration)

    total_reel_duration = sum(clip_durations)
    print(f"[Reel Engine] Target Reel Duration: {total_reel_duration:.1f}s across {len(selected_items)} scenes.")

    # 4. Prepare Video Writer
    safe_date_tag = "All_Media" if str(day_date_str).lower() in ("all", "all_media") else day_date_str
    temp_video_raw = config.TEMP_DIR / f"raw_{safe_date_tag}.mp4"
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_output_file = config.OUTPUT_DIR / f"Reel_{safe_date_tag}_{location_name.replace(' ', '_').replace(',', '')}_{timestamp_str}.mp4"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        str(temp_video_raw),
        fourcc,
        config.REEL_FPS,
        (config.REEL_WIDTH, config.REEL_HEIGHT)
    )

    # Typography text
    if str(day_date_str).lower() in ("all", "all_media"):
        if day_media:
            min_time = min(x["time"] for x in day_media)
            max_time = max(x["time"] for x in day_media)
            if min_time.date() == max_time.date():
                formatted_date = min_time.strftime("%d.%m.%Y")
            else:
                formatted_date = f"{min_time.strftime('%d.%m')} - {max_time.strftime('%d.%m.%Y')}"
        else:
            formatted_date = "Highlights"
    else:
        try:
            dt = datetime.strptime(day_date_str, "%Y-%m-%d")
            formatted_date = dt.strftime("%d.%m.%Y")
        except Exception:
            formatted_date = day_date_str

    subtitle_text = f"{formatted_date}  •  {location_name}"
    title_text = location_name.split(",")[0].strip()

    # 5. Frame Generation Loop
    current_time_sec = 0.0
    ken_burns_modes = ["zoom_in", "zoom_out", "pan_up"]

    for idx, (item, dur) in enumerate(zip(selected_items, clip_durations)):
        path = item["path"]
        is_video = item["is_video"]
        print(f"[{idx+1}/{len(selected_items)}] Rendering scene: {path.name} ({dur:.1f}s)...")

        if progress_callback:
            kind = "Video" if is_video else "Photo"
            progress_callback(f"Rendering scene {idx+1}/{len(selected_items)} ({kind}): {path.name}", int((idx / len(selected_items)) * 85))

        if is_video:
            # Video clip extraction
            cap = cv2.VideoCapture(str(path))
            v_fps = cap.get(cv2.CAP_PROP_FPS) or config.REEL_FPS
            needed_frames = int(dur * config.REEL_FPS)
            step = max(1.0, v_fps / config.REEL_FPS)
            
            frame_count = 0
            while frame_count < needed_frames:
                ret, frame = cap.read()
                if not ret or frame is None:
                    # Loop video if shorter than duration
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break

                # Smart 9:16 crop & resize
                frame_916 = motion_and_crop.crop_and_resize(frame, config.REEL_WIDTH, config.REEL_HEIGHT)
                # Aesthetic Color Grade
                graded = color_grade.apply_aesthetic_grade(frame_916)
                # Typography Title Overlay (first 3.5 seconds)
                final_frame = typography.blend_title_overlay(graded, current_time_sec, title_text, subtitle_text)
                
                writer.write(final_frame)
                frame_count += 1
                current_time_sec += (1.0 / config.REEL_FPS)

            cap.release()
        else:
            # Still photo: Ken Burns motion animation
            img_bgr = curator.load_cv_image(path)
            if img_bgr is None:
                continue

            mode = ken_burns_modes[idx % len(ken_burns_modes)]
            for frame_bgr in motion_and_crop.generate_ken_burns_frames(img_bgr, dur, fps=config.REEL_FPS, mode=mode):
                # Aesthetic Color Grade
                graded = color_grade.apply_aesthetic_grade(frame_bgr)
                # Typography Title Overlay (first 3.5 seconds)
                final_frame = typography.blend_title_overlay(graded, current_time_sec, title_text, subtitle_text)
                
                writer.write(final_frame)
                current_time_sec += (1.0 / config.REEL_FPS)

    writer.release()
    del writer
    import gc
    gc.collect()

    print(f"[Reel Engine] Visual frames rendered. Now muxing soundtrack...")
    if progress_callback:
        progress_callback("Muxing audio & beat-syncing soundtrack...", 90)

    # 6. Audio Muxing using FFmpeg
    ffmpeg_bin = get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(temp_video_raw),
        "-i", str(soundtrack_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",               # High aesthetic visual fidelity
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{current_time_sec:.2f}",
        "-shortest",
        str(final_output_file)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(f"[Reel Engine] SUCCESS! Aesthetic Reel saved to:\n  -> {final_output_file}")
        if progress_callback:
            progress_callback("Reel render complete!", 100)
        
        # Clean up temp raw video safely
        try:
            if temp_video_raw.exists():
                temp_video_raw.unlink()
        except Exception:
            pass
            
        return final_output_file
    except Exception as e:
        print(f"[Reel Engine] FFmpeg mux note: {e}. Outputting video directly.")
        if final_output_file.exists():
            return final_output_file
        try:
            if temp_video_raw.exists():
                import shutil
                shutil.copy2(str(temp_video_raw), str(final_output_file))
        except Exception:
            pass
        return final_output_file

def process_all_eligible_days(input_folder=config.INPUT_DIR):
    """
    Scans input folder, finds all days with 30+ media items, and generates reels.
    """
    grouped_days = curator.scan_and_group_by_day(input_folder)
    print(f"\n[Scanner] Found {len(grouped_days)} dates in {input_folder}")

    generated_reels = []
    for day_str, items in grouped_days.items():
        is_eligible, reason, stats = curator.check_day_eligibility(items)
        print(f"  - Date {day_str}: {stats['total']} items ({stats['photos']} photos, {stats['videos']} videos)")
        if is_eligible:
            print(f"    >>> Triggering automatic reel creation for {day_str} ({stats['photos']} photos + {stats['videos']} videos)!")
            reel_path = render_reel_for_day(day_str, items)
            if reel_path:
                generated_reels.append(reel_path)
        else:
            print(f"    (Skipping: {reason})")

    return generated_reels

if __name__ == "__main__":
    process_all_eligible_days()
