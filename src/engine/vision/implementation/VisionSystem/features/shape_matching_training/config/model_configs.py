"""
Model Configuration Classes

Provides configuration classes for different machine learning models
with comprehensive parameter validation and documentation.
"""

from dataclasses import dataclass
from typing import Optional, Union, Dict, Any
from .base_config import (
    BaseConfig, 
    ConfigValidationError,
    validate_positive_number,
    validate_positive_integer,
    validate_choice,
    validate_probability
)


@dataclass
class SGDClassifierConfig(BaseConfig):
    """
    Configuration for SGDClassifier (Stochastic Gradient Descent Classifier)
    
    SGD is an online learning algorithm that updates model parameters for each training sample,
    making it suitable for large datasets and online/incremental learning scenarios.
    """
    
    # Core Algorithm Parameters
    loss: str = 'log_loss'
    penalty: Optional[str] = 'l2'
    alpha: float = 0.0001
    l1_ratio: float = 0.15
    
    # Learning Parameters
    fit_intercept: bool = True
    max_iter: int = 1000
    tol: Optional[float] = 1e-3
    shuffle: bool = True
    verbose: int = 0
    epsilon: float = 0.1
    
    # Learning Rate and Optimization
    learning_rate: str = 'optimal'
    eta0: float = 0.0
    power_t: float = 0.5
    
    # Early Stopping
    early_stopping: bool = False
    validation_fraction: float = 0.1
    n_iter_no_change: int = 5
    
    # Data Handling
    class_weight: Optional[Union[Dict, str]] = None
    warm_start: bool = False
    average: Union[bool, int] = False
    
    # System Parameters
    random_state: Optional[int] = 42
    
    def validate(self) -> None:
        """Validate SGD classifier configuration parameters"""
        # Validate loss function
        valid_losses = [
            'hinge', 'log_loss', 'modified_huber', 'squared_hinge', 
            'perceptron', 'squared_error', 'huber', 'epsilon_insensitive',
            'squared_epsilon_insensitive'
        ]
        validate_choice(self.loss, valid_losses, 'loss')
        
        # Validate penalty
        if self.penalty is not None:
            valid_penalties = ['l1', 'l2', 'elasticnet']
            validate_choice(self.penalty, valid_penalties, 'penalty')
        
        # Validate numerical parameters
        validate_positive_number(self.alpha, 'alpha')
        validate_probability(self.l1_ratio, 'l1_ratio')
        validate_positive_integer(self.max_iter, 'max_iter')
        
        if self.tol is not None:
            validate_positive_number(self.tol, 'tol')
        
        validate_positive_number(self.epsilon, 'epsilon')
        
        # Validate learning rate
        valid_lr_schedules = ['constant', 'optimal', 'invscaling', 'adaptive']
        validate_choice(self.learning_rate, valid_lr_schedules, 'learning_rate')
        
        # Validate early stopping parameters
        if self.early_stopping:
            validate_probability(self.validation_fraction, 'validation_fraction')
            validate_positive_integer(self.n_iter_no_change, 'n_iter_no_change')
        
        # Validate class_weight
        if isinstance(self.class_weight, str):
            validate_choice(self.class_weight, ['balanced'], 'class_weight')


@dataclass  
class CalibratedClassifierConfig(BaseConfig):
    """
    Configuration for CalibratedClassifierCV (Probability Calibration)
    
    Calibration improves the reliability of predicted probabilities by mapping
    the classifier's output to better-calibrated probability estimates.
    """
    
    method: str = 'sigmoid'
    cv: Union[int, str, None] = 3
    n_jobs: Optional[int] = None
    ensemble: bool = True
    
    def validate(self) -> None:
        """Validate calibration configuration parameters"""
        # Validate calibration method
        valid_methods = ['sigmoid', 'isotonic']
        validate_choice(self.method, valid_methods, 'method')
        
        # Validate cross-validation parameter
        if isinstance(self.cv, int):
            validate_positive_integer(self.cv, 'cv')
        elif isinstance(self.cv, str):
            validate_choice(self.cv, ['prefit'], 'cv')


@dataclass
class SGDCalibratedConfig(BaseConfig):
    """
    Complete configuration for SGD Online (Calibrated) model combining
    SGDClassifier with CalibratedClassifierCV
    """
    
    sgd_config: SGDClassifierConfig = None
    calibration_config: CalibratedClassifierConfig = None
    
    def __post_init__(self):
        """Initialize default configurations if not provided"""
        if self.sgd_config is None:
            self.sgd_config = SGDClassifierConfig()
        if self.calibration_config is None:
            self.calibration_config = CalibratedClassifierConfig()
        
        # Call parent's __post_init__ for validation
        super().__post_init__()
    
    def validate(self) -> None:
        """Validate the combined configuration"""
        if not isinstance(self.sgd_config, SGDClassifierConfig):
            raise ConfigValidationError("sgd_config must be an SGDClassifierConfig instance")
        if not isinstance(self.calibration_config, CalibratedClassifierConfig):
            raise ConfigValidationError("calibration_config must be a CalibratedClassifierConfig instance")
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get human-readable information about the configured model
        
        Returns:
            Model configuration summary
        """
        return {
            'model_type': 'SGD Online (Calibrated)',
            'base_classifier': 'SGDClassifier',
            'calibration_method': self.calibration_config.method,
            'loss_function': self.sgd_config.loss,
            'regularization': self.sgd_config.penalty,
            'alpha': self.sgd_config.alpha,
            'max_iterations': self.sgd_config.max_iter,
            'cv_folds': self.calibration_config.cv,
            'random_state': self.sgd_config.random_state
        }


class ModelConfigRegistry:
    """
    Registry for predefined model configurations.
    
    Provides easy access to common model configuration presets
    for different use cases and performance requirements.
    """
    
    @staticmethod
    def get_default_sgd_calibrated() -> SGDCalibratedConfig:
        """
        Get the default configuration used in the original training script
        
        Returns:
            Default SGD calibrated configuration
        """
        return SGDCalibratedConfig(
            sgd_config=SGDClassifierConfig(
                loss='log_loss',
                random_state=42
            ),
            calibration_config=CalibratedClassifierConfig(
                method='sigmoid',
                cv=3
            )
        )
    
    @staticmethod
    def get_robust_sgd_calibrated() -> SGDCalibratedConfig:
        """
        Get a more robust configuration for noisy data
        
        Returns:
            Robust SGD calibrated configuration
        """
        return SGDCalibratedConfig(
            sgd_config=SGDClassifierConfig(
                loss='modified_huber',  # More robust to outliers
                penalty='elasticnet',   # Combines L1 and L2
                alpha=0.001,           # Slightly stronger regularization
                l1_ratio=0.2,          # 20% L1, 80% L2
                max_iter=2000,         # More iterations
                early_stopping=True,   # Stop early if not improving
                validation_fraction=0.1,
                class_weight='balanced', # Handle class imbalance
                random_state=42
            ),
            calibration_config=CalibratedClassifierConfig(
                method='isotonic',     # More flexible calibration
                cv=5                   # More robust cross-validation
            )
        )
    
    @staticmethod
    def get_fast_sgd_calibrated() -> SGDCalibratedConfig:
        """
        Get a configuration optimized for speed
        
        Returns:
            Fast training SGD calibrated configuration
        """
        return SGDCalibratedConfig(
            sgd_config=SGDClassifierConfig(
                loss='log_loss',
                alpha=0.01,           # Higher alpha for faster convergence
                max_iter=500,         # Fewer iterations
                tol=1e-2,            # Looser tolerance
                random_state=42
            ),
            calibration_config=CalibratedClassifierConfig(
                method='sigmoid',     # Faster than isotonic
                cv=3,                # Fewer CV folds
                ensemble=False       # Single calibrator instead of ensemble
            )
        )
    
    @classmethod
    def list_available_configs(cls) -> Dict[str, str]:
        """
        List all available predefined configurations
        
        Returns:
            Dictionary mapping config names to descriptions
        """
        return {
            'default': 'Default SGD calibrated configuration for general use',
            'robust': 'Robust configuration for noisy data and imbalanced datasets',
            'fast': 'Speed-optimized configuration for quick training'
        }
    
    @classmethod
    def get_config(cls, config_name: str) -> SGDCalibratedConfig:
        """
        Get a predefined configuration by name
        
        Args:
            config_name: Name of the configuration to retrieve
            
        Returns:
            Requested configuration
            
        Raises:
            ValueError: If configuration name is not found
        """
        configs = {
            'default': cls.get_default_sgd_calibrated,
            'robust': cls.get_robust_sgd_calibrated,
            'fast': cls.get_fast_sgd_calibrated
        }
        
        if config_name not in configs:
            available = list(configs.keys())
            raise ValueError(f"Unknown configuration '{config_name}'. Available: {available}")
        
        return configs[config_name]()