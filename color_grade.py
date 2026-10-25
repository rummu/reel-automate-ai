"""
Aesthetic Color Grading & Film Emulation Engine
- Inspired by Arif Hakim (@ariffathulhakim) cinematic aesthetic
- Portra/Kodak film curves, lifted soft shadows, golden highlights
- Procedural fine film grain & optical vignette
"""

import cv2
import numpy as np
import config

# Pre-computed vignette mask cache
_VIGNETTE_MASK = None

def get_vignette_mask(w=config.REEL_WIDTH, h=config.REEL_HEIGHT, strength=config.VIGNETTE_STRENGTH):
    """Generates a smooth elliptical vignette falloff mask."""
    global _VIGNETTE_MASK
    if _VIGNETTE_MASK is not None and _VIGNETTE_MASK.shape[:2] == (h, w):
        return _VIGNETTE_MASK

    # Create radial distance map
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    # Normalize coordinates so edges reach 1.0
    dist = np.sqrt(((x - cx) / cx) ** 2 + ((y - cy) / cy) ** 2)
    # Cosine smooth falloff
    mask = 1.0 - strength * np.clip((dist - 0.5) / 0.7, 0.0, 1.0)
    _VIGNETTE_MASK = mask.astype(np.float32)[:, :, np.newaxis]
    return _VIGNETTE_MASK

def apply_film_tone_curve(img_bgr: np.ndarray, preset="arif_cinematic") -> np.ndarray:
    """
    Applies cinematic tone curves and color balances in float32.
    """
    # Normalize to 0.0 - 1.0
    f_img = img_bgr.astype(np.float32) / 255.0
    b, g, r = f_img[:, :, 0], f_img[:, :, 1], f_img[:, :, 2]

    if preset == "arif_cinematic":
        # Lifted soft shadows (film blacks)
        b = b * 0.92 + 0.04
        g = g * 0.95 + 0.02
        r = r * 0.98 + 0.03

        # S-curve for contrast
        r = np.sin((r - 0.5) * np.pi) * 0.5 + 0.5
        g = np.sin((g - 0.5) * np.pi) * 0.5 + 0.5
        b = np.sin((b - 0.5) * np.pi) * 0.5 + 0.5

        # Warm golden highlights (slight red/yellow boost in upper range)
        highlights = np.clip((r + g + b) / 3.0 - 0.5, 0.0, 1.0) * 2.0
        r += highlights * 0.05
        g += highlights * 0.02
        b -= highlights * 0.03

    elif preset == "golden_hour":
        r = r * 1.08 + 0.02
        g = g * 1.02
        b = b * 0.88
        
    elif preset == "moody_film":
        # Desaturate greens, boost contrast, cool shadows
        b = b * 0.95 + 0.05
        r = r * 0.92
        g = g * 0.90

    # Clip values
    r = np.clip(r, 0.0, 1.0)
    g = np.clip(g, 0.0, 1.0)
    b = np.clip(b, 0.0, 1.0)

    graded = np.dstack([b, g, r])
    return (graded * 255.0).astype(np.uint8)

def apply_film_grain(img_bgr: np.ndarray, intensity=config.GRAIN_INTENSITY) -> np.ndarray:
    """Generates fine organic 35mm film grain."""
    h, w = img_bgr.shape[:2]
    noise = np.random.normal(loc=0.0, scale=intensity * 255.0, size=(h, w, 1))
    noisy = img_bgr.astype(np.float32) + noise
    return np.clip(noisy, 0.0, 255.0).astype(np.uint8)

def apply_aesthetic_grade(img_bgr: np.ndarray, preset=config.AESTHETIC_PRESET) -> np.ndarray:
    """
    Complete aesthetic grading pass:
    1. Film tone curve
    2. Subtle optical vignette
    3. Fine 35mm film grain
    """
    graded = apply_film_tone_curve(img_bgr, preset=preset)

    if config.ADD_VIGNETTE:
        mask = get_vignette_mask(graded.shape[1], graded.shape[0])
        graded = (graded.astype(np.float32) * mask).astype(np.uint8)

    if config.ADD_FILM_GRAIN:
        graded = apply_film_grain(graded, intensity=config.GRAIN_INTENSITY)

    return graded
