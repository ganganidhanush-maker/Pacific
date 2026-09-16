# Pacific / Octopus AI — Computer Use Guide

Autonomous Windows 11 desktop control combining deterministic low-level actuation (**Windows-Use**) and visual desktop companion capabilities (**Clacky**).

---

## 1. Overview

Pacific's Computer Use layer transforms natural language goals into real-world Windows 11 actions without breaking existing web, research, voice, or video avatar workflows.

```
                  +-----------------------------------+
                  |   Kiwi (Kimi K3) / Groq Llama 3   |
                  |         (Reasoning Brain)         |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------------------------+
                  |         MasterOrchestrator        |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------------------------+
                  |           ComputerAgent           |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------------------------+
                  |         ComputerUseRouter         |
                  |     (Safety Policy + Watchdog)    |
                  +--------+-----------------+--------+
                           |                 |
                           v                 v
            +--------------------+     +--------------------+
            | WindowsUseAdapter  |     |   ClackyAdapter    |
            | (UIA, Win32, App,  |     | (Pointing Overlay, |
            |  PowerShell, File) |     |  DPI Coords, Macro)|
            +--------------------+     +--------------------+
```

---

## 2. Key Capabilities

1. **Native UI Automation (UIA)**:
   - Traverses the live Windows COM accessibility tree (`UIAutomationCore.dll`).
   - Identifies buttons, edit boxes, list items, and windows by name, type, and bounding rectangle without calling expensive vision models.
2. **Deterministic Mouse & Keyboard Actuation**:
   - Win32 `SendInput` and `mouse_event` for accurate clicks, drags, text typing, and keyboard shortcuts (`ctrl+s`, `alt+f4`, `win+r`).
3. **Application Lifecycle**:
   - Launch, focus, minimize, and close desktop applications (Notepad, Calculator, VS Code, File Explorer).
4. **Visual Companion Pointing (Clacky Overlay)**:
   - Emits visual pulse rings and highlight overlays at element coordinates (`#clackyOverlay`) without stealing cursor focus.
5. **Emergency Stop (Watchdog)**:
   - Pressing **`ESC`** on the hardware keyboard or clicking **`STOP ESC`** in the UI halts all computer operations within 50ms.
6. **Safety Policy Engine**:
   - **SAFE**: Instant execution (reads, clicks, text typing, app switching).
   - **CONFIRM**: Prompts user before destructive actions (file deletion, external scripts).
   - **HIGH_RISK**: Destructive system operations (formatting disks, registry manipulation, system directory deletion) are blocked by default.

---

## 3. How to Use

### A. Via Desktop UI (`orb-ui.html`)
1. Click the **9-Dots menu** in the top right and select **🖥️ Computer Use** (or simply type naturally in the Main Agent).
2. Enter your goal:
   - *"Open Notepad and write meeting notes"*
   - *"Show me system resource usage using PowerShell"*
   - *"Highlight the center of the screen"*
3. The Studio Video Avatar will speak the confirmation aloud, and the action will execute on your desktop.
4. **Emergency Stop**: Press **`ESC`** on your keyboard at any time or click the red **`STOP ESC`** button in the top left.

### B. Python API
```python
import asyncio
from computer_use import computer_agent_instance

async def main():
    # 1. Autonomous multi-step task
    result = await computer_agent_instance.run_task("Open Notepad and write hello world")
    print("Success:", result["success"])
    print("Spoken summary:", result["spoken_summary"])

    # 2. Atomic tool execution
    action_res = computer_agent_instance.execute_action(
        tool="powershell",
        params={"command": "Get-Process | Select-Object -First 3 ProcessName, CPU"}
    )
    print("Output:", action_res.output)

asyncio.run(main())
```

### C. REST API Endpoints
- `POST /api/computer/execute`:
  ```json
  { "task": "Open Notepad and type notes" }
  ```
  or atomic tool:
  ```json
  { "tool": "click", "params": { "x": 500, "y": 300 } }
  ```
- `GET /api/computer/observe`: Live snapshot of active window, open windows, and accessibility tree nodes.
- `GET /api/computer/status`: Active task, emergency abort state, and execution history.
- `POST /api/computer/stop`: Emergency stop aborting all running actions.
- `POST /api/computer/reset`: Reset abort state.
- `GET /api/computer/events`: Server-Sent Events (SSE) streaming real-time pointing and status updates.

---

## 4. Verification & Testing

Run the automated test suite anytime:
```powershell
.venv\Scripts\python.exe -m unittest tests/test_computer_use.py
```
