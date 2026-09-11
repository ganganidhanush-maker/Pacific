#!/usr/bin/env python3
"""
Octopus AI Agent - Main Entry Point

Run this script to start the Octopus AI Agent with Groq LLM integration.
The agent will automate WhatsApp, Instagram, Canva and other websites based on natural language commands.

Usage:
    python main.py
    
Environment Variables:
    GROQ_API_KEY: Your Groq API key (required)
    GROQ_MODEL: Model to use (default: llama-3.3-70b-versatile)
    BROWSER_HEADLESS: Run browser in headless mode (default: true)
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from octopus_ai.agent.agent import OctopusAgent
from octopus_ai.interface.chat import ChatInterface


async def main():
    """Main entry point for Octopus AI Agent."""
    
    print("=" * 60)
    print("       OCTOPUS AI AGENT - Web Automation System")
    print("=" * 60)
    print()
    print("Platforms supported:")
    print("  • WhatsApp Web - Send messages, check chats")
    print("  • Instagram - Follow, like, comment, DM")
    print("  • Canva - Create presentations, designs")
    print("  • Any website - General browsing automation")
    print()
    print("Example commands:")
    print('  "Open WhatsApp and send Hi to Rahul"')
    print('  "Go to Instagram and check my notifications"')
    print('  "Create a presentation in Canva about AI"')
    print()
    print("Type 'quit' or 'exit' to stop the agent.")
    print("=" * 60)
    print()
    
    # Initialize agent with Groq API key from environment
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        print("ERROR: GROQ_API_KEY not found in environment!")
        print("Please set GROQ_API_KEY environment variable or create a .env file.")
        print(f"Current env keys: {list(os.environ.keys())}")
        return
    
    print(f"✓ Groq API key loaded")
    print(f"✓ Initializing Octopus Agent...")
    
    try:
        agent = OctopusAgent(groq_api_key=groq_api_key)
        print(f"✓ Agent initialized successfully")
        print(f"✓ Available platforms: {agent.get_status()['available_platforms']}")
        print()
        
        # Create chat interface
        interface = ChatInterface(agent)
        
        # Start interactive chat
        await interface.start()
        
    except Exception as e:
        print(f"\n✗ Error initializing agent: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure GROQ_API_KEY is set correctly")
        print("2. Check your internet connection")
        print("3. Verify Docker container is running with proper permissions")


def run_demo():
    """Run a quick demo of the agent capabilities."""
    print("\n" + "=" * 60)
    print("              OCTOPUS AI DEMO MODE")
    print("=" * 60)
    
    # Test without actual browser automation
    from octopus_ai.agent.groq_llm import GroqLLM, PLATFORM_WORKFLOWS
    
    llm = GroqLLM()
    
    test_commands = [
        "Open WhatsApp Web and send a message to Rahul saying I'll call him after 6 PM",
        "Go to Instagram and check my notifications",
        "Create a presentation in Canva about artificial intelligence"
    ]
    
    tools = [
        {"name": "browser.open", "description": "Open a URL", "parameters": {"url": "string"}},
        {"name": "browser.click", "description": "Click an element", "parameters": {"selector": "string"}},
        {"name": "browser.type", "description": "Type text", "parameters": {"selector": "string", "text": "string"}},
        {"name": "browser.read", "description": "Read page content", "parameters": {"selector": "string"}},
        {"name": "browser.wait", "description": "Wait for time", "parameters": {"seconds": "number"}}
    ]
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {cmd}")
        print('-' * 60)
        
        response = llm.chat(cmd, available_tools=tools)
        
        print(f"Action: {response.get('action')}")
        if response.get('action') == 'tool_call':
            print(f"Tool: {response.get('tool_name')}")
            print(f"Parameters: {response.get('parameters')}")
        else:
            content = response.get('content', '')
            print(f"Response: {content[:300]}...")
    
    print("\n" + "=" * 60)
    print("Demo complete! Ready for full automation.")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        asyncio.run(main())
