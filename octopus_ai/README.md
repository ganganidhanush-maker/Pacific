# Octopus AI Agent

**AI-Powered Browser Automation System**

Octopus is an intelligent web automation platform where the **AI Agent is the brain**, not Selenium. The agent understands natural language requests, plans tasks, calls browser automation tools, observes results, and adapts until the task is complete.

## Architecture

```
USER → AI AGENT (Brain) → TOOLS (Hands) → SELENIUM (Engine) → WEB → OBSERVE → AI AGENT
```

### Key Components

1. **AI Agent** - Understands requests, plans tasks, makes decisions
2. **Memory** - Maintains conversation history and context
3. **Safety Layer** - Permission checks for dangerous actions
4. **Tool Layer** - Browser automation commands (open, click, type, read, etc.)
5. **Browser Engine** - Selenium WebDriver execution
6. **Target Websites** - WhatsApp, Instagram, Canva, Google, etc.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Groq API key (get from https://console.groq.com)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd octopus_ai
```

2. Create `.env` file with your Groq API key:
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

3. Run with Docker Compose:
```bash
docker-compose up --build
```

### Usage Examples

Once running, interact with Octopus via the chat interface:

**WhatsApp Automation:**
```
"Open WhatsApp Web and send 'Hello' to Rahul"
```

**Instagram Automation:**
```
"Go to Instagram and follow @username"
```

**Canva Automation:**
```
"Open Canva and create a new presentation"
```

**General Web Tasks:**
```
"Search Google for 'best restaurants near me'"
"Go to example.com and click the login button"
```

## Predefined Workflows

### WhatsApp
- Open WhatsApp Web
- Check authentication status
- Find contact by name
- Open conversation
- Type and send message
- Verify delivery

### Instagram
- Open Instagram
- Navigate to profile
- Follow/unfollow users
- Like posts
- Read comments

### Canva
- Open Canva
- Create new design
- Select template
- Add/edit elements
- Export design

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Your Groq API key | Required |
| `GROQ_MODEL` | LLM model to use | `llama-3.1-70b-versatile` |
| `BROWSER_HEADLESS` | Run browser without UI | `true` |
| `BROWSER_WINDOW_SIZE` | Browser window dimensions | `1920,1080` |

### Safety Permissions

Configure permission levels for different action types:

- `READ` - Automatic
- `SEARCH` - Automatic
- `CLICK` - Automatic
- `TYPE` - Automatic
- `SEND_MESSAGE` - Optional confirmation
- `DELETE` - Confirmation required
- `PURCHASE` - Confirmation required
- `POST_PUBLICLY` - Confirmation required

## Project Structure

```
octopus_ai/
├── agent/          # AI Agent logic
│   ├── agent.py    # Main agent class
│   └── groq_llm.py # Groq LLM integration
├── tools/          # Browser automation tools
│   └── browser_tools.py
├── engine/         # Browser engine
│   └── selenium_engine.py
├── memory/         # Context management
│   └── context.py
├── safety/         # Permission system
│   └── permissions.py
├── interface/      # User interaction
│   └── chat.py
├── system.py       # Main system integration
├── main.py         # Entry point
├── Dockerfile      # Container configuration
├── docker-compose.yml
├── requirements.txt
├── .env.example    # Environment template
└── README.md
```

## Development

### Run Without Docker

```bash
pip install -r requirements.txt
python main.py
```

### Demo Mode (No Browser)

Test the AI reasoning without launching a browser:

```bash
python main.py --demo
```

## Features

- ✅ Natural language understanding
- ✅ Task planning and decomposition
- ✅ Tool selection and execution
- ✅ Result observation and adaptation
- ✅ Conversation memory
- ✅ Safety permissions
- ✅ Multi-website support
- ✅ Docker containerization
- ✅ Persistent browser sessions

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a PR.
