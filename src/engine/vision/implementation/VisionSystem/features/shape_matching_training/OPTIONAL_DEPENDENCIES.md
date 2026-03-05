# Optional Dependencies

This document explains optional dependencies for the shape matching training module and how to handle them.

## YAML Support (PyYAML)

### What is YAML used for?

YAML is used for **configuration file serialization** in a human-readable format. It provides an alternative to JSON for saving and loading configuration files.

**Features that use YAML:**
- `config.to_yaml()` - Save configuration to YAML format
- `config.from_yaml()` - Load configuration from YAML file
- More readable than JSON for complex configurations

### Installation

If you want to use YAML features, install PyYAML:

```bash
pip install PyYAML
```

### Graceful Fallback

The module handles missing YAML gracefully:

```python
from shape_matching_training.config.training_configs import DefaultTrainingConfig

config = DefaultTrainingConfig()

# JSON always works (no dependencies)
json_str = config.to_json()
config.save_to_file("config.json")  # Uses JSON by default

# YAML requires PyYAML
try:
    yaml_str = config.to_yaml()
except ImportError as e:
    print("YAML not available, using JSON instead")
    json_str = config.to_json()
```

### Configuration File Formats

| Format | Extension | Dependency | Human Readable |
|--------|-----------|------------|----------------|
| JSON   | `.json`   | ✅ Built-in | ⭐⭐⭐ |
| YAML   | `.yaml/.yml` | 📦 PyYAML | ⭐⭐⭐⭐⭐ |

### Example Configuration Files

**JSON Format (always available):**
```json
{
  "dataset": {
    "n_shapes": 8,
    "n_scales": 3,
    "n_variants": 5,
    "included_shapes": ["circle", "square", "triangle"]
  },
  "training": {
    "test_size": 0.3,
    "random_state": 42
  }
}
```

**YAML Format (requires PyYAML):**
```yaml
dataset:
  n_shapes: 8
  n_scales: 3
  n_variants: 5
  included_shapes:
    - circle
    - square
    - triangle

training:
  test_size: 0.3
  random_state: 42
```

## Other Optional Dependencies

### Visualization (matplotlib, seaborn)

Required for plotting and visualization features:

```bash
pip install matplotlib seaborn
```

**Used for:**
- Training progress plots
- Confusion matrices
- Feature importance charts
- Model comparison visualizations

### Testing (pytest)

Required for running the test suite:

```bash
pip install pytest pytest-cov
```

**Used for:**
- Unit tests
- Integration tests
- Performance tests
- Coverage reporting

## Installation Recommendations

### Minimal Installation
For basic functionality (dataset generation, training, evaluation):
```bash
# Core dependencies only (numpy, scikit-learn, opencv-python)
pip install numpy scikit-learn opencv-python
```

### Full Installation
For all features including YAML and visualizations:
```bash
pip install numpy scikit-learn opencv-python PyYAML matplotlib seaborn
```

### Development Installation
For development and testing:
```bash
pip install numpy scikit-learn opencv-python PyYAML matplotlib seaborn pytest pytest-cov
```

## Error Messages

When optional dependencies are missing, you'll see helpful error messages:

```
ImportError: PyYAML is not installed. Install it with: pip install PyYAML
Alternatively, use to_json() or save_to_file() for JSON format.
```

These errors include:
- ✅ Clear explanation of what's missing
- ✅ Installation command
- ✅ Alternative approaches that don't require the dependency