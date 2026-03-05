import time
import threading
import unittest
from src.engine.hardware.generator.timer.generator_timer import GeneratorTimer


class TestGeneratorTimerElapsed(unittest.TestCase):
    def test_elapsed_none_before_start(self):
        timer = GeneratorTimer(timeout_minutes=1.0, on_timeout=lambda: None)
        self.assertIsNone(timer.elapsed_seconds)

    def test_elapsed_non_none_after_start(self):
        timer = GeneratorTimer(timeout_minutes=1.0, on_timeout=lambda: None)
        timer.start()
        try:
            self.assertIsNotNone(timer.elapsed_seconds)
        finally:
            timer.stop()

    def test_elapsed_positive_after_start(self):
        timer = GeneratorTimer(timeout_minutes=1.0, on_timeout=lambda: None)
        timer.start()
        time.sleep(0.05)
        try:
            self.assertGreater(timer.elapsed_seconds, 0.0)
        finally:
            timer.stop()

    def test_elapsed_frozen_after_stop(self):
        timer = GeneratorTimer(timeout_minutes=1.0, on_timeout=lambda: None)
        timer.start()
        time.sleep(0.05)
        timer.stop()
        elapsed_at_stop = timer.elapsed_seconds
        time.sleep(0.05)
        self.assertAlmostEqual(timer.elapsed_seconds, elapsed_at_stop, places=2)


class TestGeneratorTimerStop(unittest.TestCase):
    def test_stop_without_start_does_not_raise(self):
        timer = GeneratorTimer(timeout_minutes=1.0, on_timeout=lambda: None)
        timer.stop()  # should not raise

    def test_double_start_does_not_create_extra_threads(self):
        timer = GeneratorTimer(timeout_minutes=1.0, on_timeout=lambda: None)
        timer.start()
        timer.start()  # second start — thread already alive
        try:
            self.assertIsNotNone(timer._thread)
        finally:
            timer.stop()


class TestGeneratorTimerTimeout(unittest.TestCase):
    def test_on_timeout_called_when_timeout_reached(self):
        fired = threading.Event()
        timer = GeneratorTimer(
            timeout_minutes=0.0,          # 0 minutes → fires immediately
            on_timeout=fired.set,
            poll_interval_s=0.01,
        )
        timer.start()
        self.assertTrue(fired.wait(timeout=1.0), "on_timeout was not called")

    def test_on_timeout_not_called_when_stopped_early(self):
        fired = threading.Event()
        timer = GeneratorTimer(
            timeout_minutes=10.0,
            on_timeout=fired.set,
            poll_interval_s=0.01,
        )
        timer.start()
        timer.stop()
        fired.wait(timeout=0.1)
        self.assertFalse(fired.is_set())

