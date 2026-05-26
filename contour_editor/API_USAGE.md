# Contour Editor - Public API Usage Guide

This document describes how to integrate the Contour Editor into your application.

## Installation

Ensure the contour editor package is in your Python path:

```python
import sys
sys.path.insert(0, '/path/to/contour_editor/src')
```

## Quick Start

### Minimal Example

```python
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from contour_editor import MainApplicationFrame

app = QApplication([])
window = QWidget()
layout = QVBoxLayout(window)

# Create and add the editor
editor = MainApplicationFrame()
layout.addWidget(editor)

window.show()
app.exec()
```

## Configuration API

### 1. Configure Segment Manager Backend

**Required before creating any editor instances.**

```python
from contour_editor import SegmentManagerProvider, BezierSegmentManager

# Option A: Use the built-in BezierSegmentManager directly
class SegmentManagerAdapter:
    def __init__(self):
        self._manager = BezierSegmentManager()
    
    def __getattr__(self, name):
        return getattr(self._manager, name)

SegmentManagerProvider.get_instance().set_manager_class(SegmentManagerAdapter)

# Option B: Implement your own ISegmentManager
from contour_editor import ISegmentManager

class MyCustomSegmentManager(ISegmentManager):
    @property
    def segments(self):
        # Return list of segments
        pass
    
    # Implement other required methods...

SegmentManagerProvider.get_instance().set_manager_class(MyCustomSegmentManager)
```

### 2. Configure Settings

**Define segment-level settings for your application.**

```python
from contour_editor import SettingsConfig, SettingsGroup, ISettingsProvider, SettingsProviderRegistry

# Create settings config
config = SettingsConfig(
    default_settings={
        "speed": "100",
        "temperature": "25",
        "material_type": "Type A"
    },
    groups=[
        SettingsGroup("Basic Settings", ["speed", "temperature"]),
        SettingsGroup("Material", ["material_type"])
    ],
    combo_field_key="material_type"  # This field will be a dropdown
)

# Create and register a settings provider
class MySettingsProvider(ISettingsProvider):
    def __init__(self, config, available_materials):
        self._config = config
        self._materials = available_materials
    
    def get_all_setting_keys(self):
        return list(self._config.default_settings.keys())
    
    def get_default_values(self):
        return self._config.default_settings.copy()
    
    def get_material_type_key(self):
        return self._config.combo_field_key or ""
    
    def get_available_material_types(self):
        return self._materials
    
    def get_default_material_type(self):
        return self._materials[0] if self._materials else ""
    
    def get_setting_label(self, key: str):
        # Convert snake_case to Title Case
        return key.replace('_', ' ').title()
    
    def get_settings_tabs_config(self):
        # Return list of (tab_name, keys_list) tuples
        return [(group.title, group.keys) for group in self._config.groups]

# Register the provider (IMPORTANT!)
provider = MySettingsProvider(config, ["Type A", "Type B", "Type C"])
SettingsProviderRegistry.get_instance().set_provider(provider)

# Apply configuration to UI
from contour_editor.ui.new_widgets.SegmentSettingsWidget import configure_segment_settings
configure_segment_settings(config)
```

### 3. Configure Widget Provider

**Use custom input widgets (e.g., for virtual keyboards).**

```python
from contour_editor import WidgetProvider
from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox, QLineEdit

class MyWidgetFactory:
    def create_double_spinbox(self, parent=None):
        # Return custom QDoubleSpinBox
        return QDoubleSpinBox(parent)
    
    def create_spinbox(self, parent=None):
        return QSpinBox(parent)
    
    def create_lineedit(self, parent=None):
        return QLineEdit(parent)

WidgetProvider.get().set_custom_factory(MyWidgetFactory())
```

### 4. Configure Workpiece Form

**Provide a form for creating workpiece metadata.**

```python
from contour_editor import WorkpieceFormProvider
from PyQt6.QtWidgets import QWidget

class MyWorkpieceForm(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Build your form UI
    
    def get_data(self):
        # Return dict with form data
        return {"name": "...", "description": "..."}

class MyFormFactory:
    def create_form(self, parent=None):
        return MyWorkpieceForm(parent)

WorkpieceFormProvider.get().set_factory(MyFormFactory())
```

### 5. Configure Dialog Provider

**Customize dialog messages.**

```python
from contour_editor import DialogProvider

class MyDialogProvider:
    def show_info(self, message, title="Info"):
        # Custom info dialog
        pass
    
    def show_warning(self, message, title="Warning"):
        pass
    
    def show_error(self, message, title="Error"):
        pass

DialogProvider.get().set_custom_provider(MyDialogProvider())
```

## Complete Integration Example

```python
from PyQt6.QtWidgets import QApplication
from contour_editor import (
    MainApplicationFrame,
    SegmentManagerProvider,
    BezierSegmentManager,
    SettingsConfig,
    SettingsGroup,
    WidgetProvider,
    WorkpieceFormProvider,
    CaptureDataHandler,
    SaveWorkpieceHandler,
    ContourEditorData,
    WorkpieceAdapter
)

class ContourEditorIntegration:
    def __init__(self, parent=None, controller=None):
        self.controller = controller
        self.editor = None
        
        # Step 1: Configure backend (MUST BE FIRST)
        self._configure_segment_manager()
        
        # Step 2: Configure settings
        self._configure_settings()
        
        # Step 3: Configure widgets (optional)
        self._configure_widgets()
        
        # Step 4: Configure workpiece form (optional)
        self._configure_workpiece_form()
        
        # Step 5: Create editor
        self.editor = MainApplicationFrame(parent=parent)
        
        # Step 6: Connect signals
        self._connect_signals()
    
    def _configure_segment_manager(self):
        """Register segment manager backend"""
        class SegmentManagerAdapter:
            def __init__(self):
                self._manager = BezierSegmentManager()
            def __getattr__(self, name):
                return getattr(self._manager, name)
        
        SegmentManagerProvider.get_instance().set_manager_class(SegmentManagerAdapter)
    
    def _configure_settings(self):
        """Configure segment settings"""
        from contour_editor.ui.new_widgets.SegmentSettingsWidget import configure_segment_settings
        
        config = SettingsConfig(
            default_settings={
                "speed": "100",
                "power": "50"
            },
            groups=[
                SettingsGroup("Motion", ["speed", "power"])
            ]
        )
        configure_segment_settings(config)
    
    def _configure_widgets(self):
        """Configure custom widgets (optional)"""
        # Example: Virtual keyboard integration
        pass
    
    def _configure_workpiece_form(self):
        """Configure workpiece form (optional but recommended)"""
        from contour_editor import WorkpieceFormProvider
        from my_app.forms import MyWorkpieceFormFactory
        
        factory = MyWorkpieceFormFactory()
        WorkpieceFormProvider.get().set_factory(factory)
        print("✅ Workpiece form configured")
    
    def _connect_signals(self):
        """Connect editor signals to application"""
        self.editor.capture_requested.connect(self.on_capture)
        self.editor.save_workpiece_requested.connect(self.on_save_workpiece)
        self.editor.execute_workpiece_requested.connect(self.on_execute)
    
    def on_capture(self):
        """Handle capture request"""
        # Get capture data from your system
        capture_data = {
            'image': ...,  # numpy array or QImage
            'contours': {
                'Workpiece': [[...]],  # List of contours
                'Contour': [[]],
                'Fill': [[]]
            }
        }
        
        # Load into editor using handler
        editor_data = CaptureDataHandler.handle_capture_data(
            workpiece_manager=self.editor.contourEditor.workpiece_manager,
            capture_data=capture_data,
            close_contour=True
        )
    
    def on_save_workpiece(self, form_data):
        """Handle workpiece save request"""
        success, message = SaveWorkpieceHandler.save_workpiece(
            workpiece_manager=self.editor.contourEditor.workpiece_manager,
            form_data=form_data,
            controller=self.controller
        )
        return success, message
    
    def on_execute(self, workpiece):
        """Handle workpiece execution request"""
        # Execute the workpiece in your system
        pass
    
    def load_workpiece(self, workpiece):
        """Load a workpiece object into the editor"""
        self.editor.contourEditor.load_workpiece(workpiece)
    
    def set_image(self, image):
        """Set background image (numpy array or QImage)"""
        self.editor.set_image(image)
    
    def get_editor_data(self) -> ContourEditorData:
        """Get current editor data"""
        return self.editor.contourEditor.workpiece_manager.export_editor_data()
    
    def get_workpiece_dict(self) -> dict:
        """Convert editor data to workpiece dict"""
        editor_data = self.get_editor_data()
        return WorkpieceAdapter.to_workpiece_data(editor_data)


# Usage
app = QApplication([])
integration = ContourEditorIntegration()
integration.editor.show()
app.exec()
```

## Data Flow

### Loading Data into Editor

```python
from contour_editor import ContourEditorData

# Method 1: From ContourEditorData
editor_data = ContourEditorData(
    layers={
        'Workpiece': [[(x1, y1), (x2, y2), ...]],
        'Contour': [...],
        'Fill': [...]
    },
    settings_by_segment={}
)
workpiece_manager.load_editor_data(editor_data)

# Method 2: From Workpiece object
workpiece_manager.load_workpiece(workpiece_object)

# Method 3: From capture data (with handler)
CaptureDataHandler.handle_capture_data(
    workpiece_manager=workpiece_manager,
    capture_data=capture_dict,
    close_contour=True
)
```

### Extracting Data from Editor

```python
# Method 1: Get ContourEditorData
editor_data = workpiece_manager.export_editor_data()

# Method 2: Convert to workpiece dict
from contour_editor import WorkpieceAdapter
workpiece_dict = WorkpieceAdapter.to_workpiece_data(editor_data)

# Method 3: Use SaveWorkpieceHandler
SaveWorkpieceHandler.save_workpiece(
    workpiece_manager=workpiece_manager,
    form_data=form_data,
    controller=controller
)
```

## API Reference

### Core Classes

- **MainApplicationFrame**: Main editor widget
- **ContourEditorData**: Domain-agnostic data container
- **WorkpieceAdapter**: Convert between formats

### Providers (Singletons)

- **SegmentManagerProvider**: Segment management backend
- **WidgetProvider**: Custom input widgets
- **WorkpieceFormProvider**: Workpiece metadata form
- **DialogProvider**: Message dialogs
- **IconProvider**: Icon resources
- **SettingsProviderRegistry**: Settings definitions

### Handlers

- **CaptureDataHandler**: Process capture data
- **SaveWorkpieceHandler**: Save workpiece workflow

### Interfaces

- **ISegmentManager**: Implement custom segment manager
- **ISettingsProvider**: Implement custom settings provider

## Signals

The `MainApplicationFrame` emits these signals:

- `capture_requested`: User requests image capture
- `save_workpiece_requested(dict)`: User wants to save workpiece
- `execute_workpiece_requested(workpiece)`: User wants to execute workpiece
- `update_camera_feed_requested()`: Request camera feed update

## Best Practices

1. **Always configure SegmentManagerProvider first** before creating any editor instances
2. **Use handlers** (CaptureDataHandler, SaveWorkpieceHandler) instead of direct data manipulation
3. **Use ContourEditorData** as the standard data exchange format
4. **Configure settings early** before users open the settings dialog
5. **Keep provider configuration separate** from editor instantiation

## Migration from Old Import Paths

If you're using old import paths like `frontend.contour_editor.*`:

```python
# Old
from frontend.contour_editor.ContourEditor import MainApplicationFrame
from frontend.contour_editor.services.CaptureDataHandler import CaptureDataHandler
from frontend.contour_editor import SegmentManagerProvider

# New
from contour_editor import MainApplicationFrame
from contour_editor import CaptureDataHandler
from contour_editor import SegmentManagerProvider
```

All public APIs are now accessible from the top-level `contour_editor` package.

