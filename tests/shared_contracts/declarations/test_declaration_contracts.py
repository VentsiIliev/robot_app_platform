import unittest

from src.engine.robot.configuration import MovementGroup
from src.shared_contracts.declarations.dispensing import DispenseChannelDefinition
from src.shared_contracts.declarations.movement import MovementGroupDefinition, MovementGroupType
from src.shared_contracts.declarations.system_specs import (
    ApplicationSpec,
    FolderSpec,
    RolePolicy,
)
from src.shared_contracts.declarations.targeting import RemoteTcpDefinition, TargetFrameDefinition
from src.shared_contracts.declarations.tooling import ToolDefinition, ToolSlotDefinition
from src.shared_contracts.declarations.work_areas import WorkAreaDefinition, WorkAreaObserverBinding


class TestSystemSpecs(unittest.TestCase):

    def test_folder_spec_defaults_translation_key_from_name(self):
        spec = FolderSpec(folder_id=1, name="Settings", display_name="Settings")

        self.assertEqual(spec.translation_key, "folder.settings")

    def test_application_spec_defaults_app_id_from_name(self):
        spec = ApplicationSpec(name="Robot Settings", folder_id=10)

        self.assertEqual(spec.app_id, "robot_settings")

    def test_role_policy_normalizes_values_to_strings(self):
        policy = RolePolicy(
            role_values=["Admin", 2],
            admin_role_value="Admin",
            default_permission_role_values=[2],
            protected_app_role_values={"app": [2]},
        )

        self.assertEqual(policy.role_values, ["Admin", "2"])
        self.assertEqual(policy.default_permission_role_values, ["2"])
        self.assertEqual(policy.protected_app_role_values, {"app": ["2"]})

    def test_role_policy_rejects_unknown_default_role(self):
        with self.assertRaises(ValueError):
            RolePolicy(
                role_values=["Admin", "Operator"],
                admin_role_value="Admin",
                default_permission_role_values=["Missing"],
            )

    def test_role_policy_rejects_unknown_protected_role(self):
        with self.assertRaises(ValueError):
            RolePolicy(
                role_values=["Admin", "Operator"],
                admin_role_value="Admin",
                protected_app_role_values={"app": ["Missing"]},
            )


class TestMovementDeclarations(unittest.TestCase):

    def test_movement_group_definition_defaults_label_from_id(self):
        definition = MovementGroupDefinition(
            id="home",
            group_type=MovementGroupType.SINGLE_POSITION,
        )

        self.assertEqual(definition.label, "home")

    def test_build_default_group_preserves_flags(self):
        definition = MovementGroupDefinition(
            id="path",
            group_type=MovementGroupType.MULTI_POSITION,
            has_iterations=True,
            has_trajectory_execution=True,
        )

        group = definition.build_default_group()

        self.assertIsInstance(group, MovementGroup)
        self.assertTrue(group.has_iterations)
        self.assertTrue(group.has_trajectory_execution)


class TestToolingDeclarations(unittest.TestCase):

    def test_tool_definition_round_trip_normalizes_values(self):
        tool = ToolDefinition.from_dict({"id": "3", "name": "  Glue Gun  "})

        self.assertEqual(tool.to_dict(), {"id": 3, "name": "Glue Gun"})

    def test_tool_slot_definition_accepts_slot_id_alias(self):
        slot = ToolSlotDefinition.from_dict(
            {
                "slot_id": "4",
                "tool_id": "7",
                "pickup_movement_group_id": "  pickup ",
                "dropoff_movement_group_id": " dropoff  ",
            }
        )

        self.assertEqual(
            slot.to_dict(),
            {
                "id": 4,
                "tool_id": 7,
                "pickup_movement_group_id": "pickup",
                "dropoff_movement_group_id": "dropoff",
            },
        )


class TestWorkAreaDeclarations(unittest.TestCase):

    def test_work_area_key_helpers_are_stable(self):
        area = WorkAreaDefinition(id="main", label="Main", color="#fff")

        self.assertEqual(area.detection_area_key(), "main")
        self.assertEqual(area.brightness_area_key(), "main__brightness")
        self.assertEqual(area.height_mapping_area_key(), "main__height_mapping")

    def test_work_area_observer_binding_preserves_payload(self):
        binding = WorkAreaObserverBinding(area_id="main", movement_group_id="observe_main")

        self.assertEqual(binding.area_id, "main")
        self.assertEqual(binding.movement_group_id, "observe_main")


class TestDispensingDeclarations(unittest.TestCase):

    def test_dispense_channel_round_trip_normalizes_values(self):
        channel = DispenseChannelDefinition.from_dict(
            {
                "id": "  left ",
                "label": " Left Nozzle ",
                "weight_cell_id": "5",
                "pump_motor_address": "9",
                "default_glue_type": " epoxy ",
            }
        )

        self.assertEqual(
            channel.to_dict(),
            {
                "id": "left",
                "label": "Left Nozzle",
                "weight_cell_id": 5,
                "pump_motor_address": 9,
                "default_glue_type": "epoxy",
            },
        )


class TestTargetingDeclarations(unittest.TestCase):

    def test_remote_tcp_round_trip_defaults_display_name(self):
        remote_tcp = RemoteTcpDefinition.from_dict({"name": "  TCP_A  "})

        self.assertEqual(
            remote_tcp.to_dict(),
            {"name": "tcp_a", "display_name": "tcp_a"},
        )

    def test_target_frame_round_trip_normalizes_values(self):
        frame = TargetFrameDefinition.from_dict(
            {
                "name": "  Frame_A ",
                "work_area_id": " area_1 ",
                "source_navigation_group": " source ",
                "target_navigation_group": " target ",
                "use_height_correction": 1,
            }
        )

        self.assertEqual(
            frame.to_dict(),
            {
                "name": "frame_a",
                "work_area_id": "area_1",
                "source_navigation_group": "source",
                "target_navigation_group": "target",
                "use_height_correction": True,
                "display_name": "frame_a",
            },
        )

