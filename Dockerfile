# Pacific / Octopus AI - Production Multi-Agent System Dockerfile
# Python 3.11 with Google Chrome, FFmpeg, Xvfb and Audio Synthesis

FROM python:3.11-slim

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

RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/chrome-data /app/octopus_ai/assets/audio_cache && chmod -R 777 /app/chrome-data /app/octopus_ai/assets/audio_cache
RUN chmod +x /app/octopus_ai/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/octopus_ai/entrypoint.sh"]
CMD []
