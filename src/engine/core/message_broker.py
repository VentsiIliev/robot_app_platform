import logging
import weakref
from typing import Dict, List, Any, Callable
from src.engine.core.i_messaging_service import IMessagingService


class MessageBroker(IMessagingService):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MessageBroker, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.subscribers: Dict[str, List[weakref.ref]] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.subscribers:
            self.subscribers[topic] = []

        if hasattr(callback, '__self__'):
            weak_callback = weakref.WeakMethod(callback, self._cleanup_callback(topic, callback))
        else:
            weak_callback = weakref.ref(callback, self._cleanup_callback(topic, callback))

        self.subscribers[topic].append(weak_callback)
        self.logger.debug(f"Subscribed to topic '{topic}'. Total subscribers: {len(self.subscribers[topic])}")

    def _cleanup_callback(self, topic: str, original_callback: Callable):
        def cleanup(weak_ref):
            if topic in self.subscribers:
                self.subscribers[topic] = [
                    ref for ref in self.subscribers[topic]
                    if ref is not weak_ref
                ]
                if topic in self.subscribers and not self.subscribers[topic]:
                    del self.subscribers[topic]
                self.logger.debug(f"Auto-cleaned up dead reference for topic '{topic}'")
        return cleanup

    def unsubscribe(self, topic: str, callback: Callable):
        if topic not in self.subscribers:
            return

        original_count = len(self.subscribers[topic])
        self.subscribers[topic] = [
            ref for ref in self.subscribers[topic]
            if ref() is not None and ref() != callback
        ]

        if not self.subscribers.get(topic):
            self.subscribers.pop(topic, None)

        removed_count = original_count - len(self.subscribers.get(topic, []))
        if removed_count > 0:
            self.logger.debug(f"Unsubscribed {removed_count} callback(s) from topic '{topic}'")

    def publish(self, topic: str, message: Any):
        if topic not in self.subscribers:
            self.logger.debug(f"No subscribers for topic '{topic}'")
            return

        live_callbacks = []
        dead_refs = []

        for weak_ref in self.subscribers[topic]:
            callback = weak_ref()
            if callback is not None:
                live_callbacks.append(callback)
            else:
                dead_refs.append(weak_ref)

        if dead_refs:
            self.subscribers[topic] = [
                ref for ref in self.subscribers[topic]
                if ref not in dead_refs
            ]
            self.logger.debug(f"Cleaned up {len(dead_refs)} dead references for topic '{topic}'")

        successful_calls = 0
        failed_calls = 0

        for callback in live_callbacks:
            try:
                self.logger.debug(f"Publishing to topic: '{topic}' message: {message}")
                callback(message)
                successful_calls += 1
            except Exception as e:
                import traceback
                traceback.print_exc()
                failed_calls += 1
                callback_info = f"{callback.__self__.__class__.__name__}.{callback.__name__}" if hasattr(callback, '__self__') else str(callback)
                self.logger.error(f"Error calling subscriber for topic '{topic}': {e} [Callback: {callback_info}]")

        if successful_calls > 0:
            self.logger.debug(f"Successfully published to {successful_calls} subscribers for topic '{topic}'")
        if failed_calls > 0:
            self.logger.warning(f"Failed to publish to {failed_calls} subscribers for topic '{topic}'")

        # A subscriber callback may have called unsubscribe() during delivery,
        # which already deleted the topic — use .get() + .pop() to be idempotent
        if not self.subscribers.get(topic):
            self.subscribers.pop(topic, None)

    def get_subscriber_count(self, topic: str) -> int:
        if topic not in self.subscribers:
            return 0
        return sum(1 for ref in self.subscribers[topic] if ref() is not None)

    def get_all_topics(self) -> List[str]:
        return list(self.subscribers.keys())

    def clear_topic(self, topic: str):
        if topic in self.subscribers:
            count = len(self.subscribers[topic])
            del self.subscribers[topic]
            self.logger.debug(f"Cleared {count} subscribers from topic '{topic}'")

    def request(self, topic: str, message: Any, timeout: float = 1.0):
        if topic not in self.subscribers:
            self.logger.debug(f"No subscribers for request topic '{topic}'")
            return None

        live_callbacks = []
        for weak_ref in self.subscribers[topic]:
            callback = weak_ref()
            if callback is not None:
                live_callbacks.append(callback)

        for callback in live_callbacks:
            try:
                self.logger.debug(f"Making request to topic: '{topic}' message: {message}")
                result = callback(message)
                if result is not None:
                    self.logger.debug(f"Got response from topic '{topic}': {result}")
                    return result
            except Exception as e:
                self.logger.error(f"Error in request callback for topic '{topic}': {e}")
                continue

        self.logger.debug(f"No response received for request topic '{topic}'")
        return None

    def clear_all(self):
        total_cleared = sum(len(subs) for subs in self.subscribers.values())
        self.subscribers.clear()
        self.logger.debug(f"Cleared all {total_cleared} subscribers from all topics")
