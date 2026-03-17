import unittest

from src.robot_systems.glue.processes.glue_dispensing.manual_debug_runner import (
    DispensingManualDriver,
)


class TestDispensingManualDriver(unittest.TestCase):
    def test_snapshot_includes_machine_and_context_details(self):
        driver = DispensingManualDriver(spray_on=False)

        snapshot = driver.get_snapshot()

        self.assertEqual(snapshot["machine"]["current_state"], "STARTING")
        self.assertEqual(snapshot["context"]["paths_total"], 2)
        self.assertIn("robot", snapshot)
        self.assertIn("motor", snapshot)
        self.assertIn("generator", snapshot)

    def test_step_advances_machine_one_state(self):
        driver = DispensingManualDriver(spray_on=False)

        stepped = driver.step()

        self.assertTrue(stepped)
        snapshot = driver.get_snapshot()
        self.assertEqual(snapshot["machine"]["current_state"], "LOADING_PATH")
        self.assertEqual(snapshot["machine"]["last_state"], "STARTING")
        self.assertEqual(snapshot["machine"]["last_next_state"], "LOADING_PATH")
        self.assertEqual(snapshot["machine"]["step_count"], 1)

    def test_move_robot_to_current_start_uses_loaded_path(self):
        driver = DispensingManualDriver(spray_on=False)
        driver.step(3)

        driver.move_robot_to_current_start()

        self.assertEqual(
            driver.robot_service.current_position,
            driver.context.current_path[0],
        )


if __name__ == "__main__":
    unittest.main()
