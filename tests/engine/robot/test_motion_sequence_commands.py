import math
import unittest

from src.engine.robot.motion_sequence import (
    OrderedExecutionPolicy,
    OrderedMotionLimitProfile,
    OrderedMotionMetadata,
    OrderedMotionProfile,
    OrderedMotionType,
    OrderedPathCommand,
    OrderedPositionCommand,
    OrderedUnwindJoint6Command,
    serialize_ordered_motion_commands,
    serialize_ordered_motion_inputs,
)


class TestOrderedMotionCommands(unittest.TestCase):
    def test_serializes_position_and_path_commands_to_existing_wire_schema(self):
        metadata = OrderedMotionMetadata(
            protected=True,
            readiness_group="paint_contact_1",
            execution_group="paint_contact_1",
            execution_policy=OrderedExecutionPolicy.CONCATENATE,
        )
        commands = [
            OrderedPositionCommand(
                label="paint_attach_1",
                motion_type=OrderedMotionType.LINEAR,
                position=(1.0, 2.0, 3.0, 180.0, 0.0, 10.0),
                profile=OrderedMotionProfile(20.0, 30.0, 0.0),
                metadata=metadata,
            ),
            OrderedPathCommand(
                label="paint_contact_1:Path",
                path=((1.0, 2.0, 3.0, 180.0, 0.0, 10.0),),
                profile=OrderedMotionProfile(10.0, 30.0),
                metadata=metadata,
                limit_profile=OrderedMotionLimitProfile.PAINT_CONTACT,
            ),
        ]

        payload = serialize_ordered_motion_commands(commands)

        self.assertEqual("linear", payload[0]["type"])
        self.assertEqual([1.0, 2.0, 3.0, 180.0, 0.0, 10.0], payload[0]["position"])
        self.assertEqual(0.0, payload[0]["blendR"])
        self.assertEqual("path", payload[1]["type"])
        self.assertEqual("paint_contact", payload[1]["limit_profile"])
        self.assertEqual("concatenate", payload[1]["execution_policy"])

    def test_serializes_joint6_unwind_command(self):
        payload = serialize_ordered_motion_commands([
            OrderedUnwindJoint6Command(
                label="prepare_dropoff_unwind",
                velocity_percent=20.0,
                acceleration_percent=30.0,
                protected=True,
            )
        ])

        self.assertEqual([{
            "type": "unwind_joint6",
            "label": "prepare_dropoff_unwind",
            "vel": 20.0,
            "acc": 30.0,
            "protected": True,
        }], payload)

    def test_rejects_raw_motion_type_strings(self):
        with self.assertRaisesRegex(TypeError, "OrderedMotionType"):
            OrderedPositionCommand(
                label="bad",
                motion_type="linier",  # type: ignore[arg-type]
                position=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                profile=OrderedMotionProfile(10.0, 10.0),
            )

    def test_rejects_invalid_position_and_path_shapes(self):
        with self.assertRaisesRegex(ValueError, "exactly six"):
            OrderedPositionCommand(
                label="short",
                motion_type=OrderedMotionType.PTP,
                position=(0.0, 0.0, 0.0),
                profile=OrderedMotionProfile(10.0, 10.0),
            )
        with self.assertRaisesRegex(ValueError, "at least one pose"):
            OrderedPathCommand(
                label="empty",
                path=(),
                profile=OrderedMotionProfile(10.0, 10.0),
            )

    def test_rejects_non_finite_motion_values(self):
        with self.assertRaisesRegex(ValueError, "velocity_percent"):
            OrderedMotionProfile(math.nan, 10.0)

    def test_input_serializer_accepts_typed_commands(self):
        typed = OrderedUnwindJoint6Command("unwind", 20.0, 30.0)

        payloads = serialize_ordered_motion_inputs([typed])

        self.assertEqual("unwind_joint6", payloads[0]["type"])

    def test_serializer_rejects_raw_dictionary_commands(self):
        with self.assertRaisesRegex(
            TypeError,
            r"commands\[0\] must be an OrderedMotionCommand, got dict",
        ):
            serialize_ordered_motion_commands([{"type": "path"}])  # type: ignore[list-item]


if __name__ == "__main__":
    unittest.main()
