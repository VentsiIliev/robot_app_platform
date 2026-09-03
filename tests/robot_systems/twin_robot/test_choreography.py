from __future__ import annotations

import tempfile
import unittest

from src.robot_systems.twin_robot.domain import (
    ChoreographyDefinition,
    ChoreographyStep,
    RobotChoreographyPose,
)
from src.robot_systems.twin_robot.storage import ChoreographyRepository


class ChoreographyDefinitionTests(unittest.TestCase):
    def test_start_step_requires_exact_joint_anchors(self):
        choreography = ChoreographyDefinition(
            choreography_id="demo",
            name="Demo",
            steps=[
                ChoreographyStep(
                    name="Start",
                    robot1=RobotChoreographyPose(pose=[1, 2, 3, 4, 5, 6]),
                    robot2=RobotChoreographyPose(pose=[1, 2, 3, 4, 5, 6]),
                ),
                ChoreographyStep(
                    name="Move",
                    robot1=RobotChoreographyPose(pose=[2, 3, 4, 5, 6, 7]),
                    robot2=RobotChoreographyPose(pose=[2, 3, 4, 5, 6, 7]),
                ),
            ],
        )

        errors = choreography.validate()

        self.assertIn("Start step must contain exact Robot 1 joint anchor", errors)
        self.assertIn("Start step must contain exact Robot 2 joint anchor", errors)

    def test_complete_choreography_round_trips_through_json_repository(self):
        choreography = ChoreographyDefinition(
            choreography_id="face_to_face",
            name="Face To Face",
            loop_count=8,
            steps=[
                ChoreographyStep(
                    name="Start",
                    robot1=RobotChoreographyPose(
                        pose=[100, 200, 300, 180, 0, 0],
                        joints=[1, 2, 3, 4, 5, 6],
                    ),
                    robot2=RobotChoreographyPose(
                        pose=[100, 200, 300, 180, 0, 0],
                        joints=[11, 12, 13, 14, 15, 16],
                    ),
                ),
                ChoreographyStep(
                    name="Reach",
                    robot1=RobotChoreographyPose(pose=[120, 220, 340, 180, 0, 0]),
                    robot2=RobotChoreographyPose(pose=[130, 210, 350, 180, 0, 0]),
                ),
            ],
        )
        self.assertEqual([], choreography.validate())

        with tempfile.TemporaryDirectory() as tmp:
            repository = ChoreographyRepository(tmp)
            repository.save(choreography)
            loaded = repository.get("face_to_face")

        self.assertEqual(choreography.to_dict(), loaded.to_dict())
        self.assertEqual(8, loaded.loop_count)
        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], loaded.start_step.robot1.joints)
        self.assertEqual([11.0, 12.0, 13.0, 14.0, 15.0, 16.0], loaded.start_step.robot2.joints)


if __name__ == "__main__":
    unittest.main()
