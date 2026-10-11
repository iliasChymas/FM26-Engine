import unittest

from match_engine import (
    JsonNativeTrace, MatchConfig, MatchEngine, MatchPlayback, NativeEventQueue, NativeMatchDriver,
    NativeStopTimeQueue, Team,
)
from match_engine.native import (
    CommentaryEventFlags, CommentaryImportance, IncidentImportance,
    MatchEventPlayerTeams, MatchStopReason, NativeMatchEvent, NativeStopTimeInfo,
    SetPieceType,
)


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.result = MatchEngine(
            Team.balanced("Home", 100), Team.balanced("Away", 200),
            MatchConfig(seed=26, seconds=900),
        ).run()

    def test_seek_clamps_and_event_updates_are_replayable(self):
        playback = MatchPlayback(self.result)
        update = playback.seek(300)
        self.assertEqual(update.current_second, 300)
        self.assertEqual(update.events, playback.request_event_update(0))
        playback.seek(10_000)
        self.assertEqual(playback.current_second, self.result["duration"])
        self.assertEqual(playback.current_time_slice, self.result["duration"] * 4)

    def test_native_time_slice_seek_uses_recovered_four_hz_boundary(self):
        playback = MatchPlayback(self.result)
        playback.seek_time_slice(42)
        self.assertEqual(playback.current_second, 10)
        self.assertEqual(playback.current_time_slice, 40)

    def test_native_shaped_events_can_omit_prototype_seconds(self):
        native_shaped = dict(self.result)
        native_shaped["events"] = [
            {key: value for key, value in event.items() if key != "second"}
            for event in self.result["events"]
        ]
        playback = MatchPlayback(native_shaped)
        update = playback.seek(10)
        self.assertTrue(all("time_slice" in event for event in update.events))

    def test_skip_dead_time_stops_on_next_event(self):
        playback = MatchPlayback(self.result)
        update = playback.skip_dead_time()
        expected = min(
            event["second"] for event in self.result["events"] if event["second"] > 0
        )
        self.assertEqual(update.current_second, expected)

    def test_highlight_navigation_is_stable(self):
        playback = MatchPlayback(self.result)
        first = playback.next_highlight()
        if first is not None:
            playback.seek(first[1] + 1)
            self.assertEqual(playback.previous_highlight(), first)

    def test_native_event_queue_replaces_suffix_at_returned_cursor(self):
        queue = NativeEventQueue()
        queue.apply_update(2, [{"time_slice": 4}, {"time_slice": 8}])
        queue.apply_update(1, [{"time_slice": 12}])
        self.assertEqual(queue.events, (
            {"time_slice": 4}, {"time_slice": 12},
        ))
        self.assertEqual(queue.cursor, 1)
        self.assertEqual(queue.current_first_event_index, 2)
        self.assertEqual(queue.current_last_event_index, 2)

    def test_native_event_queue_enforces_two_record_buffer(self):
        with self.assertRaises(ValueError):
            NativeEventQueue().apply_update(3, [{}, {}, {}])

    def test_native_event_queue_accepts_lossless_wire_records(self):
        record = NativeMatchEvent(
            (1, 2, 3, 4, 5, 6), MatchEventPlayerTeams.VISITOR_TEAM_PLAYER1,
            8052, 40, 2, CommentaryEventFlags.FLASHING,
            CommentaryImportance.HIGH, IncidentImportance.MAIN_EVENTS, 9,
        )
        events = NativeEventQueue()
        events.apply_native_update(1, [record])
        self.assertEqual(events.events, (record.as_dict(),))

    def test_tick_uses_time_slice_conversion(self):
        playback = MatchPlayback(self.result)
        update = playback.tick(0.5, speed=2.0)
        self.assertEqual(update.current_second, 1)

    def test_native_driver_preserves_tick_scaling_and_event_contract(self):
        calls = []
        def tick(delta):
            calls.append(("tick", delta))
            return {"time_slice": 4}
        def request(capacity):
            calls.append(("events", capacity))
            return 1, [{"time_slice": 4}]
        driver = NativeMatchDriver(tick, request)
        state = driver.tick_frame(0.25, speed=2.0)
        self.assertEqual(state, {"time_slice": 4})
        self.assertEqual(calls, [("tick", 0.5), ("events", 2)])
        self.assertEqual(driver.events.events, ({"time_slice": 4},))

    def test_native_driver_can_forward_wire_records_without_interpretation(self):
        record = NativeMatchEvent(
            (0, 0, 0, 0, 0, 0), MatchEventPlayerTeams.NONE,
            8052, 4, 0, CommentaryEventFlags.NONE,
            CommentaryImportance.LOW, IncidentImportance.BASIC_EVENTS, 0,
        )
        driver = NativeMatchDriver(lambda _: None, lambda _: (1, [record]))
        driver.tick_frame(0.1)
        self.assertEqual(driver.events.events, (record.as_dict(),))

    def test_native_driver_rejects_mixed_wire_and_view_records(self):
        record = NativeMatchEvent(
            (0, 0, 0, 0, 0, 0), MatchEventPlayerTeams.NONE,
            8052, 4, 0, CommentaryEventFlags.NONE,
            CommentaryImportance.LOW, IncidentImportance.BASIC_EVENTS, 0,
        )
        driver = NativeMatchDriver(lambda _: None, lambda _: (2, [record, {}]))
        with self.assertRaises(TypeError):
            driver.tick_frame(0.1)

    def test_json_native_trace_forwards_observed_records(self):
        trace = JsonNativeTrace.from_mapping({
            "frames": [{
                "state": {"flags": 1, "time_slice": 4},
                "events": [{"commentary_event": 8052, "time_slice": 4}],
            }],
        })
        driver = trace.driver()
        self.assertEqual(driver.tick_frame(0.25), {"flags": 1, "time_slice": 4})
        self.assertEqual(driver.events.events, ({"commentary_event": 8052, "time_slice": 4},))

    def test_native_stop_time_queue_replaces_suffix_and_advances_index(self):
        queue = NativeStopTimeQueue()
        queue.apply_update(2, [{"stop_time_slice": 4}, {"stop_time_slice": 8}])
        queue.apply_update(1, [{"stop_time_slice": 12}])
        self.assertEqual(queue.infos, (
            {"stop_time_slice": 4}, {"stop_time_slice": 12},
        ))
        self.assertEqual(queue.current_index, 2)

    def test_native_stop_time_queue_accepts_wire_records(self):
        record = NativeStopTimeInfo(40, MatchStopReason.SET_PIECE, SetPieceType.CORNER)
        queue = NativeStopTimeQueue()
        queue.apply_native_update(1, [record])
        self.assertEqual(queue.infos, (record.as_dict(),))


if __name__ == "__main__":
    unittest.main()
