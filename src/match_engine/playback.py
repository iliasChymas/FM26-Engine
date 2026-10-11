"""Replay boundary shaped by the observed native playback exports."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Sequence
import json
from pathlib import Path
from typing import Any

from .native import (
    NativeMatchEvent,
    NativeStopTimeInfo,
    TIME_SLICES_PER_SECOND,
    seconds_from_time_slice,
    time_slice_from_seconds,
)


@dataclass(frozen=True)
class PlaybackUpdate:
    previous_second: int
    current_second: int
    events: tuple[dict[str, Any], ...]


class NativeEventQueue:
    """Client-side mirror of ``Match.UpdateMatchEvents``.

    The managed client requests a two-element native event update buffer.  The
    native return value is the authoritative event-count cursor: records before
    that cursor are retained, records after it are replaced by the update.
    This class intentionally does not generate events or assign semantics to
    commentary IDs; it only reproduces the observed queue contract.
    """

    REQUEST_CAPACITY = 2

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._cursor = 0
        self._current_first_event_index = 0
        self._current_last_event_index = 0

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._events)

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def current_first_event_index(self) -> int:
        """Managed ``Match.CurrentFirstEventIndex`` mirror."""
        return self._current_first_event_index

    @property
    def current_last_event_index(self) -> int:
        """Managed ``m_currentLastEventIndex`` mirror."""
        return self._current_last_event_index

    def apply_update(
        self, returned_count: int, records: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        count = int(returned_count)
        if count < 0:
            raise ValueError("native event count cannot be negative")
        if count > self.REQUEST_CAPACITY:
            raise ValueError("native event update exceeds the observed two-record buffer")
        if len(records) < count:
            raise ValueError("native event update is shorter than its returned count")
        # UpdateMatchEvents removes the old suffix at the returned cursor and
        # then appends the newly returned records.
        self._events[count:] = list(records[:count])
        self._cursor = count
        # The recovered managed body advances both event-index fields to the
        # greater of the previous last index and the returned native count.
        latest_index = max(self._current_last_event_index, count)
        self._current_last_event_index = latest_index
        self._current_first_event_index = latest_index
        return self.events

    def apply_native_update(
        self,
        returned_count: int,
        records: Sequence[NativeMatchEvent],
    ) -> tuple[dict[str, Any], ...]:
        """Apply decoded wire records without interpreting their fields.

        ``NativeMatchEvent.as_dict`` is intentionally a lossless field view;
        this helper only bridges that view into the queue and does not infer
        event types, players, probabilities, or commentary meaning.
        """
        return self.apply_update(
            returned_count,
            [record.as_dict() for record in records],
        )


class NativeStopTimeQueue:
    """Mirror of the managed ``UpdateStopTimeInfos`` list update.

    The recovered body requests native stop-time records, removes the managed
    suffix beginning at the returned cursor, appends the returned records and
    advances ``m_currentStopTimeInfoIndex`` to the larger cursor.  It does not
    reveal a stop-time decision algorithm, so this class is transport/state
    plumbing only.
    """

    def __init__(self) -> None:
        self._infos: list[dict[str, Any]] = []
        self._current_index = 0

    @property
    def infos(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._infos)

    @property
    def current_index(self) -> int:
        return self._current_index

    def apply_update(
        self,
        returned_count: int,
        records: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    ) -> tuple[dict[str, Any], ...]:
        count = int(returned_count)
        if count < 0:
            raise ValueError("native stop-time count cannot be negative")
        if len(records) < count:
            raise ValueError("native stop-time update is shorter than its returned count")
        self._infos[count:] = list(records[:count])
        self._current_index = max(self._current_index, count)
        return self.infos

    def apply_native_update(
        self,
        returned_count: int,
        records: Sequence[NativeStopTimeInfo],
    ) -> tuple[dict[str, Any], ...]:
        return self.apply_update(
            returned_count,
            [record.as_dict() for record in records],
        )


class NativeMatchDriver:
    """Small adapter for the recovered native tick/event boundary.

    ``tick`` must implement the shipped ``Tick(float)`` call. ``request_events``
    receives the observed two-record capacity and returns the native count plus
    the records copied from that buffer. No simulation probabilities or event
    meanings are introduced here; this is the seam where a captured native
    trace or a future compatible implementation can be plugged in.
    """

    def __init__(
        self,
        tick: Callable[[float], Any],
        request_events: Callable[
            [int], tuple[int, Sequence[dict[str, Any] | NativeMatchEvent]]
        ],
    ) -> None:
        self._tick = tick
        self._request_events = request_events
        self.events = NativeEventQueue()
        self.last_state: Any = None

    def tick_frame(self, delta_seconds: float, speed: float = 1.0) -> Any:
        if delta_seconds < 0 or speed < 0:
            raise ValueError("delta_seconds and speed must be non-negative")
        self.last_state = self._tick(delta_seconds * speed)
        count, records = self._request_events(NativeEventQueue.REQUEST_CAPACITY)
        native_records = tuple(
            isinstance(record, NativeMatchEvent) for record in records
        )
        if any(native_records) and not all(native_records):
            raise TypeError("native event update cannot mix wire records and dictionaries")
        if all(native_records):
            self.events.apply_native_update(count, records)  # type: ignore[arg-type]
        else:
            self.events.apply_update(count, records)  # type: ignore[arg-type]
        return self.last_state


class JsonNativeTrace:
    """Trace-backed provider for the recovered native playback seam.

    The trace format is intentionally lossless and small::

        {"frames": [{"delta_seconds": 0.25,
                     "state": {...},
                     "events": [{...}],
                     "stop_time_infos": [{...}]}]}

    ``state`` and event dictionaries are returned unchanged.  A trace is a
    captured native observation, not a substitute for the protected match
    evaluator; this class never translates commentary IDs or derives tactics.
    It is useful for CLI/client regression tests once a runtime capture exists.
    """

    def __init__(self, frames: Sequence[dict[str, Any]]) -> None:
        if not frames:
            raise ValueError("native trace must contain at least one frame")
        self._frames = tuple(dict(frame) for frame in frames)
        self._index = 0

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "JsonNativeTrace":
        frames = value.get("frames")
        if not isinstance(frames, list):
            raise ValueError("native trace frames must be a JSON array")
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict):
                raise ValueError(f"native trace frames[{index}] must be an object")
            events = frame.get("events", [])
            if not isinstance(events, list) or not all(isinstance(item, dict) for item in events):
                raise ValueError(f"native trace frames[{index}].events must be object array")
        return cls(frames)

    @classmethod
    def from_path(cls, path: str | Path) -> "JsonNativeTrace":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("native trace root must be a JSON object")
        return cls.from_mapping(value)

    @property
    def finished(self) -> bool:
        return self._index >= len(self._frames)

    def tick(self, _delta_seconds: float) -> dict[str, Any]:
        frame = self._frames[min(self._index, len(self._frames) - 1)]
        self._index += 1
        state = frame.get("state", {})
        if not isinstance(state, dict):
            raise ValueError("native trace frame.state must be an object")
        return dict(state)

    def request_events(self, capacity: int) -> tuple[int, tuple[dict[str, Any], ...]]:
        frame = self._frames[max(0, min(self._index - 1, len(self._frames) - 1))]
        events = frame.get("events", [])
        if not isinstance(events, list):
            raise ValueError("native trace frame.events must be an array")
        records = tuple(dict(item) for item in events[:capacity])
        return len(records), records

    def driver(self) -> NativeMatchDriver:
        return NativeMatchDriver(self.tick, self.request_events)

    def replay(self) -> tuple[dict[str, Any], ...]:
        """Return the captured frames without interpreting their fields."""
        return tuple({
            "state": dict(frame.get("state", {})),
            "events": [dict(item) for item in frame.get("events", [])],
            "stop_time_infos": [dict(item) for item in frame.get("stop_time_infos", [])],
        } for frame in self._frames)


class MatchPlayback:
    def __init__(self, result: dict[str, Any]):
        self._duration = int(result["duration"])
        self._events = tuple(sorted(result["events"], key=self._event_second))
        self._highlights = tuple(sorted(
            ((int(item["start"]), int(item["end"])) for item in result["highlights"]),
            key=lambda window: window[0],
        ))
        self._second = 0

    def tick(self, delta_seconds: float, speed: float = 1.0) -> PlaybackUpdate:
        """Advance using the managed client's native ``Tick(float)`` contract.

        The caller supplies Unity's frame delta; playback speed multiplies it
        before the native call.  Public event timestamps are four slices per
        second, so the exposed integer position is rounded down at the same
        boundary used by the playback adapter.
        """
        if delta_seconds < 0 or speed < 0:
            raise ValueError("delta_seconds and speed must be non-negative")
        target_slice = self.current_time_slice + int(
            delta_seconds * speed * TIME_SLICES_PER_SECOND
        )
        return self.seek_time_slice(target_slice)

    @staticmethod
    def _event_second(event: dict[str, Any]) -> int:
        """Read prototype seconds or the recovered native time-slice field."""
        if "second" in event:
            return int(event["second"])
        if "time_slice" in event:
            return int(seconds_from_time_slice(int(event["time_slice"])))
        raise KeyError("event requires second or time_slice")

    @property
    def current_second(self) -> int:
        return self._second

    @property
    def maximum_second(self) -> int:
        return self._duration

    @property
    def current_time_slice(self) -> int:
        return time_slice_from_seconds(self._second)

    @property
    def maximum_time_slice(self) -> int:
        return time_slice_from_seconds(self._duration)

    def seek(self, second: int) -> PlaybackUpdate:
        target = max(0, min(self._duration, int(second)))
        previous = self._second
        low, high = sorted((previous, target))
        events = tuple(
            event for event in self._events
            if low < self._event_second(event) <= high
        )
        self._second = target
        return PlaybackUpdate(previous, target, events)

    def seek_time_slice(self, time_slice: int) -> PlaybackUpdate:
        # Prototype events currently have whole-second timestamps, so a
        # sub-second native slice resolves to its containing second.
        return self.seek(int(seconds_from_time_slice(time_slice)))

    def request_event_update(self, since_second: int) -> tuple[dict[str, Any], ...]:
        start = max(0, int(since_second))
        return tuple(
            event for event in self._events
            if start < self._event_second(event) <= self._second
        )

    def next_highlight(self) -> tuple[int, int] | None:
        return next((window for window in self._highlights if window[0] > self._second), None)

    def previous_highlight(self) -> tuple[int, int] | None:
        return next((window for window in reversed(self._highlights) if window[1] < self._second), None)

    def skip_dead_time(self) -> PlaybackUpdate:
        next_event = next(
            (self._event_second(event) for event in self._events
             if self._event_second(event) > self._second),
            self._duration,
        )
        return self.seek(next_event)
