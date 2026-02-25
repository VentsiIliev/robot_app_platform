import logging

class VisionService:

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Vision service initialized")