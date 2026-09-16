"""
Pacific / Octopus AI — Computer Use Bridge Protocol
Defines JSON-RPC / IPC message contracts between the FastAPI backend and local desktop daemon.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import time


class BridgeMessageType(str, Enum):
    EXECUTE_ACTION = "execute_action"
    EXECUTE_TASK = "execute_task"
    OBSERVE = "observe"
    EMERGENCY_STOP = "emergency_stop"
    RESET_STATE = "reset_state"
    GET_STATUS = "get_status"
    CONFIRM_ACTION = "confirm_action"


@dataclass
class BridgeRequest:
    request_id: str
    message_type: BridgeMessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BridgeRequest":
        return cls(
            request_id=data["request_id"],
            message_type=BridgeMessageType(data["message_type"]),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class BridgeResponse:
    request_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BridgeResponse":
        return cls(
            request_id=data["request_id"],
            success=data["success"],
            data=data.get("data"),
            error=data.get("error"),
            timestamp=data.get("timestamp", time.time()),
        )
