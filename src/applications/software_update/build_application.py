"""Shared application composition; each system supplies its maintenance gate."""
from .software_update_application import SoftwareUpdateApplication
from .service.software_update_service import SoftwareUpdateService


def build_software_update_application(can_schedule):
    return SoftwareUpdateApplication(SoftwareUpdateService(can_schedule))
