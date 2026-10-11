# Ghidra evidence: FM26 native match boundary

This note records observations obtained through the connected GhidraMCP
project `FM`, program `/game_plugin.dll`. It is a clean-room evidence ledger:
the implementation may use these public boundary facts, but it does not copy
private source or claim that wrapper behavior is the simulation algorithm.

## Program state

- GhidraMCP instance: GUI, version 7.0.0, 205 endpoints.
- Program path in the Ghidra project: `/game_plugin.dll`.
- Exported native match functions are present as imported/export-table labels.
- The program contains more than 129,000 discovered functions; auto-analysis
  was still running while this pass inspected the export wrappers.

## Export addresses and wrapper behavior

The following are the exported entry points and the protected-interface calls
visible in their decompilation. Addresses are Ghidra virtual addresses; the
RVA is the address minus the PE image base used by the decompiler comments.

| Export | VA | RVA | Observed operation |
| --- | ---: | ---: | --- |
| `i_plugin_match_interface_setup` | `0x19a268c40` | `0x1a268c40` | validates handle, copies eight 32-bit setup words, calls vtable `+0x18`, writes a `PluginMatchSetup` result |
| `i_plugin_match_interface_shutdown` | `0x193fc0ee0` | `0x13fc0ee0` | calls vtable `+0x70` |
| `i_plugin_match_interface_get_environment_setup` | `0x19c8903a0` | `0x1c8903a0` | calls vtable `+0x40`, copies exactly `0x420` bytes |
| `i_plugin_match_playback_interface_tick` | `0x185defed0` | `0x5defed0` | calls vtable `+0x20` with a `float`, copies a `0x24`-byte `MatchState` |
| `i_plugin_match_playback_interface_get_max_match_time` | `0x18c9ed960` | `0xc9ed960` | calls vtable `+0x28`, returns a 32-bit value |
| `i_plugin_match_playback_interface_seek` | `0x187a9a490` | `0x7a9a490` | calls vtable `+0xa8`, passes the low 32 bits of the requested slice |
| `i_plugin_match_playback_interface_skip_dead_sim_time` | `0x18a382320` | `0xa382320` | calls vtable `+0xb0` |
| `i_plugin_match_playback_interface_request_match_events_update` | `0x19277a170` | `0x1277a170` | copies a two-word native-array carrier, calls vtable `+0xb8`, returns a 32-bit count |
| `i_plugin_match_playback_interface_request_match_stop_time_infos_update` | `0x19c06ba10` | `0x1c06ba10` | same carrier shape, calls vtable `+0xd0`, returns a 32-bit count |
| `i_plugin_match_playback_interface_plugin_data_update` | `0x1945655d0` | `0x145655d0` | calls vtable `+0x18` |

Additional wrapper calls inspected in this pass make the argument widths
explicit:

- `get_current_match_time_slice` calls vtable `+0x30` and returns a 32-bit
  value.
- `seek` truncates its public 64-bit argument to the low 32 bits before the
  virtual call; this is an ABI fact, not evidence that the native timeline is
  intrinsically 32-bit everywhere.
- `request_match_stop_time_infos_update` copies 16 input bytes into a
  0x50-byte temporary carrier, clears the remaining fields, calls `+0xd0`,
  returns the 32-bit count, and conditionally invokes the carrier's disposer
  selected by its low two flag bits.
- `get_playback_interface` is a protected/obfuscated dispatcher target rather
  than a useful source-level implementation in this analysis; its export
  thunk is still a valid boundary symbol.
- `plugin_data_update` calls vtable `+0x18` with no explicit payload.

Every wrapper first calls `WaitForActivation`, loads the opaque interface
object from the handle carrier, validates it through an internal helper, and
uses an atomic temporary reference while making the virtual call. Invalid
handles zero the output or return zero and report through the native logger.
Those lifetime operations are boundary plumbing, not event-generation rules.

The exported symbols are ten-byte thunks into shared wrapper bodies. For
example, the tick export jumps to `FUN_18001d890`, and the event-update export
jumps to `FUN_18001e220`. The event-update body copies the first 16 bytes of
the managed native-array carrier, clears the remaining temporary carrier
fields, calls the protected vtable slot, returns its count, and disposes a
temporary allocation when the carrier's low flag bits request it. This is why
the recreation treats the native-array layout as a transport boundary rather
than trying to interpret it as a match-event list without a runtime trace.

## Match-state copy

The `Tick` wrapper copies the returned fields into a caller-owned `0x24`-byte
buffer. The observed writes correspond to the recovered `MatchState` layout:

```text
flags                         @ 0x00 (u32)
time_slice                    @ 0x04 (i32)
catching_up_to_time_slice     @ 0x08 (i32)
time                          @ 0x0c (f32)
injury_time                   @ 0x10 (i32)
period                        @ 0x14 (byte)
home_crowd_mood               @ 0x15 (byte)
away_crowd_mood               @ 0x16 (byte)
home_goals                    @ 0x17 (signed byte)
away_goals                    @ 0x18 (signed byte)
match_events_update_size      @ 0x1c (u32)
stop_time_infos_update_size   @ 0x20 (u32)
```

The native update request wrappers do not themselves generate or interpret
events. They pass the native-array carrier to the protected object and return
the count produced by that object.

## Animation/playback separation

The export table also contains a separate `simatchplayback...anim.i_matches`
interface. Its wrappers call different virtual slots: create uses `+0x18`,
update-to-time uses `+0x30` with a low-32-bit time slice and a second 32-bit
argument, get-ball-contacts uses `+0x80` with a time slice and an output array
carrier, play-match-event-at-time uses `+0xa0` with two low-32-bit arguments,
clear-data uses `+0x28`, and release uses `+0x20`. These are animation/data
playback services, not evidence that the match simulator chooses events from
the same interface.

The playback commentary accessors are also distinct from event generation:
`GetCommentaryStringCount` calls `+0xc0` with an event index and past-tense
flag, while `GetCommentaryString` calls `+0xc8` with the event index, the
past-tense flag, and a signed string index. The latter returns a managed string
through the native marshalling layer. This confirms that commentary text is
looked up after an event index exists; it is not a source of event-selection
probabilities.

Additional interface getters corroborated the post-setup data boundary:
`GetMatchInfo` calls vtable `+0x88` and writes the managed 20-byte
`MatchInfo`; `GetMatchUniqueIds` calls `+0x80` and writes the managed 24-byte
unique-ID record; `GetOutsideEnvironmentSetup` calls `+0x68` and writes the
managed 12-byte outside-environment record. `GetEntitySetup` calls `+0x20`
with a caller-provided native-array carrier, while `GetEnvironmentSetup`
calls `+0x40` and copies a fixed `0x420` bytes. These calls produce client
presentation/setup data after the PKM-backed native setup and are not player
decision inputs exposed by the wrapper ABI.

## Protected play-loop anchors

Using RIP-relative references from the raw diagnostic strings, Ghidra resolves
the `MATCH::play` diagnostic to `FUN_1824ec170` and the
`MATCH::check_for_basic_time_slice_skipping` diagnostic to
`FUN_1824eda20`, which is called by `FUN_183e08ad0`. This is the first static
anchor inside the protected play loop rather than an export thunk.

Observed, without assigning names to opaque fields:

- `FUN_1824ec170` takes a state pointer and two integer arguments, examines a
  mode byte at `state+0x142fa`, and dispatches to state-specific routines at
  `FUN_183e08ad0`, `FUN_183e0a170`, `FUN_183e0b9f0`, and `FUN_183e0be00`.
- The state-specific routines repeatedly read/write `state+0x14278` and each
  increments that 32-bit field once per completed iteration. The routines also
  update two team-side objects at `state+0x14100` and `state+0x14108`, call
  ball/player update helpers, and invoke event/transition helpers. Their
  return values contain small mode/status bytes (observed low-byte values
  include 1, 2, 3 and 4), but the enum meaning is not established.
- `FUN_1824eda20` asks an internal timeline predicate about
  `state+0x14278 + 1`, checks several stop/target fields, and may advance
  transient data or dispatch to stop/skipping helpers. A diagnostic is emitted
  only on one late-path condition. The literal thresholds and field offsets are
  recorded evidence; their domain meanings remain unresolved.

This anchor is useful for future static call-graph work and confirms that the
native engine advances discrete integer time slices internally. It still does
not reveal the player-attribute utility, random-number stream, or event
selection probabilities.

Caller context adds a useful control-flow constraint. Several callers invoke
`FUN_1824ec170(state, 1, target_slice)` and then compare the state field at
`+0x14278` with that target. Other callers repeatedly invoke
`FUN_1824ec170(state, 0, -1)` while the stop flag is clear. One caller targets
`current_slice + 0x4b0` and compares against that bound. This demonstrates a
targeted advance versus repeated single-slice advance at the native boundary;
it does not by itself establish the public `Tick(float)` conversion or the
meaning of the mode byte.

## Event record layout corroboration

The `get_simatchplayback__si__match__match_event_layout_signature` decompiler
constructs a serialized layout string with the following fields and offsets:

```text
six 32-bit player IDs       @ 0x00, 0x04, 0x08, 0x0c, 0x10, 0x14
player-team bit flags       @ 0x18 (u8)
commentary event             @ 0x1a (u16)
time slice                   @ 0x1c (i32)
duration                    @ 0x20 (i32)
event flags                  @ 0x24 (u8)
commentary importance        @ 0x25 (u8)
incident importance          @ 0x26 (u8)
data1                        @ 0x28 (i32)
record size                  0x2c
```

This is consistent with the managed marshaller and the existing explicit
little-endian decoder. It does not establish which event IDs the simulator
chooses or what `data1` means for each event.

## Setup boundary

The setup wrapper copies eight 32-bit words from the setup-config input into a
temporary native object and invokes the protected setup method. The output
buffer is the recovered `PluginMatchSetup` record:

```text
opaque match handle         @ 0x00 (u64)
match-engine version        @ 0x08 (u32)
match version               @ 0x0c (u32)
entity count                @ 0x10 (i32)
```

This confirms that a valid recreation must accept the full setup/input carrier
and not only seed, duration, team names, and a handful of tactics. The native
wrapper still does not expose the protected setup or event-generation logic.

## Unresolved questions

1. The vtable implementation behind the wrapper offsets is still the primary
   target for static analysis; the wrapper alone cannot reveal probabilities.
2. The native-array carrier layout must be confirmed at runtime before any
   Frida hook dereferences it.
3. `PluginMatchSetupConfig` identifies a pinned PKM byte span and flags, but
   the PKM field semantics and native input partition remain partly opaque.
4. The QME distributions and xG tables are serialized inputs; their revision
   selection, feature transforms, and use in detailed match play remain to be
   demonstrated.
