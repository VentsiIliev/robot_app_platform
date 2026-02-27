from typing import Callable, Tuple, List
from PyQt6.QtWidgets import QWidget
from .app_descriptor import AppDescriptor
from pl_gui.shell.base_app_widget.AppWidget import AppWidget


def build_app_registry(plugin_manager, widget_factory_instance) -> Tuple[List[AppDescriptor], Callable[[str], QWidget]]:
    """
    Build app descriptors and factory from loaded plugins_example.

    This is the integration point - it knows about plugins_example, but MainWindow doesn't.

    Args:
        plugin_manager: Object with get_loaded_application_names() and get_application(name)
        widget_factory_instance: Instance that can create widgets via create_widget(app_name)

    Returns:
        (app_descriptors, widget_factory_callable)
    """

    descriptors = []

    for plugin_name in plugin_manager.get_loaded_application_names():
        plugin = plugin_manager.get_application(plugin_name)
        if plugin:
            json_metadata = getattr(plugin, '_json_metadata', {})
            folder_id = json_metadata.get('folder_id', 1)
            icon_str = json_metadata.get('icon_str', 'fa5s.users-cog')

            descriptors.append(AppDescriptor(
                name=plugin_name,
                icon_str=icon_str,
                folder_id=folder_id
            ))
            print(f"[AppRegistry] Registered {plugin_name} to folder {folder_id} with icon {icon_str}")

    def factory(app_name: str) -> QWidget:
        """Create widget for given app name."""
        widget = widget_factory_instance.create_widget(app_name)
        if not widget:
            print(f"[AppRegistry] No widget found for '{app_name}', using fallback")
            widget = AppWidget(app_name=f"Placeholder ({app_name})")
        return widget

    return descriptors, factory


