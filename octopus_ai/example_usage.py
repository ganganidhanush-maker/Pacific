"""
Octopus AI - Example Usage

This demonstrates the core architecture of Octopus as an agentic browser automation system.
"""

from octopus_ai import OctopusSystem, create_octopus

def demo_architecture():
    """Demonstrate the Octopus architecture components"""
    
    print("=" * 70)
    print("🐙 OCTOPUS AI - AGENTIC BROWSER AUTOMATION SYSTEM")
    print("=" * 70)
    
    # Show the key loop from the architecture
    print("\n📋 THE KEY LOOP:")
    print("""
    USER
      ↓
    AI AGENT (Brain)
      ↓
    THINK / PLAN
      ↓
    CALL TOOL
      ↓
    SELENIUM (Engine)
      ↓
    WEB PAGE
      ↓
    OBSERVE RESULT
      ↓
    AI AGENT (evaluates)
      ↓
    NEXT ACTION
      ↓
    ... (repeat until complete)
      ↓
    TASK COMPLETE
      ↓
    USER
    """)
    
    print("\n🏗️  SIX MAJOR MODULES:")
    print("""
    1. AI Agent (Brain)
       - Understands requests
       - Plans tasks
       - Makes decisions
       - Calls tools
    
    2. Tool Layer (Hands)
       - browser.open()
       - browser.click()
       - browser.type()
       - browser.read()
       - browser.scroll()
       - browser.screenshot()
    
    3. Browser Engine (Physical Controller)
       - Selenium WebDriver
       - Playwright (future)
    
    4. Memory (Context)
       - Conversation history
       - Current task state
       - Previous actions
    
    5. Safety Layer (Control)
       - Permission checks
       - Domain restrictions
       - Confirmation requirements
    
    6. Interface (Mouth/Ears)
       - Chat UI
       - Voice (future)
    """)
    
    print("\n✅ EXAMPLE WORKFLOW:")
    print("""
    User: "Open WhatsApp Web and reply to Rahul saying I'll call him after 6 PM"
    
    Agent Process:
    1. UNDERSTAND: Goal = Send message to Rahul on WhatsApp
    2. PLAN: 
       - Open WhatsApp Web
       - Check authentication
       - Find Rahul
       - Open conversation
       - Type message
       - Send message
       - Verify delivery
    3. EXECUTE: Call tools via Selenium
    4. OBSERVE: Check each step's result
    5. ADAPT: Handle errors if any
    6. COMPLETE: Report success to user
    """)
    
    print("=" * 70)
    print("\n🚀 To use Octopus in your code:")
    print("""
    from octopus_ai import OctopusSystem
    
    # Initialize
    octopus = OctopusSystem(headless=True)
    
    # Chat with it
    response = octopus.chat("Open Google and search for Python")
    print(response)
    
    # Or execute direct actions
    result = octopus.execute_action("browser.open", url="https://google.com")
    
    # Get status
    status = octopus.get_status()
    
    # Cleanup
    octopus.quit()
    """)
    print("=" * 70)


if __name__ == "__main__":
    demo_architecture()
