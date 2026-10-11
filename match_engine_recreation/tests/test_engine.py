import unittest

from match_engine import EventType, MatchConfig, MatchEngine, Tactics, Team


def simulate(seed: int = 26, seconds: int = 900):
    return MatchEngine(
        Team.balanced("Home", 100, Tactics(pressing=.7)),
        Team.balanced("Away", 200, Tactics(directness=.65)),
        MatchConfig(seed=seed, seconds=seconds),
    ).run()


class EngineTests(unittest.TestCase):
    def test_seed_is_deterministic(self):
        self.assertEqual(simulate(), simulate())

    def test_different_seeds_change_event_stream(self):
        self.assertNotEqual(simulate(1)["events"], simulate(2)["events"])

    def test_statistics_are_consistent(self):
        result = simulate(seconds=5400)
        for stats in result["stats"].values():
            self.assertLessEqual(stats["completed_passes"], stats["passes"])
            self.assertLessEqual(stats["shots_on_target"], stats["shots"])
            self.assertGreaterEqual(stats["xg"], 0)
        self.assertAlmostEqual(sum(s["possession"] for s in result["stats"].values()), 100, delta=.2)
        for event in result["events"]:
            self.assertLessEqual(len(event["player_ids"]), 6)
            self.assertEqual(event["time_slice"], event["second"] * 4)
            if event["actor"] is not None:
                self.assertTrue(event["player_ids"])

    def test_tactics_are_bounded(self):
        with self.assertRaises(ValueError):
            Tactics(tempo=1.1)

    def test_supplied_extended_attributes_and_condition_are_retained(self):
        from match_engine.model import Player
        player = Player.from_mapping({
            "name": "Measured", "role": "ST", "finishing": .6,
            "attributes": {"finishing": .91, "anticipation": .88},
            "condition": .72,
        })
        self.assertAlmostEqual(player.attribute("finishing"), .91)
        self.assertAlmostEqual(player.attribute("anticipation"), .88)
        self.assertAlmostEqual(player.energy, .72)

    def test_native_restart_categories_are_representable(self):
        self.assertEqual(EventType.THROW_IN.value, "throw_in")
        self.assertEqual(EventType.PENALTY.value, "penalty")

    def test_only_recovered_commentary_ids_are_attached(self):
        result = simulate(seconds=5400)
        known = {
            event["commentary_event"] for event in result["events"]
            if event["commentary_event"] is not None
        }
        self.assertIn(8052, known)  # native kick-off ID
        self.assertIn(8065, known)  # native default-shot ID
        self.assertTrue(all(event["commentary_event"] is None or 8000 <= event["commentary_event"] <= 9219
                            for event in result["events"]))

    def test_additional_recovered_commentary_categories(self):
        from match_engine.model import MatchEvent
        expected = {
            EventType.OWN_GOAL: 8143,
            EventType.MISSED_PENALTY: 8144,
            EventType.SCORED_PENALTY: 8145,
            EventType.GOALKEEPER_HELD: 8165,
            EventType.SUBSTITUTION: 8027,
            EventType.INJURY_FORCED_OFF: 8022,
            EventType.INJURY_SENT_OFF: 8023,
            EventType.INJURY_GOES_ON: 8024,
            EventType.SECOND_YELLOW: 8183,
            EventType.FINAL_WHISTLE: 8194,
        }
        for event_type, native_id in expected.items():
            self.assertEqual(MatchEvent(0, event_type).native_commentary_event, native_id)

    def test_explicit_pass_and_run_with_ball_ids(self):
        from match_engine.model import MatchEvent
        self.assertEqual(MatchEvent(0, EventType.PASS).native_commentary_event, 8050)
        self.assertEqual(MatchEvent(0, EventType.CARRY).native_commentary_event, 8011)

    def test_match_has_restart_and_stoppage_state(self):
        result = simulate(seconds=5400)
        types = [event["type"] for event in result["events"]]
        self.assertEqual(types[-1], EventType.FULL_TIME)
        self.assertEqual(types.count(EventType.ADDED_TIME), 2)
        self.assertGreaterEqual(result["duration"], 5400)
        self.assertTrue(any(kind in types for kind in (
            EventType.CORNER, EventType.GOAL_KICK, EventType.FREE_KICK,
        )))

    def test_spatial_events_stay_on_pitch(self):
        for event in simulate(seconds=5400)["events"]:
            position = event["position"]
            if position is not None:
                self.assertGreaterEqual(position["x"], 0)
                self.assertLessEqual(position["x"], 1)
                self.assertGreaterEqual(position["y"], 0)
                self.assertLessEqual(position["y"], 1)

    def test_seed_batch_has_football_scale_output(self):
        samples = [simulate(seed, seconds=5400) for seed in range(20)]
        mean_shots = sum(sum(s["shots"] for s in match["stats"].values())
                         for match in samples) / len(samples)
        mean_goals = sum(sum(match["score"].values()) for match in samples) / len(samples)
        self.assertGreater(mean_shots, 12)
        self.assertLess(mean_shots, 45)
        self.assertGreater(mean_goals, .5)
        self.assertLess(mean_goals, 6)


if __name__ == "__main__":
    unittest.main()
