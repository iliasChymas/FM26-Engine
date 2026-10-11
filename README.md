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

Run it from this directory:

```bash
cd match_engine_recreation
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

The `match_engine_recreation` package currently contains:

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
