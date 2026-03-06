from src.engine.robot.features.navigation_service import NavigationService


class GlueNavigationService:

    _GROUP_HOME        = "HOME"
    _GROUP_LOGIN       = "LOGIN"
    _GROUP_CALIBRATION = "CALIBRATION"

    def __init__(self, navigation: NavigationService):
        self._nav = navigation

    def move_home(self, z_offset: float = 0.0) -> bool:
        return self._move_with_z_offset(self._GROUP_HOME, z_offset)

    def move_to_login_position(self) -> bool:
        return self._nav.move_to_group(self._GROUP_LOGIN)

    def move_to_calibration_position(self, z_offset: float = 0.0) -> bool:
        return self._move_with_z_offset(self._GROUP_CALIBRATION, z_offset)

    def move_to(self, group_name: str, z_offset: float = 0.0) -> bool:
        return self._move_with_z_offset(group_name, z_offset) if z_offset else self._nav.move_to_group(group_name)

    def move_linear(self, group_name: str) -> bool:
        return self._nav.move_linear_group(group_name)

    def get_group_names(self) -> list[str]:
        return self._nav.get_group_names()

    def _move_with_z_offset(self, group_name: str, z_offset: float) -> bool:
        if not z_offset:
            return self._nav.move_to_group(group_name)
        try:
            config = self._nav._get_config()  # still needed to read position
            group = self._nav._get_group(config, group_name)
            position = group.parse_position()
            if position is None:
                return False
            position = list(position)
            position[2] += z_offset
            return self._nav.move_to_position(position, group_name)
        except Exception:
            import traceback
            traceback.print_exc()
            return False

