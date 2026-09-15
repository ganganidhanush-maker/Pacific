"""
Octopus Memory Module - Context Management

The memory module maintains context across interactions:
- Conversation history
- Current website/page
- Current task state
- Previous actions
- Important variables/results
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .persistent_memory import persistent_memory_instance, PersistentMemory


class Memory:
    """
    Memory system for the Octopus AI Agent
    
    Stores and retrieves context needed for multi-step tasks.
    Backboned by SQLite PersistentMemory for cross-session continuity
    and NotebookLM-style source grounding (RAG).
    """
    
    def __init__(self, max_history_length: int = 100):
        self.max_history_length = max_history_length
        self.persistent: PersistentMemory = persistent_memory_instance
        
        # Short-term memory (pre-loaded from persistent SQLite store)
        try:
            self.conversation_history: List[Dict[str, Any]] = self.persistent.get_recent_history(limit=max_history_length)
        except Exception:
            self.conversation_history = []
        self.action_history: List[Dict[str, Any]] = []
        
        # Current state
        self.current_task: Optional[Dict[str, Any]] = None
        self.current_website: Optional[str] = None
        self.current_page: Optional[str] = None
        
        # Variables/Context
        self.variables: Dict[str, Any] = {}
        
        # Important results
        self.important_results: List[Dict[str, Any]] = []
    
    def store(self, key: str, value: Any) -> None:
        """Store a value in memory and persist to SQLite database."""
        self.variables[key] = value
        try:
            self.persistent.store_variable(key, value)
        except Exception:
            pass
    
    def retrieve(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from memory or SQLite fallback."""
        if key in self.variables:
            return self.variables[key]
        try:
            val = self.persistent.retrieve_variable(key, default)
            if val is not None:
                self.variables[key] = val
            return val
        except Exception:
            return default
    
    def add_conversation(self, role: str, content: str, agent_name: str = "main") -> None:
        """
        Add a conversation turn and persist to SQLite.
        """
        entry = {
            "role": role,
            "content": content,
            "agent": agent_name,
            "timestamp": datetime.now().isoformat()
        }
        self.conversation_history.append(entry)
        
        # Trim if too long
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]

        # Persist to database
        try:
            self.persistent.add_message(role=role, content=content, agent_name=agent_name)
        except Exception:
            pass

    # =========================================================================
    # NOTEBOOKLM KNOWLEDGE BASE INTEGRATION
    # =========================================================================
    def index_document(self, file_path: str, tags: str = "notes") -> Dict[str, Any]:
        """Index a local PDF, text, or code file into the persistent knowledge base."""
        return self.persistent.index_local_file(file_path, tags=tags)

    def query_knowledge_base(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve grounded excerpts from indexed student/teacher materials."""
        return self.persistent.query_knowledge_base(query, top_k=top_k)

    async def generate_study_guide(self, source_id: int) -> Dict[str, Any]:
        """Generate a NotebookLM-style comprehensive Study Guide."""
        return await self.persistent.generate_notebooklm_study_guide(source_id)

    async def generate_audio_overview(self, source_id: int) -> Dict[str, Any]:
        """Generate a NotebookLM-style Audio Overview script for the Avatar."""
        return await self.persistent.generate_audio_overview_script(source_id)
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        return self.conversation_history[-limit:]
    
    def add_action(self, action: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> None:
        """
        Record an action and its result
        
        Args:
            action: The action taken (tool call) or action dict with result
            result: The result of the action (optional if included in action)
        """
        if result is None and isinstance(action, dict) and "result" in action:
            act = action.get("action", {k: v for k, v in action.items() if k != "result"})
            res = action.get("result", {})
            entry = {
                "action": act,
                "result": res,
                "timestamp": action.get("timestamp", datetime.now().isoformat())
            }
        else:
            entry = {
                "action": action,
                "result": result or {},
                "timestamp": datetime.now().isoformat()
            }
        
        self.action_history.append(entry)
        
        # Trim if too long
        if len(self.action_history) > self.max_history_length:
            self.action_history = self.action_history[-self.max_history_length:]
    
    def get_action_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent action history"""
        return self.action_history[-limit:]
    
    def get_recent_actions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent actions (alias for get_action_history)"""
        return self.get_action_history(limit=limit)

    def clear(self) -> None:
        """Clear all memory (alias for clear_all)"""
        self.clear_all()
    
    def set_current_task(self, task: Dict[str, Any]) -> None:
        """Set the current task being executed"""
        self.current_task = task
    
    def get_current_task(self) -> Optional[Dict[str, Any]]:
        """Get the current task"""
        return self.current_task
    
    def set_current_location(self, url: str, page_title: Optional[str] = None) -> None:
        """Set the current browser location"""
        self.current_website = url
        self.current_page = page_title
    
    def get_current_location(self) -> Dict[str, Optional[str]]:
        """Get the current browser location"""
        return {
            "website": self.current_website,
            "page": self.current_page,
            "url": self.current_website
        }
    
    def store_important_result(self, result: Dict[str, Any]) -> None:
        """Store an important result for later reference"""
        self.important_results.append({
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_important_results(self) -> List[Dict[str, Any]]:
        """Get all important results"""
        return self.important_results
    
    def clear_short_term(self) -> None:
        """Clear short-term memory (conversation and action history)"""
        self.conversation_history = []
        self.action_history = []
    
    def clear_all(self) -> None:
        """Clear all memory"""
        self.clear_short_term()
        self.current_task = None
        self.current_website = None
        self.current_page = None
        self.variables = {}
        self.important_results = []
    
    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current context
        
        Useful for providing context to the AI agent
        """
        return {
            "current_task": self.current_task,
            "current_location": self.get_current_location(),
            "recent_conversation": self.get_conversation_history(limit=5),
            "recent_actions": self.get_action_history(limit=10),
            "variables": self.variables,
            "important_results": self.important_results[-5:]  # Last 5
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Export entire memory state as dictionary"""
        return {
            "conversation_history": self.conversation_history,
            "action_history": self.action_history,
            "current_task": self.current_task,
            "current_website": self.current_website,
            "current_page": self.current_page,
            "variables": self.variables,
            "important_results": self.important_results
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """Create Memory instance from dictionary"""
        memory = cls()
        memory.conversation_history = data.get("conversation_history", [])
        memory.action_history = data.get("action_history", [])
        memory.current_task = data.get("current_task")
        memory.current_website = data.get("current_website")
        memory.current_page = data.get("current_page")
        memory.variables = data.get("variables", {})
        memory.important_results = data.get("important_results", [])
        return memory


# Example usage
if __name__ == "__main__":
    memory = Memory()
    
    # Store conversation
    memory.add_conversation("user", "Open WhatsApp Web and reply to Rahul")
    memory.add_conversation("assistant", "Opening WhatsApp Web...")
    
    # Store task
    memory.set_current_task({
        "goal": "Send message to Rahul",
        "platform": "WhatsApp Web",
        "contact": "Rahul",
        "message": "I'll call you after 6 PM"
    })
    
    # Store actions
    memory.add_action(
        {"tool": "browser.open", "params": {"url": "https://web.whatsapp.com"}},
        {"success": True, "title": "WhatsApp Web"}
    )
    
    # Store variable
    memory.store("contact_name", "Rahul")
    
    # Get context summary
    context = memory.get_context_summary()
    print("Current Context:")
    print(f"Task: {context['current_task']}")
    print(f"Location: {context['current_location']}")
    print(f"Recent actions: {len(context['recent_actions'])}")
