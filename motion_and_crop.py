"""
Smart 9:16 Framing & Ken Burns Motion Module
- Saliency / Face-aware 9:16 vertical cropping
- Smooth Ken Burns zoom and pan drift for still photos
- Video snippet extraction and reframing
"""

import cv2
import numpy as np
import config

# Load face cascade for intelligent framing
FACE_CASCADE = None
try:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
except Exception:
    FACE_CASCADE = None

def get_smart_crop_box(img_w: int, img_h: int, target_w=config.REEL_WIDTH, target_h=config.REEL_HEIGHT, focus_point=None):
    """
    Computes (x1, y1, x2, y2) to crop an image to exact target aspect ratio (9:16),
    keeping focus_point (normalized 0.0 - 1.0) inside the crop window.
    """
    target_aspect = target_w / float(target_h) # 9 / 16 = 0.5625
    img_aspect = img_w / float(img_h)

    if img_aspect > target_aspect:
        # Image is wider than 9:16 -> Crop sides
        crop_h = img_h
        crop_w = int(img_h * target_aspect)
        
        # Determine center X
        if focus_point and "x" in focus_point:
            desired_cx = int(focus_point["x"] * img_w)
            x1 = max(0, min(img_w - crop_w, desired_cx - crop_w // 2))
        else:
            x1 = (img_w - crop_w) // 2
        x2 = x1 + crop_w
        y1, y2 = 0, crop_h
    else:
        # Image is taller than 9:16 -> Crop top/bottom
        crop_w = img_w
        crop_h = int(img_w / target_aspect)
        
        # Determine center Y (default slightly above center for portraits/cityscapes)
        if focus_point and "y" in focus_point:
            desired_cy = int(focus_point["y"] * img_h)
            y1 = max(0, min(img_h - crop_h, desired_cy - crop_h // 2))
        else:
            # Golden ratio / upper-third bias
            y1 = int((img_h - crop_h) * 0.35)
        y2 = y1 + crop_h
        x1, x2 = 0, crop_w

    return x1, y1, x2, y2

def detect_visual_focus(img_bgr: np.ndarray):
    """
    Finds center of interest (faces or highest contrast area).
    Returns normalized { "x": float, "y": float }
    """
    h, w = img_bgr.shape[:2]
    
    # 1. Check for faces
    if FACE_CASCADE and not FACE_CASCADE.empty():
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
        if len(faces) > 0:
            # Average face center
            fx_sum = sum(x + fw // 2 for (x, y, fw, fh) in faces)
            fy_sum = sum(y + fh // 2 for (x, y, fw, fh) in faces)
            return {"x": fx_sum / (len(faces) * w), "y": fy_sum / (len(faces) * h)}

    # 2. Default: upper-center for aesthetic city/travel framing
    return {"x": 0.5, "y": 0.42}

def crop_and_resize(img_bgr: np.ndarray, target_w=config.REEL_WIDTH, target_h=config.REEL_HEIGHT) -> np.ndarray:
    """Smart crops image to 9:16 and resizes to target_w x target_h."""
    h, w = img_bgr.shape[:2]
    focus = detect_visual_focus(img_bgr)
    x1, y1, x2, y2 = get_smart_crop_box(w, h, target_w, target_h, focus)
    cropped = img_bgr[y1:y2, x1:x2]
    return cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

def generate_ken_burns_frames(img_bgr: np.ndarray, duration_sec: float, fps=config.REEL_FPS, mode="zoom_in"):
    """
    Generates a stream of frames simulating subtle cinematic camera drift.
    mode options: 'zoom_in', 'zoom_out', 'pan_up'
    """
    num_frames = int(duration_sec * fps)
    if num_frames <= 0:
        num_frames = 1

    # Base crop to 9:16 at slightly higher resolution to allow zoom without pixelation
    h, w = img_bgr.shape[:2]
    focus = detect_visual_focus(img_bgr)
    
    # Crop base 9:16 with extra margin for zooming
    zoom_max = config.KEN_BURNS_ZOOM_RATIO
    base_target_w = int(config.REEL_WIDTH * zoom_max)
    base_target_h = int(config.REEL_HEIGHT * zoom_max)
    
    x1, y1, x2, y2 = get_smart_crop_box(w, h, base_target_w, base_target_h, focus)
    base_canvas = cv2.resize(img_bgr[y1:y2, x1:x2], (base_target_w, base_target_h), interpolation=cv2.INTER_LANCZOS4)

    cw, ch = base_canvas.shape[1], base_canvas.shape[0]
    out_w, out_h = config.REEL_WIDTH, config.REEL_HEIGHT

    for f_idx in range(num_frames):
        t = f_idx / float(max(1, num_frames - 1))
        # Smooth ease-in-out curve
        ease_t = 0.5 * (1.0 - np.cos(np.pi * t))

        if mode == "zoom_in":
            # Scale from 1.0 (wider) to 1.12 (closer)
            scale = 1.0 + (zoom_max - 1.0) * ease_t
        elif mode == "zoom_out":
            scale = zoom_max - (zoom_max - 1.0) * ease_t
        else: # pan
            scale = 1.05

        curr_w = int(out_w * scale)
        curr_h = int(out_h * scale)
        
        # Center crop window in canvas
        x_center = cw // 2
        y_center = ch // 2
        
        if mode == "pan_up":
            # Drift upward
            drift = int((ch - curr_h) * 0.4 * (ease_t - 0.5))
            y_center += drift

        x1_sub = max(0, x_center - curr_w // 2)
        y1_sub = max(0, y_center - curr_h // 2)
        x2_sub = min(cw, x1_sub + curr_w)
        y2_sub = min(ch, y1_sub + curr_h)

        sub_frame = base_canvas[y1_sub:y2_sub, x1_sub:x2_sub]
        yield cv2.resize(sub_frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
