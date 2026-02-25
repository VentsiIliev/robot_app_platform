from src.settings.settings_menu.category_descriptor import CategoryDescriptor
from src.settings.settings_menu.settings_menu import SettingsNavigationWidget
from src.settings.settings_view.build_showcase import build_showcase

def build_settings_menu_showcase():
    CUSTOM_CATEGORIES = [
        CategoryDescriptor(
            id = "users",
            icon = "mdi.account-group"
        ),
        CategoryDescriptor(
            id = "database",
            icon = "mdi.database"
        ),
        CategoryDescriptor(
            id = "api",
            icon = "mdi.api"
        ),
        CategoryDescriptor(
            id = "backup",
            icon = "mdi.backup-restore"
        ),
        CategoryDescriptor(
            id = "logging",
            icon = "mdi.text-box"
        )
    ]

    # Define factory map - functions that create widgets for each category
    factory_map = {
        "users": build_showcase,
        "database": build_showcase,
        "api": build_showcase,
        "backup": build_showcase,
        "logging": build_showcase,
    }

    nav = SettingsNavigationWidget(
            categories=CUSTOM_CATEGORIES,
            factory_map=factory_map
        )

    return nav