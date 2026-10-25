"""
AI Aesthetic Reel Studio - Modern Web Dashboard
Runs a local web application to monitor Google Drive folders, preview generated 9:16 reels,
customize aesthetic presets, and manually or automatically trigger edits.
"""

import os
import sys
import json
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, send_from_directory, send_file

import config
import curator
import reel_generator
import drive_watcher

app = Flask(__name__)

# State
APP_STATE = {
    "is_rendering": False,
    "last_rendered": None,
    "current_day": None,
    "progress_message": "Idle",
    "progress_percent": 0,
    "watcher_active": False,
    "cloud_sync_status": None
}

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reel Automate AI • Aesthetic Studio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #07090e;
      --card-bg: rgba(18, 22, 34, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent-primary: #7928ca;
      --accent-gradient: linear-gradient(135deg, #ff0080, #7928ca 50%, #0070f3);
      --accent-warm: linear-gradient(135deg, #f59e0b, #ef4444);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      --success: #10b981;
      --radius: 16px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    }

    body {
      background: var(--bg);
      background-image: 
        radial-gradient(at 0% 0%, rgba(121, 40, 202, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(255, 0, 128, 0.1) 0px, transparent 50%);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      padding: 24px 40px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--card-border);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo-badge {
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: var(--accent-gradient);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 4px 20px rgba(121, 40, 202, 0.4);
    }

    .brand h1 {
      font-family: 'Outfit', sans-serif;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: linear-gradient(90deg, #ffffff, #a5b4fc);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand p {
      font-size: 12px;
      color: var(--text-muted);
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: #34d399;
      padding: 6px 14px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 500;
    }

    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 10px var(--success);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(1.2); }
      100% { opacity: 1; transform: scale(1); }
    }

    main {
      padding: 40px;
      max-width: 1400px;
      margin: 0 auto;
      width: 100%;
      display: grid;
      grid-template-columns: 1fr 420px;
      gap: 36px;
    }

    @media (max-width: 1024px) {
      main {
        grid-template-columns: 1fr;
      }
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 28px;
      backdrop-filter: blur(16px);
      box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35);
      margin-bottom: 28px;
    }

    .card-title {
      font-family: 'Outfit', sans-serif;
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Days Feed */
    .day-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 12px;
      transition: all 0.2s ease;
    }

    .day-row:hover {
      background: rgba(255, 255, 255, 0.06);
      border-color: rgba(255, 255, 255, 0.12);
    }

    .day-info h3 {
      font-size: 16px;
      font-weight: 600;
      color: #fff;
    }

    .day-info p {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .badge-eligible {
      background: rgba(121, 40, 202, 0.2);
      border: 1px solid rgba(121, 40, 202, 0.4);
      color: #c084fc;
      padding: 4px 10px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
    }

    .badge-waiting {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-dim);
      padding: 4px 10px;
      border-radius: 8px;
      font-size: 12px;
    }

    .badge-no-photos {
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid rgba(245, 158, 11, 0.35);
      color: #fbbf24;
      padding: 4px 10px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
    }

    .spinner {
      width: 44px;
      height: 44px;
      border: 3px solid rgba(255, 255, 255, 0.12);
      border-top-color: #c084fc;
      border-radius: 50%;
      animation: spin 0.85s linear infinite;
      margin: 0 auto 16px;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .progress-bar-container {
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 999px;
      overflow: hidden;
      margin-top: 14px;
    }

    .progress-bar-fill {
      height: 100%;
      width: 5%;
      background: var(--accent-gradient);
      border-radius: 999px;
      transition: width 0.35s ease;
    }

    .btn {
      background: var(--accent-gradient);
      color: #fff;
      border: none;
      border-radius: 10px;
      padding: 10px 18px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
    }

    .btn:hover {
      opacity: 0.92;
      transform: translateY(-1px);
    }

    .btn:active {
      transform: translateY(0);
    }

    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
      border: 1px solid rgba(255, 255, 255, 0.12);
    }

    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.12);
    }

    /* Style Selector */
    .style-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 12px;
    }

    .style-option {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 14px;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s ease;
    }

    .style-option.active {
      border-color: #a855f7;
      background: rgba(168, 85, 247, 0.15);
      box-shadow: 0 0 20px rgba(168, 85, 247, 0.2);
    }

    .style-option h4 {
      font-size: 14px;
      font-weight: 600;
    }

    .style-option p {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }

    /* Phone Mockup Frame */
    .preview-container {
      position: sticky;
      top: 100px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    .phone-frame {
      width: 320px;
      height: 600px;
      background: #000;
      border: 6px solid #2d3748;
      border-radius: 38px;
      position: relative;
      overflow: hidden;
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8), 0 0 24px rgba(121, 40, 202, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .phone-notch {
      position: absolute;
      top: 0;
      left: 50%;
      transform: translateX(-50%);
      width: 110px;
      height: 20px;
      background: #2d3748;
      border-bottom-left-radius: 14px;
      border-bottom-right-radius: 14px;
      z-index: 20;
    }

    .phone-video {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .placeholder-reel {
      text-align: center;
      padding: 30px;
      color: var(--text-dim);
    }

    .placeholder-reel svg {
      width: 48px;
      height: 48px;
      margin-bottom: 12px;
      stroke: var(--text-dim);
    }

    /* Terminal Console */
    .console-box {
      background: #040507;
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      padding: 16px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      color: #38bdf8;
      height: 140px;
      overflow-y: auto;
      line-height: 1.5;
    }

    .setting-group {
      margin-bottom: 16px;
    }

    .setting-group label {
      display: block;
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }

    .setting-input {
      width: 100%;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      padding: 10px 14px;
      color: #fff;
      font-size: 14px;
      outline: none;
    }

    .setting-input:focus {
      border-color: #a855f7;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="logo-badge">🎬</div>
      <div>
        <h1>Reel Automate AI</h1>
        <p>Aesthetic Instagram Reel Generator • Arif Hakim Style</p>
      </div>
    </div>
    <div class="status-pill">
      <div class="pulse-dot"></div>
      <span id="watcher-status">Google Drive Watcher Active</span>
    </div>
  </header>

  <main>
    <!-- Left Column: Controls & Feed -->
    <div class="controls-area">
      <!-- Days Radar -->
      <div class="card">
        <div class="card-title">
          <span>📅 Detected Media in Google Drive</span>
          <button class="btn btn-secondary" onclick="refreshDays()">🔄 Rescan</button>
        </div>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
          ⚡ <strong>Dynamic Media Engine:</strong> Supports any number of photos & videos (1, 2, or 100+ items). Always paced to produce a 30s to 1-minute aesthetic reel.
        </p>

        <div id="days-container">
          <!-- Dynamically populated -->
          <div style="color: var(--text-dim); text-align: center; padding: 20px;">Scanning media...</div>
        </div>
      </div>

      <!-- Rendered Reels Radar -->
      <div class="card">
        <div class="card-title">
          <span>🎬 Rendered Reels (Ready to View & Share)</span>
          <button class="btn btn-secondary" onclick="loadCompletedReels()">🔄 Refresh</button>
        </div>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 14px;">
          Your finished 9:16 aesthetic reels rendered and saved on your system.
        </p>

        <!-- Cloud Drive Info Box -->
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 12px 14px; margin-bottom: 16px; font-size: 12px; color: #6ee7b7; line-height: 1.5;">
          <strong>✅ Google Drive Connected & Active:</strong> Rendered reels are automatically uploaded straight into your Google Drive folder (<a href="https://drive.google.com/drive/folders/1-vkMEQClKcQOWCobYHHNR96W2FjODxgJ?usp=sharing" target="_blank" style="color: #a7f3d0; text-decoration: underline;">Open Output Folder</a>). You can also download or preview any reel below.
        </div>

        <div id="reels-container">
          <div style="color: var(--text-dim); text-align: center; padding: 16px;">Checking rendered reels...</div>
        </div>
      </div>

      <!-- Aesthetic Style Studio -->
      <div class="card">
        <div class="card-title">🎨 Cinematic Style & Typography</div>
        
        <div class="setting-group">
          <label>Location Badge Overlay (Upper / Lower Third)</label>
          <input type="text" id="location-input" class="setting-input" value="Munich, Germany" placeholder="e.g. Berlin, Germany">
        </div>

        <label style="font-size: 13px; color: var(--text-muted);">Color Grade Emulation</label>
        <div class="style-grid">
          <div class="style-option active" onclick="selectStyle(this, 'arif_cinematic')">
            <h4>🌆 Arif Hakim NYC</h4>
            <p>Portra film tone, warm highlights & lifted soft blacks</p>
          </div>
          <div class="style-option" onclick="selectStyle(this, 'golden_hour')">
            <h4>🌅 Golden Hour</h4>
            <p>Honey warm European sunset glow</p>
          </div>
          <div class="style-option" onclick="selectStyle(this, 'moody_film')">
            <h4>🎞️ Moody Film</h4>
            <p>Desaturated greens & nostalgic 35mm grain</p>
          </div>
        </div>
      </div>

      <!-- Live Engine Logs -->
      <div class="card">
        <div class="card-title">⚙️ Processing Console</div>
        <div class="console-box" id="console-logs">
          [System Ready] Google Drive folder watcher initialized.<br>
          Drop your day's photos into Google Drive anytime.
        </div>
      </div>
    </div>

    <!-- Right Column: Phone Mockup Reel Preview -->
    <div class="preview-container">
      <div class="phone-frame">
        <div class="phone-notch"></div>
        <div id="reel-viewport" style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">
          <div class="placeholder-reel">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p style="font-size: 13px;">No reel rendered yet</p>
            <p style="font-size: 11px; margin-top: 4px; color: var(--text-dim);">Pick a ready day on the left to generate</p>
          </div>
        </div>
      </div>

      <div style="margin-top: 20px; display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;">
        <button id="download-btn" class="btn" style="display: none;" onclick="downloadLatestReel()">
          ⬇️ Download MP4
        </button>
        <button class="btn btn-secondary" onclick="openOutputFolder()">
          ☁️ Open in Drive
        </button>
        <button class="btn btn-secondary" onclick="revealReelFile()">
          📁 Show on PC
        </button>
      </div>
    </div>
  </main>

  <script>
    let activeStyle = "arif_cinematic";
    let latestReelUrl = null;
    let currentReelFilename = null;
    let cloudOutputUrl = "";

    function log(msg) {
      const box = document.getElementById("console-logs");
      box.innerHTML += `<div>> ${msg}</div>`;
      box.scrollTop = box.scrollHeight;
    }

    function selectStyle(el, styleName) {
      document.querySelectorAll(".style-option").forEach(e => e.classList.remove("active"));
      el.classList.add("active");
      activeStyle = styleName;
      log(`Selected color preset: ${styleName}`);
    }

    async function refreshDays() {
      try {
        log("Scanning Google Drive input queue...");
        const res = await fetch("/api/days");
        const data = await res.json();
        cloudOutputUrl = data.output_path || "";
        const container = document.getElementById("days-container");

        if (Object.keys(data.days).length === 0) {
          container.innerHTML = `
            <div style="text-align: center; padding: 24px; color: var(--text-dim);">
              <p>No photos found in Google Drive folder yet.</p>
              <p style="font-size: 12px; margin-top: 6px;">Folder path: <code>${data.input_path}</code></p>
            </div>
          `;
          return;
        }

        let html = "";

        // 1. Featured Unified Folder Row (All Media Combined)
        if (data.all_media && data.all_media.total > 0) {
          const all = data.all_media;
          const allEligible = all.is_eligible;
          const allHasPhotos = all.has_photos;

          let allBadge = "";
          let allAction = "";
          if (!allHasPhotos) {
            allBadge = `<span class="badge-no-photos">⏳ ADD PHOTOS IN DRIVE</span>`;
            allAction = `<button class="btn btn-secondary" style="opacity: 0.55;" onclick="log('⚠️ Note: Reel will be made once photos are added to Google Drive.')">Waiting for Photos</button>`;
          } else if (allEligible) {
            allBadge = `<span class="badge-eligible" style="background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.4); color: #34d399;">✨ READY (${all.total}/15 items)</span>`;
            allAction = `<button class="btn" style="box-shadow: 0 0 16px rgba(121, 40, 202, 0.5);" onclick="generateReel('all', false, this)">⚡ Generate Reel (All ${all.total} Items)</button>`;
          } else {
            allBadge = `<span class="badge-waiting">${all.total}/15 items</span>`;
            allAction = `<button class="btn btn-secondary" style="opacity: 0.85;" onclick="generateReel('all', true, this)">Force Edit (All ${all.total})</button>`;
          }

          html += `
            <div class="day-row" style="background: rgba(121, 40, 202, 0.16); border: 1px solid rgba(168, 85, 247, 0.45); padding: 18px 20px; margin-bottom: 16px;">
              <div class="day-info">
                <h3 style="color: #f3e8ff; font-size: 16px; font-weight: 700;">🌟 Entire Drive Folder (All 18 Media Items)</h3>
                <p style="color: #d8b4fe; font-size: 13px; margin-top: 3px;">
                  📸 ${all.photos} photos  •  🎥 ${all.videos} videos (${all.total} total media files across all dates)
                </p>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                ${allBadge}
                ${allAction}
              </div>
            </div>
            <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600;">
              Or Generate by Individual iPhone Capture Date:
            </div>
          `;
        }

        for (const [day, info] of Object.entries(data.days)) {
          const isEligible = typeof info === "object" ? info.is_eligible : info >= 15;
          const hasPhotos = typeof info === "object" ? info.has_photos : true;
          const totalCount = typeof info === "object" ? info.total : info;
          const photoCount = typeof info === "object" ? info.photos : 0;
          const videoCount = typeof info === "object" ? info.videos : 0;

          let mediaDesc = `${totalCount} media files recorded`;
          if (typeof info === "object" && (photoCount > 0 || videoCount > 0)) {
            mediaDesc = `📸 ${photoCount} photos  •  🎥 ${videoCount} videos (${totalCount} total)`;
          }

          let badgeHtml = "";
          let actionBtn = "";

          if (!hasPhotos) {
            badgeHtml = `<span class="badge-no-photos">⏳ ADD PHOTOS IN DRIVE</span>`;
            actionBtn = `<button class="btn btn-secondary" style="opacity: 0.55;" onclick="log('⚠️ Note: Reel will be made once photos are added to Google Drive.')">Waiting for Photos</button>`;
          } else if (isEligible) {
            badgeHtml = `<span class="badge-eligible">✨ READY (${photoCount}P + ${videoCount}V)</span>`;
            actionBtn = `<button class="btn" onclick="generateReel('${day}', false, this)">⚡ Generate Reel</button>`;
          } else {
            badgeHtml = `<span class="badge-waiting">${totalCount}/15 items</span>`;
            actionBtn = `<button class="btn btn-secondary" style="opacity: 0.8;" onclick="generateReel('${day}', true, this)">Force Edit</button>`;
          }

          html += `
            <div class="day-row">
              <div class="day-info">
                <h3>🗓️ ${day}</h3>
                <p>${mediaDesc}</p>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                ${badgeHtml}
                ${actionBtn}
              </div>
            </div>
          `;
        }
        container.innerHTML = html;
      } catch (err) {
        log("Error refreshing days: " + err);
      }
    }

    async function loadCompletedReels() {
      try {
        const res = await fetch("/api/reels");
        const data = await res.json();
        if (data.cloud_output_url) {
          cloudOutputUrl = data.cloud_output_url;
        }
        const container = document.getElementById("reels-container");

        if (!data.reels || data.reels.length === 0) {
          container.innerHTML = `
            <div style="text-align: center; padding: 16px; color: var(--text-dim); font-size: 13px;">
              No reels rendered yet. Click <strong>⚡ Generate Reel</strong> or <strong>Force Edit</strong> on a day above!
            </div>
          `;
          return;
        }

        let html = "";
        data.reels.forEach((r) => {
          html += `
            <div class="day-row" style="margin-bottom: 10px;">
              <div class="day-info" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <h3 style="font-size: 14px;" title="${r.name}">🎬 ${r.name}</h3>
                <p style="font-size: 12px;">${r.size_mb} MB • ${r.time_str}</p>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="playReel('${r.name}')">▶ Preview</button>
                <a href="${r.url}" download="${r.name}" class="btn" style="padding: 6px 12px; font-size: 12px;">⬇ Save</a>
                <button class="btn btn-secondary" style="padding: 6px 10px; font-size: 12px;" title="Show on PC" onclick="revealReelFile('${r.name}')">📁</button>
              </div>
            </div>
          `;
        });
        container.innerHTML = html;

        // Auto-play the newest reel in phone preview if not playing yet
        if (!latestReelUrl && data.reels.length > 0) {
          playReel(data.reels[0].name);
        }
      } catch (e) {
        log("Error loading completed reels: " + e);
      }
    }

    async function generateReel(dayStr, force = false, btnEl = null) {
      const location = document.getElementById("location-input").value;
      log(`Initiating reel render for date: ${dayStr} [Style: ${activeStyle}, Location: ${location}]...`);
      
      if (btnEl) {
        btnEl.disabled = true;
        btnEl.innerHTML = `⏳ Rendering...`;
      }

      // Show immediate live feedback inside the phone simulator with progress bar
      const viewport = document.getElementById("reel-viewport");
      viewport.innerHTML = `
        <div style="text-align: center; padding: 24px; color: #fff; max-width: 280px;">
          <div class="spinner"></div>
          <h3 style="font-size: 16px; font-weight: 600; color: #c084fc; margin-bottom: 6px;">🎬 Rendering Reel</h3>
          <p id="render-status-msg" style="font-size: 12px; color: var(--text-muted); line-height: 1.4; min-height: 34px;">
            Assembling 1080x1920 video snippets, Ken Burns drifts & Portra film tone...
          </p>
          <div class="progress-bar-container">
            <div id="render-progress-bar" class="progress-bar-fill"></div>
          </div>
          <div style="margin-top: 14px; padding: 6px 12px; border-radius: 8px; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); color: #fbbf24; font-size: 11px;">
            ⏱️ Takes ~1–2 minutes. Auto-plays when ready!
          </div>
        </div>
      `;

      try {
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ day: dayStr, style: activeStyle, location: location, force: force })
        });
        const data = await res.json();
        
        if (data.status === "started") {
          log("Rendering started in background. Motion drift & color grading in progress...");
          pollRenderStatus(btnEl, force);
        } else {
          log("Notice: " + data.message);
          viewport.innerHTML = `<div class="placeholder-reel"><p style="color:#ef4444; font-size:13px;">${data.message}</p></div>`;
          if (btnEl) {
            btnEl.disabled = false;
            btnEl.innerHTML = force ? "Force Edit" : "⚡ Generate Reel";
          }
        }
      } catch (err) {
        log("Generation request error: " + err);
        if (btnEl) {
          btnEl.disabled = false;
          btnEl.innerHTML = force ? "Force Edit" : "⚡ Generate Reel";
        }
      }
    }

    function pollRenderStatus(btnEl = null, force = false) {
      const interval = setInterval(async () => {
        try {
          const res = await fetch("/api/status");
          const status = await res.json();
          
          if (status.is_rendering) {
            const statusMsgEl = document.getElementById("render-status-msg");
            const progressBar = document.getElementById("render-progress-bar");
            if (statusMsgEl && status.progress_message) {
              statusMsgEl.innerText = status.progress_message;
            }
            if (progressBar && status.progress_percent) {
              progressBar.style.width = `${status.progress_percent}%`;
            }
          } else {
            clearInterval(interval);
            if (btnEl) {
              btnEl.disabled = false;
              btnEl.innerHTML = force ? "Force Edit" : "⚡ Generate Reel";
            }
            if (status.last_rendered) {
              log(`✨ REEL COMPLETED! Saved to: ${status.last_rendered}`);
              playReel(status.last_rendered);
              loadCompletedReels();
              refreshDays();
            }
          }
        } catch (e) {
          console.error(e);
        }
      }, 1500);
    }

    function playReel(filename) {
      latestReelUrl = `/reels/${filename}`;
      currentReelFilename = filename;
      const viewport = document.getElementById("reel-viewport");
      viewport.innerHTML = `
        <video class="phone-video" src="${latestReelUrl}" autoplay loop playsinline controls></video>
      `;
      document.getElementById("download-btn").style.display = "inline-flex";
      log(`Now playing: ${filename}`);
    }

    function downloadLatestReel() {
      if (latestReelUrl) {
        const a = document.createElement("a");
        a.href = latestReelUrl;
        a.download = currentReelFilename || "Aesthetic_Reel.mp4";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        log(`Downloading: ${currentReelFilename || 'Reel.mp4'}`);
      }
    }

    function revealReelFile(filename) {
      const fname = filename || currentReelFilename || "";
      fetch(`/api/reveal-reel?filename=${encodeURIComponent(fname)}`);
      log(`Opened File Explorer on PC for reel: ${fname || 'output folder'}`);
    }

    function openOutputFolder() {
      if (cloudOutputUrl) {
        window.open(cloudOutputUrl, "_blank");
      }
      fetch("/api/open-folder");
      log("Opening Google Drive reels output folder...");
    }

    // Initial load
    refreshDays();
    loadCompletedReels();
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route("/api/days")
def get_days():
    if config.IS_CLOUD_INPUT:
        try:
            google_drive_api.download_folder_from_cloud(config.CLOUD_INPUT_URL, config.GOOGLE_DRIVE_INPUT_FOLDER)
        except Exception as e:
            print(f"[Dashboard] Error syncing cloud input: {e}")

    all_items = curator.get_all_media_items(config.GOOGLE_DRIVE_INPUT_FOLDER)
    all_eligible, all_reason, all_stats = curator.check_day_eligibility(all_items)

    grouped = curator.scan_and_group_by_day(config.GOOGLE_DRIVE_INPUT_FOLDER)
    summary = {}
    for day, items in grouped.items():
        is_eligible, reason, stats = curator.check_day_eligibility(items)
        summary[day] = {
            "total": stats["total"],
            "photos": stats["photos"],
            "videos": stats["videos"],
            "has_photos": stats["has_photos"],
            "is_eligible": is_eligible,
            "status_message": reason
        }
    return jsonify({
        "all_media": {
            "total": all_stats["total"],
            "photos": all_stats["photos"],
            "videos": all_stats["videos"],
            "has_photos": all_stats["has_photos"],
            "is_eligible": all_eligible,
            "status_message": all_reason
        },
        "days": summary,
        "is_cloud_input": config.IS_CLOUD_INPUT,
        "is_cloud_output": config.IS_CLOUD_OUTPUT,
        "input_path": config.CLOUD_INPUT_URL if config.IS_CLOUD_INPUT else str(config.GOOGLE_DRIVE_INPUT_FOLDER),
        "output_path": config.CLOUD_OUTPUT_URL if config.IS_CLOUD_OUTPUT else str(config.GOOGLE_DRIVE_OUTPUT_FOLDER),
        "require_photos": config.REQUIRE_PHOTOS
    })

@app.route("/api/status")
def get_status():
    return jsonify(APP_STATE)

@app.route("/api/generate", methods=["POST"])
def trigger_generate():
    if APP_STATE["is_rendering"]:
        return jsonify({"status": "busy", "message": "A reel is already being rendered."})

    data = request.json or {}
    day_target = data.get("day")
    location = data.get("location", config.DEFAULT_LOCATION_NAME)
    style = data.get("style", "arif_cinematic")
    force = data.get("force", False)

    if config.IS_CLOUD_INPUT:
        try:
            google_drive_api.download_folder_from_cloud(config.CLOUD_INPUT_URL, config.GOOGLE_DRIVE_INPUT_FOLDER)
        except Exception as e:
            print(f"[Dashboard] Error syncing cloud input: {e}")

    if str(day_target).lower() in ("all", "all_media"):
        day_media = curator.get_all_media_items(config.GOOGLE_DRIVE_INPUT_FOLDER)
    else:
        grouped = curator.scan_and_group_by_day(config.GOOGLE_DRIVE_INPUT_FOLDER)
        day_media = grouped.get(day_target, [])

    is_eligible, reason, stats = curator.check_day_eligibility(day_media)

    # Strictly require photos: Reels are only created when photos are added to Google Drive
    if config.REQUIRE_PHOTOS and not stats["has_photos"]:
        return jsonify({
            "status": "waiting_for_photos",
            "message": f"Waiting for photos in Drive: Day {day_target} has {stats['videos']} videos but 0 photos. Reel will only be made once photos are added to Google Drive."
        })

    if not is_eligible and not force:
        return jsonify({
            "status": "threshold_not_met",
            "message": reason
        })

    def run_render_task():
        APP_STATE["is_rendering"] = True
        APP_STATE["current_day"] = day_target
        APP_STATE["progress_message"] = "Starting scene rendering..."
        APP_STATE["progress_percent"] = 5

        def on_progress(msg, pct=None):
            APP_STATE["progress_message"] = msg
            if pct is not None:
                APP_STATE["progress_percent"] = pct

        try:
            config.AESTHETIC_PRESET = style
            rendered = reel_generator.render_reel_for_day(
                day_target, day_media, location_name=location, force=force, progress_callback=on_progress
            )
            if rendered:
                APP_STATE["last_rendered"] = rendered.name
                APP_STATE["progress_message"] = "Syncing with Google Drive..."
                sync_res = drive_watcher.sync_reel_to_google_drive(rendered)
                APP_STATE["cloud_sync_status"] = sync_res
                APP_STATE["progress_message"] = "Reel complete!"
                APP_STATE["progress_percent"] = 100
        except Exception as e:
            print(f"[Dashboard] Render error: {e}")
            APP_STATE["progress_message"] = f"Render error: {e}"
        finally:
            APP_STATE["is_rendering"] = False

    t = threading.Thread(target=run_render_task)
    t.daemon = True
    t.start()

    return jsonify({"status": "started", "day": day_target})

@app.route("/reels/<path:filename>")
def serve_reel(filename):
    return send_from_directory(config.OUTPUT_DIR, filename)

@app.route("/api/reels")
def list_reels():
    reels = []
    if config.OUTPUT_DIR.exists():
        for f in sorted(config.OUTPUT_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            reels.append({
                "name": f.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "mtime": stat.st_mtime,
                "time_str": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %H:%M"),
                "url": f"/reels/{f.name}",
                "drive_url": config.CLOUD_OUTPUT_URL if config.IS_CLOUD_OUTPUT else None
            })
    return jsonify({
        "reels": reels,
        "cloud_output_url": config.CLOUD_OUTPUT_URL if config.IS_CLOUD_OUTPUT else "",
        "is_cloud_output": config.IS_CLOUD_OUTPUT
    })

@app.route("/api/reveal-reel")
def reveal_reel():
    filename = request.args.get("filename", "")
    target = (config.OUTPUT_DIR / filename) if filename else config.OUTPUT_DIR
    try:
        import subprocess
        if target.is_file():
            subprocess.Popen(f'explorer.exe /select,"{str(target.resolve())}"')
        else:
            subprocess.Popen(f'explorer.exe "{str(config.OUTPUT_DIR.resolve())}"')
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/open-folder")
def open_output_folder():
    if config.IS_CLOUD_OUTPUT:
        import webbrowser
        webbrowser.open(config.CLOUD_OUTPUT_URL)
    else:
        try:
            os.startfile(str(config.GOOGLE_DRIVE_OUTPUT_FOLDER))
        except Exception as e:
            print(f"Cannot open folder: {e}")
    return jsonify({"status": "ok"})

def run_dashboard(port=5000):
    print(f"\n=======================================================")
    print(f"  🎬 REEL AUTOMATE AI DASHBOARD RUNNING ON:")
    print(f"  👉 http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    run_dashboard()
