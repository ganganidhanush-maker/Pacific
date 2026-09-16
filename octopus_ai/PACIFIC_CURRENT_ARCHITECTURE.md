# Pacific / Octopus AI — Computer Use Integration Architecture
**Document Version:** 1.0.0  
**Date:** 2026-09-16  
**Status:** Approved for Implementation

---

## Executive Summary

Pacific / Octopus AI is evolving from a multi-agent educational and productivity system into an autonomous Windows computer-use platform. This document defines the architectural integration of two external computer-use engines:
1. **Windows-Use (`Jeomon/Windows-Use`)**: Primary deterministic low-level Windows execution engine (UI Automation tree, mouse/keyboard actuation, application lifecycle, PowerShell shell, file manipulation, virtual desktops).
2. **Clacky (`Raynan00/clacky`)**: High-level desktop companion layer (screen coordinate normalization, element pointing/highlighting overlays, voice-first action routing, routine skill learning, and global ESC hotkey watchdog).

The central reasoning brain remains **Kiwi (Kimi K3) / Groq Llama 3**, coordinated by the **MasterOrchestrator**. The new **ComputerAgent** acts as the unified facade in Pacific, using a **ComputerUseRouter** to dispatch low-level and companion tasks through isolated adapters.

---

## 1. Pacific's Current Architecture

### 1.1 Core Components
- **`MasterOrchestrator` (`octopus_ai/agent/orchestrator.py`)**:
  - Central dispatcher that accepts natural language requests.
  - Decomposes goals into structured execution plans across specialized subagents.
  - Synthesizes execution results into spoken summaries for the Avatar.
- **Subagents (`octopus_ai/agent/subagents/`)**:
  - `web_agent.py`: Selenium-driven automation (WhatsApp Web, Canva, Instagram, Google Search) with persistent profiles.
  - `desktop_agent.py`: Basic local file search, text inspection, file creation.
  - `research_agent.py`: Academic and web topic research, slide outlines.
  - `chatbot_agent.py`: General contextual conversation.
- **Reasoning Engines (`octopus_ai/agent/`)**:
  - `kimi_llm.py`: Deep reasoning, planning, multi-step problem solving via Kimi K3 / Moonshot.
  - `groq_llm.py`: Ultra-low latency tool routing, classification, intent extraction via Llama 3 on Groq.
  - `server/local_llm_service.py`: Local LLM / API proxy with memory management.
- **Interface & Audio/Video Layer (`server/`, `orb-ui.html`)**:
  - FastAPI server (`server/app.py`) providing REST endpoints and WebSocket events.
  - Chatterbox engine (`server/chatterbox_service.py`) for neural STT and TTS.
  - Studio Video Avatar system with seamless state transitions (`idle.mp4`, `speaking.mp4`, `thinking.mp4`).

### 1.2 Current Limitations in Desktop Control
- Existing `DesktopAgent` is limited to basic Python file I/O and shell execution.
- No direct Windows UI Automation (UIA) tree inspection.
- No awareness of running desktop applications (e.g. VS Code, Excel, File Explorer, Notepad).
- No deterministic mouse/keyboard control with coordinate or UI element grounding.
- No screen highlight or pointing companion capabilities.
- No hardware-level emergency stop (ESC listener).

---

## 2. Clacky Architecture Analysis

### 2.1 Key Modules & Capabilities
- **`clacky/agent/computer_loop.py`**: State machine executing observe-plan-act cycles.
- **`clacky/shell/screen/capture.py`**: Multi-monitor screen capture, DPI scaling calculations, coordinate normalization (`[0, 1]` to actual pixel resolution).
- **`clacky/shell/hotkey.py`**: Low-level Windows keyboard hook (`SetWindowsHookEx` or `GetAsyncKeyState`) listening for `VK_ESCAPE` to trigger immediate emergency cancellation.
- **Element Pointing & Highlights**: Generates pointing events (`x`, `y`, `label`, `duration`, `pulse`) so the user visually sees what the AI is referencing on screen without stealing cursor control.
- **Skills & Routine Learning (`clacky/shell/skills/`, `routing.py`)**: Ability to record, store, and replay parameterized sequences of actions.

### 2.2 Clacky Strengths & Weaknesses
- **Strengths**: User companion feel, visual cursor/pulse feedback, emergency stop hotkey, DPI-aware coordinate mapping.
- **Weaknesses**: Relies heavily on vision-only screenshot analysis for actuation, which increases latency and API token cost.

---

## 3. Windows-Use Architecture Analysis

### 3.1 Key Modules & Capabilities
- **`windows_use/uia/`**:
  - Direct integration with Windows COM UI Automation (`IUIAutomation`, `comtypes`).
  - Fast accessibility tree traversal extracting control types, names, automation IDs, bounding rectangles, and patterns (Invoke, Value, Selection).
  - Enables element location without calling vision models.
- **`windows_use/agent/desktop/service.py`**:
  - Direct Windows API integration via `pywin32` (`win32gui`, `win32process`, `win32con`) and `ctypes`.
  - Window management: find window by title/class, activate window, minimize/maximize/restore, move/resize.
  - Mouse & Keyboard: `mouse_event`, `keybd_event`, SendInput with precise scancodes.
- **`windows_use/agent/tools/service.py`**:
  - `app_tool`: Launch, switch, and terminate Windows applications.
  - `click_tool`, `type_tool`, `move_tool`, `scroll_tool`, `shortcut_tool`: Precise desktop actuation.
  - `shell_tool`: PowerShell execution with strict timeout and output size limits.
  - `file_tool`: Local Windows filesystem manipulation.
  - `scrape_tool`: Scrape text from accessibility tree nodes.
- **`windows_use/vdm/`**:
  - Virtual Desktop Manager interfacing with `IVirtualDesktopManager` to switch and isolate desktop workspaces.

### 3.2 Windows-Use Strengths & Weaknesses
- **Strengths**: Native Windows UIA integration (fast, robust, low-cost), comprehensive OS tools, zero dependency on vision for standard UI elements.
- **Weaknesses**: Headless execution can confuse users if there is no visual feedback; lacks natural companion pointing or routine learning layer.

---

## 4. Architectural Comparison & Integration Decisions

| Capability / Feature | Pacific Current | Clacky | Windows-Use | Pacific Integration Decision |
| :--- | :--- | :--- | :--- | :--- |
| **Reasoning & Planning** | Kiwi / Groq LLM | Custom Planner | LLM prompt loop | **REUSE PACIFIC**: Kiwi/Groq remains the sole reasoning brain. |
| **Orchestration** | MasterOrchestrator | Monolithic loop | Monolithic loop | **REUSE PACIFIC**: Orchestrator delegates to new `ComputerAgent`. |
| **Accessibility Tree (UIA)** | None | Minimal | Native COM (`comtypes`, `uia`) | **ADAPT & WRAP WINDOWS-USE**: Primary method for UI element location. |
| **App Management** | None | Limited | Full (`win32process`, UIA) | **ADAPT & WRAP WINDOWS-USE**: Launch, focus, and close desktop apps. |
| **Mouse / Keyboard Control**| None | PyAutoGUI | Direct Win32 `SendInput` | **ADAPT & WRAP WINDOWS-USE**: Low-level Win32 actuation. |
| **PowerShell / Shell** | Python subprocess | Basic shell | PowerShell with output limit | **ADAPT & WRAP WINDOWS-USE**: Safe bounded PowerShell execution. |
| **Screen Pointing Overlay** | None | Coordinate pulse overlay | None | **ADAPT & WRAP CLACKY**: Visual element highlighting in Pacific UI. |
| **Coordinate Normalization**| None | Multi-monitor DPI aware | Window-relative | **WRAP CLACKY**: DPI-aware normalization for visual targeting. |
| **Emergency Stop (ESC)** | None | Win32 Hook `VK_ESCAPE` | None | **ADAPT CLACKY**: Global Watchdog thread intercepting ESC immediately. |
| **Routines / Skill Learning**| None | Skill recorder & replay | None | **ADAPT CLACKY**: Record and replay repeatable desktop macros. |
| **Virtual Desktops** | None | None | `IVirtualDesktopManager` | **WRAP WINDOWS-USE**: Support multi-workspace desktop operations. |
| **Voice & Avatar Interface** | Chatterbox + Video | None | None | **REUSE PACIFIC**: Maintain 1080p Studio Video & neural voice. |
| **Browser Engine** | Selenium (persistent) | Vision browser | None | **REUSE PACIFIC**: Keep existing Selenium web agent for web tasks. |

---

## 5. Unified Pacific Computer Use Engine

### 5.1 Directory Structure
```
octopus_ai/
    computer_use/
        __init__.py                  # Public exports & module alias
        computer_agent.py            # Unified Pacific Computer Agent
        router.py                    # Intelligent tool dispatcher
        policy.py                    # Safety policy engine (SAFE, CONFIRM, HIGH_RISK)
        state.py                     # Computer state & observation model
        events.py                    # Real-time event bus (actuation, observation, abort)
        watchdog.py                  # Global ESC hotkey & emergency abort listener
        adapters/
            __init__.py
            windows_use_adapter.py   # Windows-Use execution adapter (UIA, Win32, Shell, App)
            clacky_adapter.py        # Clacky companion adapter (Pointing, Screen, Routines)
        bridge/
            __init__.py
            protocol.py              # IPC message format between backend and desktop
            client.py                # Local bridge client for FastAPI
            server.py                # Local desktop daemon with win32 token
```

### 5.2 The Unified Execution Flow
1. **User Request**: User asks Pacific to perform an action (e.g., *"Open Notepad, write meeting notes, and save to Desktop"*).
2. **MasterOrchestrator**: Identifies intent requiring `AgentType.COMPUTER` and dispatches task to `ComputerAgent`.
3. **ComputerAgent Observe Phase**:
   - Query `WindowsUseAdapter` for the active window and UI Automation tree.
   - If UIA elements are found, element IDs and bounding boxes are extracted directly without vision model overhead.
   - If target is graphical or non-standard, fallback to screen capture via `ClackyAdapter`.
4. **Policy Check**:
   - `ComputerPolicyEngine` evaluates the proposed action.
   - `SAFE`: Non-destructive (read UIA, click button, switch app, move mouse) -> executes immediately.
   - `CONFIRM`: File overwrite, PowerShell script execution, system settings -> requests user approval.
   - `HIGH_RISK`: Registry edit, disk format, credential access -> blocked unless autonomous dev mode with explicit override.
5. **Actuate & Visual Feedback**:
   - `WindowsUseAdapter` issues Win32 `SendInput` or UIA Invoke.
   - `ClackyAdapter` fires visual pointing event to Pacific UI overlay to indicate active focus.
6. **Verify Phase**:
   - Re-inspect UIA tree or verify filesystem state.
   - Verify that Notepad was launched, text matches, and file exists on disk.
7. **Complete & Synthesize**:
   - Return structured result to `MasterOrchestrator`.
   - Avatar speaks natural confirmation via Chatterbox TTS.

---

## 6. Safety, Security, and Emergency Abort

1. **Global ESC Watchdog (`watchdog.py`)**:
   - Background daemon monitoring Windows `GetAsyncKeyState(VK_ESCAPE)` or global low-level hook.
   - Pressing `ESC` sets an atomic cancellation token across all running computer tasks within 50ms.
   - Audio chime and UI alert inform the user that desktop control was immediately halted.
2. **Command Sandboxing**:
   - PowerShell commands are executed with non-elevated user permissions.
   - Dangerous commands (`rmdir /s /q C:\`, `Format-Volume`, `Invoke-WebRequest -OutFile ...exe`) trigger immediate `CONFIRM` or rejection.
3. **Observation Verification**:
   - Pacific never assumes an action succeeded without state verification (`Observe -> Think -> Act -> Verify`).

---

## 7. Hardware, OS Dependencies, and Fallback Strategy

- **Target OS**: Windows 10 / Windows 11 (64-bit).
- **Core Windows Libraries**: `pywin32` (`win32gui`, `win32process`, `win32con`), `comtypes` (UIA COM interface), `ctypes`.
- **Graceful Non-Windows Fallback**:
  - In Linux/Docker or CI test environments, Windows-specific modules are conditionally imported.
  - A mock adapter provides headless verification to prevent runtime crashes.
