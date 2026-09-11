"""
Octopus Safety/Permission Layer - Control System

Before executing potentially dangerous actions, the safety layer checks permissions.

Permission Levels:
- READ → automatic
- SEARCH → automatic
- CLICK → automatic
- TYPE → automatic
- SEND MESSAGE → optional confirmation
- DELETE → confirmation required
- PURCHASE → confirmation required
- POST PUBLICLY → confirmation required
"""

from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class PermissionLevel(Enum):
    """Different levels of action permissions"""
    
    AUTOMATIC = "automatic"           # No confirmation needed
    OPTIONAL = "optional"             # Can be configured either way
    CONFIRMATION_REQUIRED = "confirmation_required"  # Always requires confirmation
    BLOCKED = "blocked"               # Never allowed


class ActionCategory(Enum):
    """Categories of browser actions"""
    
    READ = "read"                     # Reading page content
    NAVIGATE = "navigate"             # Opening URLs, back, forward
    INTERACT = "interact"             # Clicking, scrolling
    INPUT = "input"                   # Typing text
    COMMUNICATE = "communicate"       # Sending messages, emails
    MODIFY = "modify"                 # Changing data, deleting
    TRANSACTION = "transaction"       # Purchases, payments
    PUBLISH = "publish"               # Posting publicly
    AUTHENTICATION = "authentication" # Login/logout actions


class SafetyLayer:
    """
    Safety and permission system for Octopus
    
    Controls which actions the AI Agent can perform automatically
    and which require user confirmation
    """
    
    def __init__(self):
        # Default permission levels for each action category
        self.default_permissions = {
            ActionCategory.READ: PermissionLevel.AUTOMATIC,
            ActionCategory.NAVIGATE: PermissionLevel.AUTOMATIC,
            ActionCategory.INTERACT: PermissionLevel.AUTOMATIC,
            ActionCategory.INPUT: PermissionLevel.AUTOMATIC,
            ActionCategory.COMMUNICATE: PermissionLevel.OPTIONAL,
            ActionCategory.MODIFY: PermissionLevel.CONFIRMATION_REQUIRED,
            ActionCategory.TRANSACTION: PermissionLevel.CONFIRMATION_REQUIRED,
            ActionCategory.PUBLISH: PermissionLevel.CONFIRMATION_REQUIRED,
            ActionCategory.AUTHENTICATION: PermissionLevel.OPTIONAL,
        }
        
        # Custom rules for specific websites
        self.website_rules: Dict[str, Dict[ActionCategory, PermissionLevel]] = {}
        
        # Custom rules for specific tools
        self.tool_rules: Dict[str, PermissionLevel] = {}
        
        # Confirmation callback (set by application)
        self.confirmation_callback: Optional[Callable[[Dict[str, Any]], bool]] = None
        
        # Blocked domains
        self.blocked_domains: List[str] = []
        
        # Allowed domains (if set, only these are allowed)
        self.allowed_domains: Optional[List[str]] = None
    
    def configure_permission(self, category: ActionCategory, level: PermissionLevel) -> None:
        """Configure permission level for an action category"""
        self.default_permissions[category] = level
    
    def add_website_rule(self, domain: str, category: ActionCategory, level: PermissionLevel) -> None:
        """Add a custom rule for a specific website"""
        if domain not in self.website_rules:
            self.website_rules[domain] = {}
        self.website_rules[domain][category] = level
    
    def add_tool_rule(self, tool_name: str, level: PermissionLevel) -> None:
        """Add a custom rule for a specific tool"""
        self.tool_rules[tool_name] = level
    
    def add_blocked_domain(self, domain: str) -> None:
        """Add a blocked domain"""
        if domain not in self.blocked_domains:
            self.blocked_domains.append(domain)
    
    def set_allowed_domains(self, domains: List[str]) -> None:
        """Set list of allowed domains (whitelist mode)"""
        self.allowed_domains = domains
    
    def set_confirmation_callback(self, callback: Callable[[Dict[str, Any]], bool]) -> None:
        """
        Set callback function for confirmation requests
        
        Callback should return True to proceed, False to cancel
        Receives dict with action details
        """
        self.confirmation_callback = callback
    
    def categorize_tool(self, tool_name: str) -> ActionCategory:
        """Map tool names to action categories"""
        tool_to_category = {
            "browser.open": ActionCategory.NAVIGATE,
            "browser.back": ActionCategory.NAVIGATE,
            "browser.refresh": ActionCategory.NAVIGATE,
            "browser.read": ActionCategory.READ,
            "browser.find": ActionCategory.READ,
            "browser.click": ActionCategory.INTERACT,
            "browser.scroll": ActionCategory.INTERACT,
            "browser.type": ActionCategory.INPUT,
            "browser.wait": ActionCategory.INTERACT,
            "browser.screenshot": ActionCategory.READ,
        }
        
        return tool_to_category.get(tool_name, ActionCategory.INTERACT)
    
    def check_domain_allowed(self, url: str) -> bool:
        """Check if a URL's domain is allowed"""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Check blocked domains
        for blocked in self.blocked_domains:
            if blocked in domain:
                return False
        
        # Check allowed domains (whitelist mode)
        if self.allowed_domains:
            for allowed in self.allowed_domains:
                if allowed in domain:
                    return True
            return False
        
        return True
    
    def get_permission_level(self, tool_name: str, url: Optional[str] = None) -> PermissionLevel:
        """
        Get the permission level for a specific tool
        
        Checks in order:
        1. Tool-specific rules
        2. Website-specific rules
        3. Category default rules
        """
        # Check tool-specific rules first
        if tool_name in self.tool_rules:
            return self.tool_rules[tool_name]
        
        # Get action category
        category = self.categorize_tool(tool_name)
        
        # Check website-specific rules
        if url:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            
            for rule_domain, rules in self.website_rules.items():
                if rule_domain in domain and category in rules:
                    return rules[category]
        
        # Return default for category
        return self.default_permissions.get(category, PermissionLevel.AUTOMATIC)
    
    def check_permission(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if an action is allowed
        
        Args:
            action: Dict containing:
                - tool: Tool name
                - params: Tool parameters
                - url: Current URL (optional)
        
        Returns:
            Dict with:
                - allowed: bool
                - requires_confirmation: bool
                - reason: str (if blocked)
        """
        tool_name = action.get("tool", "")
        params = action.get("params", {})
        url = params.get("url") or action.get("url", None)
        
        # Check domain restrictions
        if url and not self.check_domain_allowed(url):
            return {
                "allowed": False,
                "requires_confirmation": False,
                "reason": f"Domain not allowed: {url}"
            }
        
        # Get permission level
        permission_level = self.get_permission_level(tool_name, url)
        
        # Determine if allowed
        if permission_level == PermissionLevel.BLOCKED:
            return {
                "allowed": False,
                "requires_confirmation": False,
                "reason": f"Action blocked: {tool_name}"
            }
        
        if permission_level == PermissionLevel.AUTOMATIC:
            return {
                "allowed": True,
                "requires_confirmation": False,
                "reason": "Automatic action"
            }
        
        if permission_level == PermissionLevel.CONFIRMATION_REQUIRED:
            # If confirmation callback is set, use it
            if self.confirmation_callback:
                confirmed = self.confirmation_callback(action)
                return {
                    "allowed": confirmed,
                    "requires_confirmation": True,
                    "reason": "Confirmation required" if not confirmed else "Confirmed by user"
                }
            else:
                # No callback means we can't confirm, so block
                return {
                    "allowed": False,
                    "requires_confirmation": True,
                    "reason": "Confirmation required but no callback configured"
                }
        
        # OPTIONAL - treat as automatic unless configured otherwise
        return {
            "allowed": True,
            "requires_confirmation": False,
            "reason": "Optional action (auto-approved)"
        }
    
    def get_safety_report(self) -> Dict[str, Any]:
        """Get a report of current safety configuration"""
        return {
            "default_permissions": {
                cat.value: perm.value 
                for cat, perm in self.default_permissions.items()
            },
            "website_rules": {
                domain: {cat.value: perm.value for cat, perm in rules.items()}
                for domain, rules in self.website_rules.items()
            },
            "tool_rules": {
                tool: perm.value 
                for tool, perm in self.tool_rules.items()
            },
            "blocked_domains": self.blocked_domains,
            "allowed_domains": self.allowed_domains,
            "has_confirmation_callback": self.confirmation_callback is not None
        }


# Example usage
if __name__ == "__main__":
    safety = SafetyLayer()
    
    # Configure some custom rules
    safety.configure_permission(ActionCategory.COMMUNICATE, PermissionLevel.CONFIRMATION_REQUIRED)
    safety.add_blocked_domain("gambling-site.com")
    
    # Test permission checks
    test_actions = [
        {"tool": "browser.open", "params": {"url": "https://web.whatsapp.com"}},
        {"tool": "browser.click", "params": {"selector": "#send-button"}},
        {"tool": "browser.type", "params": {"text": "Hello"}},
        {"tool": "browser.open", "params": {"url": "https://gambling-site.com"}},
    ]
    
    print("Safety Permission Checks:")
    for action in test_actions:
        result = safety.check_permission(action)
        print(f"\n{action['tool']}:")
        print(f"  Allowed: {result['allowed']}")
        print(f"  Requires Confirmation: {result['requires_confirmation']}")
        print(f"  Reason: {result['reason']}")
    
    # Print safety report
    print("\n\nSafety Report:")
    report = safety.get_safety_report()
    for key, value in report.items():
        print(f"{key}: {value}")
