import gc
import unittest

from src.engine.core.message_broker import MessageBroker
from src.engine.core.messaging_service import MessagingService


class _Recorder:
    def __init__(self):
        self.messages = []

    def on_message(self, message):
        self.messages.append(message)


class _SelfUnsubscriber:
    def __init__(self, broker, topic):
        self._broker = broker
        self._topic = topic
        self.calls = 0

    def on_message(self, message):
        self.calls += 1
        self._broker.unsubscribe(self._topic, self.on_message)


class TestMessageBroker(unittest.TestCase):

    def setUp(self):
        self.broker = MessageBroker()
        self.broker.clear_all()

    def tearDown(self):
        self.broker.clear_all()

    def test_publish_delivers_to_bound_subscriber(self):
        recorder = _Recorder()

        self.broker.subscribe("topic/demo", recorder.on_message)
        self.broker.publish("topic/demo", {"value": 1})

        self.assertEqual(recorder.messages, [{"value": 1}])

    def test_unsubscribe_removes_bound_subscriber(self):
        recorder = _Recorder()

        self.broker.subscribe("topic/demo", recorder.on_message)
        self.broker.unsubscribe("topic/demo", recorder.on_message)
        self.broker.publish("topic/demo", "ignored")

        self.assertEqual(recorder.messages, [])
        self.assertEqual(self.broker.get_subscriber_count("topic/demo"), 0)

    def test_publish_allows_callback_to_unsubscribe_itself(self):
        listener = _SelfUnsubscriber(self.broker, "topic/demo")

        self.broker.subscribe("topic/demo", listener.on_message)
        self.broker.publish("topic/demo", "first")
        self.broker.publish("topic/demo", "second")

        self.assertEqual(listener.calls, 1)
        self.assertEqual(self.broker.get_subscriber_count("topic/demo"), 0)

    def test_dead_bound_method_is_cleaned_up(self):
        recorder = _Recorder()
        self.broker.subscribe("topic/demo", recorder.on_message)

        del recorder
        gc.collect()

        self.broker.publish("topic/demo", "ignored")

        self.assertEqual(self.broker.get_subscriber_count("topic/demo"), 0)
        self.assertNotIn("topic/demo", self.broker.subscribers)

    def test_request_returns_first_non_none_response(self):
        def no_reply(message):
            return None

        def reply(message):
            return f"reply:{message}"

        self.broker.subscribe("topic/request", no_reply)
        self.broker.subscribe("topic/request", reply)

        result = self.broker.request("topic/request", "ping")

        self.assertEqual(result, "reply:ping")

    def test_get_all_topics_includes_published_topic_without_subscribers(self):
        self.broker.publish("topic/published-only", {"value": 1})

        topics = self.broker.get_all_topics()

        self.assertIn("topic/published-only", topics)


class TestMessagingService(unittest.TestCase):

    def setUp(self):
        self.service = MessagingService()
        self.service.clear_all()

    def tearDown(self):
        self.service.clear_all()

    def test_publish_and_subscribe_use_shared_broker(self):
        recorder = _Recorder()

        self.service.subscribe("topic/demo", recorder.on_message)
        self.service.publish("topic/demo", 42)

        self.assertEqual(recorder.messages, [42])
