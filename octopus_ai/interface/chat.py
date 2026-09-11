"""
Octopus User Interface Module

Conversation interface for user interaction with Octopus.
Initially a simple chat interface, expandable to voice later.
"""

from typing import Dict, Any, List, Optional, Callable


class ChatInterface:
    """
    Simple chat interface for Octopus
    
    Handles user input and displays agent responses
    """
    
    def __init__(self):
        self.message_history: List[Dict[str, str]] = []
        self.on_message_callback: Optional[Callable[[str], str]] = None
    
    def set_message_handler(self, callback: Callable[[str], str]) -> None:
        """
        Set callback function to handle user messages
        
        Callback receives user message and should return agent response
        """
        self.on_message_callback = callback
    
    def receive_user_message(self, message: str) -> Dict[str, Any]:
        """
        Receive a message from the user
        
        Returns response dict with message and metadata
        """
        # Store in history
        self.message_history.append({
            "role": "user",
            "content": message
        })
        
        # Process if handler is set
        if self.on_message_callback:
            try:
                response = self.on_message_callback(message)
                
                # Store response in history
                self.message_history.append({
                    "role": "assistant",
                    "content": response
                })
                
                return {
                    "success": True,
                    "response": response,
                    "history_length": len(self.message_history)
                }
            except Exception as e:
                error_response = f"Error processing request: {str(e)}"
                self.message_history.append({
                    "role": "assistant",
                    "content": error_response
                })
                return {
                    "success": False,
                    "error": str(e),
                    "response": error_response
                }
        else:
            return {
                "success": False,
                "error": "No message handler configured",
                "response": "I'm not connected to an agent yet."
            }
    
    def get_history(self, limit: int = 20) -> List[Dict[str, str]]:
        """Get recent conversation history"""
        return self.message_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear conversation history"""
        self.message_history = []
    
    def display_message(self, role: str, content: str) -> None:
        """Display a message (for CLI usage)"""
        prefix = "👤 You" if role == "user" else "🐙 Octopus"
        print(f"\n{prefix}:")
        print(f"  {content}")


class WebChatInterface(ChatInterface):
    """
    Web-based chat interface for Octopus
    
    Can be integrated with Flask/FastAPI web applications
    """
    
    def __init__(self):
        super().__init__()
        self.clients: List[Any] = []  # WebSocket clients
    
    def add_client(self, client: Any) -> None:
        """Add a WebSocket client"""
        self.clients.append(client)
    
    def remove_client(self, client: Any) -> None:
        """Remove a WebSocket client"""
        if client in self.clients:
            self.clients.remove(client)
    
    async def broadcast_message(self, role: str, content: str) -> None:
        """Broadcast message to all connected clients"""
        message = {
            "type": "chat_message",
            "role": role,
            "content": content
        }
        
        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                pass  # Client disconnected
    
    async def receive_websocket_message(self, message: str, client: Any) -> Dict[str, Any]:
        """Handle incoming WebSocket message"""
        result = self.receive_user_message(message)
        
        # Broadcast response
        if result.get("success"):
            await self.broadcast_message("assistant", result["response"])
        
        return result


# Example usage
if __name__ == "__main__":
    print("Octopus Chat Interface Demo\n")
    print("=" * 50)
    
    interface = ChatInterface()
    
    # Simulate a simple echo handler
    def echo_handler(message: str) -> str:
        return f"Echo: {message}"
    
    interface.set_message_handler(echo_handler)
    
    # Test messages
    test_messages = [
        "Hello Octopus!",
        "Open WhatsApp Web",
        "Send a message to Rahul"
    ]
    
    for msg in test_messages:
        result = interface.receive_user_message(msg)
        interface.display_message("user", msg)
        interface.display_message("assistant", result["response"])
    
    print("\n" + "=" * 50)
    print(f"\nTotal messages in history: {len(interface.get_history())}")
