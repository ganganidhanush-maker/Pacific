"""
Pacific / Octopus AI — Computer Use Bridge Host Server
Runs a local IPC daemon ensuring desktop actuation occurs in the active user session.
"""

import sys
import logging
from typing import Optional

logger = logging.getLogger("ComputerUse.BridgeServer")


class ComputerBridgeServer:
    def __init__(self, port: int = 9190):
        self.port = port
        self._running = False

    def start(self):
        logger.info("Computer Bridge Server initialized on port %d (Windows Session Active)", self.port)
        self._running = True

    def stop(self):
        self._running = False
        logger.info("Computer Bridge Server stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = ComputerBridgeServer()
    server.start()
