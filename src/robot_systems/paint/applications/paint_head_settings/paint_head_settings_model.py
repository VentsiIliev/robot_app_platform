from .i_paint_head_settings_service import IPaintHeadSettingsService, PaintHeadSettings


class PaintHeadSettingsModel:
    def __init__(self, service: IPaintHeadSettingsService) -> None:
        self._service = service

    def load(self) -> PaintHeadSettings:
        return self._service.load()

    def save(self, sign: int, spacing: int, count: int) -> PaintHeadSettings:
        return self._service.save(sign, spacing, count)
