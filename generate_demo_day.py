"""
Demo Test Generator
Creates 32 simulated sample photos for 'Today' in the input queue
so you can immediately test the 30+ items trigger and reel generation.
"""

from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import cv2
import config

def generate_aesthetic_test_images(num_images=32):
    """Generates synthetic high-resolution test photos simulating city landscapes."""
    today = datetime.now()
    output_dir = config.INPUT_DIR / today.strftime("%Y-%m-%d")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Demo Setup] Generating {num_images} sample aesthetic photos in:\n  -> {output_dir}")

    # Golden hour, blue hour, and city tones
    palettes = [
        # Sunset / Golden hour
        [(255, 140, 0), (255, 69, 0), (75, 0, 130)],
        # European moody blue hour
        [(15, 32, 67), (40, 60, 110), (220, 180, 140)],
        # Warm street tones
        [(40, 30, 20), (180, 120, 70), (240, 220, 190)],
        # Forest / Park greenery
        [(20, 45, 25), (60, 120, 70), (200, 230, 180)]
    ]

    w, h = 1440, 1920

    for i in range(num_images):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        palette = palettes[i % len(palettes)]
        
        # Smooth vertical color gradient
        for y in range(h):
            t = y / float(h)
            if t < 0.5:
                sub_t = t * 2.0
                c1, c2 = palette[0], palette[1]
            else:
                sub_t = (t - 0.5) * 2.0
                c1, c2 = palette[1], palette[2]

            b = int(c1[0] * (1.0 - sub_t) + c2[0] * sub_t)
            g = int(c1[1] * (1.0 - sub_t) + c2[1] * sub_t)
            r = int(c1[2] * (1.0 - sub_t) + c2[2] * sub_t)
            img[y, :] = (b, g, r)

        # Draw aesthetic architectural silhouette & sun
        sun_y = int(h * 0.45 + np.sin(i) * 100)
        sun_x = int(w * 0.5 + np.cos(i) * 200)
        cv2.circle(img, (sun_x, sun_y), 90, (255, 255, 230), -1)
        
        # City skyline silhouette blocks
        for bx in range(0, w, 90):
            bh = int(350 + np.sin(bx + i * 15) * 180)
            cv2.rectangle(img, (bx, h - bh), (bx + 80, h), (18, 14, 22), -1)

        # Subtle noise
        noise = np.random.normal(0, 4, (h, w, 3)).astype(np.int16)
        noisy = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # Save with simulated capture time throughout the day
        file_path = output_dir / f"IMG_GERMANY_{i+1:03d}.jpg"
        cv2.imwrite(str(file_path), noisy)

    print(f"[Demo Setup] SUCCESS! {num_images} photos created for date {today.strftime('%Y-%m-%d')}.")
    print("Now run 'python drive_watcher.py --watch' or 'python dashboard.py' to see the automation trigger!")

if __name__ == "__main__":
    generate_aesthetic_test_images(32)
