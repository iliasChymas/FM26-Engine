from __future__ import annotations

import random
from dataclasses import dataclass

from .model import EventType, MatchEvent


@dataclass(frozen=True)
class CommentaryVariant:
    """Clean-room equivalent of the observed live/replay/weight/delay shape."""

    live: str
    replay: str | None = None
    weight: int = 1
    delay: int = 0

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("commentary weight cannot be negative")
        if self.delay < 0:
            raise ValueError("commentary delay cannot be negative")


# Independently authored placeholders. Their unit weights and zero delays are
# prototype choices, not extracted FM tuning constants.
LINES = {
    EventType.KICK_OFF: (CommentaryVariant("The match begins."),),
    EventType.SHOT: (
        CommentaryVariant("{actor} takes aim.", "{actor} took aim."),
        CommentaryVariant("A shooting chance for {actor}."),
    ),
    EventType.GOAL: (CommentaryVariant("Goal! {actor} scores for {team}."),),
    EventType.SAVE: (CommentaryVariant("{actor} makes the save."),),
    EventType.MISS: (CommentaryVariant("{actor} sends the effort wide."),),
    EventType.OFFSIDE: (CommentaryVariant("{actor} is caught offside."),),
    EventType.FREE_KICK: (CommentaryVariant("A free kick for {team}."),),
    EventType.CORNER: (CommentaryVariant("{team} win a corner."),),
    EventType.GOAL_KICK: (CommentaryVariant("Goal kick."),),
    EventType.THROW_IN: (CommentaryVariant("A throw-in for {team}."),),
    EventType.YELLOW: (CommentaryVariant("{actor} is shown a yellow card."),),
    EventType.RED: (CommentaryVariant("{actor} is sent off."),),
    EventType.HALF_TIME: (CommentaryVariant("Half-time."),),
    EventType.ADDED_TIME: (CommentaryVariant("The officials indicate added time."),),
    EventType.FULL_TIME: (CommentaryVariant("Full-time."),),
}


def select_variant(
    event: MatchEvent,
    seed: int = 0,
    variants: tuple[CommentaryVariant, ...] | None = None,
) -> CommentaryVariant | None:
    choices = variants if variants is not None else LINES.get(event.type)
    if not choices or not any(item.weight for item in choices):
        return None
    rng = random.Random((seed << 16) ^ event.second ^ list(EventType).index(event.type))
    return rng.choices(choices, weights=[item.weight for item in choices], k=1)[0]


def render(event: MatchEvent, seed: int = 0, *, replay: bool = False) -> str | None:
    variant = select_variant(event, seed)
    if variant is None:
        return None
    line = variant.replay if replay and variant.replay is not None else variant.live
    return line.format(actor=event.actor or "A player", team=event.team or "the team")
