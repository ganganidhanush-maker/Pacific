# Octopus AI Agent - Docker Documentation

## Quick Start with Docker

### Prerequisites
- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+)

### Option 1: Using Docker Compose (Recommended)

```bash
# Build and run the container
docker-compose up --build

# Run in detached mode (background)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop the container
docker-compose down

# Stop and remove volumes (clears Chrome data)
docker compose down -v
```

Once running, simply open **http://localhost:8000** on your host computer to interact with the full Desktop Avatar, 9-dots menu, and all 5 agents!

### Option 2: Using Docker Directly

```bash
# Build the image
docker build -t pacific-octopus-ai .

# Run the container with port 8000 mapped
docker run -it --rm \
  -p 8000:8000 \
  -e DISPLAY=:99 \
  -e HOST=0.0.0.0 \
  -e PORT=8000 \
  -v chrome-data:/app/chrome-data \
  pacific-octopus-ai
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DISPLAY` | Virtual display for headless browser (Xvfb) | `:99` |
| `BROWSER_HEADLESS` | Run Chrome in headless automation mode | `true` |
| `IN_DOCKER` | Indicates containerized execution | `1` |
| `GROQ_API_KEY` | Optional Groq API key for cloud LLM reasoning | - |
| `GROQ_MODEL` | Groq model selection | `llama-3.3-70b-versatile` |

## Volumes

| Volume | Purpose |
|--------|---------|
| `chrome-data` | Persists Chrome user data (cookies, active sessions, cache) |
| `audio_cache` | Persists synthesized audio speech files |

## Ports

| Port | Service |
|------|---------|
| `8000` | Web interface (future) |

## Development Workflow

### Mount Local Code

The docker-compose.yml already mounts your local code:

```yaml
volumes:
  - .:/app
```

This means any changes you make locally will be reflected in the container immediately.

### Rebuild After Dependency Changes

If you update `requirements.txt`:

```bash
docker-compose up --build
```

### Access Container Shell

```bash
# Running container
docker exec -it octopus-ai-agent bash

# Or if using docker-compose
docker-compose exec octopus-agent bash
```

### Run Specific Commands

```bash
# Run tests
docker-compose run octopus-agent pytest

# Run Python REPL
docker-compose run octopus-agent python

# Run a specific script
docker-compose run octopus-agent python my_script.py
```

## Troubleshooting

### Chrome Won't Start

Check if Chrome is properly installed:
```bash
docker-compose run octopus-agent google-chrome --version
```

### Display Issues

Ensure Xvfb is running:
```bash
docker-compose exec octopus-agent ps aux | grep Xvfb
```

### Permission Errors

If you encounter permission issues with mounted volumes:
```bash
sudo chown -R $USER:$USER .
```

### Clear All Data

```bash
docker-compose down -v
docker system prune -a
```

## Building for Production

### Optimize Image Size

For production, consider:
1. Using a smaller base image (e.g., `python:3.11-alpine`)
2. Removing development dependencies
3. Multi-stage builds

### Security Considerations

1. Don't commit `.env` files with API keys
2. Use Docker secrets for sensitive data
3. Run as non-root user (requires Dockerfile modifications)

## Next Steps

1. **Integrate LLM**: Add your preferred LLM provider API key
2. **Customize Tools**: Extend browser tools for your use case
3. **Add Web Interface**: Implement Flask/FastAPI frontend
4. **Deploy**: Deploy to cloud providers (AWS, GCP, Azure)

## Example: Running with OpenAI Integration

```bash
# Create .env file
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Run with environment variables
docker-compose --env-file .env up --build
```

## Architecture Reminder

```
USER → AI AGENT → TOOLS → SELENIUM → WEB → OBSERVE → AI AGENT
```

The container includes:
- ✅ Python 3.11
- ✅ Google Chrome
- ✅ ChromeDriver
- ✅ Selenium
- ✅ All project modules
- ✅ Virtual display (Xvfb) for headless operation
