"""Identifiers recovered from the shipped IL2CPP managed metadata.

These values mirror public managed enum declarations. They do not describe
native simulation internals beyond those declaration boundaries.
"""

from enum import IntEnum


class ManagedTacticalStyle(IntEnum):
    INVALID = -1
    CONTROL_POSSESSION = 0
    GEGENPRESS = 1
    TIKI_TAKA = 2
    VERTICAL_TIKI_TAKA = 3
    WING_PLAY = 4
    ROUTE_ONE = 5
    FLUID_COUNTER_ATTACK = 6
    DIRECT_COUNTER_ATTACK = 7
    CATENACCIO = 8
    PARK_THE_BUS = 9
    BLANK_SLATE = 10
    MAX = 11


class ManagedTeamInstruction(IntEnum):
    """`FM.UI.TacticTeamInstructions` values recovered from metadata.

    These identify instruction slots, not their native evaluator weights.
    """

    FORMATION = 0
    PASSING_DIRECTNESS = 1
    PASSING_VERTICALITY = 2
    ATTACKING_TRANSITION = 3
    TEAM_WIDTH = 4
    CREATIVE_FREEDOM = 5
    PLAY_FOR_SET_PIECES = 6
    TIME_WASTING = 7
    LINE_OF_ENGAGEMENT = 8
    DEFENSIVE_LINE = 9
    PRESSING_TRIGGER = 10
    DEFENSIVE_TRANSITION = 11
    TACKLING = 12
    TACTICAL_STYLE = 13
    MENTALITY = 14
    DEFENSIVE_LINE_BEHAVIOUR = 15
    GOALKEEPER_DISTRIBUTION_TARGET = 16
    GOALKEEPER_DISTRIBUTION_SPEED = 17
    PATIENCE = 18
    DRIBBLING = 19
    PASS_RECEPTION = 20
    TEMPO = 21
    CROSS_ENGAGEMENT = 22
    PREVENT_SHORT_GK_DISTRIBUTION = 23
    BUILD_UP_STRATEGY = 24
    PRESSING_TRAP = 25
    CROSSING_STYLE = 26
    SHOTS_FROM_DISTANCE = 27
    SUPPORTING_RUNS = 28
    GOAL_KICKS = 29
    PROGRESS_THROUGH = 30
    SUPPORTING_RUNS_SECONDARY = 31
