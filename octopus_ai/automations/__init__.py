"""
Octopus AI Automations Package

Exports:
- BaseAutomation, AutomationCategory, AutomationStatus, TaskStep, AutomationResult
- AutomationRegistry
- Pre-configured default registry with Web and Desktop automations
"""

from .base import (
    BaseAutomation,
    AutomationCategory,
    AutomationStatus,
    TaskStep,
    AutomationResult,
    AutomationRegistry
)
from .preview.preview_manager import PreviewManager
from .web.whatsapp import WhatsAppAutomation
from .web.instagram import InstagramAutomation
from .web.canva import CanvaAutomation
from .web.browser_task import BrowserTaskAutomation
from .desktop.system_task import SystemTaskAutomation


def create_default_registry(driver=None) -> AutomationRegistry:
    """Create and populate registry with all built-in automations."""
    registry = AutomationRegistry()
    preview = PreviewManager()
    if driver:
        preview.set_driver(driver)

    whatsapp = WhatsAppAutomation(driver=driver, preview_callback=preview.update_step)
    instagram = InstagramAutomation(driver=driver, preview_callback=preview.update_step)
    canva = CanvaAutomation(driver=driver, preview_callback=preview.update_step)
    browser_task = BrowserTaskAutomation(driver=driver, preview_callback=preview.update_step)
    system_task = SystemTaskAutomation(driver=driver, preview_callback=preview.update_step)

    registry.register(whatsapp)
    registry.register(instagram)
    registry.register(canva)
    registry.register(browser_task)
    registry.register(system_task)

    return registry


__all__ = [
    "BaseAutomation",
    "AutomationCategory",
    "AutomationStatus",
    "TaskStep",
    "AutomationResult",
    "AutomationRegistry",
    "PreviewManager",
    "WhatsAppAutomation",
    "InstagramAutomation",
    "CanvaAutomation",
    "BrowserTaskAutomation",
    "SystemTaskAutomation",
    "create_default_registry"
]
