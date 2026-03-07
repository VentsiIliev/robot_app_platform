"""
Tests for broker_debug service layer.

Covers:
- StubBrokerDebugService  — interface compliance + in-memory behaviour
- BrokerDebugApplicationService — delegation to IMessagingService
"""
import unittest
from unittest.mock import MagicMock, call

from src.applications.broker_debug.service.i_broker_debug_service import IBrokerDebugService
from src.applications.broker_debug.service.stub_broker_debug_service import StubBrokerDebugService
from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_messaging(topics=None):
    ms = MagicMock()
    ms.get_all_topics.return_value         = list(topics or ["a/b", "c/d"])
    ms.get_subscriber_count.return_value   = 2
    return ms


# ══════════════════════════════════════════════════════════════════════════════
# StubBrokerDebugService
# ══════════════════════════════════════════════════════════════════════════════

class TestStubBrokerDebugService(unittest.TestCase):

    def setUp(self):
        self._stub = StubBrokerDebugService()

    def test_implements_interface(self):
        self.assertIsInstance(self._stub, IBrokerDebugService)

    def test_get_all_topics_returns_list(self):
        topics = self._stub.get_all_topics()
        self.assertIsInstance(topics, list)
        self.assertGreater(len(topics), 0)

    def test_get_all_topics_returns_sorted_list(self):
        topics = self._stub.get_all_topics()
        self.assertEqual(topics, sorted(topics))

    def test_get_subscriber_count_returns_int(self):
        topics = self._stub.get_all_topics()
        count  = self._stub.get_subscriber_count(topics[0])
        self.assertIsInstance(count, int)

    def test_get_subscriber_count_unknown_topic_returns_zero(self):
        self.assertEqual(self._stub.get_subscriber_count("no-such-topic"), 0)

    def test_publish_does_not_raise(self):
        self._stub.publish("test/topic", "hello")

    def test_subscribe_spy_does_not_raise(self):
        cb = MagicMock()
        self._stub.subscribe_spy("test/topic", cb)

    def test_unsubscribe_spy_does_not_raise(self):
        cb = MagicMock()
        self._stub.unsubscribe_spy("test/topic", cb)

    def test_clear_topic_removes_topic(self):
        topics_before = set(self._stub.get_all_topics())
        topic_to_clear = next(iter(topics_before))
        self._stub.clear_topic(topic_to_clear)
        self.assertNotIn(topic_to_clear, self._stub.get_all_topics())

    def test_clear_unknown_topic_does_not_raise(self):
        self._stub.clear_topic("no-such-topic")

    def test_get_topic_map_returns_dict(self):
        result = self._stub.get_topic_map()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_get_topic_map_values_are_ints(self):
        for v in self._stub.get_topic_map().values():
            self.assertIsInstance(v, int)


# ══════════════════════════════════════════════════════════════════════════════
# BrokerDebugApplicationService — get_all_topics
# ══════════════════════════════════════════════════════════════════════════════

class TestBrokerDebugApplicationServiceTopics(unittest.TestCase):

    def test_get_all_topics_delegates_to_messaging(self):
        ms  = _make_messaging(["z/1", "a/2", "m/3"])
        svc = BrokerDebugApplicationService(ms)
        topics = svc.get_all_topics()
        ms.get_all_topics.assert_called_once()
        self.assertEqual(topics, sorted(["z/1", "a/2", "m/3"]))

    def test_get_subscriber_count_delegates_to_messaging(self):
        ms  = _make_messaging()
        ms.get_subscriber_count.return_value = 5
        svc = BrokerDebugApplicationService(ms)
        self.assertEqual(svc.get_subscriber_count("a/b"), 5)
        ms.get_subscriber_count.assert_called_once_with("a/b")


# ══════════════════════════════════════════════════════════════════════════════
# BrokerDebugApplicationService — publish
# ══════════════════════════════════════════════════════════════════════════════

class TestBrokerDebugApplicationServicePublish(unittest.TestCase):

    def test_publish_delegates_to_messaging(self):
        ms  = _make_messaging()
        svc = BrokerDebugApplicationService(ms)
        svc.publish("test/topic", "payload")
        ms.publish.assert_called_once_with("test/topic", "payload")


# ══════════════════════════════════════════════════════════════════════════════
# BrokerDebugApplicationService — spy subscribe / unsubscribe
# ══════════════════════════════════════════════════════════════════════════════

class TestBrokerDebugApplicationServiceSpy(unittest.TestCase):

    def test_subscribe_spy_calls_messaging_subscribe(self):
        ms  = _make_messaging()
        svc = BrokerDebugApplicationService(ms)
        cb  = MagicMock()
        svc.subscribe_spy("test/topic", cb)
        ms.subscribe.assert_called_once_with("test/topic", cb)

    def test_unsubscribe_spy_calls_messaging_unsubscribe(self):
        ms  = _make_messaging()
        svc = BrokerDebugApplicationService(ms)
        cb  = MagicMock()
        svc.subscribe_spy("test/topic", cb)
        svc.unsubscribe_spy("test/topic", cb)
        ms.unsubscribe.assert_called_once_with("test/topic", cb)

    def test_subscribe_spy_stores_callback(self):
        ms  = _make_messaging()
        svc = BrokerDebugApplicationService(ms)
        cb  = MagicMock()
        svc.subscribe_spy("test/topic", cb)
        self.assertIn("test/topic", svc._spies)

    def test_unsubscribe_spy_removes_stored_callback(self):
        ms  = _make_messaging()
        svc = BrokerDebugApplicationService(ms)
        cb  = MagicMock()
        svc.subscribe_spy("test/topic", cb)
        svc.unsubscribe_spy("test/topic", cb)
        self.assertNotIn("test/topic", svc._spies)


# ══════════════════════════════════════════════════════════════════════════════
# BrokerDebugApplicationService — get_topic_map
# ══════════════════════════════════════════════════════════════════════════════

class TestBrokerDebugApplicationServiceTopicMap(unittest.TestCase):

    def test_get_topic_map_counts_subscribers_per_topic(self):
        ms  = _make_messaging(["a/b", "c/d"])
        ms.get_subscriber_count.side_effect = lambda t: 3 if t == "a/b" else 1
        svc = BrokerDebugApplicationService(ms)
        result = svc.get_topic_map()
        self.assertEqual(result["a/b"], 3)
        self.assertEqual(result["c/d"], 1)

    def test_get_topic_map_returns_dict(self):
        svc = BrokerDebugApplicationService(_make_messaging())
        self.assertIsInstance(svc.get_topic_map(), dict)


if __name__ == "__main__":
    unittest.main()
