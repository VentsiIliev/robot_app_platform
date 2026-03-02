# Contour Editor Plugin - Standalone Mode Quick Guide

## ✅ Setup Complete!

The standalone runner is ready to use. You can now run the Contour Editor plugin in isolation for development and testing.

## 🚀 How to Run

### Option 1: Using the launcher script (Recommended)
```bash
cd /home/ilv/cobot-soft/cobot-soft-v5.1/cobot-soft-v5/cobot-glue-dispensing-v5/src/plugins/core/contour_editor
./launch.sh
```

### Option 2: Direct Python execution
```bash
python3 /home/ilv/cobot-soft/cobot-soft-v5.1/cobot-soft-v5/cobot-glue-dispensing-v5/src/plugins/core/contour_editor/run_standalone.py
```

## 📋 What's Available

### ✅ Fully Functional
- **Contour Drawing**: Full interactive drawing capabilities
- **Bezier Curves**: Curve editing and manipulation
- **Layer Management**: Switch between Workpiece/Contour/Fill layers
- **Segment Settings**: Configure glue parameters per segment
- **Point Manager**: Add/remove/edit points
- **UI Components**: All buttons, panels, and controls

### ⚠️ Mocked (for testing only)
- **Camera Capture**: Returns blank test images
- **Robot Movement**: Logs movements, no actual robot control
- **Workpiece Save**: Simulated save operations
- **Workpiece Execution**: Simulated execution

## 🎯 Development Workflow

1. **Make changes** to plugin code (any file in `/src/plugins/core/contour_editor/` or `/src/frontend/contour_editor/`)
2. **Run standalone**: `./launch.sh`
3. **Test changes**: Interact with the UI
4. **Debug**: Check console output for mock service calls
5. **Repeat**: No need to restart the full application!

## 🔧 What Gets Tested

### UI Components
- Toolbar buttons and actions
- Sliding panels and animations
- Layer switching
- Settings panels
- Point editing controls

### Core Functionality
- Contour drawing algorithms
- Bezier curve calculations
- Point interpolation
- Segment management
- Settings persistence

### Integration Points
- Mock controller service calls
- Signal/slot connections
- Data flow between components

## 📝 Example Use Cases

### Test New Drawing Tool
```python
# 1. Add new tool to toolbar
# 2. Run standalone: ./launch.sh
# 3. Test the new tool interactively
# 4. Debug without full app overhead
```

### Test Settings Changes
```python
# 1. Modify segment settings panel
# 2. Run standalone
# 3. Verify settings UI and validation
# 4. Check console for mock save calls
```

### Test Contour Algorithms
```python
# 1. Update interpolation code
# 2. Run standalone
# 3. Draw contours and observe behavior
# 4. Verify calculations in console output
```

## 🐛 Debugging Tips

### Console Output
The standalone runner prints all mock service calls:
```
[Mock Robot] Moving to calibration position
[Mock Vision] Capturing image
[Mock Operations] Saving workpiece: Test Workpiece
[Mock Controller] UPDATE_CAMERA_FEED requested
```

### Check Imports
If something doesn't load, check import paths:
```python
import sys
sys.path.insert(0, '/path/to/src')
```

### Clear Python Cache
If you make changes but they don't appear, clear the cache:
```bash
cd /home/ilv/cobot-soft/cobot-soft-v5.1/cobot-soft-v5/cobot-glue-dispensing-v5/src/plugins/core/contour_editor
rm -rf __pycache__
./launch.sh
```

### Verify Plugin Loading
Look for this message:
```
✅ Contour Editor Plugin loaded successfully in standalone mode
```

## 🎨 UI Testing

The standalone mode gives you a clean environment to test:
- Button responsiveness
- Panel animations
- Color schemes
- Layout adjustments
- Keyboard shortcuts

## 💾 Files Created

```
src/plugins/core/contour_editor/
├── run_standalone.py       # Main standalone runner
├── launch.sh               # Quick launcher script
├── README_STANDALONE.md    # Full documentation
└── USAGE_GUIDE.md         # This file
```

## 📚 Next Steps

1. **Run it**: `./launch.sh`
2. **Explore**: Click around, draw some contours
3. **Develop**: Make changes and rerun
4. **Test**: Verify your changes work
5. **Integrate**: Merge back into full application

## 🎉 Benefits

✅ **Faster iteration**: No full app startup
✅ **Isolated testing**: Focus on plugin only
✅ **Easy debugging**: Clear console output
✅ **Safe environment**: No robot/camera hardware involved
✅ **Quick validation**: Test changes immediately

---

**Ready to start?** Run `./launch.sh` and start developing! 🚀

