import unittest
from pathlib import Path

from match_engine.pkm import (
    inspect_first_adjacent_string_pair,
    inspect_observed_catalogue,
    inspect_pkm_bytes,
)


class PkmInspectionTests(unittest.TestCase):
    def test_shipped_fixtures_retain_observed_catalogue(self):
        root = Path(__file__).parents[2] / "data" / "game_simulation" / "test match"
        fixtures = (root / "match.pkm", root / "match_female.pkm")
        if not all(path.exists() for path in fixtures):
            self.skipTest("FM26 PKM fixtures are not present")
        inspections = [inspect_pkm_bytes(path.read_bytes()) for path in fixtures]
        for inspection in inspections:
            self.assertEqual(inspection.version_bytes, (3, 1))
            self.assertIsNotNone(inspection.catalogue)
            assert inspection.catalogue is not None
            self.assertEqual(len(inspection.catalogue.records), 93)
            self.assertEqual(inspection.catalogue.sentinel_offset, 0xBE8)
        self.assertEqual(
            [row.as_dict() for row in inspections[0].catalogue.records],
            [row.as_dict() for row in inspections[1].catalogue.records],
        )
        self.assertEqual(
            (inspections[0].first_post_catalogue_string_pair.first.value,
             inspections[0].first_post_catalogue_string_pair.second.value),
            ("Italian Serie A", "Serie A"),
        )
        self.assertEqual(inspections[0].first_post_catalogue_string_pair.offset, 0xDDE)
        self.assertEqual(
            (inspections[1].first_post_catalogue_string_pair.first.value,
             inspections[1].first_post_catalogue_string_pair.second.value),
            ("Women's Super League", "Super League"),
        )
        self.assertEqual(inspections[1].first_post_catalogue_string_pair.offset, 0xDDE)

    def test_observed_prefix_and_length_prefixed_strings(self):
        payload = b"\x03\x01mkp.\x00\x00" + b"\xaa\xbb" + (7).to_bytes(4, "little") + b"Serie A"
        result = inspect_pkm_bytes(payload)
        self.assertEqual(result.version_bytes, (3, 1))
        self.assertEqual(result.marker, "mkp.")
        self.assertEqual([item.value for item in result.strings], ["Serie A"])
        self.assertEqual(result.strings[0].offset, 14)

    def test_rejects_unobserved_container(self):
        with self.assertRaises(ValueError):
            inspect_pkm_bytes(b"\x03\x01nope\x00\x00")

    def test_observed_catalogue_record_framing(self):
        def record(record_id, text, flag_a, link):
            raw = text.encode()
            return (
                record_id.to_bytes(2, "little")
                + len(raw).to_bytes(4, "little") + raw
                + bytes([flag_a]) + link.to_bytes(4, "little") + b"\x01"
            )

        payload = b"prefix" + record(5, "first", 1, 6) + record(6, "second", 0, 7) + b"\xff\xff"
        result = inspect_observed_catalogue(payload)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.offset, 6)
        self.assertEqual(result.sentinel_offset, len(payload) - 2)
        self.assertEqual([row.record_id for row in result.records], [5, 6])
        self.assertEqual([row.link_value for row in result.records], [6, 7])

    def test_finds_adjacent_string_pair_without_naming_surrounding_fields(self):
        first = b"Long Name"
        second = b"Short"
        payload = (
            b"opaque" + len(first).to_bytes(4, "little") + first
            + len(second).to_bytes(4, "little") + second + b"tail"
        )
        result = inspect_first_adjacent_string_pair(payload)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.offset, 6)
        self.assertEqual(result.first.value, "Long Name")
        self.assertEqual(result.second.value, "Short")


if __name__ == "__main__":
    unittest.main()
