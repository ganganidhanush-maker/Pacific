# Octopus AI Agent - Production Dockerfile
# Python 3.11 with Google Chrome, FFmpeg, Xvfb and Audio Synthesis

FROM python:3.11-slim

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    HOST=0.0.0.0 \
    PORT=8000 \
    IN_DOCKER=1 \
    BROWSER_HEADLESS=true \
    CHROME_USER_DATA_DIR=/app/chrome-data \
    DISPLAY=:99

# Install system dependencies (Chrome requirements, Xvfb virtual display, FFmpeg for audio/video)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    xvfb \
    ffmpeg \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    libgbm1 \
    libpango-1.0-0 \
    fonts-liberation \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome Stable via modern keyring
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && (python -m playwright install chromium || true)

# Copy application source code
COPY . .

# Ensure data and cache directories exist with write permissions
RUN mkdir -p /app/chrome-data /app/.chrome_profile /app/assets/audio_cache \
    && chmod -R 777 /app/chrome-data /app/.chrome_profile /app/assets/audio_cache

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose API and UI port
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
