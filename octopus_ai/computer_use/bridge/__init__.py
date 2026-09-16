"""
Pacific / Octopus AI — Computer Use Bridge
Exports bridge client, protocol, and server.
"""

from .protocol import BridgeRequest, BridgeResponse, BridgeMessageType
from .client import ComputerBridgeClient, bridge_client
from .server import ComputerBridgeServer

__all__ = [
    "BridgeRequest",
    "BridgeResponse",
    "BridgeMessageType",
    "ComputerBridgeClient",
    "bridge_client",
    "ComputerBridgeServer",
]
