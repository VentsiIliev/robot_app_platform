from src.engine.core.message_broker import MessageBroker


class EngineContext:
    def __init__(self):
        self.broker = MessageBroker()

    @classmethod
    def build(cls) -> 'EngineContext':
        return cls()