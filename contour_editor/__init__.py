"""
Contour Editor Package

A standalone, backend-agnostic contour editing widget for PyQt6.
Can be used standalone or integrated via dependency injection.

NOTE: Workpiece-specific functionality has moved to the 'workpiece_editor' package.
If you need workpiece support, use 'from workpiece_editor import ...' instead.

Public API for external applications:
- MainApplicationFrame: Main editor widget
- ContourEditorBuilder: Builder for configuring the editor
- ContourEditorData: Domain-agnostic data model
- Providers: Dependency injection for dialogs, widgets, icons, forms
- Interfaces: ISegmentManager, ISettingsProvider, IAdditionalDataForm
"""

import warnings

# Main widget
from .core.main_frame import MainApplicationFrame
from .builder import ContourEditorBuilder

# Core data models
from .persistence.data.editor_data_model import ContourEditorData
from .models.segment import Segment, Layer

# Interfaces for implementing custom backends
from .models.interfaces import ISegmentManager, ISettingsProvider, IAdditionalDataForm, AdditionalDataFormBase

# Providers for dependency injection
from .persistence.providers import (
    DialogProvider,
    WidgetProvider,
    IconProvider,
    AdditionalFormProvider,
    AdditionalFormBehaviorProvider,
)
from .persistence.data.segment_provider import SegmentManagerProvider
from .persistence.data.settings_provider_registry import SettingsProviderRegistry
from .persistence.data.layer_config_registry import LayerConfigRegistry
from .persistence.config.layer_config import ContourEditorLayerConfig, LayerRoleConfig

# Settings configuration
from .models.settings_config import SettingsConfig, SettingsGroup

# Backend implementation (for standalone use)
from .models.bezier_segment_manager import BezierSegmentManager

# Deprecated exports - kept for backward compatibility with warnings
def _deprecated_import(name, new_location):
    warnings.warn(
        f"{name} has been moved to '{new_location}'. "
        f"Please update your imports: from {new_location} import {name}",
        DeprecationWarning,
        stacklevel=3
    )

def __getattr__(name):
    """Handle deprecated imports with warnings"""
    deprecated_imports = {
        'WorkpieceAdapter': 'workpiece_editor',
        'SaveWorkpieceHandler': 'workpiece_editor',
        'CaptureDataHandler': 'workpiece_editor',
        'BaseWorkpiece': 'workpiece_editor',
        'GenericWorkpiece': 'workpiece_editor',
        'WorkpieceFactory': 'workpiece_editor',
        'WorkpieceField': 'workpiece_editor',
        'WorkpieceBase': 'workpiece_editor',
        'WorkpieceFieldProvider': 'workpiece_editor',
    }

    if name in deprecated_imports:
        _deprecated_import(name, deprecated_imports[name])
        # Try to import from new location
        import importlib
        try:
            module = importlib.import_module(deprecated_imports[name])
            return getattr(module, name)
        except (ImportError, AttributeError):
            raise AttributeError(f"'{name}' has been moved to '{deprecated_imports[name]}' package")

    raise AttributeError(f"module 'contour_editor' has no attribute '{name}'")

__all__ = [
    # Core editor components
    'MainApplicationFrame',
    'ContourEditorBuilder',

    # Data models
    'ContourEditorData',
    'Segment',
    'Layer',

    # Interfaces
    'ISegmentManager',
    'ISettingsProvider',
    'IAdditionalDataForm',
    'AdditionalDataFormBase',

    # Providers
    'DialogProvider',
    'WidgetProvider',
    'IconProvider',
    'AdditionalFormProvider',
    'AdditionalFormBehaviorProvider',
    'SegmentManagerProvider',
    'SettingsProviderRegistry',
    'LayerConfigRegistry',
    'ContourEditorLayerConfig',
    'LayerRoleConfig',

    # Settings
    'SettingsConfig',
    'SettingsGroup',

    # Default backend implementation
    'BezierSegmentManager',
]

# Version information
from ._version import __version__, __version_info__
