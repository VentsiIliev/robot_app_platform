"""
Training Configuration Classes

Provides configuration classes for training pipeline parameters,
dataset generation settings, and evaluation criteria.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from .base_config import (
    BaseConfig,
    ConfigValidationError,
    validate_positive_number,
    validate_positive_integer,
    validate_probability
)
from .model_configs import SGDCalibratedConfig, ModelConfigRegistry


@dataclass
class DatasetConfig(BaseConfig):
    """Configuration for synthetic dataset generation"""
    
    # Dataset size parameters
    n_shapes: int = 8
    n_scales: int = 3
    n_variants: int = 5
    n_noisy: int = 4
    
    # Shape selection
    included_shapes: Optional[List[str]] = None
    include_hard_negatives: bool = True
    
    # Generation parameters
    img_size: tuple = (256, 256)
    noise_level: float = 0.2
    deform_strength: float = 0.01
    epsilon_ratio: float = 0.01
    
    # Scale parameters
    min_scale: float = 0.5
    max_scale: float = 3.0
    
    def validate(self) -> None:
        """Validate dataset configuration parameters"""
        validate_positive_integer(self.n_shapes, 'n_shapes')
        validate_positive_integer(self.n_scales, 'n_scales')
        validate_positive_integer(self.n_variants, 'n_variants')
        validate_positive_integer(self.n_noisy, 'n_noisy')
        
        if self.n_shapes > 22:  # Max available shapes
            raise ConfigValidationError("n_shapes cannot exceed 22 (max available shapes)")
        
        validate_positive_number(self.noise_level, 'noise_level')
        validate_positive_number(self.deform_strength, 'deform_strength')
        validate_positive_number(self.epsilon_ratio, 'epsilon_ratio')
        
        validate_positive_number(self.min_scale, 'min_scale')
        validate_positive_number(self.max_scale, 'max_scale')
        
        if self.min_scale >= self.max_scale:
            raise ConfigValidationError("min_scale must be less than max_scale")
        
        if not isinstance(self.img_size, tuple) or len(self.img_size) != 2:
            raise ConfigValidationError("img_size must be a tuple of (width, height)")


@dataclass
class FeatureConfig(BaseConfig):
    """Configuration for feature extraction"""
    
    # Feature extraction parameters
    n_fourier_descriptors: int = 4
    n_curvature_bins: int = 16
    use_parallel_processing: bool = True
    max_workers: Optional[int] = None
    
    # Feature selection
    feature_types: List[str] = field(default_factory=lambda: [
        'hu_moments', 'fourier', 'geometric', 'curvature'
    ])
    
    def validate(self) -> None:
        """Validate feature extraction configuration"""
        validate_positive_integer(self.n_fourier_descriptors, 'n_fourier_descriptors')
        validate_positive_integer(self.n_curvature_bins, 'n_curvature_bins')
        
        if self.max_workers is not None:
            validate_positive_integer(self.max_workers, 'max_workers')
        
        valid_feature_types = ['hu_moments', 'fourier', 'geometric', 'curvature']
        for feature_type in self.feature_types:
            if feature_type not in valid_feature_types:
                raise ConfigValidationError(
                    f"Invalid feature type '{feature_type}'. "
                    f"Valid types: {valid_feature_types}"
                )


@dataclass
class TrainingConfig(BaseConfig):
    """Configuration for training process"""
    
    # Data splitting
    test_size: float = 0.3
    validation_size: float = 0.1
    random_state: int = 42
    
    # Training parameters
    batch_size: int = 1000
    enable_visualizations: bool = True
    save_intermediate_results: bool = True
    
    # Model selection
    model_configs: List[str] = field(default_factory=lambda: ['default', 'robust'])
    
    # Performance thresholds
    min_accuracy_threshold: float = 0.95
    confidence_threshold: float = 0.8
    
    def validate(self) -> None:
        """Validate training configuration"""
        validate_probability(self.test_size, 'test_size')
        validate_probability(self.validation_size, 'validation_size')
        
        if self.test_size + self.validation_size >= 1.0:
            raise ConfigValidationError("test_size + validation_size must be < 1.0")
        
        validate_positive_integer(self.batch_size, 'batch_size')
        validate_probability(self.min_accuracy_threshold, 'min_accuracy_threshold')
        validate_probability(self.confidence_threshold, 'confidence_threshold')
        
        # Validate model configs exist
        available_configs = list(ModelConfigRegistry.list_available_configs().keys())
        for config_name in self.model_configs:
            if config_name not in available_configs:
                raise ConfigValidationError(
                    f"Unknown model config '{config_name}'. "
                    f"Available: {available_configs}"
                )


@dataclass
class IOConfig(BaseConfig):
    """Configuration for input/output operations"""
    
    # Save directories
    models_dir: Path = field(default_factory=lambda: Path("saved_models"))
    datasets_dir: Path = field(default_factory=lambda: Path("saved_datasets"))
    results_dir: Path = field(default_factory=lambda: Path("results"))
    
    # File naming
    timestamp_format: str = "%Y%m%d_%H%M%S"
    model_name_template: str = "{model_type}_acc{accuracy:.3f}"
    
    # Storage options
    save_model_metadata: bool = True
    save_training_history: bool = True
    compress_datasets: bool = False
    
    # Cleanup options
    max_saved_models: int = 10
    auto_cleanup: bool = True
    
    def validate(self) -> None:
        """Validate I/O configuration"""
        validate_positive_integer(self.max_saved_models, 'max_saved_models')
        
        # Validate path types
        if not isinstance(self.models_dir, Path):
            self.models_dir = Path(self.models_dir)
        if not isinstance(self.datasets_dir, Path):
            self.datasets_dir = Path(self.datasets_dir)
        if not isinstance(self.results_dir, Path):
            self.results_dir = Path(self.results_dir)


@dataclass
class DefaultTrainingConfig(BaseConfig):
    """Complete default configuration for training pipeline"""
    
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    io: IOConfig = field(default_factory=IOConfig)
    
    def validate(self) -> None:
        """Validate all configuration components"""
        # Individual configs are validated in their __post_init__
        pass


@dataclass
class RobustTrainingConfig(BaseConfig):
    """Configuration optimized for robust training with noisy data"""
    
    dataset: DatasetConfig = field(default_factory=lambda: DatasetConfig(
        n_shapes=15,
        n_scales=6,
        n_variants=8,
        n_noisy=6,
        noise_level=0.5,  # Higher noise
        include_hard_negatives=True
    ))
    
    features: FeatureConfig = field(default_factory=lambda: FeatureConfig(
        n_fourier_descriptors=6,  # More descriptors
        n_curvature_bins=20,      # More bins
        use_parallel_processing=True
    ))
    
    training: TrainingConfig = field(default_factory=lambda: TrainingConfig(
        test_size=0.2,  # More training data
        validation_size=0.1,
        model_configs=['robust'],  # Use robust model only
        min_accuracy_threshold=0.92,  # Slightly lower threshold
        batch_size=500  # Smaller batches
    ))
    
    io: IOConfig = field(default_factory=IOConfig)
    
    def validate(self) -> None:
        """Validate robust configuration components"""
        pass


@dataclass  
class FastTrainingConfig(BaseConfig):
    """Configuration optimized for fast training and prototyping"""
    
    dataset: DatasetConfig = field(default_factory=lambda: DatasetConfig(
        n_shapes=6,      # Fewer shapes
        n_scales=3,      # Fewer scales
        n_variants=3,    # Fewer variants
        n_noisy=2,       # Less noise variation
        img_size=(128, 128)  # Smaller images
    ))
    
    features: FeatureConfig = field(default_factory=lambda: FeatureConfig(
        n_fourier_descriptors=3,  # Fewer descriptors
        n_curvature_bins=12,      # Fewer bins
        use_parallel_processing=True
    ))
    
    training: TrainingConfig = field(default_factory=lambda: TrainingConfig(
        test_size=0.3,
        model_configs=['fast'],   # Use fast model only
        enable_visualizations=False,  # Skip visualizations
        batch_size=2000   # Larger batches
    ))
    
    io: IOConfig = field(default_factory=lambda: IOConfig(
        save_training_history=False,  # Skip detailed history
        max_saved_models=3   # Keep fewer models
    ))
    
    def validate(self) -> None:
        """Validate fast configuration components"""
        pass


class TrainingConfigRegistry:
    """Registry for predefined training configurations"""
    
    @staticmethod
    def get_default() -> DefaultTrainingConfig:
        """Get default training configuration"""
        return DefaultTrainingConfig()
    
    @staticmethod
    def get_robust() -> RobustTrainingConfig:
        """Get robust training configuration"""
        return RobustTrainingConfig()
    
    @staticmethod
    def get_fast() -> FastTrainingConfig:
        """Get fast training configuration"""
        return FastTrainingConfig()
    
    @classmethod
    def list_available_configs(cls) -> Dict[str, str]:
        """List available training configurations"""
        return {
            'default': 'Balanced configuration for general use',
            'robust': 'Robust configuration for noisy data and production use',
            'fast': 'Fast configuration for prototyping and development'
        }
    
    @classmethod
    def get_config(cls, config_name: str) -> BaseConfig:
        """Get a training configuration by name"""
        configs = {
            'default': cls.get_default,
            'robust': cls.get_robust,
            'fast': cls.get_fast
        }
        
        if config_name not in configs:
            available = list(configs.keys())
            raise ValueError(f"Unknown config '{config_name}'. Available: {available}")
        
        return configs[config_name]()