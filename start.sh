#!/bin/bash
# Startup script for 24/7 Cloud Deployment

echo "Starting Reel Automate AI Cloud Services..."

# 1. Start Web Dashboard in the background
python dashboard.py &

# 2. Start Continuous Google Drive Watcher in the foreground
python -u drive_watcher.py --watch
