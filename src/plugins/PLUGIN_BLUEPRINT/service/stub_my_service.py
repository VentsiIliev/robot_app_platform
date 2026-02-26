from src.plugins.PLUGIN_BLUEPRINT.service.i_my_service import IMyService


class StubMyService(IMyService):

    def get_value(self) -> str:
        print("[MyPlugin] get_value → stub_value")
        return "stub_value"

    def save_value(self, value: str) -> None:
        print(f"[MyPlugin] save_value → {value!r}")
