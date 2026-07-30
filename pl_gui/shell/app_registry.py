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

    descriptors = plugin_manager.get_descriptors()

    def factory(app_name: str) -> QWidget:
        """Create widget for given app name."""
        widget = widget_factory_instance.create_widget(app_name)
        if not widget:
            print(f"[AppRegistry] No widget found for '{app_name}', using fallback")
            widget = AppWidget(app_name=f"Placeholder ({app_name})")
        return widget

    return descriptors, factory

