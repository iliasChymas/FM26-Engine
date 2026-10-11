from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .native import TIME_SLICES_PER_SECOND


class EventType(StrEnum):
    KICK_OFF = "kick_off"
    PASS = "pass"
    CARRY = "carry"
    SHOT = "shot"
    GOAL = "goal"
    OWN_GOAL = "own_goal"
    SAVE = "save"
    MISS = "miss"
    GOALKEEPER_HELD = "goalkeeper_held"
    MISSED_PENALTY = "missed_penalty"
    SCORED_PENALTY = "scored_penalty"
    SUBSTITUTION = "substitution"
    INJURY = "injury"
    INJURY_FORCED_OFF = "injury_forced_off"
    INJURY_SENT_OFF = "injury_sent_off"
    INJURY_GOES_ON = "injury_goes_on"
    TURNOVER = "turnover"
    OFFSIDE = "offside"
    FOUL = "foul"
    FREE_KICK = "free_kick"
    CORNER = "corner"
    THROW_IN = "throw_in"
    PENALTY = "penalty"
    GOAL_KICK = "goal_kick"
    YELLOW = "yellow"
    SECOND_YELLOW = "second_yellow"
    RED = "red"
    HALF_TIME = "half_time"
    ADDED_TIME = "added_time"
    FULL_TIME = "full_time"
    FINAL_WHISTLE = "final_whistle"


@dataclass(frozen=True)
class Tactics:
    formation: str = "4-3-3"
    mentality: float = 0.55
    pressing: float = 0.55
    directness: float = 0.45
    tempo: float = 0.55
    width: float = 0.55
    defensive_line: float = 0.52
    # These names mirror the managed tactical-instruction boundary.  Their
    # values are retained as input data even where the native evaluator is not
    # yet recovered; callers can therefore supply a complete system without
    # silently reducing it to six invented scalars.
    tactical_style: str | int | None = None
    instructions: dict[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("mentality", "pressing", "directness", "tempo", "width", "defensive_line"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass
class Player:
    id: int
    name: str
    role: str
    passing: float
    finishing: float
    tackling: float
    decisions: float
    pace: float
    stamina: float
    goalkeeping: float = 0.0
    fatigue: float = 0.0
    yellow: bool = False
    sent_off: bool = False
    # Extended roster/system data accepted by the CLI.  The native match
    # engine receives considerably more than the six prototype attributes;
    # preserve those fields losslessly until their evaluator is established.
    attributes: dict[str, float] = field(default_factory=dict)
    position: str | None = None
    in_possession_role: str | None = None
    out_of_possession_role: str | None = None
    duty: str = "support"
    instructions: dict[str, str | int | float | bool] = field(default_factory=dict)
    condition: float = 1.0
    match_sharpness: float = 1.0
    morale: float = 0.5

    @property
    def energy(self) -> float:
        return max(0.35, min(1.0, self.condition * (1.0 - self.fatigue)))

    def attribute(self, name: str, fallback: float = 0.5) -> float:
        """Return a normalized supplied attribute without inventing a mapping.

        Scenario attributes are deliberately normalized to ``[0, 1]``.  The
        fallback exists only for legacy compact scenarios; a full roster can
        provide arbitrary additional attributes in ``attributes``.
        """
        value = self.attributes.get(name, getattr(self, name, fallback))
        return max(0.0, min(1.0, float(value)))

    def as_input_dict(self) -> dict[str, object]:
        """Serialize supplied roster fields for reproducible CLI output."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "position": self.position,
            "in_possession_role": self.in_possession_role,
            "out_of_possession_role": self.out_of_possession_role,
            "duty": self.duty,
            "attributes": {
                "passing": self.passing,
                "finishing": self.finishing,
                "tackling": self.tackling,
                "decisions": self.decisions,
                "pace": self.pace,
                "stamina": self.stamina,
                "goalkeeping": self.goalkeeping,
                **self.attributes,
            },
            "instructions": dict(self.instructions),
            "condition": self.condition,
            "match_sharpness": self.match_sharpness,
            "morale": self.morale,
        }


@dataclass
class Team:
    name: str
    players: list[Player]
    tactics: Tactics = field(default_factory=Tactics)
    substitutes: list[Player] = field(default_factory=list)

    @classmethod
    def from_mapping(
        cls,
        name: str,
        base_id: int,
        data: dict[str, object],
        tactics: Tactics | None = None,
    ) -> "Team":
        """Build a team from the explicit scenario roster/system schema.

        A missing ``players`` array retains the legacy balanced fixture.  When
        present, player records are kept as supplied and must contain the
        actual match roster attributes used by the caller.
        """
        raw_players = data.get("players")
        if raw_players is None:
            return cls.balanced(name, base_id, tactics)
        if not isinstance(raw_players, list) or not raw_players:
            raise ValueError(f"{name}.players must be a non-empty JSON array")
        players: list[Player] = []
        for index, raw in enumerate(raw_players):
            if not isinstance(raw, dict):
                raise ValueError(f"{name}.players[{index}] must be a JSON object")
            players.append(Player.from_mapping(raw, default_id=base_id + index, default_team=name))
        raw_substitutes = data.get("substitutes", [])
        if raw_substitutes is None:
            raw_substitutes = []
        if not isinstance(raw_substitutes, list):
            raise ValueError(f"{name}.substitutes must be a JSON array")
        substitutes: list[Player] = []
        for index, raw in enumerate(raw_substitutes):
            if not isinstance(raw, dict):
                raise ValueError(f"{name}.substitutes[{index}] must be a JSON object")
            substitutes.append(Player.from_mapping(
                raw, default_id=base_id + 100 + index, default_team=name,
            ))
        return cls(name, players, tactics or Tactics(), substitutes)

    @classmethod
    def balanced(cls, name: str, base_id: int, tactics: Tactics | None = None) -> "Team":
        roles = ["GK", "FB", "CB", "CB", "FB", "DM", "CM", "CM", "W", "W", "ST"]
        players = []
        for index, role in enumerate(roles):
            bias = ((base_id + index * 7) % 11 - 5) / 100
            players.append(Player(
                id=base_id + index,
                name=f"{name} {index + 1}",
                role=role,
                passing=max(.35, min(.9, .64 + bias)),
                finishing=max(.25, min(.9, .70 + bias if role in {"ST", "W"} else .48 + bias)),
                tackling=max(.25, min(.9, .70 + bias if role in {"CB", "FB", "DM"} else .48 + bias)),
                decisions=max(.35, min(.9, .63 + bias)),
                pace=max(.35, min(.9, .66 + bias)),
                stamina=max(.4, min(.9, .68 + bias)),
                goalkeeping=.76 + bias if role == "GK" else 0.0,
            ))
        return cls(name, players, tactics or Tactics())

    def as_input_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "formation": self.tactics.formation,
            "tactical_style": self.tactics.tactical_style,
            "instructions": dict(self.tactics.instructions),
            "players": [player.as_input_dict() for player in self.players],
            "substitutes": [player.as_input_dict() for player in self.substitutes],
        }


def _player_from_mapping(
    cls: type[Player], data: dict[str, object], *, default_id: int = 0,
    default_team: str = "Team",
) -> Player:
    """Parse a normalized player record while preserving extra attributes."""
    def number(key: str, fallback: float) -> float:
        value = data.get(key, fallback)
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"player {data.get('name', default_id)}.{key} must be numeric") from exc
        if not 0.0 <= result <= 1.0:
            raise ValueError(f"player {data.get('name', default_id)}.{key} must be in [0, 1]")
        return result

    extra = data.get("attributes", {})
    if extra is None:
        extra = {}
    if not isinstance(extra, dict):
        raise ValueError("player.attributes must be a JSON object")
    attributes: dict[str, float] = {}
    for key, value in extra.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"player.attributes.{key} must be numeric") from exc
        if not 0.0 <= numeric <= 1.0:
            raise ValueError(f"player.attributes.{key} must be in [0, 1]")
        attributes[str(key)] = numeric
    instructions = data.get("instructions", {})
    if instructions is None:
        instructions = {}
    if not isinstance(instructions, dict):
        raise ValueError("player.instructions must be a JSON object")
    return Player(
        id=int(data.get("id", default_id)),
        name=str(data.get("name", f"{default_team} {default_id}")),
        role=str(data.get("role", data.get("position", "CM"))),
        passing=number("passing", .55),
        finishing=number("finishing", .50),
        tackling=number("tackling", .50),
        decisions=number("decisions", .55),
        pace=number("pace", .55),
        stamina=number("stamina", .65),
        goalkeeping=number("goalkeeping", 0.0),
        fatigue=number("fatigue", 0.0),
        yellow=bool(data.get("yellow", False)),
        sent_off=bool(data.get("sent_off", False)),
        attributes=attributes,
        position=None if data.get("position") is None else str(data["position"]),
        in_possession_role=(None if data.get("in_possession_role") is None
                            else str(data["in_possession_role"])),
        out_of_possession_role=(None if data.get("out_of_possession_role") is None
                                else str(data["out_of_possession_role"])),
        duty=str(data.get("duty", "support")),
        instructions=dict(instructions),
        condition=number("condition", 1.0),
        match_sharpness=number("match_sharpness", 1.0),
        morale=number("morale", 0.5),
    )


Player.from_mapping = classmethod(_player_from_mapping)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class MatchConfig:
    seed: int = 1
    seconds: int = 90 * 60
    tick_seconds: int = 5
    home_advantage: float = 0.025
    # Evidence-backed setup metadata.  The native boundary receives a PKM
    # byte span plus flags/user-team, while competition/region/unique IDs are
    # exposed through post-setup getters.  Preserve these inputs for CLI
    # experiments without pretending their native evaluator semantics are
    # known.
    setup: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchEvent:
    second: int
    type: EventType
    team: str | None = None
    actor: str | None = None
    target: str | None = None
    xg: float = 0.0
    detail: str = ""
    important: bool = False
    x: float | None = None
    y: float | None = None
    team_index: int | None = None
    player_ids: tuple[int, ...] = ()

    @property
    def native_commentary_event(self) -> int | None:
        """Return only explicitly recovered native IDs; unknowns stay unmapped."""
        from .native import NativeCommentaryEvent

        mapping = {
            EventType.KICK_OFF: NativeCommentaryEvent.KICK_OFF,
            # These IDs are explicit managed enum names.  They identify the
            # representational event category only; the simulator's choice of
            # pass subtype remains unresolved.
            EventType.PASS: NativeCommentaryEvent.PASS_IT,
            EventType.CARRY: NativeCommentaryEvent.RUN_WITH_BALL,
            EventType.CORNER: NativeCommentaryEvent.RESTART_CORNER,
            EventType.THROW_IN: NativeCommentaryEvent.RESTART_THROW_IN,
            EventType.GOAL_KICK: NativeCommentaryEvent.RESTART_GOAL_KICK,
            EventType.OFFSIDE: NativeCommentaryEvent.RESTART_OFFSIDE,
            EventType.FREE_KICK: NativeCommentaryEvent.RESTART_FREE_KICK,
            EventType.PENALTY: NativeCommentaryEvent.RESTART_PENALTY,
            EventType.SHOT: NativeCommentaryEvent.DEFAULT_SHOT,
            EventType.GOAL: NativeCommentaryEvent.GOAL,
            EventType.OWN_GOAL: NativeCommentaryEvent.OWN_GOAL,
            EventType.MISSED_PENALTY: NativeCommentaryEvent.MISSED_PENALTY,
            EventType.SCORED_PENALTY: NativeCommentaryEvent.SCORED_PENALTY,
            EventType.GOALKEEPER_HELD: NativeCommentaryEvent.GOALKEEPER_HELD,
            EventType.SUBSTITUTION: NativeCommentaryEvent.SUBSTITUTION,
            EventType.INJURY_FORCED_OFF: NativeCommentaryEvent.PLAYER_INJURED_FORCED_OFF,
            EventType.INJURY_SENT_OFF: NativeCommentaryEvent.PLAYER_INJURED_SENT_OFF,
            EventType.INJURY_GOES_ON: NativeCommentaryEvent.PLAYER_INJURED_GOES_ON,
            EventType.FOUL: NativeCommentaryEvent.FOUL,
            EventType.YELLOW: NativeCommentaryEvent.YELLOW_CARD,
            EventType.SECOND_YELLOW: NativeCommentaryEvent.SECOND_YELLOW_CARD,
            EventType.RED: NativeCommentaryEvent.SENT_OFF,
            EventType.FINAL_WHISTLE: NativeCommentaryEvent.FINAL_WHISTLE,
        }
        event = mapping.get(self.type)
        return None if event is None else int(event)

    def as_dict(self) -> dict[str, object]:
        return {
            "second": self.second,
            # The native playback ABI exposes event time as an integer slice;
            # four slices per second is the recovered public conversion.
            "time_slice": self.second * TIME_SLICES_PER_SECOND,
            "type": self.type.value, "team": self.team,
            "commentary_event": self.native_commentary_event,
            "actor": self.actor, "target": self.target, "xg": round(self.xg, 4),
            "detail": self.detail, "important": self.important,
            "position": None if self.x is None else {
                "x": round(self.x, 3), "y": round(self.y or 0.0, 3),
            },
            "team_index": self.team_index,
            "player_ids": list(self.player_ids),
        }


@dataclass
class MatchStats:
    goals: int = 0
    shots: int = 0
    shots_on_target: int = 0
    xg: float = 0.0
    passes: int = 0
    completed_passes: int = 0
    fouls: int = 0
    yellows: int = 0
    reds: int = 0
    corners: int = 0
    offsides: int = 0
    possession_ticks: int = 0
