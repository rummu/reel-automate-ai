"""
Audio Beat Analysis & Sync Engine
- Analyzes background music for tempo and beat timestamps
- Snaps video cuts to musical transients
- Provides procedural aesthetic lo-fi backup audio if no MP3 is supplied
"""

import math
from pathlib import Path
import numpy as np
import scipy.io.wavfile as wavfile
import config

def get_available_music_tracks():
    """Returns list of audio files found in music/ directory."""
    music_dir = config.MUSIC_DIR
    music_files = []
    for ext in [".mp3", ".wav", ".m4a", ".aac"]:
        music_files.extend(list(music_dir.glob(f"*{ext}")))
    return music_files

def generate_procedural_lofi_track(output_path: Path, duration_sec=45.0, sample_rate=44100):
    """
    Generates a gentle, warm cinematic ambient soundscape (warm chords + subtle rhythmic pulse)
    so the reel generator works immediately without external downloads.
    """
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    
    # 78 BPM Tempo (Chillhop / Lo-Fi)
    bpm = 78.0
    beat_sec = 60.0 / bpm
    
    # Chord Frequencies: Fmaj7 -> Em7 -> Dm7 -> Cmaj7 (warm nostalgic progression)
    chords = [
        [174.61, 220.00, 261.63, 329.63], # Fmaj7
        [164.81, 196.00, 246.94, 293.66], # Em7
        [146.83, 174.61, 220.00, 261.63], # Dm7
        [130.81, 164.81, 196.00, 246.94], # Cmaj7
    ]
    chord_len = beat_sec * 4 # 1 measure per chord
    
    audio = np.zeros_like(t)
    
    for i in range(len(t)):
        current_time = t[i]
        chord_idx = int((current_time / chord_len) % len(chords))
        notes = chords[chord_idx]
        
        # Soft warm organ / pad sound
        sample_val = 0.0
        for f in notes:
            # Fundamental + soft second harmonic
            sample_val += 0.18 * math.sin(2.0 * math.pi * f * current_time)
            sample_val += 0.06 * math.sin(2.0 * math.pi * f * 2.0 * current_time)
            
        audio[i] = sample_val

    # Add gentle rhythmic kick / pulse on beats
    pulse_freq = 65.0
    for beat_i in range(int(duration_sec / beat_sec)):
        beat_t = beat_i * beat_sec
        start_idx = int(beat_t * sample_rate)
        pulse_len = int(0.18 * sample_rate)
        end_idx = min(len(audio), start_idx + pulse_len)
        
        pulse_env = np.exp(-18.0 * np.linspace(0, 0.18, end_idx - start_idx))
        pulse_wave = np.sin(2.0 * math.pi * pulse_freq * np.linspace(0, 0.18, end_idx - start_idx))
        audio[start_idx:end_idx] += 0.25 * pulse_wave * pulse_env

    # Soft tape / vinyl hiss noise for aesthetic texture
    hiss = np.random.normal(0, 0.008, len(audio))
    audio += hiss

    # Smooth fade out at the end (last 2 seconds)
    fade_len = int(2.5 * sample_rate)
    audio[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

    # Normalize to 16-bit PCM
    audio = audio / max(0.001, np.max(np.abs(audio))) * 0.85
    audio_int16 = (audio * 32767).astype(np.int16)

    wavfile.write(str(output_path), sample_rate, audio_int16)
    print(f"[AudioSync] Generated procedural aesthetic soundtrack: {output_path.name}")
    return output_path

def get_track_and_beat_timestamps(target_duration: float, music_path: Path = None):
    """
    Returns (audio_path, beat_timestamps_list)
    """
    if music_path is None or not music_path.exists():
        tracks = get_available_music_tracks()
        if tracks:
            music_path = tracks[0]
        else:
            procedural_path = config.TEMP_DIR / "aesthetic_ambient.wav"
            music_path = generate_procedural_lofi_track(procedural_path, duration_sec=target_duration + 5.0)

    # Try librosa for precise beat onset detection
    try:
        import librosa
        y, sr = librosa.load(str(music_path), sr=22050, duration=target_duration + 10.0)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        if len(beat_times) > 5:
            return music_path, beat_times
    except Exception as e:
        print(f"[AudioSync] Librosa beat detection note: {e}. Using tempo grid fallback.")

    # Fallback to high-precision chillhop tempo grid (78 BPM)
    bpm = 78.0
    beat_interval = 60.0 / bpm # ~0.77 sec
    beat_times = np.arange(beat_interval, target_duration + 5.0, beat_interval)
    return music_path, beat_times

def calculate_clip_durations(num_clips: int, beat_times: np.ndarray, target_total_duration=45.0):
    """
    Calculates duration for each clip so transitions land directly on musical beats.
    Guarantees the total reel duration is strictly between 30.0 and 60.0 seconds.
    """
    # Enforce strict 30s to 60s target duration range
    target_total_duration = max(30.0, min(60.0, float(target_total_duration)))
    ideal_clip_dur = target_total_duration / float(max(1, num_clips))
    
    durations = []
    current_time = 0.0

    min_interval = max(1.2, min(ideal_clip_dur * 0.6, 2.5))
    max_interval = max(4.0, ideal_clip_dur * 1.5)

    for i in range(num_clips):
        desired_end = current_time + ideal_clip_dur
        min_allowed = current_time + min_interval
        candidate_beats = [b for b in beat_times if b >= min_allowed]

        if candidate_beats and i < num_clips - 1:
            best_beat = min(candidate_beats, key=lambda b: abs(b - desired_end))
            clip_dur = best_beat - current_time
        else:
            clip_dur = ideal_clip_dur

        clip_dur = max(min_interval, min(max_interval, clip_dur))
        durations.append(clip_dur)
        current_time += clip_dur

    # Strict normalization to guarantee reel duration is always between 30.0 and 60.0 seconds
    current_total = sum(durations)
    if current_total < 30.0:
        scale = 32.0 / current_total
        durations = [d * scale for d in durations]
    elif current_total > 60.0:
        scale = 58.0 / current_total
        durations = [d * scale for d in durations]

    return durations
