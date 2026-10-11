# FM26 match-engine recreation — beginner recap

This folder is a clean-room attempt to understand and recreate the **FM26
match engine**. The target is the part that simulates a football match: player
decisions, movement, possession, shots, fouls, cards, goals, stoppages and the
events sent to the match presentation layer.

It is **not** an attempt to decompile the whole game, copy Football Manager,
or reproduce the user interface. It is also not yet a behaviourally identical
replacement. Anything that is proven is marked as such; anything still
uncertain is kept as an explicit unknown instead of being presented as fact.

## Where we are now

We can already run deterministic, system-level match simulations from the CLI.
The simulator accepts teams, real player rosters, formations, roles, duties,
player attributes, condition, morale, tactical instructions and match setup
metadata. It produces structured events, scores, xG, possession chains,
fatigue, cards, set pieces, match statistics and replay-friendly snapshots.

The implementation is a **useful test harness**, not FM26 parity. Its tactical
coefficients and event probabilities are deliberately labelled as provisional
until native evaluator behaviour is recovered.

Run it from the repository root:

```bash
PYTHONPATH=src python -m match_engine.cli --seed 26 --pretty
PYTHONPATH=src python -m match_engine.cli --scenario examples/full_scenario.json --pretty
PYTHONPATH=src python -m match_engine.cli --seed 7 --seconds 900 \
  --home-name Alpha --away-name Beta --home-pressing .8 --away-directness .2
```

Run the regression tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
```

The current suite covers the engine, CLI, scenario input, native records,
commentary, FMF/PKM parsing and playback contracts.

## What FM26 appears to look like

At a high level the native match path appears to be layered like this:

```text
Managed FM / Unity code
        |
        | setup PKM bytes, teams and environment
        v
Plugin playback interface (small public ABI)
        |
        | Setup, Tick, Seek, event updates, stop-time updates
        v
Native playback/manager objects
        |
        | owns the simulation state and presentation queues
        v
Native MATCH simulation state
        |
        | player containers, pitch/ball state, tactics, clock, PRNG
        v
Internal candidate/event/commentary queues
        |
        v
Public MatchEvent records consumed by managed playback
```

The public interface is intentionally narrow. It exposes records such as
`MatchState` (0x24 bytes), `MatchEvent` (0x2c bytes), `StopTimeInfo` (8 bytes),
entity setup, environment setup, ball data and transforms. The public wrapper
does not itself decide whether a shot, pass or foul happens; it forwards calls
through a playback object's virtual-function table.

Important recovered operations include:

- `Setup`: accepts flags, user-team ID and a pointer/count span of PKM bytes.
- `Tick(float)`: advances playback and returns current time, score, period and
  update counts.
- `RequestMatchEventsUpdate`: copies the current native event prefix into a
  managed two-element buffer and returns the count.
- `Seek`, current/max time, stop-time updates, highlight navigation and
  animation/ball getters.

The managed update loop calls `Tick`, requests event updates, removes the stale
managed suffix, and appends the returned event records. That gives us a solid
stream/cursor contract even though the private event-selection rules are still
being recovered.

## Why decompilation is difficult

FM26 does several things that make ordinary “open the executable and read the
source” decompilation impossible:

1. **Unity IL2CPP** converts managed C# into native C++-style machine code.
   The original class and method structure is partly available through metadata,
   but the source implementation is not.
2. The match implementation lives in a very large native
   `fm_Data/Plugins/x86_64/game_plugin.dll` (about 515 MB), with stripped or
   generated names and many thousands of functions.
3. Important code is reached through interfaces and virtual tables. The public
   exports are small wrappers; the actual implementation is selected indirectly
   at runtime.
4. Ghidra often sees protected/generated regions and produces warnings,
   unreachable blocks, guessed types and enormous decompilations. A plausible
   decompiler variable name is not evidence of a real field meaning.
5. Data is split across compressed FMF resources, PKM setup files, IL2CPP
   metadata, native tables and runtime-created objects. A number in a resource
   is not automatically a gameplay coefficient.
6. The real engine is stateful and time-stepped. A single static function rarely
   explains the whole decision; player state, ball state, tactics, clock,
   random state and presentation queues interact over many calls.

For that reason the investigation separates **ABI facts**, **static native
evidence**, **runtime observations** and **hypotheses**. See
[`docs/FINDINGS.md`](docs/FINDINGS.md) for the evidence ledger and
[`docs/NATIVE_ABI.md`](docs/NATIVE_ABI.md) for exact record layouts.

## What we have actually found

### Public boundary

- Exact little-endian layouts for the public match/state/event/stop-time,
  setup, environment, entity, ball and replay records.
- The setup path and the role of PKM as the native setup/input carrier.
- A base conversion of four time slices per real-world second, with live speed
  scaling and replay behaviour distinguished.
- The managed event-buffer cursor behaviour described above.

### Native simulation skeleton

Static analysis identified a native state allocation of approximately `0x14330`
bytes. It contains side/player handles, pitch/environment state, current time
slice, status/stop fields and the native PRNG state. A core step routine
(`FUN_183e08ad0`) updates both sides, ball/pitch state and the clock. Driver
paths (`FUN_180ae00b0` and `FUN_180ae10b0`) schedule buffered or single-slice
advancement; they are scheduling paths, not the complete decision model.

The setup PRNG recurrence is recovered for the observed setup path:

```text
s = seed32 * 0xa4e7735a4c957f2d + 0x5851f42d4c957f2e  (mod 2^64)
s = s * 0x5851f42d4c957f2d + increment                 (mod 2^64)
```

Its use in every gameplay decision is **not** proven.

### Internal event/commentary path

The native engine uses internal records that are not the public 0x2c event
record. `FUN_1822ece40` allocates and deduplicates a 0x28-byte internal record;
its pointer and byte fields remain opaque. `FUN_182872b10` and
`FUN_1828738c0` form a real candidate/commentary selection and merge path. It
uses the native random state, event-ID ranges, side/player fields, time windows
and coalescing rules. This is a major breakthrough: it is genuine native event
selection evidence, not a guessed Poisson model.

The remaining hard boundary is the adapter that turns those internal candidates
into the public `MatchEvent` array returned through the playback interface.
That serializer and the exact meanings of several event fields are still being
traced.

### Data resources

We can inspect structure without pretending to understand every value:

- FMF contains commentary/presentation selectors, weighted variants and delay
  fields, xG records, quick-match distributions, role vectors, expected-score
  revisions and tactical-style templates.
- PKM contains setup data, squads/formations and repeated reference catalogues.
- IL2CPP metadata provides managed enums, field offsets, marshalling declarations
  and the 1,220-entry commentary enum.

The inspectors preserve raw values and framing. They do not silently convert
unknown resource integers into simulation rules.

## What we created

The repository currently contains:

- a deterministic Python match simulator and CLI;
- complete scenario input with players and tactical systems;
- typed event, commentary, replay and match-stat output;
- a native wire-model layer for recovered FM26 records;
- a lossless native-trace playback seam for captured frames;
- FMF and PKM structural inspectors;
- managed metadata/resource parsers;
- repeatable unit tests for all of the above;
- an evidence ledger that records confidence and unresolved questions.

The clean-room engine intentionally keeps unknown tactical instruction values as
input/provenance data rather than inventing FM coefficients. This lets us test
systems now and replace individual approximations as native evidence improves.

## What is still missing

We do not yet have:

- the exact player attribute normalization and evaluator formulas;
- the exact possession/action state machine and spatial movement model;
- the complete mapping from tactical instructions to native state;
- the public 0x2c event serializer and all field semantics;
- proven use of xG/QME tables in the live detailed match path;
- a reliable live black-box capture of a native match run;
- proof that every recovered native function belongs to the detailed match
  simulator rather than presentation, animation or manager code.

Therefore the current simulator is suitable for CLI system tests, regression
tests and architecture work. It must not be described as an FM26 clone.

## What happens next

The next work is focused narrowly on the **event-generation algorithm**:

1. Identify the playback object's concrete vtable implementation behind `Tick`
   and event-update requests.
2. Trace the internal 0x28 candidate queue into the public 0x2c event buffer.
3. Correlate event IDs, player/team bytes, time windows and stop-time records
   using controlled native traces.
4. Recover evidence-backed player/system inputs and only then replace matching
   heuristic portions of the Python engine.
5. Add CLI fixtures so every recovered rule can be replayed and regression
   tested.

The goal is not to guess faster. The goal is to make the simulator progressively
more faithful while preserving a usable CLI at every stage.

## Supporting documents

- [`docs/FINDINGS.md`](docs/FINDINGS.md) — chronological reverse-engineering
  evidence and confidence boundaries.
- [`docs/NATIVE_ABI.md`](docs/NATIVE_ABI.md) — recovered public record layouts
  and wrapper contracts.
- [`docs/GHIDRA_MATCH_BOUNDARY.md`](docs/GHIDRA_MATCH_BOUNDARY.md) — Ghidra
  boundary notes and addresses.
- [`examples/full_scenario.json`](examples/full_scenario.json) — a complete
  roster/system input example.

This work uses the repository’s reverse-engineering workflow documented by
[`reverse-engineer-anything`](/home/ilias/.agents/skills/reverse-engineer-anything/SKILL.md).

## Learning guide: how to think about a match engine

If you are new to simulation programming, imagine the match as a state machine
that runs many small steps. Each step reads the current state and writes the
next state. The state includes the clock, score, possession, ball location,
player locations, fatigue, tactical instructions and pending restarts.

At a high level, an action chain looks like this:

```text
team has possession
    -> choose a useful teammate or space
    -> choose pass, carry, cross, shot or risky action
    -> resolve pressure and technical execution
    -> update ball and player state
    -> create a fact/event if the action is presentation-worthy
```

A goal is therefore usually not an independent random number. It is the end of
a chain involving possession, positioning, chance creation, a shot and a shot
outcome. The current Python engine models that chain approximately. The native
investigation is trying to discover the equivalent FM26 chain and its exact
inputs.

### Football concepts used in the input

- **Formation:** the initial spatial arrangement, such as `4-3-3` or
  `4-2-3-1`. It is not the same thing as a player's role.
- **Role and duty:** what a player is asked to do in possession and out of
  possession, such as overlap, hold position, press or cover.
- **Mentality:** the side's broad risk/initiative setting.
- **Pressing:** how aggressively the team tries to recover the ball.
- **Directness:** how quickly the team attempts to move the ball forward.
- **Tempo:** how quickly decisions and circulation are attempted.
- **Width:** how horizontally spread the team tries to be.
- **Defensive line:** how high the defensive block is positioned.
- **Condition/fatigue:** changing physical capacity during the match.

These names are useful football concepts and accepted scenario fields. They are
not proof that the native engine combines them with the same simple weights as
our prototype.

### Scenario anatomy

The full example demonstrates the input shape. At the top are a seed and match
duration. Each side has a name, formation, tactics and a player list. A player
has a stable ID so that events can refer back to that player without relying on
display names. Core attributes are normalized to `[0, 1]` in this project.

```json
{
  "seed": 26,
  "seconds": 5400,
  "home": {
    "name": "Evidence FC",
    "formation": "4-3-3",
    "tactics": {
      "mentality": 0.62,
      "pressing": 0.78,
      "directness": 0.42,
      "tempo": 0.71,
      "width": 0.64,
      "defensive-line": 0.68,
      "instructions": {
        "DefensiveTransition": "counterpress"
      }
    },
    "players": [
      {
        "id": 1001,
        "name": "Example striker",
        "position": "ST",
        "role": "ST",
        "finishing": 0.86,
        "decisions": 0.72,
        "pace": 0.83,
        "stamina": 0.82
      }
    ]
  }
}
```

The parser allows additional attributes and instruction values. Unknown values
are preserved as scenario provenance; they are not silently converted into
invented FM coefficients.

## Learning by running experiments

The most useful experiments change one thing at a time:

1. Hold the seed fixed and change only pressing.
2. Keep tactics fixed and change one player's finishing or decisions.
3. Run many different seeds and compare distributions, not one match.
4. Replace a full roster with a deliberately weak or strong roster.
5. Replay the same native trace and check that unknown bytes remain unchanged.

These experiments test our implementation and expose regressions. They do not
alone prove FM26 uses the same formula; that requires native or controlled
runtime evidence.

## How the FM26 side is structured

The current model of the shipped engine is:

```text
Managed FM / Unity code
        |
        | setup PKM bytes, teams and environment
        v
Small plugin playback ABI
        |
        | Setup, Tick, Seek, event/stop-time updates
        v
Native playback and manager objects
        |
        | references the live simulation and presentation queues
        v
Native MATCH state
        |
        | players, sides, pitch, ball, tactics, clock and PRNG
        v
Internal action/event/commentary candidates
        |
        v
Public MatchEvent records consumed by managed playback
```

The public boundary is strong evidence. `MatchState` is `0x24` bytes,
`MatchEvent` is `0x2c`, and `StopTimeInfo` is 8 bytes. Setup accepts flags, a
signed user-team ID and a pointer/count span of PKM bytes. `Tick(float)`
advances playback and returns clock/score/update counts. The event-update call
fills a small native array and returns the number of valid records.

This tells us how data crosses the boundary. It does not, by itself, explain
how a player decides to pass or shoot.

### Native state and stepping

Static analysis found a native state allocation of approximately `0x14330`
bytes. Observed regions include side/player handles, pitch/environment state,
current time slice, status/stop fields and random state. `FUN_183e08ad0` is a
real simulation-step path that updates both side containers, pitch/ball state
and time. `FUN_180ae00b0` and `FUN_180ae10b0` are driver/scheduling paths for
buffered or single-slice advancement.

Ghidra names such as `FUN_183e08ad0` are generated addresses, not original
source names. They are useful anchors, but a name alone does not prove a
semantic interpretation.

### Native random state

The observed setup path initializes a 64-bit state from a 32-bit setup seed:

```text
state = seed32 * 0xa4e7735a4c957f2d
        + 0x5851f42d4c957f2e                  (mod 2^64)
state = state * 0x5851f42d4c957f2d + increment (mod 2^64)
```

The output then applies an xor/rotate transformation. This recurrence is
proven for setup and a native event-candidate gate. It is not proven to drive
every gameplay decision identically.

## The event-generation investigation

The central research question is how native simulation state becomes a public
time-stamped event. The evidence currently supports this sequence:

1. A simulation step changes player, ball and match state.
2. Native transition code creates internal candidates.
3. `FUN_1822ece40` allocates/deduplicates a 0x28-byte internal record.
4. `FUN_182872b10` applies a random gate and selector/event-ID logic.
5. `FUN_1828738c0` merges or filters nearby candidates using IDs, player/team
   bytes and time differences.
6. An unresolved adapter should convert accepted candidates into public
   `MatchEvent` records.
7. Managed playback consumes those records and looks up presentation data.

This is why independent “one random roll per commentary line” is the wrong
mental model. The native path has state, selectors, candidate coalescing and
time windows. The public serializer and the exact meaning of several fields
remain the key unresolved boundary.

## Why decompilation is difficult

### IL2CPP removes the original source shape

FM26 is a Unity IL2CPP build. C# classes become native code, while metadata
retains useful declarations, enums and marshalling layouts. We can often prove
that a field is an `int` at offset `0x1c`; we usually cannot recover the
developer's original variable name or explanatory source comment.

### The native plugin is huge and indirect

The match implementation is in a roughly 515 MB `game_plugin.dll` with many
generated or stripped functions. Exported functions are often wrappers that
call a virtual function through an object pointer. The interesting code is
found by following object creation, vtables, callers and state-field accesses.

### Ghidra output is evidence, not an oracle

Ghidra may produce guessed types, unreachable-block warnings, huge functions
and names like `FUN_182872b10`. We validate interpretations with callers,
callees, allocation sizes, repeated offsets, strings/RTTI, managed declarations
and runtime observations. A readable decompilation line is a clue, not proof.

### Resource numbers are ambiguous

FMF files are compressed resource containers. PKM files carry match setup and
reference data. Metadata carries managed declarations. A serialized integer may
be a UI ID, version, lookup index or gameplay coefficient. We preserve raw
values until surrounding code establishes its meaning.

## Evidence labels in the notes

- **Observed ABI:** size, offset, export, wrapper copy or marshal operation
  directly established from the shipped build.
- **Static native evidence:** repeated field access or related calls, but no
  complete runtime proof.
- **Runtime evidence:** controlled execution or captured trace confirms a
  transition.
- **Hypothesis:** plausible interpretation that still needs corroboration.

This distinction is the most important habit in reverse engineering: do not
turn a plausible guess into a gameplay coefficient just because it produces
nice-looking matches.

## A learning path through the code

1. Read `examples/full_scenario.json` to learn the input vocabulary.
2. Read `src/match_engine/model.py` for teams, players, tactics and events.
3. Read `src/match_engine/engine.py` and follow the clock/possession/action
   loop.
4. Run the CLI, change one input, and compare JSON output.
5. Read `src/match_engine/native.py` to see exact byte records.
6. Read `docs/NATIVE_ABI.md` for the evidence behind each field offset.
7. Read the later entries of `docs/FINDINGS.md` for the native event path.

## What is still missing

We do not yet know the exact player normalization/evaluator formulas, spatial
movement model, full tactical-to-native mapping, public 0x2c serializer, live
use of xG/QME tables, complete playback vtable implementation, or a sufficiently
controlled black-box native match trace.

The current engine is suitable for CLI system tests, architecture work and
regression tests. It should not be marketed as FM26 parity.

## Roadmap

The next work stays focused on event generation:

1. Identify the concrete playback implementation behind `Tick` and event
   updates.
2. Follow the internal 0x28 candidate queue into the public 0x2c array.
3. Correlate event IDs, player/team bytes, time windows and stop-time records.
4. Recover native player/system input mappings.
5. Replace only matching heuristic subsystems in the Python engine.
6. Add replayable fixtures and regression tests for each recovered rule.

The goal is not to guess faster. It is to become more faithful while keeping a
usable CLI at every stage.
