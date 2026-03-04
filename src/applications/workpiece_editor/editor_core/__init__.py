"""
Workpiece Editor Package

Adds workpiece-specific functionality on top of the domain-agnostic contour_editor.
This package handles workpiece data models, transformation adapters, and
workpiece-aware handlers.

Public API for workpiece-specific applications:
- WorkpieceEditorBuilder: Builder that wraps ContourEditorBuilder with workpiece support
- WorkpieceAdapter: Convert between workpiece objects and ContourEditorData
- WorkpieceManager: Manage workpiece loading/exporting
- Handlers: SaveWorkpieceHandler, CaptureDataHandler, load_workpiece
- Models: BaseWorkpiece, GenericWorkpiece, WorkpieceFactory, WorkpieceField
"""

# Builder
from .builder import WorkpieceEditorBuilder

# Adapters
from .adapters import WorkpieceAdapter

# Managers
from .managers import WorkpieceManager

# Handlers
from .handlers import SaveWorkpieceHandler, CaptureDataHandler, StartHandler, CaptureHandler

# Models
from .models import BaseWorkpiece, GenericWorkpiece, WorkpieceFactory, WorkpieceField

# Re-export commonly needed contour_editor components for convenience
from contour_editor import (
    ContourEditorData,
    Segment,
    Layer,
    ISegmentManager,
    ISettingsProvider,
    BezierSegmentManager,
    SettingsConfig,
    SettingsGroup,
    MainApplicationFrame
)

__all__ = [
    # Workpiece-specific
    'WorkpieceEditorBuilder',
    'WorkpieceAdapter',
    'WorkpieceManager',
    'SaveWorkpieceHandler',
    'CaptureDataHandler',
    'StartHandler',
    'CaptureHandler',
    'BaseWorkpiece',
    'GenericWorkpiece',
    'WorkpieceFactory',
    'WorkpieceField',

    # Re-exported from contour_editor for convenience
    'ContourEditorData',
    'Segment',
    'Layer',
    'ISegmentManager',
    'ISettingsProvider',
    'BezierSegmentManager',
    'SettingsConfig',
    'SettingsGroup',
    'MainApplicationFrame'
]

# Version information
from ._version import __version__, __version_info__

__all__ += ['__version__']
