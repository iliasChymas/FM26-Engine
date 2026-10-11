import unittest
from pathlib import Path

from match_engine.fmf import (
    inspect_commentary_xml,
    inspect_stat_attribute_payload,
    inspect_stat_distribution_payload,
    inspect_expected_scores,
    inspect_qme_roles,
    inspect_qme_role_lookup,
    inspect_qme_revisions,
    inspect_tactical_style_xml,
    inspect_xg_payload,
)
from match_engine.managed import ManagedTacticalStyle


class FmfInspectionTests(unittest.TestCase):
    def test_shipped_xg_table_has_observed_model_grid(self):
        path = Path(__file__).parents[2] / "shared" / "data" / "simatch.fmf"
        if not path.exists():
            self.skipTest("FM26 shared data is not present")
        from match_engine.fmf import inspect_xg_models

        records = inspect_xg_models(path)
        self.assertEqual(len(records), 110)
        self.assertEqual(len({r.shot_type for r in records}), 11)
        self.assertEqual(len({r.version for r in records}), 10)
        self.assertEqual(
            sum(bool(r.coefficients) and all(v == 0 for v in r.coefficients.values())
                for r in records),
            11,
        )

    def test_shipped_qme_tables_retain_serialized_rows(self):
        path = Path(__file__).parents[2] / "shared" / "data" / "simatch.fmf"
        if not path.exists():
            self.skipTest("FM26 shared data is not present")
        expected = inspect_expected_scores(path)
        roles = inspect_qme_roles(path)
        lookup = inspect_qme_role_lookup(path)
        self.assertEqual(len(expected), 66)
        self.assertEqual(len(roles), 183)
        self.assertEqual(len(lookup), 250)
        self.assertEqual(len(roles[0].coefficients), 52)
        self.assertEqual(expected[0].negative_multiplier, 1000)
        self.assertEqual(expected[0].positive_multiplier, 1200)
        self.assertEqual(lookup[0].index, 0)
        self.assertEqual(lookup[0].role, 1)
        self.assertGreater(max(item.role for item in lookup), 2**32)
        revisions = inspect_qme_revisions(path)
        self.assertEqual(len(revisions), 6)
        self.assertEqual({item.start_value for item in revisions}, {6700})
        self.assertEqual(revisions[-1].version.year, 26)

    def test_extracts_selector_structure_without_translation_text(self):
        xml = b'''<record><list id="evts"><record>
          <integer id="id" value="7"/><list id="evar"><record>
          <translation_record id="game" value="not returned"/>
          <integer id="prob" value="30"/><integer id="dely" value="3"/>
          </record></list></record></list></record>'''
        result = inspect_commentary_xml(xml)
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.first_event_id, 7)
        self.assertEqual(result.variant_count, 1)
        self.assertEqual(result.probability_min, 30)
        self.assertEqual(result.delay_max, 3)

    def test_extracts_raw_xg_record_with_inline_and_i32_values(self):
        record = (
            b"Z\x0ccoefficients*"
            b"\x03foo\x92"  # inline integer 1
            b"\x03bar\x02\xc0\x1d\xfe\xff"  # int32 -123456
            b"\x09shot_type\x88headers"
            b"\x0eversion_numberZ"
            b"\x0dversion_major\x92"
            b"\x0dversion_minor\x82"
            b"\x0fversion_release\xa2"
            b"\x0cversion_year\x02\x1a\x00\x00\x00"
        )
        result = inspect_xg_payload(b"prefix" + record + b"suffix")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].payload_offset, 6)
        self.assertEqual(result[0].shot_type, "headers")
        self.assertEqual(result[0].coefficients, {"foo": 1, "bar": -123456})
        self.assertEqual(
            (result[0].version.major, result[0].version.minor,
             result[0].version.release, result[0].version.year),
            (1, 0, 2, 26),
        )

    def test_xg_record_exposes_only_observed_raw_dot_product(self):
        from match_engine.fmf import XgModelRecord, XgModelVersion
        record = XgModelRecord(0, "regular", XgModelVersion(1, 0, 0, 26),
                               {"distance": 3, "intercept": -2})
        self.assertEqual(record.raw_linear_score({"distance": 4, "intercept": 1}), 10.0)
        with self.assertRaises(ValueError):
            record.raw_linear_score({"distance": 4})

    def test_extracts_normal_and_binned_distribution_rows(self):
        normal = (
            b"\x0eability_window9\x82\x02c\x00\x00\x00"
            b"\x10attribute_window9\x82\x17"
            b"\x11distribution_typexnormal"
            b"\x04mean\x07\x00\x00\x00\x00\x00\x00\x24\x40"
            b"\x08position\xb8goalkeeper"
            b"\x09stat_type\xb8key_passes"
            b"\x08variance\x27"
        )
        binned = (
            b"\x0eability_window9\x02d\x00\x00\x00\x02\x81\x00\x00\x00"
            b"\x10attribute_window9\x82\x02\x14\x00\x00\x00"
            b"\x11distribution_typexbinned\x04mean\xb9"
            + b"\x17" * 9 + b"\x37"
            + b"\x08position\xe8defender_left"
            b"\x09stat_type\x08\x11\x00\x00\x00tackle_completion"
            b"\x08variance\x17"
        )
        result = inspect_stat_distribution_payload(normal + binned)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].ability_window, (0, 99))
        self.assertEqual(result[0].attribute_window, (0, 0.0))
        self.assertEqual(result[0].mean, 10.0)
        self.assertEqual(result[0].variance, 1.0)
        self.assertEqual(result[1].distribution_type, "binned")
        self.assertEqual(result[1].mean, (0.0,) * 9 + (2.0,))

    def test_extracts_stat_attribute_mapping(self):
        payload = (
            b":\x13relevant_attributesI"
            b"\x98crossing\x78vision\xa8technique"
            b"\x09stat_type\x08\x10\x00\x00\x00cross_completion"
        )
        result = inspect_stat_attribute_payload(payload)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].stat_type, "cross_completion")
        self.assertEqual(
            result[0].relevant_attributes,
            ("crossing", "vision", "technique"),
        )

    def test_tactical_style_parser_excludes_authored_text(self):
        xml = b'''<record><record id="1" folder="press" tactical_style_id="PRESS">
          <translation id="text" value="excluded"/>
          <list id="attribute_template"><record id="10">
            <integer id="min" value="18"/><integer id="max" value="20"/>
          </record></list>
          <list id="tendency_template"><record id="77">
            <integer id="min" value="13"/><integer id="max" value="20"/>
          </record></list>
          <list id="preferred_roles"><integer value="31"/><integer value="27"/></list>
        </record></record>'''
        result = inspect_tactical_style_xml(xml, payload_offset=123)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].payload_offset, 123)
        self.assertEqual(result[0].attribute_ranges, {10: (18, 20)})
        self.assertEqual(result[0].tendency_ranges, {77: (13, 20)})
        self.assertEqual(result[0].preferred_role_ids, (31, 27))
        self.assertEqual(result[0].managed_style, ManagedTacticalStyle.GEGENPRESS)
        self.assertNotIn("excluded", repr(result[0]))


if __name__ == "__main__":
    unittest.main()
