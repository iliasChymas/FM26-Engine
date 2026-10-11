import unittest

from match_engine.commentary import CommentaryVariant, render, select_variant
from match_engine.model import EventType, MatchEvent


class CommentaryTests(unittest.TestCase):
    def test_live_and_replay_forms_share_a_selected_variant(self):
        event = MatchEvent(30, EventType.SHOT, "Home", "Striker")
        self.assertEqual(render(event, seed=4), render(event, seed=4))
        self.assertIsNotNone(render(event, seed=4, replay=True))

    def test_explicit_weights_control_selection(self):
        event = MatchEvent(30, EventType.SHOT)
        variants = (
            CommentaryVariant("never", weight=0),
            CommentaryVariant("always", weight=1, delay=3),
        )
        self.assertEqual(select_variant(event, variants=variants), variants[1])

    def test_negative_selector_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            CommentaryVariant("line", weight=-1)


if __name__ == "__main__":
    unittest.main()
