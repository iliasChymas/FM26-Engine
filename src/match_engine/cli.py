from __future__ import annotations

import argparse
import json

from .engine import MatchEngine
from .model import MatchConfig, Tactics, Team
from .playback import JsonNativeTrace


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic clean-room football match")
    parser.add_argument("--scenario", help="JSON scenario file for repeatable team/tactic inputs")
    parser.add_argument("--native-trace", help="Replay a captured native playback trace JSON")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seconds", type=int)
    parser.add_argument("--home-name")
    parser.add_argument("--away-name")
    parser.add_argument("--home-formation")
    parser.add_argument("--away-formation")
    for side in ("home", "away"):
        for field in ("mentality", "pressing", "directness", "tempo", "width", "defensive-line"):
            parser.add_argument(f"--{side}-{field}", type=float)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    scenario: dict[str, object] = {}
    if args.scenario:
        with open(args.scenario, encoding="utf-8") as stream:
            scenario = json.load(stream)
        if not isinstance(scenario, dict):
            raise ValueError("scenario root must be a JSON object")

    if args.native_trace:
        trace = JsonNativeTrace.from_path(args.native_trace)
        print(json.dumps({"mode": "native_trace", "frames": trace.replay()},
                         indent=2 if args.pretty else None))
        return

    def scalar(name: str, default: object) -> object:
        value = getattr(args, name)
        return default if value is None else value

    seed = int(scalar("seed", scenario.get("seed", 26)))
    seconds = int(scalar("seconds", scenario.get("seconds", 5400)))

    def tactics(side: str, formation: str, defaults: dict[str, float], side_data: dict[str, object]) -> Tactics:
        scenario_tactics = side_data.get("tactics", {})
        if not isinstance(scenario_tactics, dict):
            raise ValueError(f"scenario {side}.tactics must be a JSON object")
        values = {
            field: getattr(args, f"{side}_{field.replace('-', '_')}")
            for field in ("mentality", "pressing", "directness", "tempo", "width", "defensive-line")
        }
        values = {
            key.replace("-", "_"): (
                value if value is not None else scenario_tactics.get(key, defaults[key])
            ) for key, value in values.items()
        }
        instructions = scenario_tactics.get("instructions", {})
        if instructions is None:
            instructions = {}
        if not isinstance(instructions, dict):
            raise ValueError(f"scenario {side}.tactics.instructions must be a JSON object")
        return Tactics(
            formation=formation,
            tactical_style=scenario_tactics.get("tactical_style"),
            instructions=dict(instructions),
            **values,
        )

    sides = {}
    for side in ("home", "away"):
        data = scenario.get(side, {})
        if not isinstance(data, dict):
            raise ValueError(f"scenario {side} must be a JSON object")
        sides[side] = data

    home_name = str(scalar("home_name", sides["home"].get("name", "Home")))
    away_name = str(scalar("away_name", sides["away"].get("name", "Away")))
    home_formation = str(scalar("home_formation", sides["home"].get("formation", "4-3-3")))
    away_formation = str(scalar("away_formation", sides["away"].get("formation", "4-2-3-1")))
    home_id = int(sides["home"].get("base_id", 100))
    away_id = int(sides["away"].get("base_id", 200))
    home_data = dict(sides["home"])
    away_data = dict(sides["away"])
    home = Team.from_mapping(
        home_name, home_id, home_data,
        tactics("home", home_formation, {
            "mentality": .60, "pressing": .62, "directness": .45,
            "tempo": .60, "width": .55, "defensive-line": .52,
        }, home_data),
    )
    away = Team.from_mapping(
        away_name, away_id, away_data,
        tactics("away", away_formation, {
            "mentality": .55, "pressing": .55, "directness": .58,
            "tempo": .55, "width": .55, "defensive-line": .52,
        }, away_data),
    )
    setup = scenario.get("setup", {})
    if setup is None:
        setup = {}
    if not isinstance(setup, dict):
        raise ValueError("scenario.setup must be a JSON object")
    result = MatchEngine(
        home,
        away,
        MatchConfig(seed=seed, seconds=seconds, setup=dict(setup)),
    ).run()
    print(json.dumps(result, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
