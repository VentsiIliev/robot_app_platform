import unittest

from src.robot_systems.paint.processes.paint.work_area_nesting import WorkAreaNestingService


class WorkAreaNestingServiceTest(unittest.TestCase):
    def test_margin_and_padding_control_reservations(self):
        service = WorkAreaNestingService()
        boundary = [(0, 0), (100, 0), (100, 60), (0, 60)]

        first, message = service.reserve(
            boundary, width_mm=30, height_mm=20, margin_mm=10, padding_mm=5
        )
        self.assertEqual("", message)
        self.assertEqual((25.0, 20.0), first.center_xy)
        service.commit()

        second, message = service.reserve(
            boundary, width_mm=30, height_mm=20, margin_mm=10, padding_mm=5
        )
        self.assertEqual("", message)
        self.assertEqual((60.0, 20.0), second.center_xy)

    def test_reports_full_without_overwriting_committed_positions(self):
        service = WorkAreaNestingService()
        boundary = [(0, 0), (50, 0), (50, 40), (0, 40)]
        reservation, _ = service.reserve(
            boundary, width_mm=30, height_mm=20, margin_mm=5, padding_mm=5
        )
        self.assertIsNotNone(reservation)
        service.commit()
        reservation, message = service.reserve(
            boundary, width_mm=30, height_mm=20, margin_mm=5, padding_mm=5
        )
        self.assertIsNone(reservation)
        self.assertIn("no space", message)


if __name__ == "__main__":
    unittest.main()
