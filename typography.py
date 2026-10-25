"""
Aesthetic Minimalist Typography Module
- Renders elegant location and date badges (Arif Hakim style)
- Clean letter-spacing, elegant font hierarchy, and smooth alpha fade in/out
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import config

def render_aesthetic_title_badge(
    title_text: str,
    subtitle_text: str,
    frame_w=config.REEL_WIDTH,
    frame_h=config.REEL_HEIGHT,
    opacity=1.0
) -> np.ndarray:
    """
    Renders an aesthetic transparent overlay containing minimalist lower-third typography.
    Returns:
        np.ndarray (H, W, 4) RGBA overlay
    """
    if opacity <= 0.0:
        return np.zeros((frame_h, frame_w, 4), dtype=np.uint8)

    overlay = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Attempt to load clean modern sans-serif fonts
    font_title = None
    font_sub = None
    for font_name in ["HelveticaNeue", "Helvetica", "Arial", "Segoe UI", "DejaVuSans"]:
        try:
            font_title = ImageFont.truetype(font_name, size=46)
            font_sub = ImageFont.truetype(font_name, size=28)
            break
        except Exception:
            continue

    if font_title is None:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Position: Lower third, left aligned with aesthetic margin
    margin_x = 90
    base_y = frame_h - 320

    # Letter spaced title (e.g. "B E R L I N ,  G E R M A N Y")
    spaced_title = "  ".join(title_text.upper())
    
    alpha_int = int(255 * min(1.0, max(0.0, opacity)))
    
    # Subtle drop shadow for readability over bright video backgrounds
    shadow_color = (0, 0, 0, int(alpha_int * 0.45))
    text_color = (255, 255, 255, alpha_int)
    accent_color = (235, 235, 235, int(alpha_int * 0.85))

    # Draw Title Shadow & Text
    draw.text((margin_x + 2, base_y + 2), spaced_title, font=font_title, fill=shadow_color)
    draw.text((margin_x, base_y), spaced_title, font=font_title, fill=text_color)

    # Draw Subtitle (e.g. "25.10.2026 • 18:42")
    sub_y = base_y + 65
    draw.text((margin_x + 2, sub_y + 2), subtitle_text, font=font_sub, fill=shadow_color)
    draw.text((margin_x, sub_y), subtitle_text, font=font_sub, fill=accent_color)

    # Subtle minimal separator line
    line_y = sub_y + 45
    draw.line([(margin_x, line_y), (margin_x + 120, line_y)], fill=(255, 255, 255, int(alpha_int * 0.6)), width=2)

    return np.array(overlay)

def blend_title_overlay(frame_bgr: np.ndarray, current_sec: float, title: str, subtitle: str) -> np.ndarray:
    """
    Blends the title overlay onto frame_bgr if within the first 3.5 seconds.
    Smooth fade in (0.2s - 0.7s) and fade out (2.8s - 3.4s).
    """
    if current_sec > 3.6:
        return frame_bgr

    # Compute opacity
    if current_sec < 0.2:
        opacity = 0.0
    elif current_sec <= 0.8:
        opacity = (current_sec - 0.2) / 0.6
    elif current_sec <= 2.8:
        opacity = 1.0
    elif current_sec <= 3.5:
        opacity = 1.0 - (current_sec - 2.8) / 0.7
    else:
        opacity = 0.0

    if opacity <= 0.01:
        return frame_bgr

    h, w = frame_bgr.shape[:2]
    overlay_rgba = render_aesthetic_title_badge(title, subtitle, frame_w=w, frame_h=h, opacity=opacity)
    
    alpha = overlay_rgba[:, :, 3].astype(np.float32) / 255.0
    alpha = alpha[:, :, np.newaxis]
    
    overlay_bgr = overlay_rgba[:, :, :3][:, :, ::-1] # RGBA to BGR
    
    blended = (frame_bgr.astype(np.float32) * (1.0 - alpha) + overlay_bgr.astype(np.float32) * alpha)
    return np.clip(blended, 0.0, 255.0).astype(np.uint8)
