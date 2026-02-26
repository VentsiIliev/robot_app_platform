import unittest
from unittest.mock import patch

from src.bootstrap.build_engine import EngineContext
from src.engine.core.i_messaging_service import IMessagingService


class TestEngineContextBuild(unittest.TestCase):

    def test_build_returns_engine_context(self):
        ctx = EngineContext.build()
        self.assertIsInstance(ctx, EngineContext)

    def test_build_each_call_returns_new_instance(self):
        c1 = EngineContext.build()
        c2 = EngineContext.build()
        self.assertIsNot(c1, c2)

    def test_messaging_service_present(self):
        ctx = EngineContext.build()
        self.assertIsNotNone(ctx.messaging_service)

    def test_messaging_service_implements_interface(self):
        ctx = EngineContext.build()
        self.assertIsInstance(ctx.messaging_service, IMessagingService)

    def test_messaging_service_is_independent_per_context(self):
        c1 = EngineContext.build()
        c2 = EngineContext.build()
        self.assertIsNot(c1.messaging_service, c2.messaging_service)

    def test_messaging_service_can_subscribe(self):
        ctx = EngineContext.build()
        received = []

        def on_msg(msg):
            received.append(msg)

        ctx.messaging_service.subscribe("test/topic", on_msg)
        ctx.messaging_service.publish("test/topic", "hello")
        self.assertEqual(received, ["hello"])

    def test_messaging_service_can_publish_without_subscribers(self):
        ctx = EngineContext.build()
        ctx.messaging_service.publish("no/subscribers", "msg")  # must not raise

    def test_init_creates_messaging_service(self):
        ctx = EngineContext()
        self.assertIsNotNone(ctx.messaging_service)


if __name__ == "__main__":
    unittest.main()