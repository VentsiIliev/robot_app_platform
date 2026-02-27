from src.applications.APPLICATION_BLUEPRINT.service.i_my_service import IMyService


class StubMyService(IMyService):

    def get_value(self) -> str:
        print("[MyApplication] get_value → stub_value")
        return "stub_value"

    def save_value(self, value: str) -> None:
        print(f"[MyApplication] save_value → {value!r}")
