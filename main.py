#!/usr/bin/env python3
"""
Pacific / Octopus AI - Root Entry Point
Allows any user who forks and clones the repository to run 'python main.py' directly.
"""

import os
import sys
from pathlib import Path

# Add repository root and octopus_ai package to sys.path
root_dir = Path(__file__).resolve().parent
pkg_dir = root_dir / "octopus_ai"

for p in [str(root_dir), str(pkg_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        from octopus_ai.main import run_demo
        run_demo()
    else:
        from octopus_ai.main import main
        initial_agent = "main"
        if "--agent" in sys.argv:
            idx = sys.argv.index("--agent")
            if idx + 1 < len(sys.argv):
                initial_agent = sys.argv[idx + 1].strip().lower()
        main(initial_agent=initial_agent)
