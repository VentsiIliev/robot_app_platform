"""
Contour Editor Builder
Provides a fluent API for configuring and building the contour editor.
"""
from typing import Optional, Callable, Any
from .core.main_frame import MainApplicationFrame
from .persistence.data.segment_provider import SegmentManagerProvider
from .persistence.data.settings_provider_registry import SettingsProviderRegistry
from .persistence.data.layer_config_registry import LayerConfigRegistry
from .persistence.providers.form_provider import AdditionalFormProvider
from .persistence.providers.widget_provider import WidgetProvider
from .models.settings_config import SettingsConfig
from .persistence.config.layer_config import ContourEditorLayerConfig
from .ui.new_widgets.SegmentSettingsWidget import configure_segment_settings


class ContourEditorBuilder:
    """
    Builder for configuring and creating a ContourEditor instance.
    Example:
        editor = (ContourEditorBuilder()
                  .with_segment_manager(MySegmentManager)
                  .with_settings(my_config, my_provider)
                  .with_form(my_form_factory)
                  .on_save(my_save_handler)
                  .build())
    """

    def __init__(self):
        self._parent = None
        self._segment_manager_class = None
        self._settings_config: Optional[SettingsConfig] = None
        self._settings_provider = None
        self._layer_config: Optional[ContourEditorLayerConfig] = None
        self._form_factory = None
        self._widget_factory = None
        self._save_callback: Optional[Callable] = None
        self._capture_callback: Optional[Callable] = None
        self._execute_callback: Optional[Callable] = None
        self._update_camera_feed_callback: Optional[Callable] = None
        self._editor: Optional[MainApplicationFrame] = None

    def with_parent(self, parent):
        """Set parent widget"""
        self._parent = parent
        return self

    def with_segment_manager(self, manager_class):
        """Configure segment manager backend (REQUIRED)"""
        self._segment_manager_class = manager_class
        return self

    def with_settings(self, config: SettingsConfig, provider=None):
        """Configure segment settings (optional)"""
        self._settings_config = config
        self._settings_provider = provider
        return self

    def with_layer_config(self, config: ContourEditorLayerConfig):
        """Configure semantic layer names and visibility (optional)"""
        self._layer_config = config
        return self

    def with_form(self, form_factory):
        """Configure additional data form (optional)"""
        self._form_factory = form_factory
        return self

    def with_widgets(self, widget_factory):
        """Configure custom widgets (optional)"""
        self._widget_factory = widget_factory
        return self

    def on_save(self, callback: Callable[[dict], None]):
        """Set callback for save events"""
        self._save_callback = callback
        return self

    def on_capture(self, callback: Callable[[], None]):
        """Set callback for capture events"""
        self._capture_callback = callback
        return self

    def on_execute(self, callback: Callable[[Any], None]):
        """Set callback for execute events"""
        self._execute_callback = callback
        return self

    def on_update_camera_feed(self, callback: Callable[[], None]):
        """
        Set callback for camera feed update events.

        Args:
            callback: Function() called when camera feed should be updated

        Example:
            def handle_camera_update():
                image = camera.get_image()
                editor.set_image(image)

            builder.on_update_camera_feed(handle_camera_update)
        """
        self._update_camera_feed_callback = callback
        return self

    def build(self) -> MainApplicationFrame:
        """Build and return configured editor instance"""
        if not self._segment_manager_class:
            raise ValueError("Segment manager is required. Call with_segment_manager() first.")
        self._configure_segment_manager()
        if self._settings_config:
            self._configure_settings()
        if self._layer_config:
            self._configure_layer_config()
        if self._widget_factory:
            self._configure_widgets()
        if self._form_factory:
            self._configure_form()
        self._editor = MainApplicationFrame(parent=self._parent)
        self._connect_signals()
        print("✅ Contour Editor built successfully")
        return self._editor

    def _configure_segment_manager(self):
        """Configure segment manager backend"""
        manager_class = self._segment_manager_class

        class Adapter:
            def __init__(self):
                self._manager = manager_class()

            def __getattr__(self, name):
                return getattr(self._manager, name)

        SegmentManagerProvider.get_instance().set_manager_class(Adapter)
        print("✅ Segment manager configured")

    def _configure_settings(self):
        """Configure settings provider and UI"""
        if self._settings_provider:
            SettingsProviderRegistry.get_instance().set_provider(self._settings_provider)
            print("✅ Settings provider registered")
        if self._settings_config:
            configure_segment_settings(self._settings_config)
            print("✅ Settings UI configured")

    def _configure_layer_config(self):
        """Configure editor layer semantics"""
        LayerConfigRegistry.get_instance().set_config(self._layer_config)
        print("✅ Layer config registered")

    def _configure_widgets(self):
        """Configure custom widget factory"""
        if self._widget_factory:
            WidgetProvider.get().set_custom_factory(self._widget_factory)
            print("✅ Custom widgets configured")

    def _configure_form(self):
        """Configure additional data form factory"""
        if self._form_factory:
            AdditionalFormProvider.get().set_factory(self._form_factory)
            print("✅ Additional data form configured")

    def _connect_signals(self):
        """Connect user callbacks to editor signals"""
        if self._save_callback:
            self._editor.save_requested.connect(self._save_callback)
            print("✅ Save callback connected")
        if self._capture_callback:
            self._editor.capture_requested.connect(self._capture_callback)
            print("✅ Capture callback connected")
        if self._execute_callback:
            self._editor.execute_requested.connect(self._execute_callback)
            print("✅ Execute callback connected")
        if self._update_camera_feed_callback:
            self._editor.update_camera_feed_requested.connect(self._update_camera_feed_callback)
            print("✅ Camera feed update callback connected")
