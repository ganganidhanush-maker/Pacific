#!/bin/bash
set -e

if [ -n "$DISPLAY" ]; then
    Xvfb "$DISPLAY" -screen 0 1920x1080x24 -ac > /dev/null 2>&1 &
    sleep 1
fi

mkdir -p /app/chrome-data /app/assets/audio_cache

esho_banner="=========================================================="
echo "$esho_banner"
echo "          OCTOPUS AI — DOCKER CONTAINER READY            "
echo "$esho_banner"
echo "• Avatar & Multi-Agent UI: http://localhost:8000"
echo "• Browser Engine: Headless Chrome with persistent session"
echo "$esho_banner"

exec python main.py "$@"
