import unittest

from match_engine.managed import ManagedTacticalStyle


class ManagedMetadataTests(unittest.TestCase):
    def test_recovered_tactical_style_values(self):
        self.assertEqual(ManagedTacticalStyle.CONTROL_POSSESSION, 0)
        self.assertEqual(ManagedTacticalStyle.BLANK_SLATE, 10)
        self.assertEqual(ManagedTacticalStyle.MAX, 11)

if __name__ == "__main__":
    unittest.main()
