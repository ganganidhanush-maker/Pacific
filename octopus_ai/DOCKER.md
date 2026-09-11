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
docker-compose down -v
```

### Option 2: Using Docker Directly

```bash
# Build the image
docker build -t octopus-ai-agent .

# Run the container with virtual display
docker run -it --rm \
  -e DISPLAY=:99 \
  -e CHROME_BIN=/usr/bin/google-chrome \
  -e CHROMEDRIVER_PATH=/usr/local/bin/chromedriver \
  -v chrome-data:/app/chrome-data \
  octopus-ai-agent

# Or run with custom command
docker run -it --rm \
  -e DISPLAY=:99 \
  -v $(pwd):/app \
  octopus-ai-agent python example_usage.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DISPLAY` | Virtual display for headless browser | `:99` |
| `CHROME_BIN` | Path to Chrome binary | `/usr/bin/google-chrome` |
| `CHROMEDRIVER_PATH` | Path to ChromeDriver | `/usr/local/bin/chromedriver` |
| `PYTHONUNBUFFERED` | Python output buffering | `1` |
| `OPENAI_API_KEY` | OpenAI API key (for LLM integration) | - |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative LLM) | - |

## Volumes

| Volume | Purpose |
|--------|---------|
| `chrome-data` | Persists Chrome user data (cookies, sessions, cache) |

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
