"""Clean-room representations of recovered FM26 playback wire records.

Field types, offsets and enum values come from the installed build's IL2CPP
metadata. These records model the public marshalling boundary, not internal
native simulation classes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum, IntFlag


TIME_SLICES_PER_SECOND = 4
COMMENTARY_EVENT_BASE = 8000
COMMENTARY_EVENT_COUNT = 1220
COMMENTARY_EVENT_LAST = COMMENTARY_EVENT_BASE + COMMENTARY_EVENT_COUNT - 1


@dataclass
class ObservedSetupRandom:
    """The 64-bit generator arithmetic observed in native setup code.

    This is deliberately kept separate from :class:`MatchEngine`: static
    evidence proves the recurrence during setup and its direct use by the
    native commentary/event-candidate gate, but does not prove that every
    gameplay decision consumes this stream.
    """

    state: int
    increment: int = 1

    MULTIPLIER = 0x5851F42D4C957F2D
    MASK64 = (1 << 64) - 1
    MASK32 = (1 << 32) - 1

    @classmethod
    def from_setup_seed(cls, seed: int) -> "ObservedSetupRandom":
        seed32 = seed & cls.MASK32
        state = (seed32 * 0xA4E7735A4C957F2D + 0x5851F42D4C957F2E) & cls.MASK64
        return cls(state=state, increment=1)

    def next_value_1_to_20(self) -> int:
        return ((self.next_uint32() * 0x13) >> 32) + 1

    def next_uint32(self) -> int:
        """Advance and return the raw rotated 32-bit output.

        The raw value is useful for the native commentary-candidate gate,
        which compares it directly against an observed threshold.  No generic
        probability API is exposed because the native call sites use different
        scales and contexts.
        """
        old = self.state & self.MASK64
        mixed = ((old >> 45) ^ (old >> 27)) & self.MASK32
        rotate = (old >> 59) & 0x1F
        rotated = ((mixed >> rotate) | (mixed << ((32 - rotate) & 31))) & self.MASK32
        self.state = (old * self.MULTIPLIER + self.increment) & self.MASK64
        return rotated


def native_commentary_event_id(fmf_event_index: int) -> int:
    """Translate the observed FMF selector index to its native event ID."""
    if not 0 <= fmf_event_index < COMMENTARY_EVENT_COUNT:
        raise ValueError(f"FMF commentary event index out of range: {fmf_event_index}")
    return COMMENTARY_EVENT_BASE + fmf_event_index


def fmf_commentary_event_index(native_event_id: int) -> int:
    """Translate an observed native commentary ID back to its FMF index."""
    index = native_event_id - COMMENTARY_EVENT_BASE
    if not 0 <= index < COMMENTARY_EVENT_COUNT:
        raise ValueError(f"native commentary event ID out of range: {native_event_id}")
    return index


def time_slice_from_seconds(seconds: int | float) -> int:
    """Observed replay conversion; live speed scaling is a separate boundary."""
    return int(seconds * TIME_SLICES_PER_SECOND)


def seconds_from_time_slice(time_slice: int) -> float:
    return time_slice / TIME_SLICES_PER_SECOND


class MatchStopReason(IntEnum):
    NOT_STOPPED = 0
    END_OF_PERIOD = 1
    SET_PIECE = 2
    START_OF_PERIOD = 3
    START_OF_GAME = 4
    END_OF_GAME = 5
    END_OF_CELEBRATION = 6
    PENALTY_AWARDED = 7


class SetPieceType(IntEnum):
    INVALID = 0
    CORNER = 1
    THROW_DEFENSIVE = 2
    THROW_MIDFIELD = 3
    THROW_ATTACKING = 4
    THROW_ATTACKING_FLAT_THROW = 5
    PENALTY = 6
    GOAL_KICK = 7
    FREE_KICK_SHOOTING_CHANCE = 8
    FREE_KICK_SMALL_CHANCE_OF_SHOT = 9
    FREE_KICK_CORNER_POSITION_POSSIBLE_SHOT = 10
    FREE_KICK_CORNER_POSITION = 11
    FREE_KICK_OPP_HALF = 12
    FREE_KICK_WIDE_QUITE_NEAR_OPP_GOAL = 13
    FREE_KICK_OWN_HALF_WIDE = 14
    FREE_KICK_OWN_HALF_CENTRAL = 15
    FREE_KICK_AS_GOAL_KICK = 16
    KICK_OFF = 17


class MatchPeriod(IntEnum):
    INVALID = -1
    KICK_OFF = 0
    HALF_TIME = 1
    EXTRA_TIME_KICK_OFF = 2
    EXTRA_TIME_HALF_TIME = 3
    PENALTIES = 4
    FULL_TIME = 5
    FIRST_HALF = 6
    SECOND_HALF = 7
    EXTRA_TIME_FIRST_HALF = 8
    EXTRA_TIME_SECOND_HALF = 9


class MatchStateFlags(IntFlag):
    NONE = 0
    SIMULATING = 1
    FINISHED = 2
    HIGHLIGHT_THREAD_AHEAD_ENOUGH = 4


class PluginMatchSetupFlags(IntFlag):
    NONE = 0
    VIEWING_PAST_MATCH = 1
    SPECTATING_MATCH = 2
    CATCHING_UP = 4
    DONT_USE_LICENSED_KITS = 8
    LOADING_PKM = 16


class ViewableMatchType(IntEnum):
    INVALID = -1
    MANAGING = 0
    SPECTATING = 1
    PAST = 2


class CompetitionType(IntEnum):
    UNKNOWN = 0
    INTERNATIONAL_FINALS = 1
    MAJOR_EURO = 2
    FRIENDLY = 3
    DOMESTIC_LEAGUE = 4
    DOMESTIC_CUP = 5
    SUPER_CUP = 6
    INTERNATIONAL_QUALIFIERS = 7
    RESERVES = 8
    MINOR_EURO = 9
    OTHER_INTERNATIONAL = 10


class SubCompetitionType(IntEnum):
    UNKNOWN = 0
    UEFA_CHAMPIONS_LEAGUE = 1
    UEFA_EUROPA_LEAGUE = 2
    UEFA_CONFERENCE_LEAGUE = 3
    UEFA_SUPER_CUP = 4
    PREMIER_LEAGUE = 5
    FIFA_WORLD_CUP = 6
    CLUB_FRIENDLY = 7
    INTERNATIONAL_FRIENDLY = 8


class StageType(IntEnum):
    UNKNOWN = 0
    FIRST_ROUND = 1
    SECOND_ROUND = 2
    THIRD_ROUND = 3
    FOURTH_ROUND = 4
    QUARTER_FINAL = 5
    SEMI_FINAL = 6
    THIRD_PLACE_PLAYOFF = 7
    FINAL = 8
    GROUP_STAGE = 9
    UCL_LEAGUE_PHASE = 10
    CUP_16TH_ROUND = 11


class TrophyType(IntEnum):
    NOT_SET = 0
    SILVER_PLATE = 1
    NATIONAL_CUP_3 = 2
    NATIONAL_CUP_2 = 3
    NATIONAL_CUP_1 = 4
    NATIONAL_CHAMPIONSHIP_3 = 5
    NATIONAL_CHAMPIONSHIP_2 = 6
    NATIONAL_CHAMPIONSHIP_1 = 7
    INTERNATIONAL_2 = 8
    INTERNATIONAL_1 = 9
    CONTINENTAL_2 = 10
    CONTINENTAL_1 = 11
    UEFA_CHAMPIONS_LEAGUE = 12
    UEFA_EUROPA_LEAGUE = 13
    UEFA_CONFERENCE_LEAGUE = 14
    UEFA_SUPER_CUP = 15
    FIFA_WORLD_CUP = 16


class MatchGender(IntEnum):
    MALE = 0
    FEMALE = 1


class PrecipitationType(IntEnum):
    DRY = 0
    WET = 1
    DRIZZLE = 2
    SHOWER = 3
    RAIN = 4
    DOWNPOUR = 5
    SLEET = 6
    HAIL = 7
    LIGHT_SNOW = 8
    HEAVY_SNOW = 9
    MAX = 10


class EntityKind(IntEnum):
    UNUSED = -1
    PLAYER = 0
    REFEREE = 1
    ASSISTANT_REFEREE = 2
    MANAGER = 3
    DOCTOR = 4
    PHYSIO = 5
    STRETCHER_BEARER = 6


class MatchClientStatus(IntEnum):
    INVALID = 0
    IDLE = 1
    WAITING = 2
    DISCONNECTED = 3
    WATCHING_MATCH = 4


class CrowdMood(IntEnum):
    IDLE_NEUTRAL = 0
    IDLE_MUTED = 1
    IDLE_UNHAPPY = 2
    IDLE_HAPPY = 3
    IDLE_VERY_HAPPY = 4
    IDLE_DISAPPOINTED = 5
    IDLE_EXCITED = 6
    IDLE_ANGRY = 7
    IDLE_FRUSTRATED = 8
    CELEBRATING = 9
    CELEBRATING_WILDLY = 10
    MINOR_APPRECIATION = 11
    MAJOR_APPRECIATION = 12
    ANGRY = 13
    VERY_ANGRY = 14
    ENCOURAGING = 15
    FRUSTRATION = 16
    MISSED_CHANCE = 17
    CONCEDE_VITAL_GOAL = 18
    CONCEDE_NON_VITAL_GOAL = 19
    ANTICIPATION = 20
    DISAPPOINTMENT = 21
    DISTRACTION = 22
    NERVOUS = 23
    GOADING = 24
    SINGING = 25


class BillboardFlags(IntFlag):
    NONE = 0
    SHOW_INFO = 1
    IS_SUB = 2
    HAS_YELLOW_CARD = 4
    HAS_RED_CARD = 8
    HAS_SLIGHT_INJURY = 16
    HAS_SERIOUS_INJURY = 32


class MatchEventPlayerTeams(IntFlag):
    NONE = 0
    VISITOR_TEAM_PLAYER1 = 1
    VISITOR_TEAM_PLAYER2 = 2
    VISITOR_TEAM_PLAYER3 = 4
    VISITOR_TEAM_PLAYER4 = 8
    VISITOR_TEAM_PLAYER5 = 16
    VISITOR_TEAM_PLAYER6 = 32


class CommentaryEventFlags(IntFlag):
    NONE = 0
    FLASHING = 1
    IS_CARD = 2
    SKIPPABLE = 4
    IS_END_OF_PERIOD = 8


class CommentaryImportance(IntEnum):
    VERY_LOW = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4
    MUST_SHOW = 5


class IncidentImportance(IntEnum):
    SKIPPABLE = 0
    BASIC_EVENTS = 1
    POSSIBLE_EVENTS = 2
    EXTENDED_EVENTS = 3
    MAIN_EVENTS = 4
    MAJOR_EVENTS = 5
    ESSENTIAL_EVENTS = 6
    GOAL_ACTION = 7
    GOALS = 8


class NativeCommentaryEvent(IntEnum):
    """Verified IDs used by the prototype; the native table contains 1,220."""

    WAIT = 8000
    BALL_GOES_LOOSE = 8001
    LOSE_CONTROL_OF_BALL = 8002
    MOVE_ONTO_PASS = 8007
    RUN_WITH_BALL = 8011
    PLAYER_INJURED_FORCED_OFF = 8022
    PLAYER_INJURED_SENT_OFF = 8023
    PLAYER_INJURED_GOES_ON = 8024
    SUBSTITUTION = 8027
    ATTEMPT_PASS_CHIP = 8039
    ATTEMPT_PASS_CROSS = 8040
    ATTEMPT_PASS_FLOOR = 8041
    ATTEMPT_PASS_LONG_HIGH = 8042
    ATTEMPT_PASS_LONG_MID = 8043
    PASS_IT = 8050
    KICK_OFF = 8052
    RESTART_CORNER = 8053
    RESTART_THROW_IN = 8054
    RESTART_GOAL_KICK = 8055
    RESTART_OFFSIDE = 8056
    RESTART_FREE_KICK = 8057
    RESTART_PENALTY = 8058
    TAKE_CORNER = 8064
    DEFAULT_SHOT = 8065
    SHOT_DEFLECTED_WIDE = 8066
    SHOT_DEFLECTED = 8068
    GOAL_ONE = 8142
    GOAL = 8142
    OWN_GOAL = 8143
    MISSED_PENALTY = 8144
    SCORED_PENALTY = 8145
    GOALKEEPER_HELD = 8165
    FOUL = 8169
    SECOND_YELLOW_CARD = 8183
    SENT_OFF = 8184
    YELLOW_CARD = 8185
    FINAL_WHISTLE = 8194


class BallContactID(IntEnum):
    NONE = 0
    CROSSBAR = 1
    POST = 2
    GROUND = 3
    DUGOUT = 4
    AD_HOARDING = 5
    CORNER_FLAG = 6
    NET_INSIDE = 7
    NET_OUTSIDE = 8
    SAVE = 9
    DEFLECTION = 10
    HEADER = 11
    KICK = 12
    THROW = 13


class AnimationMatchID(IntEnum):
    """Managed `SI.Match.Anim.MatchID`; the shipped enum exposes only None."""

    NONE = 255


@dataclass(frozen=True)
class NativePluginMatchSetupConfig:
    """Recovered setup call input, including the native PKM byte span."""

    flags: PluginMatchSetupFlags
    user_team_id: int
    pkm_bytes_address: int
    pkm_byte_count: int

    # Recovered offsets: flags 0x00, team 0x08, pointer 0x10, count 0x18.
    FORMAT = struct.Struct("<I4xb7xQi4x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            int(self.flags), self.user_team_id, self.pkm_bytes_address,
            self.pkm_byte_count,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativePluginMatchSetupConfig":
        flags, team, address, count = cls.FORMAT.unpack(data)
        return cls(PluginMatchSetupFlags(flags), team, address, count)


@dataclass(frozen=True)
class NativeMatchHandle:
    """Managed `MatchHandle` value type (`ulong`, with zero invalid)."""

    value: int

    FORMAT = struct.Struct("<Q")
    INVALID = 0

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("MatchHandle must fit an unsigned 64-bit value")

    @property
    def is_valid(self) -> bool:
        return self.value != self.INVALID

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.value)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchHandle":
        return cls(cls.FORMAT.unpack(data)[0])


@dataclass(frozen=True)
class NativePluginMatchSetup:
    """Recovered result of the public native match setup call."""

    handle: int
    match_engine_version: int
    match_version: int
    entity_count: int

    # MatchHandle is a ulong; the struct retains its trailing 8-byte alignment.
    FORMAT = struct.Struct("<QIIi4x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.handle, self.match_engine_version, self.match_version,
            self.entity_count,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativePluginMatchSetup":
        return cls(*cls.FORMAT.unpack(data))


@dataclass(frozen=True)
class NativeMatchInfo:
    viewable_match_type: ViewableMatchType
    competition_type: CompetitionType
    sub_competition_type: SubCompetitionType
    stage_type: StageType
    trophy_type: TrophyType
    match_gender: MatchGender
    competition_year: int
    guard_of_honour_team_id: int
    trophy_presentation_team_id: int
    last_home_match_of_season_team_id: int
    winning_team_id: int
    user_team_id: int

    FORMAT = struct.Struct("<5b3xiH5bx")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            int(self.viewable_match_type), int(self.competition_type),
            int(self.sub_competition_type), int(self.stage_type),
            int(self.trophy_type), int(self.match_gender), self.competition_year,
            self.guard_of_honour_team_id, self.trophy_presentation_team_id,
            self.last_home_match_of_season_team_id, self.winning_team_id,
            self.user_team_id,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchInfo":
        values = cls.FORMAT.unpack(data)
        return cls(
            ViewableMatchType(values[0]), CompetitionType(values[1]),
            SubCompetitionType(values[2]), StageType(values[3]),
            TrophyType(values[4]), MatchGender(values[5]), *values[6:],
        )


@dataclass(frozen=True)
class NativeUniqueIds:
    """Exact `UniqueIds` result returned for a match handle."""

    team_unique_id: int
    parent_comp_unique_id: int
    sub_comp_unique_id: int
    nation_unique_id: int
    match_unique_id: int

    FORMAT = struct.Struct("<4iq")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.team_unique_id, self.parent_comp_unique_id,
            self.sub_comp_unique_id, self.nation_unique_id,
            self.match_unique_id,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeUniqueIds":
        return cls(*cls.FORMAT.unpack(data))


@dataclass(frozen=True)
class NativeCrowdKitSetup:
    """Exact crowd-shirt colours and style returned per crowd kit."""

    shirt_background_color: tuple[float, float, float, float]
    shirt_foreground_color: tuple[float, float, float, float]
    shirt_outline_color: tuple[float, float, float, float]
    shirt_style: int

    FORMAT = struct.Struct("<12fb3x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            *self.shirt_background_color, *self.shirt_foreground_color,
            *self.shirt_outline_color, self.shirt_style,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeCrowdKitSetup":
        values = cls.FORMAT.unpack(data)
        return cls(tuple(values[:4]), tuple(values[4:8]), tuple(values[8:12]), values[12])


@dataclass(frozen=True)
class NativeStadiumColouringData:
    """Exact team, stadium and competition colour payload."""

    home_team_unique_id: int
    home_team_container_unique_id: int
    home_team_logo_number: int
    home_team_background_colour: tuple[float, float, float, float]
    home_team_foreground_colour: tuple[float, float, float, float]
    home_team_outline_colour: tuple[float, float, float, float]
    away_team_unique_id: int
    away_team_container_unique_id: int
    away_team_logo_number: int
    away_team_background_colour: tuple[float, float, float, float]
    away_team_foreground_colour: tuple[float, float, float, float]
    away_team_outline_colour: tuple[float, float, float, float]
    stadium_primary_colour: tuple[float, float, float, float]
    stadium_secondary_colour: tuple[float, float, float, float]
    competition_id: int
    competition_primary_colour: tuple[float, float, float, float]
    competition_secondary_colour: tuple[float, float, float, float]
    competition_tertiary_colour: tuple[float, float, float, float]

    FORMAT = struct.Struct("<3I12f3I12f8fI12f")

    def pack(self) -> bytes:
        values: list[object] = [
            self.home_team_unique_id, self.home_team_container_unique_id,
            self.home_team_logo_number, *self.home_team_background_colour,
            *self.home_team_foreground_colour, *self.home_team_outline_colour,
            self.away_team_unique_id, self.away_team_container_unique_id,
            self.away_team_logo_number, *self.away_team_background_colour,
            *self.away_team_foreground_colour, *self.away_team_outline_colour,
            *self.stadium_primary_colour, *self.stadium_secondary_colour,
            self.competition_id, *self.competition_primary_colour,
            *self.competition_secondary_colour, *self.competition_tertiary_colour,
        ]
        return self.FORMAT.pack(*values)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeStadiumColouringData":
        values = cls.FORMAT.unpack(data)
        return cls(
            values[0], values[1], values[2], tuple(values[3:7]),
            tuple(values[7:11]), tuple(values[11:15]), values[15], values[16],
            values[17], tuple(values[18:22]), tuple(values[22:26]),
            tuple(values[26:30]), tuple(values[30:34]), tuple(values[34:38]),
            values[38], tuple(values[39:43]), tuple(values[43:47]),
            tuple(values[47:51]),
        )


@dataclass(frozen=True)
class NativeMatchOutsideEnvironmentSetup:
    seed: int
    region_id: int
    city_population: int

    FORMAT = struct.Struct("<ibi3x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.seed, self.region_id, self.city_population)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchOutsideEnvironmentSetup":
        return cls(*cls.FORMAT.unpack(data))


@dataclass(frozen=True)
class NativeMatchStadiumLocationSetup:
    longitude: float
    latitude: float
    orientation: float
    altitude: float
    time_zone: float

    FORMAT = struct.Struct("<5f")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.longitude, self.latitude, self.orientation,
            self.altitude, self.time_zone,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchStadiumLocationSetup":
        return cls(*cls.FORMAT.unpack(data))


@dataclass(frozen=True)
class NativePitchSetupInfo:
    pitch_length: float
    pitch_width: float
    wetness_strength: float
    pitch_condition_rating: int
    precipitation_type: PrecipitationType
    pitch_type: int
    pitch_pattern: int
    has_under_soil_heating: int

    FORMAT = struct.Struct("<fffh4B2x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.pitch_length, self.pitch_width, self.wetness_strength,
            self.pitch_condition_rating, int(self.precipitation_type),
            self.pitch_type, self.pitch_pattern, self.has_under_soil_heating,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativePitchSetupInfo":
        values = cls.FORMAT.unpack(data)
        return cls(*values[:4], PrecipitationType(values[4]), *values[5:])


@dataclass(frozen=True)
class NativeMatchLightingAndWeatherSetup:
    day: int
    time: float
    precipitation_type: PrecipitationType
    precipitation_chance: float
    precipitation_intensity: float
    temperature: float
    wind_strength: float
    wind_direction: tuple[float, float, float]
    fog_density: float
    fog_falloff: float

    FORMAT = struct.Struct("<ififfff3fff")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.day, self.time, int(self.precipitation_type),
            self.precipitation_chance, self.precipitation_intensity,
            self.temperature, self.wind_strength, *self.wind_direction,
            self.fog_density, self.fog_falloff,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchLightingAndWeatherSetup":
        values = cls.FORMAT.unpack(data)
        return cls(
            values[0], values[1], PrecipitationType(values[2]), *values[3:7],
            tuple(values[7:10]), values[10], values[11],
        )


@dataclass(frozen=True)
class NativeStandSetupInfo:
    capacity: int
    age: int
    has_roof: int
    is_under_renovation: int

    FORMAT = struct.Struct("<ii2b2x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.capacity, self.age, self.has_roof, self.is_under_renovation,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeStandSetupInfo":
        return cls(*cls.FORMAT.unpack(data))


@dataclass(frozen=True)
class NativeStadiumSetupInfo:
    stadium_capacity: int
    stadium_id: int
    attendance: int
    home_fans_count: int
    away_fans_count: int
    stadium_age: int
    gap_to_stands: float
    uses_seats_only: int
    has_digital_ad_hoardings: int
    has_virtual_assistant_referee_stand: int
    is_enclosed: int
    stands: tuple[NativeStandSetupInfo, ...]
    primary_seat_color: tuple[float, float, float, float]
    secondary_seat_color: tuple[float, float, float, float]

    FORMAT = struct.Struct(
        "<6if4b" + "ii2b2x" * 8 + "8f"
    )

    def __post_init__(self) -> None:
        if len(self.stands) != 8:
            raise ValueError("StadiumSetupInfo requires exactly eight stands")

    def pack(self) -> bytes:
        values: list[object] = [
            self.stadium_capacity, self.stadium_id, self.attendance,
            self.home_fans_count, self.away_fans_count, self.stadium_age,
            self.gap_to_stands, self.uses_seats_only,
            self.has_digital_ad_hoardings,
            self.has_virtual_assistant_referee_stand, self.is_enclosed,
        ]
        for stand in self.stands:
            values.extend((stand.capacity, stand.age, stand.has_roof, stand.is_under_renovation))
        values.extend((*self.primary_seat_color, *self.secondary_seat_color))
        return self.FORMAT.pack(*values)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeStadiumSetupInfo":
        values = cls.FORMAT.unpack(data)
        stands = tuple(
            NativeStandSetupInfo(*values[11 + i * 4:15 + i * 4]) for i in range(8)
        )
        return cls(
            *values[:7], *values[7:11], stands,
            tuple(values[43:47]), tuple(values[47:51]),
        )


@dataclass(frozen=True)
class NativeMatchStadiumSetup:
    pitch: NativePitchSetupInfo
    stadium: NativeStadiumSetupInfo

    FORMAT = struct.Struct("<180s")
    SIZE = 0xB4

    def pack(self) -> bytes:
        return self.pitch.pack() + self.stadium.pack()

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchStadiumSetup":
        if len(data) != cls.SIZE:
            raise ValueError(f"MatchStadiumSetup must be exactly {cls.SIZE} bytes")
        return cls(
            NativePitchSetupInfo.unpack(data[:0x14]),
            NativeStadiumSetupInfo.unpack(data[0x14:]),
        )


@dataclass(frozen=True)
class NativePlayerKitSetup:
    """Opaque exact player-kit payload; field offsets are recovered separately."""

    raw: bytes

    SIZE = 0xD4

    def __post_init__(self) -> None:
        if len(self.raw) != self.SIZE:
            raise ValueError(f"PlayerKitSetup must be exactly {self.SIZE} bytes")

    def fields(self) -> dict[str, object]:
        """Decode the explicitly declared PlayerKitSetup fields."""
        styles = struct.unpack_from("<4b", self.raw, 0)
        names = (
            "shorts_style", "socks_style", "shirt_style", "back_of_shirt_type",
        )
        result: dict[str, object] = dict(zip(names, styles))
        colors = (
            "shirt_background_color", "shirt_foreground_color", "shirt_outline_color",
            "shirt_number_color", "shirt_number_outline_color", "shorts_background_color",
            "shorts_foreground_color", "socks_background_color", "socks_foreground_color",
            "icon_background_color", "icon_foreground_color", "icon_outline_color",
            "icon_number_color",
        )
        for index, name in enumerate(colors):
            result[name] = struct.unpack_from("<4f", self.raw, 4 + index * 0x10)
        return result


@dataclass(frozen=True)
class NativeTeamKitSetup:
    """Opaque exact team-kit payload with its recovered 0x200-byte stride."""

    raw: bytes

    SIZE = 0x200

    def __post_init__(self) -> None:
        if len(self.raw) != self.SIZE:
            raise ValueError(f"TeamKitSetup must be exactly {self.SIZE} bytes")

    def fields(self) -> dict[str, object]:
        """Decode the explicit TeamKitSetup fields, retaining nested kits."""
        result: dict[str, object] = {"kit_type": struct.unpack_from("<b", self.raw, 0)[0]}
        result["player_kit"] = NativePlayerKitSetup(self.raw[0x04:0xD8]).fields()
        result["goalkeeper_kit"] = NativePlayerKitSetup(self.raw[0xD8:0x1AC]).fields()
        colors = (
            "title_background_color", "title_foreground_color", "title_outline_color",
            "sub_shirt_background_color",
        )
        for index, name in enumerate(colors):
            result[name] = struct.unpack_from("<4f", self.raw, 0x1AC + index * 0x10)
        result["team_id"] = struct.unpack_from("<q", self.raw, 0x1F0)[0]
        result["is_winner_of_current_competition"] = bool(self.raw[0x1F8])
        result["dont_use_licensed_kits"] = bool(self.raw[0x1F9])
        return result


@dataclass(frozen=True)
class NativeRefereeKitSetup:
    raw: bytes

    SIZE = 0x20

    def __post_init__(self) -> None:
        if len(self.raw) != self.SIZE:
            raise ValueError(f"RefereeKitSetup must be exactly {self.SIZE} bytes")

    def fields(self) -> dict[str, tuple[float, float, float, float]]:
        return {
            "shirt_background_color": struct.unpack_from("<4f", self.raw, 0),
            "shirt_foreground_color": struct.unpack_from("<4f", self.raw, 0x10),
        }


@dataclass(frozen=True)
class NativeMatchEnvironmentSetup:
    home_team_kit: NativeTeamKitSetup
    away_team_kit: NativeTeamKitSetup
    referee_kit: NativeRefereeKitSetup

    FORMAT = struct.Struct("<512s512s32s")
    SIZE = 0x420

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.home_team_kit.raw, self.away_team_kit.raw, self.referee_kit.raw,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchEnvironmentSetup":
        home, away, referee = cls.FORMAT.unpack(data)
        return cls(NativeTeamKitSetup(home), NativeTeamKitSetup(away), NativeRefereeKitSetup(referee))


@dataclass(frozen=True)
class NativeAppearanceData:
    """Opaque but exact `AppearanceData` payload (0xe8 bytes)."""

    raw: bytes

    SIZE = 0xE8

    def __post_init__(self) -> None:
        if len(self.raw) != self.SIZE:
            raise ValueError(f"AppearanceData must be exactly {self.SIZE} bytes")

    _SBYTE_FIELDS = {
        "age": 0x00, "ethnicity": 0x01, "gender_index": 0x02,
        "hair_length": 0x03, "cosmetic_blush_index": 0x0C,
        "cosmetic_contour_index": 0x0D, "cosmetic_eyeliner_index": 0x0E,
        "cosmetic_eyeshadow_index": 0x0F, "cosmetic_facial_mark_index": 0x10,
        "cosmetic_face_paint_index": 0x11, "cosmetic_face_paint_colour_first_index": 0x12,
        "cosmetic_face_paint_colour_second_index": 0x13,
        "cosmetic_face_paint_colour_third_index": 0x14, "cosmetic_lipstick_index": 0x15,
        "face_detail_index": 0x16, "outfit_torso_index": 0x17,
        "outfit_legs_index": 0x18, "outfit_feet_index": 0x19,
        "outfit_torso_colour_index": 0x1A, "outfit_torso_colour_secondary_index": 0x1B,
        "outfit_torso_colour_tertiary_index": 0x1C, "outfit_legs_colour_index": 0x1D,
        "outfit_feet_colour_index": 0x1E, "outfit_accessory_left_earring_index": 0x1F,
        "outfit_accessory_left_earring_colour_index": 0x20,
        "outfit_accessory_left_earring_jewel_colour_index": 0x21,
        "outfit_accessory_left_hearing_device_index": 0x22,
        "outfit_accessory_left_hearing_device_base_colour_index": 0x23,
        "outfit_accessory_left_hearing_device_wire_colour_index": 0x24,
        "outfit_accessory_left_hearing_device_over_ear_colour_index": 0x25,
        "outfit_accessory_right_earring_index": 0x26,
        "outfit_accessory_right_earring_colour_index": 0x27,
        "outfit_accessory_right_earring_jewel_colour_index": 0x28,
        "outfit_accessory_right_hearing_device_index": 0x29,
        "outfit_accessory_right_hearing_device_base_colour_index": 0x2A,
        "outfit_accessory_right_hearing_device_wire_colour_index": 0x2B,
        "outfit_accessory_right_hearing_device_over_ear_colour_index": 0x2C,
        "outfit_accessory_left_wristwear_index": 0x2D,
        "outfit_accessory_left_wristwear_colour_index": 0x2E,
        "outfit_accessory_left_wristwear_highlight_colour_index": 0x2F,
        "outfit_accessory_right_wristwear_index": 0x30,
        "outfit_accessory_right_wristwear_colour_index": 0x31,
        "outfit_accessory_right_wristwear_highlight_colour_index": 0x32,
        "outfit_accessory_glasses_index": 0x33, "outfit_accessory_glasses_colour_index": 0x34,
        "outfit_accessory_eyepatch_index": 0x35, "outfit_accessory_eyepatch_side_index": 0x36,
        "outfit_accessory_eyepatch_colour_index": 0x37,
        "outfit_accessory_eyepatch_colour_accent_index": 0x38,
        "outfit_accessory_lapel_index": 0x39, "outfit_accessory_neck_index": 0x3A,
        "outfit_accessory_neck_colour_index": 0x3B,
        "outfit_accessory_neck_pendant_colour_index": 0x3C,
        "outfit_accessory_left_index_finger_index": 0x3D,
        "outfit_accessory_left_index_finger_colour_index": 0x3E,
        "outfit_accessory_left_index_finger_jewel_colour_index": 0x3F,
        "outfit_accessory_left_middle_finger_index": 0x40,
        "outfit_accessory_left_middle_finger_colour_index": 0x41,
        "outfit_accessory_left_middle_finger_jewel_colour_index": 0x42,
        "outfit_accessory_left_ring_finger_index": 0x43,
        "outfit_accessory_left_ring_finger_colour_index": 0x44,
        "outfit_accessory_left_ring_finger_jewel_colour_index": 0x45,
        "outfit_accessory_left_little_finger_index": 0x46,
        "outfit_accessory_left_little_finger_colour_index": 0x47,
        "outfit_accessory_left_little_finger_jewel_colour_index": 0x48,
        "outfit_accessory_right_index_finger_index": 0x49,
        "outfit_accessory_right_index_finger_colour_index": 0x4A,
        "outfit_accessory_right_index_finger_jewel_colour_index": 0x4B,
        "outfit_accessory_right_middle_finger_index": 0x4C,
        "outfit_accessory_right_middle_finger_colour_index": 0x4D,
        "outfit_accessory_right_middle_finger_jewel_colour_index": 0x4E,
        "outfit_accessory_right_ring_finger_index": 0x4F,
        "outfit_accessory_right_ring_finger_colour_index": 0x50,
        "outfit_accessory_right_ring_finger_jewel_colour_index": 0x51,
        "outfit_accessory_right_little_finger_index": 0x52,
        "outfit_accessory_right_little_finger_colour_index": 0x53,
        "outfit_accessory_right_little_finger_jewel_colour_index": 0x54,
        "eyebrow_index": 0x55, "eyebrow_colour_index": 0x56,
        "eye_colour_index": 0x57, "facial_hair_index": 0x58,
        "facial_hair_colour_index": 0x59, "hair_index": 0x5A,
        "hair_colour_index": 0x5B, "skin_tone_index": 0x5C,
    }
    _FLOAT_FIELDS = {
        "height_meters": 0x04, "weight_kilograms": 0x08,
        "brow_height": 0x60, "brow_length": 0x64, "cheek_bone_height": 0x68,
        "cheek_width": 0x6C, "cheek_shape": 0x70, "chin_height": 0x74,
        "chin_length": 0x78, "chin_width": 0x7C, "ear_angle": 0x80,
        "eye_size": 0x84, "jaw_shape": 0x88, "jaw_width": 0x8C,
        "lip_height": 0x90, "lip_pout": 0x94, "lip_thickness": 0x98,
        "lip_width": 0x9C, "nose_height": 0xA0, "nose_length": 0xA4,
        "nose_tip": 0xA8, "nose_width": 0xAC, "weight_morph": 0xB0,
        "eye_size_eyelashes": 0xB4, "eye_width": 0xB8, "eye_height": 0xBC,
        "jaw_height": 0xC0, "jaw_depth": 0xC4, "skull_height": 0xC8,
        "forehead_depth": 0xCC, "african_face_a": 0xD0,
        "south_asian_face_a": 0xD4, "european_face_a": 0xD8,
        "asian_face_a": 0xDC, "age_morph": 0xE0,
    }

    def fields(self) -> dict[str, int | float]:
        """Decode all named fields declared by the managed struct."""
        result: dict[str, int | float] = {
            name: struct.unpack_from("<b", self.raw, offset)[0]
            for name, offset in self._SBYTE_FIELDS.items()
        }
        result.update({
            name: struct.unpack_from("<f", self.raw, offset)[0]
            for name, offset in self._FLOAT_FIELDS.items()
        })
        result["outfit_tendency"] = self.raw[0xE4]
        return result


@dataclass(frozen=True)
class NativeMatchEntitySetup:
    """Exact entity record; pointer fields and appearance remain opaque."""

    kind: EntityKind
    skin_tone: int
    is_male: bool
    is_captain: bool
    is_wearing_tracksuit: bool
    hair_colour: tuple[float, float, float, float]
    height_metres: float
    weight_kilograms: float
    shirt_name_address: int
    billboard_name_address: int
    shirt_number: int
    is_wearing_goalkeeper_kit: bool
    is_wearing_arm_cast: bool
    is_wearing_elbow_support: bool
    is_wearing_face_mask: bool
    is_wearing_head_bandage: bool
    is_wearing_hijab: bool
    team_index: int
    unique_id: int
    is_regenerated: bool
    is_human: bool
    appearance: NativeAppearanceData

    FORMAT = struct.Struct("<BB3B3x4f2fQQi6Bbxi2B2x232s")
    # Cpp2IL's managed sequential record is 0x12c bytes.  The native exported
    # layout-signature routine reports a 0x130-byte enclosing record, so keep
    # the ABI padding explicit without silently changing the managed payload.
    NATIVE_SIGNATURE_SIZE = 0x130

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            int(self.kind), self.skin_tone, self.is_male, self.is_captain,
            self.is_wearing_tracksuit, *self.hair_colour, self.height_metres,
            self.weight_kilograms, self.shirt_name_address,
            self.billboard_name_address, self.shirt_number,
            self.is_wearing_goalkeeper_kit, self.is_wearing_arm_cast,
            self.is_wearing_elbow_support, self.is_wearing_face_mask,
            self.is_wearing_head_bandage, self.is_wearing_hijab, self.team_index,
            self.unique_id, self.is_regenerated, self.is_human, self.appearance.raw,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchEntitySetup":
        values = cls.FORMAT.unpack(data)
        return cls(
            EntityKind(values[0]), values[1], bool(values[2]), bool(values[3]),
            bool(values[4]), tuple(values[5:9]), values[9], values[10],
            values[11], values[12], values[13], *map(bool, values[14:20]),
            values[20], values[21], bool(values[22]), bool(values[23]),
            NativeAppearanceData(values[24]),
        )


@dataclass(frozen=True)
class NativeBillboardInfo:
    unique_id: int
    billboard_flags: BillboardFlags

    FORMAT = struct.Struct("<iI")

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.unique_id, int(self.billboard_flags))

    @classmethod
    def unpack(cls, data: bytes) -> "NativeBillboardInfo":
        unique_id, flags = cls.FORMAT.unpack(data)
        return cls(unique_id, BillboardFlags(flags))


@dataclass(frozen=True)
class NativeInternalEventRecord:
    """Opaque 0x28-byte record observed in the native event/timeline queue.

    ``FUN_1822ece40`` allocates this record before the public 0x2c
    ``NativeMatchEvent`` serializer runs.  The pointers are process-local
    payloads and the byte fields have not been assigned enum meanings, so this
    type intentionally exposes only verified offsets and neutral names.
    """

    raw: bytes

    SIZE = 0x28

    def __post_init__(self) -> None:
        if len(self.raw) != self.SIZE:
            raise ValueError(f"internal event record must be exactly {self.SIZE} bytes")

    @property
    def payload_pointer_0(self) -> int:
        return struct.unpack_from("<Q", self.raw, 0x00)[0]

    @property
    def payload_pointer_8(self) -> int:
        return struct.unpack_from("<Q", self.raw, 0x08)[0]

    @property
    def value_i32_10(self) -> int:
        return struct.unpack_from("<i", self.raw, 0x10)[0]

    @property
    def value_i32_14(self) -> int:
        return struct.unpack_from("<i", self.raw, 0x14)[0]

    @property
    def time_like_i32_18(self) -> int:
        return struct.unpack_from("<i", self.raw, 0x18)[0]

    @property
    def opaque_bytes_1c_22(self) -> bytes:
        return self.raw[0x1C:0x23]


@dataclass(frozen=True)
class NativeMatchEvent:
    player_ids: tuple[int, int, int, int, int, int]
    player_teams: MatchEventPlayerTeams
    commentary_event: int
    time_slice: int
    duration_time_slices: int
    flags: CommentaryEventFlags
    commentary_importance: CommentaryImportance
    incident_importance: IncidentImportance
    data1: int

    FORMAT = struct.Struct("<6iBxH2i3Bx i".replace(" ", ""))

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            *self.player_ids, int(self.player_teams), self.commentary_event,
            self.time_slice, self.duration_time_slices, int(self.flags),
            int(self.commentary_importance), int(self.incident_importance), self.data1,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchEvent":
        values = cls.FORMAT.unpack(data)
        return cls(
            tuple(values[:6]), MatchEventPlayerTeams(values[6]), values[7], values[8], values[9],
            CommentaryEventFlags(values[10]), CommentaryImportance(values[11]),
            IncidentImportance(values[12]), values[13],
        )

    def as_dict(self) -> dict[str, object]:
        """Expose recovered wire fields without assigning event meaning."""
        return {
            "player_ids": list(self.player_ids),
            "player_teams": int(self.player_teams),
            "commentary_event": self.commentary_event,
            "time_slice": self.time_slice,
            "duration_time_slices": self.duration_time_slices,
            "flags": int(self.flags),
            "commentary_importance": int(self.commentary_importance),
            "incident_importance": int(self.incident_importance),
            "data1": self.data1,
        }

    @classmethod
    def unpack_many(cls, data: bytes) -> tuple["NativeMatchEvent", ...]:
        """Decode a contiguous native event update without interpreting it."""
        if len(data) % cls.FORMAT.size:
            raise ValueError("native MatchEvent buffer is not record-aligned")
        return tuple(
            cls.unpack(data[offset:offset + cls.FORMAT.size])
            for offset in range(0, len(data), cls.FORMAT.size)
        )


@dataclass(frozen=True)
class ManagedCommentaryEvent:
    """Exact managed ``FM.Match.MatchCommentaryEvent`` value carrier.

    This is deliberately separate from :class:`NativeMatchEvent`.  The
    shipped managed layer adds localized present/past text and a contributor
    time slice while translating the native record.  The recovered IL does
    not expose the SIMD copy that fills those values, so callers must supply
    them explicitly; this type never invents defaults for an unavailable
    native field.
    """

    text_present: tuple[str, ...]
    text_past: tuple[str, ...]
    player_unique_ids: tuple[int, ...]
    player_teams: MatchEventPlayerTeams
    time_slice: int
    duration: int
    contributor_time_slice: int
    commentary_event: int
    flags: CommentaryEventFlags
    commentary_importance: CommentaryImportance
    incident_importance: IncidentImportance
    data1: int

    def __post_init__(self) -> None:
        if len(self.player_unique_ids) != 6:
            raise ValueError("managed commentary events carry exactly six player IDs")

    @classmethod
    def from_native(
        cls,
        record: NativeMatchEvent,
        *,
        text_present: tuple[str, ...],
        text_past: tuple[str, ...],
        contributor_time_slice: int,
    ) -> "ManagedCommentaryEvent":
        """Translate only fields proven common to native and managed records.

        Text and contributor timing are required keyword arguments because
        they are not present in the 0x2c native wire record.
        """
        return cls(
            text_present=text_present,
            text_past=text_past,
            player_unique_ids=record.player_ids,
            player_teams=record.player_teams,
            time_slice=record.time_slice,
            duration=record.duration_time_slices,
            contributor_time_slice=contributor_time_slice,
            commentary_event=record.commentary_event,
            flags=record.flags,
            commentary_importance=record.commentary_importance,
            incident_importance=record.incident_importance,
            data1=record.data1,
        )

    def as_dict(self) -> dict[str, object]:
        """Return the managed field names, retaining all recovered values."""
        return {
            "text_present": list(self.text_present),
            "text_past": list(self.text_past),
            "player_unique_ids": list(self.player_unique_ids),
            "player_teams": int(self.player_teams),
            "time_slice": self.time_slice,
            "duration": self.duration,
            "contributor_time_slice": self.contributor_time_slice,
            "commentary_event": self.commentary_event,
            "flags": int(self.flags),
            "commentary_importance": int(self.commentary_importance),
            "incident_importance": int(self.incident_importance),
            "data1": self.data1,
        }


@dataclass(frozen=True)
class NativeStopTimeInfo:
    stop_time_slice: int
    next_stop_reason: MatchStopReason
    set_piece_type: SetPieceType

    FORMAT = struct.Struct("<iBB2x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.stop_time_slice, self.next_stop_reason, self.set_piece_type)

    def as_dict(self) -> dict[str, object]:
        return {
            "stop_time_slice": self.stop_time_slice,
            "next_stop_reason": int(self.next_stop_reason),
            "set_piece_type": int(self.set_piece_type),
        }

    @classmethod
    def unpack(cls, data: bytes) -> "NativeStopTimeInfo":
        time_slice, reason, set_piece = cls.FORMAT.unpack(data)
        return cls(time_slice, MatchStopReason(reason), SetPieceType(set_piece))

    @classmethod
    def unpack_many(cls, data: bytes) -> tuple["NativeStopTimeInfo", ...]:
        """Decode a contiguous native stop-time update without interpretation."""
        if len(data) % cls.FORMAT.size:
            raise ValueError("native StopTimeInfo buffer is not record-aligned")
        return tuple(
            cls.unpack(data[offset:offset + cls.FORMAT.size])
            for offset in range(0, len(data), cls.FORMAT.size)
        )


@dataclass(frozen=True)
class NativeMatchState:
    flags: MatchStateFlags
    time_slice: int
    catching_up_to_time_slice: int
    time: float
    injury_time: int
    period: MatchPeriod
    home_crowd_mood: int
    away_crowd_mood: int
    home_goals: int
    away_goals: int
    match_events_update_size: int
    stop_time_infos_update_size: int

    FORMAT = struct.Struct("<Iii fi 5b3x II".replace(" ", ""))

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            int(self.flags), self.time_slice, self.catching_up_to_time_slice,
            self.time, self.injury_time, int(self.period), self.home_crowd_mood,
            self.away_crowd_mood, self.home_goals, self.away_goals,
            self.match_events_update_size, self.stop_time_infos_update_size,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchState":
        values = cls.FORMAT.unpack(data)
        return cls(
            MatchStateFlags(values[0]), values[1], values[2], values[3], values[4],
            MatchPeriod(values[5]), *values[6:],
        )


@dataclass(frozen=True)
class NativeBallContact:
    time: float
    position: tuple[float, float, float]
    contact_id: BallContactID

    FORMAT = struct.Struct("<4fi")

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.time, *self.position, self.contact_id)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeBallContact":
        time, x, y, z, contact = cls.FORMAT.unpack(data)
        return cls(time, (x, y, z), BallContactID(contact))


@dataclass(frozen=True)
class NativeBallVelocity:
    incoming: tuple[float, float, float]
    outgoing: tuple[float, float, float]

    FORMAT = struct.Struct("<6f")

    def pack(self) -> bytes:
        return self.FORMAT.pack(*self.incoming, *self.outgoing)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeBallVelocity":
        values = cls.FORMAT.unpack(data)
        return cls(tuple(values[:3]), tuple(values[3:]))


@dataclass(frozen=True)
class NativeMatchBallData:
    competition_id: int
    is_winter_ball: bool

    FORMAT = struct.Struct("<iB3x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.competition_id, self.is_winter_ball)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchBallData":
        competition_id, winter = cls.FORMAT.unpack(data)
        return cls(competition_id, bool(winter))


@dataclass(frozen=True)
class NativeHawkeyeReplayInfo:
    time_slice: int
    mid_time_slice: float
    ball_position: tuple[float, float, float]

    FORMAT = struct.Struct("<i4f")

    def pack(self) -> bytes:
        return self.FORMAT.pack(self.time_slice, self.mid_time_slice, *self.ball_position)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeHawkeyeReplayInfo":
        values = cls.FORMAT.unpack(data)
        return cls(values[0], values[1], tuple(values[2:]))


@dataclass(frozen=True)
class NativeOffsideReplayInfo:
    mid_time_slice: float
    time_slice: int
    attacker_position: float
    defender_position: float
    is_close_call: bool

    FORMAT = struct.Struct("<fiffB3x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(
            self.mid_time_slice, self.time_slice, self.attacker_position,
            self.defender_position, self.is_close_call,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "NativeOffsideReplayInfo":
        mid, time_slice, attacker, defender, close = cls.FORMAT.unpack(data)
        return cls(mid, time_slice, attacker, defender, bool(close))


@dataclass(frozen=True)
class NativeMatchObjectState:
    rotation: tuple[float, float, float, float]
    position: tuple[float, float, float]
    visible: bool

    FORMAT = struct.Struct("<7fB3x")

    def pack(self) -> bytes:
        return self.FORMAT.pack(*self.rotation, *self.position, self.visible)

    @classmethod
    def unpack(cls, data: bytes) -> "NativeMatchObjectState":
        values = cls.FORMAT.unpack(data)
        return cls(tuple(values[:4]), tuple(values[4:7]), bool(values[7]))
