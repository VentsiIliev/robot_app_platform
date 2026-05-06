import unittest
from datetime import timezone

from src.shared_contracts.events.glue_process_events import GlueProcessTopics
from src.shared_contracts.events.localization_events import LanguageChangedEvent, LocalizationTopics
from src.shared_contracts.events.notification_events import (
    NotificationSeverity,
    NotificationTopics,
    UserNotificationEvent,
)
from src.shared_contracts.events.pick_and_place_events import (
    MatchedWorkpieceInfo,
    PickAndPlaceDiagnosticsEvent,
    PickAndPlaceTopics,
    WorkpiecePlacedEvent,
)
from src.shared_contracts.events.process_events import (
    ProcessBusyEvent,
    ProcessState,
    ProcessStateEvent,
    ProcessTopics,
    ServiceUnavailableEvent,
)
from src.shared_contracts.events.weight_events import CellState, CellStateEvent, WeightReading, WeightTopics


class TestProcessEvents(unittest.TestCase):

    def test_process_topics_are_stable(self):
        self.assertEqual(ProcessTopics.ACTIVE, "process/active/state")
        self.assertEqual(ProcessTopics.state("glue"), "process/glue/state")
        self.assertEqual(ProcessTopics.error("glue"), "process/glue/error")
        self.assertEqual(
            ProcessTopics.service_unavailable("glue"),
            "process/glue/service_unavailable",
        )
        self.assertEqual(ProcessTopics.busy("robot_settings"), "process/robot_settings/busy")

    def test_process_state_event_uses_utc_timestamp(self):
        event = ProcessStateEvent(
            process_id="glue",
            state=ProcessState.RUNNING,
            previous=ProcessState.IDLE,
        )

        self.assertEqual(event.timestamp.tzinfo, timezone.utc)

    def test_process_support_events_preserve_payload(self):
        busy = ProcessBusyEvent(requested_by="ui", message="busy")
        unavailable = ServiceUnavailableEvent(process_id="glue", missing_services=["robot"])

        self.assertEqual(busy.requested_by, "ui")
        self.assertEqual(unavailable.missing_services, ["robot"])


class TestPickAndPlaceEvents(unittest.TestCase):

    def test_pick_and_place_topics_are_stable(self):
        self.assertEqual(PickAndPlaceTopics.WORKPIECE_PLACED, "pick_and_place/workpiece_placed")
        self.assertEqual(PickAndPlaceTopics.PLANE_RESET, "pick_and_place/plane_reset")
        self.assertEqual(PickAndPlaceTopics.MATCH_RESULT, "pick_and_place/match_result")
        self.assertEqual(PickAndPlaceTopics.DIAGNOSTICS, "pick_and_place/diagnostics")
        self.assertEqual(GlueProcessTopics.DIAGNOSTICS, "glue/process/diagnostics")

    def test_pick_and_place_events_preserve_payload(self):
        placed = WorkpiecePlacedEvent(
            workpiece_name="part-a",
            gripper_id=2,
            plane_x=10.0,
            plane_y=20.0,
            width=30.0,
            height=40.0,
        )
        matched = MatchedWorkpieceInfo(
            workpiece_name="part-a",
            workpiece_id="wp-1",
            gripper_id=2,
            orientation=90.0,
        )
        diagnostics = PickAndPlaceDiagnosticsEvent(snapshot={"stage": "startup"})

        self.assertEqual(placed.timestamp.tzinfo, timezone.utc)
        self.assertEqual(matched.workpiece_id, "wp-1")
        self.assertEqual(diagnostics.snapshot, {"stage": "startup"})


class TestWeightEvents(unittest.TestCase):

    def test_weight_topics_are_stable(self):
        self.assertEqual(WeightTopics.state(3), "weight/cell/3/state")
        self.assertEqual(WeightTopics.reading(3), "weight/cell/3/reading")
        self.assertEqual(WeightTopics.all_readings(), "weight/cell/all/reading")

    def test_weight_reading_validity_uses_inclusive_bounds(self):
        self.assertTrue(WeightReading(cell_id=1, value=10.0).is_valid(10.0, 20.0))
        self.assertFalse(WeightReading(cell_id=1, value=9.9).is_valid(10.0, 20.0))
        self.assertFalse(WeightReading(cell_id=1, value=20.1).is_valid(10.0, 20.0))

    def test_cell_state_event_uses_utc_timestamp(self):
        event = CellStateEvent(cell_id=1, state=CellState.CONNECTED)

        self.assertEqual(event.timestamp.tzinfo, timezone.utc)


class TestUiEvents(unittest.TestCase):

    def test_localization_topic_and_event_are_stable(self):
        event = LanguageChangedEvent(language_code="bg")

        self.assertEqual(LocalizationTopics.LANGUAGE_CHANGED, "localization/language_changed")
        self.assertEqual(event.language_code, "bg")
        self.assertEqual(event.timestamp.tzinfo, timezone.utc)

    def test_notification_event_defaults_are_independent(self):
        first = UserNotificationEvent(source="ui", severity=NotificationSeverity.INFO)
        second = UserNotificationEvent(source="ui", severity=NotificationSeverity.WARNING)

        self.assertEqual(NotificationTopics.USER, "ui/notification")
        self.assertEqual(first.params, {})
        self.assertEqual(second.params, {})
        self.assertIsNot(first.params, second.params)
        self.assertEqual(first.timestamp.tzinfo, timezone.utc)

