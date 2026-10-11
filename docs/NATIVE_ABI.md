# Recovered FM26 playback ABI

This document records clean-room interface facts recovered from the installed
Windows x86-64 build. It does not describe the private simulation algorithm.

## Analysis identity

- Unity version detected from the shipped player: `6000.0.52f1`
- IL2CPP metadata version: `31.1`
- `GameAssembly.dll` SHA-256:
  `7ce3eb474dc6093df633f979e869e55b2ec7953fde2e732392a694d379ff7a0c`
- Metadata SHA-256:
  `52287eadeb07d3d222c9e370e64f308260934911807e2073fb0e72f49c273213`
- Cpp2IL version:
  `2022.1.0-development.1743+b5ad444b82267cb1e4b88b8b373c008105bdea52`
- Located code registration: `0x18218E590`
- Located metadata registration: `0x182996180`

Cpp2IL reconstructed managed declarations and field offsets from the exact PE
and metadata pair. The declarations are static analysis evidence; they do not
show that a particular runtime path executed.

The native plugin separately exports `get_*_layout_signature` entry points for
the same playback records. Their presence corroborates the ABI boundary; the
protected bodies are not treated as decoded algorithms.

A bounded Proton loader probe successfully resolved and invoked the
`match_state_layout_signature` export. The probe did not capture its return
value and did not initialize a match, so this is export/loadability evidence
only.

The PE export directory contains 30 `get_*_layout_signature` symbols for this
boundary: `BallContact`, `BallVelocity`, `MatchObjectState`, `AppearanceData`,
`BillboardInfo`, `CrowdKitSetup`, `HawkeyeReplayInfo`, `MatchBallData`,
`MatchEntitySetup`, `MatchEnvironmentSetup`, `MatchEvent`, `MatchHandle`,
`MatchInfo`, `MatchLightingAndWeatherSetup`, `MatchOutsideEnvironmentSetup`,
`MatchStadiumLocationSetup`, `MatchStadiumSetup`, `MatchState`,
`OffsideReplayInfo`, `PitchSetupInfo`, `PlayerKitSetup`,
`PluginMatchSetupConfig`, `PluginMatchSetup`, `RefereeKitSetup`,
`StadiumColouringData`, `StadiumSetupInfo`, `StandSetupInfo`, `StopTimeInfo`,
`TeamKitSetup` and `UniqueIds`. This is an export-table observation; the
signature return values were not decoded.

## Blittable records

| Record | Size | Recovered fields and offsets |
| --- | ---: | --- |
| `MatchBallData` | `0x08` | `CompetitionID:i32 @0x00`, `IsWinterBall:bool8 @0x04` |
| `MatchState` | `0x24` | flags `@0x00`, time slice `@0x04`, catch-up slice `@0x08`, time `f32 @0x0c`, injury time `i32 @0x10`, period `@0x14`, two crowd moods `@0x15..16`, two signed-byte scores `@0x17..18`, event update size `u32 @0x1c`, stop-time update size `u32 @0x20` |
| `MatchEvent` | `0x2c` | six player IDs `@0x00..14`, visitor-team bit flags `@0x18`, commentary event `u16 @0x1a`, time slice `i32 @0x1c`, duration `i32 @0x20`, three importance/flag bytes `@0x24..26`, `Data1:i32 @0x28` |
| `StopTimeInfo` | `0x08` | stop slice `i32 @0x00`, next reason `u8 @0x04`, set-piece type `u8 @0x05` |
| `HawkeyeReplayInfo` | `0x14` | time slice `i32 @0x00`, mid-slice `f32 @0x04`, ball `Vector3 @0x08` |
| `OffsideReplayInfo` | `0x14` | mid-slice `f32 @0x00`, time slice `i32 @0x04`, attacker/defender positions `f32 @0x08/0x0c`, close-call bool `@0x10` |
| `BallContact` | `0x14` | time `f32 @0x00`, position `float3 @0x04`, contact enum `i32 @0x10` |
| `BallVelocity` | `0x18` | incoming and outgoing `float3` vectors |
| `MatchObjectState` | `0x20` | rigid transform `@0x00`, visible bool `@0x1c` |
| `PluginMatchSetupConfig` | `0x20` | flags `u32 @0x00`, user-team signed byte `@0x08`, PKM pointer `u64 @0x10`, PKM byte count `i32 @0x18` |
| `MatchHandle` | `0x08` | opaque `ulong` value; managed `Invalid` is zero |
| `PluginMatchSetup` | `0x18` | match handle `u64 @0x00`, match-engine version `u32 @0x08`, match version `u32 @0x0c`, entity count `i32 @0x10` |
| `MatchInfo` | `0x14` | five classification enums as `i8 @0x00..04`, gender `i32 @0x08`, competition year `u16 @0x0c`, five signed team IDs `i8 @0x0e..12` |
| `UniqueIds` | `0x18` | team/parent competition/subcompetition/nation `i32 @0x00..0c`, match ID `i64 @0x10` |
| `MatchOutsideEnvironmentSetup` | `0x0c` | seed `i32 @0x00`, region `i8 @0x04`, city population `i32 @0x08` |
| `MatchStadiumLocationSetup` | `0x14` | longitude/latitude/orientation/altitude/time-zone `f32 @0x00..10` |
| `PitchSetupInfo` | `0x14` | length/width/wetness `f32 @0x00..08`, condition `i16 @0x0c`, precipitation `@0x0e`, pitch type/pattern/heating bytes `@0x0f..11` |
| `MatchLightingAndWeatherSetup` | `0x30` | day `i32`, time `f32`, precipitation enum `i32`, chance/intensity/temperature/wind strength, wind vector, fog density/falloff |
| `StandSetupInfo` | `0x0c` | capacity/age `i32`, roof/renovation bytes |
| `StadiumSetupInfo` | `0xa0` | stadium metadata, eight `StandSetupInfo` records and two Unity `Color` values |
| `MatchStadiumSetup` | `0xb4` | `PitchSetupInfo @0x00`, `StadiumSetupInfo @0x14` |
| `PlayerKitSetup` | `0xd4` | four style bytes at `@0x00..03` and thirteen Unity `Color` fields from `@0x04` in 16-byte strides |
| `TeamKitSetup` | `0x200` | kit type, nested player/goalkeeper kits, title/subshirt colors, team ID and two flags |
| `RefereeKitSetup` | `0x20` | two Unity `Color` fields |
| `MatchEnvironmentSetup` | `0x420` | home team kit `@0x00`, away kit `@0x200`, referee kit `@0x400` |
| `AppearanceData` | `0xe8` | signed appearance/accessory indices, 35 `f32` morph/measurement fields and outfit tendency; raw bytes remain lossless |
| `MatchEntitySetup` | `0x12c` | entity kind/skin/bool flags, hair color, dimensions, two blittable-string pointers, shirt number, team/index flags, unique ID and `AppearanceData` |
| `CrowdKitSetup` | `0x34` | three Unity `Color` values at `@0x00`, `@0x10`, `@0x20`; shirt style byte `@0x30` |
| `StadiumColouringData` | `0xcc` | home/away team IDs and logo numbers, team/stadium/competition Unity colors |
| `BillboardInfo` | `0x08` | unique ID `i32 @0x00`, `BillboardFlags:u32 @0x04` |

The corresponding Python wire implementations and size/round-trip assertions
are in `src/match_engine/native.py` and `tests/test_native.py`.

## Playback boundary

The setup boundary accepts only flags, a user-team ID and a pointer/count span
containing PKM bytes. Its recovered flags distinguish viewing a past match,
spectating, catching up, suppressing licensed kits and loading a PKM. It returns
an opaque 64-bit handle, separate engine and match version numbers, and the
entity count. This directly establishes PKM as the native setup/input carrier.

`GetMatchInfo(handle)` returns an independently marshalled classification record:
viewable mode, competition/subcompetition, stage, trophy, gender, year, and
five team-role IDs. The exact enum values are represented in `native.py`; they
are output metadata and do not, by themselves, specify simulation behavior.

`GetMatchUniqueIds`, crowd-kit getters, `GetStadiumColouringData` and
`GetEntitiesBillboardInfo` are separate identity/presentation boundaries. Their
fixed records are represented losslessly; billboard bits distinguish showing
info, substitutions, cards and two injury severities.

The same interface exposes outside-environment, stadium-location, pitch and
lighting/weather records. These are setup/output boundaries with exact sizes and
offsets; the clean-room engine does not yet claim that any particular weather or
pitch field changes its private event probabilities.

`GetEntitySetup` returns a span of `MatchEntitySetup` records. The record layout
and `AppearanceData` size are now represented exactly; pointer-backed shirt and
billboard strings plus appearance bytes remain opaque rather than being decoded
as simulation attributes.

The managed record payload is `0x12c` bytes. The native exported layout-signature
getter reports a `0x130` enclosing size for the same offsets, so the implementation
keeps the four-byte native tail as unresolved padding instead of assigning it a
field meaning.

Kit records are preserved losslessly at their recovered strides and expose the
declared style/color/team fields through non-mutating decoders. Their values are
presentation data; they are not fed into private event probabilities.

The recovered `IPluginMatchPlaybackInterface` exposes:

- `Tick(float deltaTime) -> MatchState`
- `Seek(int timeSlice) -> int`
- `GetBallPosition(int timeSlice) -> Vector3`
- `GetEntityWorldTransform(int index) -> RigidTransform`
- incremental match-event and stop-time array updates returning `uint` counts
- previous/next automatic-highlight time slices
- play-one-event-at-time, skip-dead-simulation-time and speed/highlight controls
- server synchronization with current slice, stop slice and stop reason

Recovered wrapper logic for `GetTimeSlicesForRealWorldTime` establishes a base
conversion of four time slices per real-world second. Replay highlights return
that base conversion directly; non-replay playback additionally multiplies it
by the active playback-mode speed before truncating to an integer.

The separate animation interface updates a match to floating-point time and can
return ball contacts, incoming/outgoing velocity, object states, and net or
assistant-referee flag particle positions.

The managed `FM.Match.Match.UpdateMatch` path multiplies Unity frame
`deltaTime` by the active playback-mode speed before calling `Tick(float)`,
then copies the returned `MatchState` and requests event updates. The event
request uses a two-record `NativeArray<MatchEvent>`; the managed list keeps its
prefix through the returned count, drops its suffix, and appends the returned
records. This is the recovered event-stream cursor contract, not an inference
about how the native simulator chooses an event.

Cpp2IL IL recovery of the exact managed body confirms the same sequence at
instruction level: a two-element native event array is constructed, the
playback interface's `RequestMatchEventsUpdate` is called, and
`List<MatchCommentaryEvent>.RemoveRange(returnedCount, oldCount-returnedCount)`
removes the stale suffix. The method then advances the current first/last event
indices and translates native records into managed commentary carriers.
Cpp2IL marks unmanaged-memory loads and some SIMD field copies as unresolved;
those portions are retained as ABI evidence only.

The same PE export table has 62 `simatchplayback`-prefixed methods. They divide
into 15 animation methods (`i_matches_*`), 22 match setup/getter methods
(`i_plugin_match_interface_*`), 24 playback methods
(`i_plugin_match_playback_interface_*`), and one recording-path method. The
names include setup, shutdown, handle validation, event/stop-time update
requests, seek/tick, highlight navigation, commentary retrieval, transform
getters, sync controls, and speed/highlight controls. The recreation models
the data contracts and observable navigation semantics only; it does not
pretend these exported functions are a standalone simulation API.

A bounded disassembly of the exported `match_state_layout_signature` thunk
(RVA `0x11772780`) shows a relative dispatcher call/jump followed by indirect
state operations, not a plain embedded signature constant. The signature value
therefore remains intentionally unclaimed.

Fresh Cpp2IL output for `FM.GamePlugin.dll` independently exposes managed
wrapper names for the same operations, including `Marshal_NativeArray_*` for
event/stop-time buffers and `Marshal_Span_*` for entity setup. The managed
assembly also contains `Test_*_Layout` methods for the recovered records. These
are boundary and marshalling observations, not decoded simulation logic.

The managed bootstrap supplies a concrete setup sequence: pin the default
`match.pkm` bytes, set `LoadingPkm`, pass the pointer and byte count in
`PluginMatchSetupConfig`, call `IPluginMatchInterface.Setup`, then use the
returned handle/entity count to initialize the playback controller. Calling
the exported singleton outside Unity is not sufficient because the native
plugin expects its logger/data-receiver initialization first.

Reflection of the recovered `SI.Match.IPluginMatchPlaybackInterface` gives
these concrete signatures: `GetMaxMatchTime() -> Int32`,
`PlayMatchEventAtTime(Int32, Boolean) -> Int32`,
`RequestMatchEventsUpdate(NativeArray<MatchEvent>) -> UInt32`,
`RequestMatchStopTimeInfosUpdate(NativeArray<StopTimeInfo>) -> UInt32`, and
the two speed setters taking `SByte`. `IPluginMatchInterface` also exposes
`GetMatchInfo(MatchHandle)`, `GetMatchUniqueIds(MatchHandle)` and
`GetPlaybackInterface(MatchHandle)`. These signatures are managed metadata
facts; they do not establish what the native implementation computes.

Native RTTI additionally identifies separate simulation subsystems rather than
one monolithic event-probability routine: `MATCH_SYSTEM`, `MATCH_PLAYER`,
`MATCH_BALL`, `MATCH_STATS`, `MATCH_PRESSING_FACTORY`,
`MATCH_OOP_SCORING_PROVIDER`, `STAT_DISTRIBUTION_MANAGER`, `QME_STAT_MANAGER`,
`XG_SHOT_DATA`, and attack/defence set-piece routine templates. The concrete
distribution classes are `NORMAL_DISTRIBUTION`, `POISSON_DISTRIBUTION`,
`BINNED_DISTRIBUTION` and `ZERO_DISTRIBUTION`. These are type-topology
observations; their call order and parameter transforms remain to be recovered.

## Exact categorical boundaries

Recovered match periods distinguish kickoff, both regulation halves, both
extra-time halves, extra-time breaks, penalties, and full time. Stop reasons
distinguish period/game boundaries, set pieces, celebrations and penalty awards.
Set pieces distinguish corner, three throw-in regions plus flat attacking
throws, penalty, goal kick, eight free-kick contexts, and kickoff.

The native commentary event table is a contiguous 1,220-entry enum beginning at
`8000`; the independently parsed FMF selector table has 1,220 IDs `0..1219`.
The equal counts and ordering support an ID translation of `native = fmf + 8000`.
This is a strong static correspondence, not a runtime observation.

Reflection of `SI.MatchTypes.CommentaryEventDefinitions` confirms the full
managed enum contains 1,220 contiguous members from `8000` through `9219`.
Only the subset with independently recovered semantic matches is used by the
prototype; the remaining names are not treated as gameplay rules.
