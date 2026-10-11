"""Clean-room deterministic football simulation."""

from .engine import MatchEngine
from .model import EventType, MatchConfig, Tactics, Team
from .playback import (
    JsonNativeTrace, MatchPlayback, NativeEventQueue, NativeMatchDriver, NativeStopTimeQueue,
    PlaybackUpdate,
)
from .native import ManagedCommentaryEvent
from .managed import ManagedTeamInstruction, ManagedTacticalStyle

__all__ = [
    "EventType", "MatchEngine", "MatchConfig", "Tactics", "Team",
    "JsonNativeTrace", "MatchPlayback", "NativeEventQueue", "NativeMatchDriver", "NativeStopTimeQueue",
    "PlaybackUpdate",
    "ManagedCommentaryEvent",
    "ManagedTeamInstruction", "ManagedTacticalStyle",
]
