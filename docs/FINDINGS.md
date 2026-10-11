# FM26 match-engine investigation ledger

## Scope and identity

The inspected installation is the Windows x86-64 Unity/IL2CPP build. Key
artifact SHA-256 values:

- `GameAssembly.dll`: `7ce3eb474dc6093df633f979e869e55b2ec7953fde2e732392a694d379ff7a0c`
- `shared/data/simatch.fmf`: `ac0a423665f62a2bda3b65e6c604a616130d098a321c210fc5133ce69610a5b9`
- `shared/data/simatchshared.fmf`: `a75179613cf83eccc715d8180cf8cb1a78b8712f5ac70bc1d9df0d51f765ae02`
- `fm_Data/il2cpp_data/Metadata/global-metadata.dat`: `52287eadeb07d3d222c9e370e64f308260934911807e2073fb0e72f49c273213`
- `data/game_simulation/test match/match.pkm`: `d3d1e155e1bc37833fa3bf697373f12b7b729efdbfdb2b2d20c4466359829508`

## Direct observations

1. `GameAssembly.dll` is a 53.6 MB PE32+ IL2CPP image. The installation also
   contains a 15.6 MB `global-metadata.dat` and a 38.5 MB Unity symbol map.
2. Named native boundaries include match setup/state/event records; tick, seek,
   speed and highlight-window controls; entity and ball transforms; commentary;
   stop-time records; offside and Hawkeye replay information; ball contacts and
   velocity; character animation tracks; net and linesman-flag simulation.
3. The FMF header begins `02 01 66 6d 66 2e` and its first payload starts with a
   Zstandard frame. Decompressing the first `simatch.fmf` frame produces XML.
4. That XML contains event records with live (`game`) and replay (`rply`) text,
   weighted variants (`prob`), delay values (`dely`) and semantic tags such as
   event identity and presentation context.
5. IL2CPP metadata exposes formations, player/team instructions, mentalities,
   pressing, passing directness/risk, dribbling, marking, goalkeeper distribution,
   defensive roles and xG-related UI/type names.
6. The shipped PKM fixture has an `03 01 6d 6b 70 2e` (`mkp.`) header and embeds
   match setup, squads, formations and injury names. Its exact role is unknown;
   the fixture name and extension alone do not establish that it is a replay.
7. The exact IL2CPP metadata includes marshalled boundaries for `MatchEvent`,
   `MatchState`, `StopTimeInfo`, `BallContact`, and `BallVelocity`. It also names
   kick-off, corner-kick and several location-specific free-kick contexts.
8. `fm_Data/Plugins/x86_64/game_plugin.dll` is the 514.9 MB native module that
   owns the `simatch` implementation. Native RTTI names `MATCH_SYSTEM`, `MATCH`,
   `MATCH_PLAYER`, role-specific pressing managers, attack/defend set-piece
   routines, substitutions, injuries, `XG_SHOT_DATA`, and normal, Poisson,
   binned and zero distribution classes.
9. That module exports a narrow playback ABI. Observed calls include setup and
   shutdown; tick and seek; current/max time-slice access; ball position and
   velocity; entity world transforms; match-event and stop-time update requests;
   previous/next auto-highlight lookup; commentary retrieval; offside/Hawkeye
   replay data; and animation updates to a requested time.
10. Both shipped PKM fixtures begin with version bytes `03 01` and marker
    `mkp.`. Their payloads use four-byte little-endian lengths before many UTF-8
    strings. The men's fixture yields 416 validated strings of six or more bytes,
    including a 93-entry injury-name catalogue followed by competition, stadium,
    staff, tactical-formation and squad data. This establishes setup/input data,
    not match-event or replay records.
11. The first verified `simatch.fmf` XML member contains 1,220 contiguous event
    IDs (`0..1219`) and 6,716 presentation variants. Selector probabilities
    span `0..1000` and delays span `0..24`. These are observed data ranges, not
    inferred probability normalization or timing units.
12. Cpp2IL recovered metadata version 31.1 and the exact public playback record
    layouts from the shipped `GameAssembly.dll`/metadata pair. The recovered
    structures and offsets are recorded in `NATIVE_ABI.md` and implemented as
    explicit little-endian wire records in `native.py`.
13. Recovered wrapper instructions establish a base playback conversion of four
    time slices per real-world second. Replay highlights use that value directly;
    live playback scales it by the selected playback speed.
14. The decompressed `simatch.fmf` payload contains 110 structurally valid xG
    records: ten sets of the same 11 shot types (`free_kicks`, headers, three
    obscured forms, three open-goal forms, penalties, regular and volleys). The
    final `0.0.0.0` set has zero-valued maps, consistent with a serialized
    default/template; the other nine sets carry non-zero values and years 23
    through 26.
15. The records use exactly eight named features across map sizes 2, 6, 7 and 8:
    an intercept; normalized goal distance, nearest-occluder distance, intervening
    player count and ball height; visible-goal fraction; and transformed facing
    and shot-location angles. Integers have both a signed inline form (high nibble
    biased by eight) and a signed little-endian int32 form.
16. A separate shipped table contains 3,137 position/stat distribution rows over
    14 positions and 22 stat types. Its observed distribution families comprise
    1,803 Poisson, 630 normal, 580 ten-bin and 124 zero rows. Every row includes
    an ability window, attribute window, position, stat type, mean/bin vector and
    variance. The three ability bands are exactly `0..99`, `100..129` and
    `130..200`.
    Native schema strings beside these fields name this resource
    `qme_distribution_data`, so it belongs to the quick-match/stat-generation
    subsystem; it is not evidence that the detailed live simulation samples the
    same tables.
17. The same resource explicitly maps all 22 stat types to one through four
    relevant player attributes. Examples include passing plus work rate for pass
    attempts, passing plus decisions for completion, and work rate plus
    anticipation plus acceleration for pressure completion. These are serialized
    associations; their aggregation weights are not present in this table.
18. The fourth complete XML member contains ten named tactical style templates
    plus an empty `clean_slate` record. Each style carries numeric attribute
    ranges, tendency ranges and preferred-role IDs. These IDs are retained as
    IDs: the XML itself does not establish their semantic enum names. Authored
    names, descriptions and feature-of-play translations are deliberately not
    returned by the clean-room inspector.
19. Cpp2IL output from the exact `GameAssembly.dll`/metadata pair exposes
    `FM.UI.TacticalStyles`; its numeric values `0..10` correspond exactly to the
    XML record ordering and style identifiers. This mapping is implemented in
    `managed.py`. A proposed mapping of `preferred_roles` to the managed UI
    `RoleID` enum was rejected during verification: the resource contains ID 47,
    beyond that enum's maximum role value 44, so those IDs remain unresolved.
20. The recovered detailed-match setup ABI accepts a `PluginMatchSetupConfig`
    containing flags, a signed user-team ID and a native pointer/count span of
    PKM bytes. It returns an opaque handle, separate match-engine and match
    versions, and an entity count. This establishes PKM as the setup/input
    carrier at the public native boundary rather than merely inferring its role
    from its extension or fixture path.
21. Both shipped PKM fixtures contain the same structured catalogue at payload
    offset `0x234`: 93 records followed by a `0xffff` sentinel at `0xbe8`.
    Every record has a `u16` record ID, `u32` UTF-8 byte length, text bytes, one
    binary flag, a `u32` link value and a final flag byte. IDs span 5 through 113
    with gaps; the two fixtures have identical IDs, values, flags and links.
    The values are injury descriptions, establishing this as setup reference
    data rather than simulated match-event output.
22. The managed match boundary separately exposes `MatchInfo` at size `0x14`:
    five one-byte classification enums, a four-byte gender enum, a two-byte
    competition year and five signed team-role bytes. The exact values and
    round-trip representation are implemented in `native.py`; no PKM numeric
    field is being guessed into this output record.
23. The same managed boundary exposes exact environment records for outside
    seed/region/population, stadium location, pitch dimensions/condition,
    precipitation, lighting/weather and stand metadata. Their recovered sizes
    are `0x0c`, `0x14`, `0x14`, `0x30` and `0x0c` respectively. These establish
    available setup/output fields, not undocumented gameplay coefficients.
24. `GetEntitySetup` marshals a span of `MatchEntitySetup` records. Cpp2IL field
    offsets establish a `0x12c` entity record containing presentation identity,
    two blittable-string pointers, team/index flags, unique ID and a `0xe8`
    `AppearanceData` payload. The clean-room wire model preserves pointers and
    appearance bytes without treating them as match-decision inputs.
25. Stadium output is nested and fully sized by the managed declarations:
    `StadiumSetupInfo` is `0xa0` (eight `StandSetupInfo` records plus two
    16-byte Unity colors), and `MatchStadiumSetup` is `0xb4` with pitch data
    first.
26. Kit/environment output is likewise fixed-layout: `PlayerKitSetup` is
    `0xd4`, `TeamKitSetup` `0x200`, `RefereeKitSetup` `0x20`, and aggregate
    `MatchEnvironmentSetup` `0x420` with home/away/referee offsets `0x00`,
    `0x200`, `0x400`. Cpp2IL field offsets now back non-mutating decoders for
    the declared style, colour, team-ID and flags while retaining exact raw
    bytes.

27. A bounded Proton Experimental run reached the shipped Unity player in
`-batchmode -nographics`: the log reports Unity `6000.0.52f1-fm26-05f1`, PhysX
4.1.2 and a `NullGfxDevice`. It emitted no match setup, event, or simulation
trace before the probe timeout. This is launch/runtime evidence, not gameplay
behaviour evidence.

28. Cpp2IL declarations expose additional exact public outputs: `UniqueIds`
(`0x18`), `CrowdKitSetup` (`0x34`), `StadiumColouringData` (`0xcc`) and
`BillboardInfo` (`0x08`). `BillboardFlags` explicitly encode display state,
substitution, yellow/red card and slight/serious injury. These are now modeled
as fixed records; they are presentation/identity data and are not fed into the
simulation model.

29. The parsed FMF commentary selector table contains 1,220 ordered entries,
and the managed `CommentaryEventDefinitions` enum contains the corresponding
native range `8000..9219`. The implementation exposes the verified translation
(`native = FMF index + 8000`) with bounds checks; it does not claim that an
event ID alone determines when the simulator emits an event.

30. `AppearanceData` is not an undifferentiated blob at the managed boundary:
Cpp2IL gives 85 signed-byte index fields, 35 `f32` measurements/morphs and an
`OutfitTendency` byte across the exact `0xe8` payload. The clean-room decoder
exposes those declared offsets without using cosmetic values as simulation
attributes.

31. The decompressed `simatch.fmf` contains a serialized QME layer beyond the
distribution table: six `expected_score_data` arrays containing 11 named rows
each, six `role_data` arrays containing 183 total coefficient vectors (52
coefficients per vector), and six `role_lookup_data` arrays containing 250
index-to-role values. Role lookup values use both observed unsigned 32-bit and
unsigned 64-bit FMF integer encodings. These tables are now parsed losslessly;
their evaluator and revision-selection logic remain unknown.

32. Each later QME family is preceded by an explicit `start_value` of `6700`
and a serialized model version. Six such revision markers are present, with
versions `(2,5,1,24)`, `(1,0,0,25)`, `(5,14,0,25)`, `(1,7,0,26)`,
`(6,0,0,26)` and `(4,10,1,26)`. The implementation reports these markers but
does not assume which revision a live match selects.

33. Native RTTI/string inventory independently names
`simatchshared::QME_STAT_MANAGER`, `SIMULATED_STATS_MANAGER`,
`VIEWABLE_MATCH_CLIENT_TACTICS`, `PLUGIN_MATCH_EVENT` and
`UPDATE_COMPANION_MATCH_EVENT`. The plugin also exports layout-signature entry
points for every recovered playback record. These symbols corroborate the
managed/asset layering, but protected export bodies did not yield evaluator
control flow.

34. A bounded Proton loader probe resolved and invoked the exported
`get_simatchplayback__si__match__match_state_layout_signature` entry point from
the shipped `game_plugin.dll` through `rundll32` (exit code 0). The launcher did
not expose the function return value, so this proves export/loadability only;
it is not a runtime simulation observation.

35. A separate minimal Windows helper could resolve the plugin's dependent DLL
set under Proton, but terminated before capturing the signature return when it
called the export outside the game's initialization context. This reinforces
that export loadability is not equivalent to a usable standalone simulation
API; no return value or behavioral claim is derived from the failed capture.

36. The native RTTI inventory also names distinct `MATCH`, `MATCH_MANAGER`,
`MATCH_MOMENTUM_MANAGER`, `MATCH_PLAYER_RATINGS_MANAGER`, `TACTICAL_ROLE`,
`SHOT_ZONE_AREA_INFO` and `MATCH_STATS` classes. This separates match-event
generation, momentum, player ratings and post-match statistics as native
subsystems; the names alone do not establish their call order or formulas.

37. A bounded Proton batch launch with the shipped `match.pkm` fixture and a
`-pkm` argument reached the same Unity/PhysX Null-graphics initialization but
produced no PKM, setup, or match-event log before timeout. The argument is not
treated as a confirmed command-line interface; the probe provides no
behavioral fixture.

38. The managed `MatchHandle` is an eight-byte opaque `ulong` value type with
`Invalid == 0` and an explicit validity check. The clean-room boundary now
preserves that value type instead of treating handles as unconstrained Python
integers.

39. The PE export directory contains 30 layout-signature functions covering
the recovered playback/setup records, plus 62 `simatchplayback`-prefixed
methods. The methods are visibly partitioned by symbol name into 15 animation
(`i_matches_*`), 22 match setup/getter (`i_plugin_match_interface_*`) and 24
playback (`i_plugin_match_playback_interface_*`) methods, with one recording
path method. This strengthens the evidence for separate setup, playback and
animation boundaries, but the exported function bodies and signature return
values remain unavailable as algorithmic evidence.

40. The prototype event JSON now carries both its human-readable whole-second
timestamp and the recovered native integer time-slice (`4 * seconds`). No
native duration, commentary ID, or evaluator output is synthesized where the
binary evidence does not provide it.

41. The prototype CLI now exposes repeatable scenario inputs for team names,
formations and the six existing tactical fields. These are harness inputs for
the clean-room model, not claims about an FM26 command-line interface.

42. The exported `match_state_layout_signature` entry at RVA `0x11772780`
starts with a relative call/jump thunk into the plugin's protected code area;
the reached bytes perform indirect state/memory operations rather than loading
a visible constant and returning it. This bounded disassembly check does not
recover the signature value or any simulation formula, so the layout remains
validated by managed field offsets and size assertions instead.

43. Playback navigation accepts the recovered native event `time_slice` field
directly when a fixture does not include the prototype's convenience
whole-second timestamp. Conversion uses the observed four-slice rate; event
duration and commentary semantics remain untouched.

44. The prototype event vocabulary now includes `throw_in` and `penalty`, both
of which have explicit counterparts in the recovered native restart and
commentary tables. They are representational categories only; no unobserved
trigger probabilities or penalty/set-piece decision rules were added.

45. Prototype events now attach native commentary IDs only for the recovered
subset: kickoff, corner/throw-in/goal-kick/offside/free-kick/penalty restarts,
default shots, goals, fouls and cards. Other event types expose `null` rather
than a guessed ID; this preserves the observed native/FMF mapping boundary.

46. The wire layer now decodes contiguous native `MatchEvent` and
`StopTimeInfo` update buffers only when their exact recovered record sizes
(`0x2c` and `0x08`) align. This is a lossless framing operation; it does not
interpret event payloads beyond the recovered enum/field declarations.

47. Those decoded records can now be emitted as field-preserving JSON for
fixture inspection. Enum values remain numeric and `data1`/duration fields
remain opaque; no commentary or gameplay interpretation is added.

48. Integration tests now validate both shipped PKM fixtures: version `(3, 1)`
and the 93-record catalogue ending at sentinel offset `0xbe8`; all catalogue
records are byte-for-byte equivalent between the men's and women's files.

49. The first post-catalogue adjacent string pair is also stable at offset
`0xdde`: men's `Italian Serie A`/`Serie A`, and women's `Women's Super League`/
`Super League`. These are retained as observed strings; their surrounding
opaque fields are not assigned schema meaning.

50. The native plugin embeds source-path strings for distinct match subsystems:
`match.cpp`, `match_manager.cpp`, `match_player.cpp`, `match_ball.cpp`,
`match_player_tactical_position.cpp`, `pathing.cpp`, tactic-change files,
`match_commentary.cpp`, and separate highlight event/frame generators. These
paths corroborate the clean-room separation between simulation state, players,
ball/pathing, tactical changes, commentary and highlight presentation; they do
not expose implementation bodies or call order.

51. Fresh Cpp2IL output for the managed `FM.GamePlugin` assembly exposes the
corresponding wrapper inventory: `Setup`/`Shutdown`, `Tick`, `Seek`, transform
and ball getters, incremental match-event and stop-time update requests,
commentary-string getters, highlight navigation, speed controls, server sync,
and explicit `Marshal_NativeArray_*`/`Marshal_Span_*` helpers. It also contains
`Test_*_Layout` methods for the recovered records. These names corroborate the
managed/native boundary and array direction, but do not reveal private match
simulation formulas.

52. The same managed output names record-specific marshallers such as
`Marshal_SI_Match_MatchState_FromNative`,
`Marshal_SI_Match_MatchEvent__ToNative`,
`Marshal_SI_Match_StopTimeInfo__ToNative`, `MatchHandle_ToNative`, and
`MatchStopReason_ToNative`. These names are retained as boundary evidence only;
the clean-room implementation does not infer ownership or mutation semantics
from a method name alone.

53. The prototype now accepts a checked-in JSON scenario schema for repeatable
team names, base IDs, formations, tactical fields, seed and duration. This is
a harness for comparing future evidence-backed behavior; it is explicitly not
treated as the game's command-line or PKM schema.

54. Reflection over fresh Cpp2IL output recovers exact managed playback method
signatures: max-time and play-event calls use `Int32`, event/stop-time update
requests accept native arrays and return `UInt32`, and playback speed setters
take `SByte`. The match interface getters take `MatchHandle` and return match
info, unique IDs, or a playback interface. The managed animation enum also
exposes only `MatchID.None = 255`, now represented explicitly.

55. Reflection of the separate `SI.MatchTypes` assembly recovers all 1,220
`CommentaryEventDefinitions` enum members, contiguous from `EventWait = 8000`
through `EventTouchlineInstructionBerate = 9219`. This independently confirms
the full native/FMF ID range and the names of the previously sampled subset;
the recreation still maps only events whose semantics are explicitly known.

56. The representational event vocabulary now covers additional explicitly
named IDs: substitution (`8027`), own goal (`8143`), missed/scored penalty
(`8144`/`8145`), goalkeeper held (`8165`), second yellow (`8183`) and final
whistle (`8194`), plus the three injury outcomes (`8022`-`8024`). These
categories are mapped only at the commentary-ID boundary; the simulator does
not fabricate their occurrence rules.

57. Fresh Cpp2IL/ISIL output for `FM.Match.Match.UpdateMatch` shows the managed
client passes `UnityEngine.Time.deltaTime * MatchPreferences.GetActivePlaybackModeSpeed()`
to the native `IPluginMatchPlaybackInterface.Tick(Single)` call. The returned
`MatchState` is copied before `UpdateMatchEvents()` runs; this is the observed
simulation-to-client clock boundary.

58. `FM.Match.Match.UpdateMatchEvents()` allocates a two-element
`NativeArray<SI.Match.MatchEvent>`, calls
`IPluginMatchPlaybackInterface.RequestMatchEventsUpdate`, removes the
commentary-event suffix beginning at the returned count, and appends the
returned native records. It separately requests stop-time info and copies the
native max time, stop time, stop reason, current time slice, dead-time skip and
sync-request fields. This establishes queue/cursor semantics but does not
expose the native event-generation decisions.

59. The managed `MatchBootstrap.SetupConfigFromPkm` path defaults to
`../../../apps/game/data/game_simulation/test match/match.pkm`, checks the
file, pins its bytes, sets `PluginMatchSetupFlags.LoadingPkm`, and passes the
pointer/byte count to `IPluginMatchInterface.Setup`. A direct Wine probe of
the exported singleton/setup boundary reaches DLL loading and export lookup,
but the singleton call faults before setup because the game-plugin logger and
receiver initialization performed by Unity are absent. It produced no native
event records; this is a bounded negative runtime result, not an algorithmic
assumption.

60. Cpp2IL recovered the managed `FM.Match.MatchFrame` carrier used after each
native tick. Its fields include the stop-time list, commentary-event list,
current playback mode/speed, current time and time slice, event-index bounds,
chosen-highlight bounds, match flags/period/crowd moods/scores, replay state,
and current stop-time index. `TickComponents()` copies these values and passes
the frame by reference to every `IMatchComponent.MatchTick` consumer. This
confirms that event generation is native, while highlighting/animation/audio
consume a managed frame assembled afterward.

61. The recreation now exposes the xG table's exact raw coefficient dot
product as a separate helper. It requires every serialized feature explicitly
and returns no probability, scale, link function, or feature transform. This
keeps the recovered model usable by a future event generator without silently
inventing the unresolved evaluator.

62. Additional native diagnostic strings in `game_plugin.dll` name the core
entry points `MATCH::setup_match_data`, `MATCH::play`,
`MATCH::check_for_basic_time_slice_skipping`, and `MATCH::add_goal_to_stats`.
The same cluster names `TIME_RESERVED_FOR_ACTION`, `MATCH_STADIUM`,
`MATCH_TEAM`, `MATCH_REFEREE`, `MATCH_ANALYSIS_INFO`, and
`COMMENTARY_EVENT`. These are useful call-graph anchors, but the protected
binary does not expose their bodies or argument semantics.

63. The same native artifact contains RTTI anchors for `MATCH_INPUT`,
`MATCH_INPUT_BASIC_CONDITIONS`, `MATCH_INJURY_INPUT`, and
`MATCH_COMPETITION_INPUT`, plus `QUICK_MATCH_DATA_TO_PROCESS` and
`QUICK_MATCH_SETUP_HELPER`. These identify the native input partition feeding
the simulator and separate quick-match processing from viewable playback, but
no field offsets or evaluator body were recoverable from the protected image.

64. Native strings also name the startup/progress stages
`SETTING_UP_SIMULATED_STATS_MANAGER`, `QUICK_MATCH_DATA_TO_PROCESS`, and
`QUICK_MATCH_SETUP_HELPER`, as well as the serialized consumers
`qme_stat_relevant_attribute_data` and `qme_distribution_data`. This ties the
recovered FMF/QME tables to the quick-match/stat path, but still does not prove
that those tables drive viewable-match event probabilities.

65. The recreation now has an explicit `NativeMatchDriver` boundary matching
 the managed call order: scale the frame delta by playback speed, call native
 `Tick(float)`, request the observed two-record event update, and apply the
 returned count as the event-buffer cursor. The adapter deliberately has no
 event probability or commentary interpretation logic; a captured native trace
 can therefore replace the callback without rewriting playback/state code.

66. A fresh string pass over `game_plugin.dll` adds two concrete event-path
 anchors: `ATTACK_CORNER_ROUTINE_TYPE_HANDLER` and
 `DEFEND_CORNER_ROUTINE_TYPE_HANDLER`. The same binary exposes presentation
 labels for attacking/defending corners and stat fields such as shots on
 target, key passes, fouls and offsides. These establish that corner handling
 is split into attacking and defending routines and that the stats path is
 distinct, but they do not reveal the branch conditions or probabilities.

67. `NativeEventQueue` and `NativeMatchDriver` now accept the recovered
 `NativeMatchEvent` records directly and expose their lossless wire fields.
 This is a transport-only bridge: it preserves player IDs, team bitset,
 commentary ID, time/duration slices, flags, both importance values and `data1`
 without converting them into guessed high-level event meanings.

68. A fresh Cpp2IL diffable-C# pass recovered the complete managed
 `SI.MatchTypes.CommentaryEventDefinitions` value map. It starts at
 `EventWait=8000`, assigns contiguous IDs through the core pass/shot/restart/
 goal/foul/card/period events, and continues through the shipped presentation
 taxonomy. The managed `FM.Match.MatchCommentaryEvent` carrier additionally
 confirms `ContributorTimeSlice`, `Duration`, flags, both importance values and
 `Data1`. These are now available as authoritative metadata for a future
 trace-driven event translator; no simulator branch is inferred from the
 names alone.

69. Cpp2IL IL recovery (99% of managed methods) confirms the actual
 `FM.Match.Match.UpdateMatchEvents` body allocates a two-element
 `NativeArray<SI.Match.MatchEvent>`, calls
 `IPluginMatchPlaybackInterface.RequestMatchEventsUpdate`, removes the managed
 commentary suffix beginning at the returned count, and advances the current
 event indices. The recovered body also contains explicit period-start checks
 for kickoff (`8052`) and penalty-take (`8063`) IDs. Native-memory portions of
 the decompilation remain marked by Cpp2IL as unresolved, so this is not being
 extended into undocumented event-generation rules.

70. The recovered managed carrier is a distinct
 `FM.Match.MatchCommentaryEvent` with `TextPresent`, `TextPast`, six
 `PlayerUniqueIDs`, `PlayerTeams`, `TimeSlice`, `Duration`,
 `ContributorTimeSlice`, commentary/incident importance, flags and `Data1`.
 The clean-room model now represents this carrier separately from the exact
 0x2c native `MatchEvent`; text and contributor timing are required inputs to
 translation because they are not present in the native wire record.
71. `FM.Match.Match.UpdateStopTimeInfos` has the same recovered cursor shape:
 it calls `RequestMatchStopTimeInfosUpdate`, removes the managed suffix at the
 returned count, appends the returned records and advances
 `m_currentStopTimeInfoIndex` to the larger cursor. `NativeStopTimeQueue`
 mirrors that state contract without assigning stoppage or set-piece rules.
72. The recovered `FM.Match.Simulation.Match2DSimulation` component consumes
 `MatchFrame` and `MatchCommentaryEvent` data in `MatchTick`; its fields and
 methods calculate presentation bounds, camera orientation, normalized player
 positions and UI callbacks. It has no native tick, probability table or event
 emission boundary, so it is explicitly excluded from the simulation
 generator reconstruction.
73. Native RTTI exposes the match simulation’s concrete subsystem topology:
 `MATCH_SYSTEM`, `MATCH`, `MATCH_PLAYER`, `MATCH_BALL`, `MATCH_STATS`,
 `MATCH_OOP_SCORING_PROVIDER`, `MATCH_PRESSING_FACTORY` and separate
 attacking/defending set-piece routine templates. It also exposes
 `STAT_DISTRIBUTION_MANAGER`, `QME_STAT_MANAGER`, `XG_SHOT_DATA`, and concrete
 `NORMAL_DISTRIBUTION`, `POISSON_DISTRIBUTION`, `BINNED_DISTRIBUTION` and
 `ZERO_DISTRIBUTION` types. This confirms that quick-match stat generation,
 xG, pressing, out-of-possession scoring and set pieces are separate native
 subsystems; the clean-room engine must not collapse them into one guessed
 probability loop.
74. Native diagnostic strings provide two direct event-path anchors:
`MATCH::play`/`MATCH::check_for_basic_time_slice_skipping` and
`MATCH_PLAYER::add_event`. The same build reports `MATCH_PLAYER` tactical
position setup and `MATCH_BALL::set_target`/`set_coords` diagnostics. These
establish that the native play loop owns ball targets, player event insertion
and dead-time skipping; they do not disclose the branch predicates or RNG.

75. Connected GhidraMCP analysis of the GUI program `/game_plugin.dll`
 confirmed the exported wrapper/vtable boundary. `Setup` calls vtable `+0x18`,
 `Tick(float)` calls `+0x20` and copies a `0x24`-byte `MatchState`, max-time
 calls `+0x28`, environment setup calls `+0x40` and copies `0x420` bytes,
 shutdown calls `+0x70`, seek calls `+0xa8`, dead-time skipping calls `+0xb0`,
 match-event updates call `+0xb8`, and stop-time updates call `+0xd0`.
 The update wrappers return native counts and do not perform event selection
 themselves. This is stronger static evidence for the transport boundary, not
 evidence of the protected simulator formulas.

76. The same Ghidra pass recovered the exported setup and playback virtual-call
addresses and corroborated the exact `MatchEvent` layout string: six player
IDs, team flags at `0x18`, commentary at `0x1a`, time slice at `0x1c`,
duration at `0x20`, three bytes at `0x24..26`, `Data1` at `0x28`, and record
size `0x2c`. The detailed address table and limitations are recorded in
`docs/GHIDRA_MATCH_BOUNDARY.md`.

77. The recreation now accepts a full scenario-fed roster and tactical system:
 normalized core and arbitrary player attributes, positions, in/out-of-
 possession roles, duties, player instructions, condition, sharpness, morale,
 substitutes, tactical style and an instruction map. The CLI echoes this input
 in its result so experiments are reproducible. This is an input/schema
 improvement backed by the managed tactical-instruction and role declarations;
 extra instruction values are deliberately retained but not assigned invented
 native coefficients.

These are static observations. They do not prove exact runtime algorithms or
the meaning/layout of every field.

79. The managed setup path confirms that native simulation setup receives a
 pinned PKM byte span plus `PluginMatchSetupFlags` and a user-team byte; the
 managed `MatchSetup` object (entities, kits, stadium, environment, unique
 IDs) is assembled after native setup and is not the simulator's complete
 input ABI. The inspected PKM fixtures expose framing and catalogue data, but
 the semantic player/tactical records are not yet decoded.

80. Ghidra distinguishes the animation `simatchplayback...anim.i_matches`
 interface from match playback. Its exports update animation state to a
 low-32-bit time slice, retrieve ball contacts through another native-array
 carrier, and play an event at a time through separate vtable slots. Playback
 commentary accessors take an event index plus tense/string selectors. These
 observations establish a post-generation animation/commentary layer and must
 not be used as invented event-selection rules.

81. Native getters further separate post-setup presentation data from the
 simulation input: `GetMatchInfo` calls vtable `+0x88` and returns the managed
 20-byte competition/user-team record, `GetMatchUniqueIds` calls `+0x80` and
 returns the 24-byte ID record, and `GetOutsideEnvironmentSetup` calls `+0x68`
 and returns the 12-byte seed/region/population record. Entity setup uses a
 caller-owned native-array carrier and environment setup copies `0x420` bytes.
 These are useful for a faithful CLI boundary, but do not expose the native
 player/tactical decision evaluator.

82. RIP-relative references from raw `game_plugin.dll` diagnostics anchor the
 protected play loop: `MATCH::play` is referenced by `FUN_1824ec170`, and
 `MATCH::check_for_basic_time_slice_skipping` by `FUN_1824eda20`, called from
 `FUN_183e08ad0`. The dispatcher examines a mode byte at `state+0x142fa`; its
 state routines increment a 32-bit field at `state+0x14278` once per completed
 iteration while updating two team-side objects and invoking ball/player and
 transition helpers. `FUN_1824eda20` checks the next integer slice and several
 stop/target fields before allowing the loop to proceed. These offsets,
 thresholds, and call relationships are static observations; no field names,
 RNG, attribute utility, or event probability is inferred from them.

83. Ghidra caller context shows the protected play routine being driven in two
 modes: callers use `(state, 1, target_slice)` and compare the internal
 `state+0x14278` against the target, while live-style loops repeatedly use
 `(state, 0, -1)` until the stop flag is set. Another caller targets current
 slice plus `0x4b0`. This is direct evidence for targeted and single-slice
 advancement, not an inferred probability or a guessed mapping of the mode
 values.

84. The native driver around `FUN_182526980` is now mapped one layer farther.
`FUN_180965c30` calls it at `0x1809665a1` after constructing a zeroed 0x28-byte
temporary and passing the simulation object in `RDI`; the callee is its only
caller. `FUN_182526980` in turn calls the protected `FUN_1824ec170` and the
state-specific routines, plus buffer/collection helpers. The caller then reads
back a field at `simulation + 0x40` and continues with presentation/state
processing. This is strong evidence for a native simulation-driver boundary,
but it does not prove that the function is the exported Tick implementation or
that the temporary is an event request; those identities remain unknown.

85. Two helpers used by that driver expose an intermediate state/buffer layer.
`FUN_1834c1cb0` initializes a large record (including a `0x250`-byte cleared
region, sentinel fields, and linked-list storage). `FUN_1834c3450` consumes
ring-buffer ranges whose entries are 12 bytes wide, compacts them, and passes
their fields to `FUN_183cee900`/`FUN_183cecf90` along with a time/category-like
field. This is concrete evidence of structured native intermediate records and
post-processing, but neither helper is proven to emit the public 0x2c-byte
`MatchEvent`; the record conversion boundary is still unknown.

86. The driver call context narrows the role of that layer. After each
`FUN_1824ec170` advancement, `FUN_182526980` calls `FUN_1834c3450`, then
`FUN_1834b0c80`, `FUN_1834b2ec0`, and `FUN_1834b3c80`, passing simulation state
and the stop-bit-derived boolean. The same helper sequence appears in other
native stepping paths. This makes it a post-step snapshot/transition stage,
not proof that the 12-byte entries are already the exported event-update
array; public event conversion remains a separate unknown boundary.

87. `FUN_1834b0920` reveals a second native queue used by the post-step layer.
It appends records allocated at `0x20` bytes to a ring rooted at offsets
`+0x438/+0x440/+0x448/+0x450`; each record stores a 32-bit slice-like value,
an owned object/vector at `+0x08`, and a byte at `+0x18`, and sets a dirty flag
at `+0x490`. One caller feeds it observed type values `2`, `3`, `4`, and `5`
from 16-byte transition entries, with special handling for transition values
`2`, `5`, `7`, `8`, and `9`. This is the clearest static evidence so far of a
typed native presentation/transition queue, but its relationship to the public
0x2c-byte `MatchEvent` update buffer is not established.

88. Ghidra exposed the native typed-object factory `FUN_183e5e650`, used when
the driver transfers queued objects into the simulation timeline. The factory
switches on the object's byte at `+0x0d` and allocates distinct sizes/tags;
observed cases include type `4` -> 0x18 bytes/tag `0x400`, `5` -> 0x210,
`7` -> 0x80/tag `0x700`, `8` -> 0x18/tag `0x800`, `9` -> 0x18/tag `0x900`,
`0xd` -> 0x38/tag `0xd00`, `0xe` -> 0x10/tag `0xe00`, `0x13` -> 0xe18/tag
`0x1300`, and `0x19` -> 0x60 bytes. `FUN_182517870` then stamps a target
time-slice at object `+0x08` and queues the typed object. These IDs and sizes
are observed vocabulary only; no semantic event names or probability rules
are assigned from them.

89. `FUN_182517870` is the handoff that turns those typed objects into a
time-indexed native timeline. It receives an object range, allocates an object
based on the source byte at `+0x0d`, invokes its virtual copy/initialization
slot, stamps the requested time slice at object `+0x08`, and appends it to the
timeline range at `+0x13358/+0x13360/+0x13368`. The protected driver reaches
this through `FUN_182527d20` after advancing the simulation. This establishes
an internal typed timeline, but the later adapter that exposes the public
0x2c-byte `MatchEvent` records is still not identified.

90. A later timeline consumer, `FUN_1825228a0`, allocates and clears a large
`0x6a80` temporary, reconstructs player/side state from the typed timeline,
and passes `param_4 + 0x18` into its presentation-state builder. It is called
from `FUN_182522000` for both side selectors `0` and `1`, then the temporary is
released. This confirms another presentation/replay layer downstream of the
typed timeline; it should not be mistaken for the public match-event carrier.

91. The function `FUN_180ae00b0` is a strong native `MATCH::play` candidate:
it directly calls `FUN_1824ec170`, initializes match-side processing state,
and, when no explicit target is supplied, advances to a target roughly
`0x960` slices ahead before repeatedly performing single-slice advances. Each
single-step pass runs the snapshot/transition helpers and checks the native
stop bit; final status is derived from that stop state. This is an observed
advancement schedule and call sequence, not a claim that `0x960` is a public
playback duration or that the function is itself the exported Tick slot.

78. Further Ghidra wrapper inspection confirms `get_current_match_time_slice`
 calls vtable `+0x30` and returns a 32-bit value. `seek` receives a public
 64-bit argument but passes only its low 32 bits to vtable `+0xa8`. Stop-time
 update uses the same two-word input carrier as event update, expands it into
 a zeroed temporary carrier, calls `+0xd0`, returns the native count, and
 conditionally disposes the carrier according to its low two flag bits. These
 are ABI/transport facts; they do not identify the protected event generator.

92. Ghidra's exported layout-signature builders independently reproduce the
 public record schemas. `MatchEvent` is a 0x2c-byte record with 32-bit fields at
 offsets `0x00,0x04,0x08,0x0c,0x10,0x14`, one-byte fields at `0x18`, a 16-bit
 field at `0x1a`, 32-bit fields at `0x1c` and `0x20`, one-byte fields at
 `0x24,0x25,0x26`, and a final 32-bit field at `0x28`. `MatchState` is 0x24
 bytes: five 32-bit values at `0x00..0x10`, five one-byte values at
 `0x14..0x18`, then 32-bit values at `0x1c` and `0x20`. `StopTimeInfo` is an
 8-byte record with a 32-bit value at `0x00` and one-byte values at `0x04` and
 `0x05` (the remaining two bytes are padding/alignment). The setup-config
 signature is 0x20 bytes with an 8-byte value at `0x00`, one byte at `0x08`, an
 8-byte value at `0x10`, and a 32-bit value at `0x18`. These getters only emit
 layout signatures; they do not reveal simulation semantics or event-generation
 formulas, but they validate the transport structs used by the reconstruction.

93. The exported `match_entity_setup_layout_signature` adds a concrete reason
 the engine input cannot be reduced to team names and tactics: the native
 `MatchEntitySetup` is 0x130 bytes. Its signature exposes one-byte fields at
 `0x00..0x04`, a 16-byte block at `0x08`, 32-bit fields at `0x18` and `0x1c`,
 64-bit fields at `0x20` and `0x28`, a 32-bit field at `0x30`, one-byte fields
 at `0x34..0x3a`, a 32-bit field at `0x3c`, one-byte fields at `0x40` and
 `0x41`, and a final 0xe8-byte block at `0x44`. This is a verified ABI shape,
 not a semantic interpretation of the fields; the reconstruction should keep
 these opaque until player/entity capture or type evidence assigns meanings.

94. The native driver path now gives a stronger object-boundary fact. `FUN_180ae3f10`
 allocates exactly `0x14330` bytes, initializes it with `FUN_1824e5160`, installs
 the vtable-like object header, and then calls `FUN_1832c5620` with the external
 setup/context pointer. The initialized simulation object contains two side
 handles at offsets `+0x14100` and `+0x14108`, an environment/pitch-related
 handle at `+0x14178`, the current-slice field at `+0x14278`, and the stop/status
 byte region at `+0x1428c`. These offsets are directly observed; the side and
 environment labels are descriptive only, not claims about their full types.

95. `FUN_180ae00b0` and `FUN_180ae10b0` are two native driver modes over that
 same object. Both call `FUN_1824ec170` for stepping. The buffered mode advances
 toward a target computed as current slice + `0x960`, then performs repeated
 single-slice calls while running post-step queue/presentation helpers. The
 unbounded mode passes target `-1` and loops until the stop bit. This establishes
 the scheduling layer and the existence of a separate post-step queue; it does
 not establish the event probabilities or the public vtable implementation.

96. The setup path exposes a real native random-state recurrence, but its scope
 must be kept precise. In `FUN_184082100`, the match state is initialized from
 the 32-bit setup word at `state+0x20` with
 `state+0x14030 = (uint32_seed * 0xa4e7735a4c957f2d +
 0x5851f42d4c957f2e) mod 2^64`, while `state+0x14038` is set to 1. In the
 subsequent setup helper `FUN_1832c5620`, the observed generator step is
 `s = s * 0x5851f42d4c957f2d + increment (mod 2^64)` and the emitted value is
 derived from `(s_old >> 45) xor (s_old >> 27)`, rotated right by `s_old >> 59`,
 multiplied by `0x13`, then shifted and incremented. This is exact arithmetic
 observed in the setup path; it is not yet proof that every match decision uses
 this stream or that the reconstructed event RNG can be substituted directly.

97. There is a verified size distinction for entity setup. Cpp2IL's managed
 sequential `MatchEntitySetup` declaration and the existing marshaller are
 `0x12c` bytes (`AppearanceData` ends at `0x12c`), while the native exported
 layout-signature routine prints an enclosing size of `0x130` for the same
 field offsets, leaving four bytes after the final `0xe8` block. The clean-room
 model now preserves the managed payload size and records the native signature
 size explicitly; no meaning is assigned to the four-byte tail until a native
 copy/stride or runtime capture proves whether it is padding.

98. The simulation object's two observed vtable images expose a small amount of
 concrete class structure. `FUN_1824e5160` initially installs the table at
 `0x1845f9c88`; its fourth entry is a thunk into `FUN_18251c2e0`, whose body
 returns `object+0x14100 + index*8`. The driver then installs the table at
 `0x1844724a8`; the corresponding fourth entry reads `object+0x678` instead.
 The first table is adjacent to the `setup_match_data` diagnostic string, while
 the second is adjacent to match-day path strings. This is evidence of a
 setup/derived object transition and of the side-handle array location, not a
 recovered event algorithm; the vtable entries remain intentionally unnamed.

99. Setup allocates and initializes a rich per-match/per-side object graph, not a
 compact tactic-only record. `FUN_182513920(state)` allocates the
 pitch/environment object at `state+0x14178`, two side contexts at
 `+0x140e0/+0x140e8`, and two side player containers at `+0x14100/+0x14108`.
 `FUN_18277f640(side)` allocates a `0x2a80` side/player backing block at
 `side+0x528`, then creates a long sequence of per-player/per-role subobjects at
 `side+0x130..0x1f8`, linked to the side setup context. The same setup helper is
 called from public setup and clone/rebind paths, so these are simulation-state
 structures rather than merely rendering caches. `FUN_182519b50(new, old)` copies
 the PRNG state (`+0x14030/+0x14038`), current slice, timelines and remaps player
 references through each player's side/index fields. This is strong evidence that
 actual player entities and systems are carried through native state. Exact field
 meanings and event-scoring semantics remain unresolved; no heuristic aliases are
 promoted to native facts.

100. The protected play loop dispatches into a real simulation-step routine. In
 `FUN_1824ec170`, mode values select `FUN_183e08ad0`, `FUN_183e0a170`,
 `FUN_183e0b9f0`, `FUN_183e0be00` and related state routines. The common routine
 `FUN_183e08ad0(state, step)` consumes the native PRNG state, updates both side
 player containers, advances pitch/ball state and calls the specialized state
 transition routines (`1824f*`, `1825*`, `183d*`, `183e*`). It directly updates
 current-slice fields and side/player state; this is the simulation core, not the
 playback presentation queue. The routine is too large and field meanings are not
 yet stable enough to translate wholesale into Python/C++ names.

101. A confirmed internal event/timeline insertion primitive is
 `FUN_1822ece40(queue, ...)`. It allocates a `0x28`-byte record, deduplicates on
 several byte fields plus a time window, stores a time-like `i32` at record `+0x18`,
 a duration/interval-like `i32` at `+0x14`, compact byte fields at `+0x1c..+0x22`,
 and two owned payload pointers at `+0x00/+0x08`. It appends the record to a
 growable vector rooted at `queue+0x40/+0x48/+0x50` and invokes a callback at
 `queue+0x18` virtual offset `+0x38`. This is a stronger event-generation seam
 than the public wrapper, but it is not yet proven to be the exported `MatchEvent`
 serializer; the public record is `0x2c` and has a different layout.

102. `FUN_183e59f50` consumes match-state transition flags and invokes the same
 internal event/commentary sinks with concrete event IDs (for example `0x23ae`,
 `0x23b0..0x23dc`, and `0x210c`) plus side/player indices and time bounds. This
 establishes that event IDs and player/system context are generated inside the
 simulation state before playback presentation. These IDs are observed native
 values only; their semantic enum names and mapping to public `MatchEvent` fields
 remain unresolved.

103. The native commentary/event-candidate path now gives a direct, evidence-backed
 use of the recovered PRNG. `FUN_182872b10(candidate_queue, candidate, mode)` first
 advances the same 64-bit generator (`0x5851f42d4c957f2d`, xor/rotate output) and
 rejects the candidate when the rotated 32-bit output exceeds `0x19999999`.
 It then normalizes/coalesces candidate IDs in the observed `0x1fxx..0x23xx`
 ranges, carries side/player bytes at candidate offsets `0x17`, `0x18`, `0x19`,
 `0x1a`, and stores candidate records in growable rings. `FUN_1828738c0` is the
 adjacent-candidate merge/filter routine: it compares event IDs, side/player
 bytes and time differences (including a verified `<4`-slice merge case), then
 copies the surviving candidate fields forward. This is an actual native event
 selection/normalization algorithm, not a heuristic distribution, although the
 exact semantic names of the candidate IDs and the final public-record adapter
 are still unresolved.

## Inferred architecture

The most economical explanation of the evidence is a layered pipeline:

`setup + tactics + players -> simulation state -> typed match events`

`typed events -> commentary/highlight selection -> replay/playback -> Unity animation`

The explicit seeking, time slices, event-update requests and transform getters
establish a native playback boundary over time-indexed state. Whether the core
simulation stores an event-sourced stream internally remains unknown; the ABI
does not prove its internal representation.

## Prototype mapping

- `model.py`: setup/config, tactics, players, typed state and events.
- `engine.py`: fixed-step decisions, contests, fatigue, xG, discipline and event log.
- Every emitted event now carries normalized pitch coordinates. Restarts are
  explicit event boundaries, goals lead to kick-offs, and missed/deflected
  attempts lead to goal kicks or corners.
- Each half emits added-time state calculated deterministically from recorded
  stoppages. Full time is allowed to extend beyond the regulation duration.
- A 100-seed calibration smoke run currently averages 26.19 shots, 2.36 goals,
  2.60 xG, 30.22 fouls, 0.62 reds and 4.97 corners per match. These are sanity
  targets, not claimed FM26 constants.
- `highlight_windows()`: replay-friendly important-event time slices.
- `commentary.py`: independently authored weighted presentation strings.
- The commentary API now has distinct live/replay forms plus explicit weight
  and delay metadata, matching the observed selector shape without copying the
  shipped translations or their tuning values.
- `pkm.py`: execution-free inspection of only the confirmed PKM prefix and
  length-prefixed UTF-8 fields. It now parses the complete repeated catalogue
  record framing and sentinel while leaving both metadata fields semantically
  opaque.
- `fmf.py`: structural inspection of the first commentary XML member. It emits
  counts and selector ranges, deliberately excluding authored translation text.
- The same inspector now recovers all observed xG versions, shot types and exact
  raw coefficient maps with their decompressed offsets. It does not assume a
  divisor or evaluator that the static container has not established.
- It also recovers every quick-match position/stat distribution row and the
  complete stat-to-attribute association table. Values and windows remain asset
  data; interpolation and random sampling have not been guessed into the engine.
- Tactical-style inspection exposes only mechanical identifiers and ranges for
  the ten populated templates; it excludes all shipped translation content.
- `playback.py`: seek, native time-slice conversion, managed-client `Tick`
  scaling, two-record event-update cursor replacement, dead-time skip and
  adjacent-highlight navigation shaped by the exported native playback
  boundary. The queue also mirrors the recovered managed current-first and
  current-last event indices. `NativeMatchDriver` exposes the same tick/event
  seam for a native provider or trace-backed implementation; it does not
  synthesize native events.
- JSON output: stable boundary suitable for a separate 2D/3D playback client.
- `managed.py`: exact managed tactical-style IDs; similar-looking but unproven
  preferred-role mappings are intentionally excluded.
- `native.py`: setup config/result records now accompany the previously recovered
  playback records, including exact PKM pointer/count and version fields.

## Unresolved obligations

- Which native random stream is consumed by each simulation decision, exact
  internal simulation tick frequency, determinism guarantees and network
  synchronization protocol. One setup-path 64-bit recurrence is now recovered,
  but its event-decision scope is not proven. The public playback rate is known.
- Attribute scales and interactions, tactical role geometry and decision utility.
- The statistical table establishes an ability scale reaching 200 and explicit
  stat/attribute associations, but not attribute aggregation or interpolation.
- Tactical style attribute, tendency and preferred-role numeric IDs still need
  corroboration against the native enum/type definitions before use by gameplay.
- Ball physics, collision/contact model and continuous player locomotion.
- Set pieces, injuries, substitutions, added time, VAR and competition rules.
- The xG table schema and raw parameters are recovered, but the coefficient
  scale, feature transforms, model-selection rule and evaluator remain unknown.
  Goalkeeper positioning and shot placement also remain unresolved.
- FMF directory/chunk structure beyond the verified first Zstandard payload.
- Binary function bodies and call graph: the Ghidra MCP is now connected to the
  project and has yielded decompiler/caller evidence for the protected native
  play loop and its driver. Much of the binary remains control-flow protected,
  and the simulation-driver identity, field meanings and event-generation
  formulas are still unresolved.
- `game_plugin.dll` code is heavily control-flow protected. The public PE export
  names and RTTI strings are observations; disassembly at an exported layout
  getter shows dispatcher/thunk-style control flow and does not establish its
  source-level algorithm.
- Runtime behaviour: Proton can initialize Unity in Null-graphics batch mode,
  but no match was reached and no native calls were instrumented. The probe is
  therefore insufficient for behavioural claims; the exact engine remains a
  static-reconstruction target.

Parity should be measured with black-box scenario fixtures (same teams/tactics,
many seeds), distributional targets, event invariants and replay determinism—not
by copying implementation details.
