# 🎬 Reel Automate AI

An automated AI-powered Instagram Reel generator inspired by the cinematic, atmospheric travel aesthetic of **Arif Hakim (`@ariffathulhakim`)**.

The engine takes photos and video clips from your day trips, verifies whether a single calendar day reached **30+ media items**, and autonomously curates, crops, animates, color grades, and edits a **30s–60s 1080x1920 Instagram Reel**, outputting the finished video directly to your Google Drive **`reel`** folder.

---

## ✨ Features & Cinematic Pipeline

1. **Daily Grouping & 30+ Threshold Rule:**
   - Automatically extracts camera capture timestamps (`DateTimeOriginal` EXIF) from photos/videos.
   - Only triggers editing for days with **at least 30 media items**.

2. **Smart AI Curation & Sharpness Filter:**
   - Uses Laplacian variance to discard blurry/pocket shots.
   - Detects burst duplicates (perceptual histogram difference) to avoid repetitive cuts.
   - Selects the top 18–24 aesthetic highlights across morning, golden hour, and evening.

3. **Smart 9:16 Vertical Cropping:**
   - Intelligent framing with face and saliency detection to ensure people, horizons, and architecture are centered rather than cut off.

4. **Ken Burns Cinematic Motion:**
   - Animates static photos with slow camera drift (gentle zoom-in, zoom-out, and subtle upward tilt) at 60 FPS.

5. **Arif Hakim Film Emulation Color Grade:**
   - Warm golden-hour highlights & soft lifted shadows (Kodak Portra tone curves).
   - Natural 35mm optical vignette and subtle organic film grain.

6. **Minimalist Typography Overlay:**
   - Clean aesthetic location and date lower-third badge with smooth fade curves (e.g., *"MUNICH, GERMANY • 25.10.2026"*).

7. **Audio Beat-Matching (`librosa`):**
   - Automatically detects musical transients and aligns every clip cut to the rhythm.
   - Ships with an aesthetic procedural lo-fi ambient soundtrack generator and supports any custom `.mp3` dropped into `music/`.

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
Open PowerShell or Command Prompt in this folder and run:
```bash
pip install -r requirements.txt
```

### 2. Test It Right Now (Simulated 32-photo day)
Generate 32 sample sunset/city photos to test the 30+ items trigger:
```bash
python generate_demo_day.py
```

### 3. Launch the Studio Dashboard
Double-click `start_dashboard.bat` or run:
```bash
python dashboard.py
```
Open **`http://localhost:5000`** in your browser to:
- See all detected days and item counts.
- Preview rendered reels inside an interactive 9:16 smartphone player.
- Switch color grades (Arif Hakim NYC, Golden Hour, Moody Film).
- One-click render or force edit.

### 4. Run Automatic Background Watcher
Double-click `start_watcher.bat` or run:
```bash
python drive_watcher.py --watch
```
Whenever you paste photos into your Google Drive input folder, it will automatically detect days reaching 30+ items and save the finished MP4 into your Google Drive `reel` folder.

---

## 📂 Google Drive Folder Setup

In `config.py`, point your folders to your Google Drive for Desktop path:
```python
# In config.py
GOOGLE_DRIVE_INPUT_FOLDER = "G:/My Drive/Reel_Input"
GOOGLE_DRIVE_OUTPUT_FOLDER = "G:/My Drive/reel"
```
Or use the CLI command:
```bash
python drive_watcher.py --set-input-path "G:\My Drive\Reel_Input" --set-output-path "G:\My Drive\reel"
```

---

## 🎵 Custom Music
Drop any favorite MP3/WAV tracks into the `music/` folder. The beat detector will automatically sync video transitions to that track.
