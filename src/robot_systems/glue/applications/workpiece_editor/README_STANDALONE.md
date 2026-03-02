# Contour Editor Plugin - Standalone Mode

This directory contains the standalone runner for the Contour Editor plugin, allowing you to test and develop the plugin in isolation without running the full application.

## Quick Start

```bash
# From the plugin directory
cd /home/ilv/cobot-soft/cobot-soft-v5.1/cobot-soft-v5/cobot-glue-dispensing-v5/src/plugins/core/contour_editor

# Run the plugin standalone
python3 run_standalone.py
```

Or from anywhere:

```bash
python3 /home/ilv/cobot-soft/cobot-soft-v5.1/cobot-soft-v5/cobot-glue-dispensing-v5/src/plugins/core/contour_editor/run_standalone.py
```

## Features in Standalone Mode

✅ Full contour editor UI
✅ Interactive drawing and editing
✅ Bezier curve tools
✅ Layer management
✅ Mock glue types for testing
⚠️ Camera operations (mocked - no real camera)
⚠️ Robot operations (mocked - no real robot)
⚠️ Workpiece save/load (local only)

## Mock Services

The standalone runner provides mock implementations of:
- **ControllerService**: Basic controller interface
- **SettingsService**: Glue types and settings
- **Camera**: Image capture (returns test images)
- **Robot**: Movement operations (logged only)

## Development Workflow

1. Make changes to plugin code
2. Run `python3 run_standalone.py`
3. Test your changes
4. Debug issues without full app startup overhead

## Testing Specific Features

### Test Contour Drawing
1. Launch standalone mode
2. Draw contours using mouse/tools
3. Test bezier controls
4. Verify layer switching

### Test Settings
1. Check segment settings panel
2. Modify glue types
3. Test parameter validation

### Test UI Components
1. Test toolbar buttons
2. Verify panel animations
3. Check keyboard shortcuts

## Limitations

- No actual camera feed (mock images only)
- No robot connection (movements logged)
- No full backend services
- Limited persistence (memory only)

## Troubleshooting

**Import errors**: Make sure you're running from the correct directory or path is set properly.

**Missing dependencies**: Install required packages:
```bash
pip install PyQt6 numpy scipy scikit-learn shapely
```

**Camera errors**: In standalone mode, camera operations are mocked and won't fail.

## File Structure

```
contour_editor/
├── run_standalone.py      # Standalone runner
├── plugin.py              # Plugin implementation
├── ui/                    # UI components
│   └── ContourEditorAppWidget.py
└── README_STANDALONE.md   # This file
```

