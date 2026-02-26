from src.engine.core.i_messaging_service import IMessagingService
from src.engine.core.messaging_service import MessagingService


class EngineContext:
    def __init__(self):
        self.messaging_service: IMessagingService = MessagingService()   # concrete here only

    @classmethod
    def build(cls) -> 'EngineContext':
        return cls()
