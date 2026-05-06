import unittest
from src.engine.hardware.generator.timer.generator_timer import NullGeneratorTimer


class TestNullGeneratorTimer(unittest.TestCase):
    def setUp(self):
        self._timer = NullGeneratorTimer()

    def test_elapsed_seconds_is_none(self):
        self.assertIsNone(self._timer.elapsed_seconds)

    def test_start_preserves_none_elapsed_seconds(self):
        self._timer.start()
        self.assertIsNone(self._timer.elapsed_seconds)

    def test_stop_preserves_none_elapsed_seconds(self):
        self._timer.stop()
        self.assertIsNone(self._timer.elapsed_seconds)

    def test_elapsed_seconds_still_none_after_start(self):
        self._timer.start()
        self.assertIsNone(self._timer.elapsed_seconds)

    def test_elapsed_seconds_still_none_after_stop(self):
        self._timer.start()
        self._timer.stop()
        self.assertIsNone(self._timer.elapsed_seconds)
