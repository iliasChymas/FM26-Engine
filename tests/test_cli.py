import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest import mock

from match_engine.cli import main


class CliTests(unittest.TestCase):
    def test_custom_scenario_arguments_produce_named_match(self):
        argv = [
            "cleanroom-match", "--seed", "7", "--seconds", "120",
            "--home-name", "Alpha", "--away-name", "Beta",
            "--home-pressing", ".8", "--away-directness", ".2",
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", argv):
            main()
        result = json.loads(output.getvalue())
        self.assertEqual(set(result["score"]), {"Alpha", "Beta"})
        self.assertEqual(result["seed"], 7)

    def test_json_scenario_is_reproducible(self):
        scenario = {
            "seed": 8,
            "seconds": 120,
            "home": {"name": "File Home", "base_id": 10, "tactics": {"pressing": .8}},
            "away": {"name": "File Away", "base_id": 20, "tactics": {"directness": .2}},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json") as stream:
            json.dump(scenario, stream)
            stream.flush()
            argv = ["cleanroom-match", "--scenario", stream.name]
            output = io.StringIO()
            with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", argv):
                main()
            result = json.loads(output.getvalue())
        self.assertEqual(result["seed"], 8)
        self.assertEqual(set(result["score"]), {"File Home", "File Away"})

    def test_full_roster_and_system_input_is_accepted(self):
        player = {
            "id": 101,
            "name": "Named striker",
            "role": "ST",
            "position": "ST",
            "passing": .6,
            "finishing": .9,
            "tackling": .2,
            "decisions": .7,
            "pace": .8,
            "stamina": .8,
            "attributes": {"anticipation": .85, "composure": .88},
            "in_possession_role": "pressing_forward",
            "out_of_possession_role": "OPTrackingCentreForward",
            "instructions": {"RunAtDefence": True},
        }
        scenario = {
            "seed": 9,
            "seconds": 120,
            "home": {
                "name": "Full Home", "base_id": 100,
                "formation": "4-3-3",
                "tactics": {"tactical_style": "GEGENPRESS", "instructions": {"PressingTrap": "out"}},
                "players": [player],
            },
            "away": {"name": "Fallback Away", "base_id": 200},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json") as stream:
            json.dump(scenario, stream)
            stream.flush()
            argv = ["cleanroom-match", "--scenario", stream.name]
            output = io.StringIO()
            with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", argv):
                main()
        result = json.loads(output.getvalue())
        self.assertEqual(set(result["score"]), {"Full Home", "Fallback Away"})

    def test_native_setup_metadata_is_preserved(self):
        scenario = {
            "seed": 4,
            "seconds": 30,
            "setup": {
                "flags": 16,
                "user_team_id": 0,
                "pkm_path": "match.pkm",
                "match_info": {"competition_type": 4},
                "outside_environment": {"region_id": 1, "city_population": 1000},
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json") as stream:
            json.dump(scenario, stream)
            stream.flush()
            argv = ["cleanroom-match", "--scenario", stream.name]
            output = io.StringIO()
            with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", argv):
                main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["setup"], scenario["setup"])

    def test_native_trace_cli_replays_without_interpretation(self):
        trace = {"frames": [{"state": {"time_slice": 4},
                              "events": [{"commentary_event": 8052, "time_slice": 4}]}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json") as stream:
            json.dump(trace, stream)
            stream.flush()
            argv = ["cleanroom-match", "--native-trace", stream.name]
            output = io.StringIO()
            with contextlib.redirect_stdout(output), mock.patch.object(sys, "argv", argv):
                main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["mode"], "native_trace")
        self.assertEqual(result["frames"][0]["events"][0]["commentary_event"], 8052)


if __name__ == "__main__":
    unittest.main()
