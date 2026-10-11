import struct
import unittest

from match_engine.native import (
    AnimationMatchID, BallContactID, CommentaryEventFlags, CommentaryImportance, CompetitionType,
    IncidentImportance, MatchGender, MatchPeriod, MatchStateFlags, MatchStopReason,
    NativeBallContact, NativeBallVelocity, NativeHawkeyeReplayInfo,
    EntityKind, NativeAppearanceData, NativeMatchBallData, NativeMatchEntitySetup,
    NativeMatchEvent, NativeMatchInfo, NativeCommentaryEvent,
    NativeInternalEventRecord,
    ManagedCommentaryEvent,
    NativeMatchLightingAndWeatherSetup, NativeMatchObjectState,
    NativeMatchOutsideEnvironmentSetup, NativeMatchStadiumLocationSetup,
    NativeMatchStadiumSetup, NativeStadiumSetupInfo,
    NativeMatchEnvironmentSetup, NativePlayerKitSetup, NativeRefereeKitSetup,
    NativeTeamKitSetup,
    NativeUniqueIds, NativeCrowdKitSetup, NativeStadiumColouringData,
    NativeBillboardInfo, BillboardFlags, MatchEventPlayerTeams,
    NativePitchSetupInfo,
    NativeMatchState, NativeOffsideReplayInfo, NativePluginMatchSetup,
    NativeMatchHandle,
    ObservedSetupRandom,
    NativePluginMatchSetupConfig, NativeStopTimeInfo, PluginMatchSetupFlags, SetPieceType,
    NativeStandSetupInfo, PrecipitationType, StageType, SubCompetitionType,
    TrophyType, ViewableMatchType,
    TIME_SLICES_PER_SECOND, seconds_from_time_slice, time_slice_from_seconds,
    COMMENTARY_EVENT_BASE, COMMENTARY_EVENT_COUNT, COMMENTARY_EVENT_LAST,
    native_commentary_event_id, fmf_commentary_event_index,
)


class NativeBoundaryTests(unittest.TestCase):
    def test_observed_setup_random_recurrence_is_replayable(self):
        first = ObservedSetupRandom.from_setup_seed(123)
        second = ObservedSetupRandom.from_setup_seed(123)
        values = [first.next_value_1_to_20() for _ in range(8)]
        self.assertEqual(values, [second.next_value_1_to_20() for _ in range(8)])
        self.assertTrue(all(1 <= value <= 20 for value in values))
        self.assertEqual(first.state, second.state)

    def test_observed_setup_random_exposes_raw_event_gate_output(self):
        raw = ObservedSetupRandom.from_setup_seed(123)
        scaled = ObservedSetupRandom.from_setup_seed(123)
        raw_value = raw.next_uint32()
        scaled_value = scaled.next_value_1_to_20()
        self.assertEqual(scaled_value, ((raw_value * 0x13) >> 32) + 1)
        self.assertEqual(raw.state, scaled.state)

    def test_recovered_time_slice_conversion(self):
        self.assertEqual(TIME_SLICES_PER_SECOND, 4)
        self.assertEqual(time_slice_from_seconds(15), 60)
        self.assertEqual(seconds_from_time_slice(3), .75)
        self.assertEqual(AnimationMatchID.NONE, 255)

    def test_commentary_table_id_translation(self):
        self.assertEqual(COMMENTARY_EVENT_BASE, 8000)
        self.assertEqual(COMMENTARY_EVENT_COUNT, 1220)
        self.assertEqual(COMMENTARY_EVENT_LAST, 9219)
        self.assertEqual(native_commentary_event_id(0), 8000)
        self.assertEqual(native_commentary_event_id(1219), 9219)
        self.assertEqual(fmf_commentary_event_index(8000), 0)
        self.assertEqual(fmf_commentary_event_index(9219), 1219)
        with self.assertRaises(ValueError):
            native_commentary_event_id(1220)
        with self.assertRaises(ValueError):
            fmf_commentary_event_index(9220)

    def test_managed_commentary_names_keep_recovered_ids(self):
        self.assertEqual(NativeCommentaryEvent.LOSE_CONTROL_OF_BALL, 8002)
        self.assertEqual(NativeCommentaryEvent.TAKE_CORNER, 8064)
        self.assertEqual(NativeCommentaryEvent.GOAL_ONE, 8142)

    def test_recovered_wire_sizes(self):
        self.assertEqual(NativeInternalEventRecord.SIZE, 0x28)
        self.assertEqual(NativeMatchEvent.FORMAT.size, 0x2C)
        self.assertEqual(NativeStopTimeInfo.FORMAT.size, 0x08)
        self.assertEqual(NativeMatchState.FORMAT.size, 0x24)
        self.assertEqual(NativeBallContact.FORMAT.size, 0x14)
        self.assertEqual(NativeBallVelocity.FORMAT.size, 0x18)
        self.assertEqual(NativeMatchBallData.FORMAT.size, 0x08)
        self.assertEqual(NativeHawkeyeReplayInfo.FORMAT.size, 0x14)
        self.assertEqual(NativeOffsideReplayInfo.FORMAT.size, 0x14)
        self.assertEqual(NativeMatchObjectState.FORMAT.size, 0x20)
        self.assertEqual(NativePluginMatchSetupConfig.FORMAT.size, 0x20)
        self.assertEqual(NativePluginMatchSetup.FORMAT.size, 0x18)
        self.assertEqual(NativeMatchInfo.FORMAT.size, 0x14)
        self.assertEqual(NativeMatchOutsideEnvironmentSetup.FORMAT.size, 0x0c)
        self.assertEqual(NativeMatchStadiumLocationSetup.FORMAT.size, 0x14)
        self.assertEqual(NativePitchSetupInfo.FORMAT.size, 0x14)
        self.assertEqual(NativeMatchLightingAndWeatherSetup.FORMAT.size, 0x30)
        self.assertEqual(NativeStandSetupInfo.FORMAT.size, 0x0c)
        self.assertEqual(NativeStadiumSetupInfo.FORMAT.size, 0xA0)
        self.assertEqual(NativeMatchStadiumSetup.SIZE, 0xB4)
        self.assertEqual(NativePlayerKitSetup.SIZE, 0xD4)
        self.assertEqual(NativeTeamKitSetup.SIZE, 0x200)
        self.assertEqual(NativeRefereeKitSetup.SIZE, 0x20)
        self.assertEqual(NativeMatchEnvironmentSetup.FORMAT.size, 0x420)
        self.assertEqual(NativeMatchEntitySetup.FORMAT.size, 0x12c)
        self.assertEqual(NativeMatchEntitySetup.NATIVE_SIGNATURE_SIZE, 0x130)
        self.assertEqual(NativeUniqueIds.FORMAT.size, 0x18)
        self.assertEqual(NativeCrowdKitSetup.FORMAT.size, 0x34)
        self.assertEqual(NativeStadiumColouringData.FORMAT.size, 0xcc)
        self.assertEqual(NativeBillboardInfo.FORMAT.size, 0x08)

    def test_internal_event_record_remains_opaque_but_offset_stable(self):
        raw = bytearray(NativeInternalEventRecord.SIZE)
        struct.pack_into("<QQiiibbbbbbb", raw, 0,
                         0x1111, 0x2222, 7, 8, 9, 1, 2, 3, 4, 5, 6, 7)
        record = NativeInternalEventRecord(bytes(raw))
        self.assertEqual(record.payload_pointer_0, 0x1111)
        self.assertEqual(record.payload_pointer_8, 0x2222)
        self.assertEqual(record.value_i32_10, 7)
        self.assertEqual(record.value_i32_14, 8)
        self.assertEqual(record.time_like_i32_18, 9)
        self.assertEqual(record.opaque_bytes_1c_22, bytes(range(1, 8)))

    def test_plugin_setup_boundary_round_trip(self):
        handle = NativeMatchHandle(0x123456789ABCDEF0)
        self.assertTrue(handle.is_valid)
        self.assertEqual(NativeMatchHandle.unpack(handle.pack()), handle)
        self.assertFalse(NativeMatchHandle(0).is_valid)
        config = NativePluginMatchSetupConfig(
            PluginMatchSetupFlags.LOADING_PKM | PluginMatchSetupFlags.VIEWING_PAST_MATCH,
            -1, 0x123456789ABCDEF0, 2048,
        )
        setup = NativePluginMatchSetup(42, 2601, 3, 25)
        self.assertEqual(NativePluginMatchSetupConfig.unpack(config.pack()), config)
        self.assertEqual(NativePluginMatchSetup.unpack(setup.pack()), setup)

    def test_native_update_buffers_decode_only_aligned_records(self):
        event = NativeMatchEvent(
            (1, 2, 3, 4, 5, 6), MatchEventPlayerTeams.VISITOR_TEAM_PLAYER1,
            8052, 40, 0, CommentaryEventFlags.FLASHING,
            CommentaryImportance.HIGH, IncidentImportance.MAIN_EVENTS, 7,
        )
        decoded = NativeMatchEvent.unpack_many(event.pack() * 2)
        self.assertEqual(decoded, (event, event))
        self.assertEqual(decoded[0].as_dict()["commentary_event"], 8052)
        with self.assertRaises(ValueError):
            NativeMatchEvent.unpack_many(event.pack() + b"x")

        stop = NativeStopTimeInfo(40, MatchStopReason.SET_PIECE, SetPieceType.CORNER)
        self.assertEqual(NativeStopTimeInfo.unpack_many(stop.pack() * 2), (stop, stop))
        self.assertEqual(stop.as_dict()["set_piece_type"], int(SetPieceType.CORNER))
        with self.assertRaises(ValueError):
            NativeStopTimeInfo.unpack_many(stop.pack() + b"x")

    def test_managed_commentary_carrier_requires_unresolved_fields_explicitly(self):
        event = NativeMatchEvent(
            (1, 2, 3, 4, 5, 6), MatchEventPlayerTeams.VISITOR_TEAM_PLAYER1,
            8052, 40, 2, CommentaryEventFlags.FLASHING,
            CommentaryImportance.HIGH, IncidentImportance.MAIN_EVENTS, 7,
        )
        managed = ManagedCommentaryEvent.from_native(
            event, text_present=("kick-off",), text_past=(),
            contributor_time_slice=36,
        )
        self.assertEqual(managed.player_unique_ids, event.player_ids)
        self.assertEqual(managed.duration, event.duration_time_slices)
        self.assertEqual(managed.as_dict()["contributor_time_slice"], 36)
        with self.assertRaises(ValueError):
            ManagedCommentaryEvent(
                (), (), (1, 2), MatchEventPlayerTeams.NONE, 0, 0, 0,
                8000, CommentaryEventFlags.NONE, CommentaryImportance.LOW,
                IncidentImportance.SKIPPABLE, 0,
            )

    def test_match_info_boundary_round_trip(self):
        info = NativeMatchInfo(
            ViewableMatchType.MANAGING, CompetitionType.DOMESTIC_LEAGUE,
            SubCompetitionType.PREMIER_LEAGUE, StageType.UCL_LEAGUE_PHASE,
            TrophyType.NATIONAL_CHAMPIONSHIP_1, MatchGender.FEMALE, 2026,
            -1, -1, 0, 1, 0,
        )
        self.assertEqual(NativeMatchInfo.unpack(info.pack()), info)

    def test_match_identity_and_presentation_boundaries_round_trip(self):
        self.assertEqual(
            NativeUniqueIds.unpack(NativeUniqueIds(1, 2, 3, 4, 0x123456789).pack()),
            NativeUniqueIds(1, 2, 3, 4, 0x123456789),
        )
        crowd = NativeCrowdKitSetup(
            (1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0),
            (0.0, 0.0, 1.0, 1.0), 2,
        )
        self.assertEqual(NativeCrowdKitSetup.unpack(crowd.pack()), crowd)
        colour_values = [(float(i),) * 4 for i in range(12)]
        colours = NativeStadiumColouringData(
            1, 2, 3, *colour_values[0:3], 4, 5, 6, *colour_values[3:6],
            *colour_values[6:8], 9, *colour_values[8:11],
        )
        self.assertEqual(NativeStadiumColouringData.unpack(colours.pack()), colours)
        billboard = NativeBillboardInfo(55, BillboardFlags.SHOW_INFO | BillboardFlags.HAS_YELLOW_CARD)
        self.assertEqual(NativeBillboardInfo.unpack(billboard.pack()), billboard)

    def test_environment_boundaries_round_trip(self):
        values = (
            NativeMatchOutsideEnvironmentSetup(123, -4, 500000),
            NativeMatchStadiumLocationSetup(1.0, 2.0, 3.0, 4.0, 5.0),
            NativePitchSetupInfo(105.0, 68.0, .25, 17, PrecipitationType.RAIN, 2, 3, 1),
            NativeMatchLightingAndWeatherSetup(
                2026, 20.5, PrecipitationType.DRIZZLE, .2, .4, 18.0, .1,
                (1.0, 0.0, -1.0), .03, .8,
            ),
            NativeStandSetupInfo(10000, 12, 1, 0),
        )
        for value in values:
            decoded = type(value).unpack(value.pack())
            if isinstance(value, NativeMatchLightingAndWeatherSetup):
                self.assertEqual(decoded.day, value.day)
                self.assertEqual(decoded.precipitation_type, value.precipitation_type)
                self.assertAlmostEqual(decoded.time, value.time)
                self.assertAlmostEqual(decoded.temperature, value.temperature)
                self.assertEqual(decoded.wind_direction, value.wind_direction)
            else:
                self.assertEqual(decoded, value)

    def test_stadium_boundary_round_trip(self):
        stand = NativeStandSetupInfo(1000, 5, 1, 0)
        stadium = NativeStadiumSetupInfo(
            50000, 12, 42000, 25000, 17000, 8, 12.5, 1, 1, 1, 0,
            (stand,) * 8, (0.0, 0.0, 1.0, 1.0), (1.0, 1.0, 0.0, 1.0),
        )
        value = NativeMatchStadiumSetup(
            NativePitchSetupInfo(105.0, 68.0, .25, 17, PrecipitationType.DRY, 2, 3, 1),
            stadium,
        )
        self.assertEqual(NativeMatchStadiumSetup.unpack(value.pack()), value)

    def test_environment_kit_boundary_round_trip(self):
        value = NativeMatchEnvironmentSetup(
            NativeTeamKitSetup(bytes([1]) * 0x200),
            NativeTeamKitSetup(bytes([2]) * 0x200),
            NativeRefereeKitSetup(bytes([3]) * 0x20),
        )
        self.assertEqual(NativeMatchEnvironmentSetup.unpack(value.pack()), value)

    def test_explicit_appearance_and_kit_fields_decode_without_losing_raw_bytes(self):
        appearance_raw = bytearray(0xE8)
        appearance_raw[0] = 28
        appearance_raw[0x5C] = 7
        appearance_raw[0xE4] = 5
        appearance_raw[0x60:0x64] = struct.pack("<f", 0.25)
        appearance = NativeAppearanceData(bytes(appearance_raw))
        decoded = appearance.fields()
        self.assertEqual(decoded["age"], 28)
        self.assertEqual(decoded["skin_tone_index"], 7)
        self.assertEqual(decoded["outfit_tendency"], 5)
        self.assertAlmostEqual(decoded["brow_height"], .25)
        player_raw = bytearray(0xD4)
        player_raw[0:4] = bytes((1, 2, 3, 4))
        player_raw[4:20] = struct.pack("<4f", 1.0, 0.0, .5, 1.0)
        player = NativePlayerKitSetup(bytes(player_raw))
        self.assertEqual(player.fields()["shirt_style"], 3)
        self.assertEqual(player.fields()["shirt_background_color"], (1.0, 0.0, .5, 1.0))
        team_raw = bytearray(0x200)
        team_raw[0] = 9
        team_raw[0x1F0:0x1F8] = struct.pack("<q", 1234)
        team = NativeTeamKitSetup(bytes(team_raw))
        self.assertEqual(team.fields()["kit_type"], 9)
        self.assertEqual(team.fields()["team_id"], 1234)

    def test_entity_setup_boundary_round_trip(self):
        entity = NativeMatchEntitySetup(
            EntityKind.PLAYER, 4, True, False, False, (1.0, .5, .25, 1.0),
            1.0, 75.0, 0x1000, 0x2000, 9, False, False, False, False,
            False, False, 1, 12345, False, True,
            NativeAppearanceData(bytes(0xE8)),
        )
        self.assertEqual(NativeMatchEntitySetup.unpack(entity.pack()), entity)

    def test_match_event_round_trip(self):
        event = NativeMatchEvent(
            (1, 2, 3, 4, 5, 6), MatchEventPlayerTeams.VISITOR_TEAM_PLAYER2 | MatchEventPlayerTeams.VISITOR_TEAM_PLAYER4, 8052, 120, 4,
            CommentaryEventFlags.FLASHING, CommentaryImportance.HIGH,
            IncidentImportance.MAIN_EVENTS, 99,
        )
        self.assertEqual(NativeMatchEvent.unpack(event.pack()), event)

    def test_stop_and_state_round_trip(self):
        stop = NativeStopTimeInfo(450, MatchStopReason.SET_PIECE, SetPieceType.CORNER)
        self.assertEqual(NativeStopTimeInfo.unpack(stop.pack()), stop)
        state = NativeMatchState(
            MatchStateFlags.SIMULATING, 450, 460, 45.0, 2,
            MatchPeriod.FIRST_HALF, 0, 5, 1, 0, 3, 2,
        )
        decoded = NativeMatchState.unpack(state.pack())
        self.assertEqual(decoded, state)

    def test_ball_boundary_round_trip(self):
        contact = NativeBallContact(1.5, (2.0, 3.0, 4.0), BallContactID.POST)
        velocity = NativeBallVelocity((1.0, 2.0, 3.0), (4.0, 5.0, 6.0))
        self.assertEqual(NativeBallContact.unpack(contact.pack()), contact)
        self.assertEqual(NativeBallVelocity.unpack(velocity.pack()), velocity)

    def test_replay_and_object_boundaries_round_trip(self):
        values = (
            NativeMatchBallData(12, True),
            NativeHawkeyeReplayInfo(100, 100.5, (1.0, 2.0, 3.0)),
            NativeOffsideReplayInfo(100.5, 100, 3.0, 2.5, True),
            NativeMatchObjectState((0.0, 0.0, 0.0, 1.0), (1.0, 2.0, 3.0), True),
        )
        for value in values:
            self.assertEqual(type(value).unpack(value.pack()), value)


if __name__ == "__main__":
    unittest.main()
