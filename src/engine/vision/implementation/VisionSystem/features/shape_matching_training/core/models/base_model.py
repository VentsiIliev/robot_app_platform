"""
Abstract Base Model Interface

Provides the abstract base class and interfaces for machine learning models
used in shape similarity detection, ensuring consistent APIs and behavior.
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional, Union
import pickle
import joblib
from pathlib import Path
from datetime import datetime


class PredictionResult:
    """Container for model prediction results"""
    
    def __init__(self, 
                 prediction: int,
                 confidence: float,
                 probabilities: Optional[np.ndarray] = None,
                 features: Optional[np.ndarray] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.prediction = prediction
        self.confidence = confidence
        self.probabilities = probabilities
        self.features = features
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'prediction': self.prediction,
            'confidence': self.confidence,
            'probabilities': self.probabilities.tolist() if self.probabilities is not None else None,
            'features': self.features.tolist() if self.features is not None else None,
            'metadata': self.metadata
        }


class ModelMetrics:
    """Container for model performance metrics"""
    
    def __init__(self, metrics: Dict[str, float]):
        self.metrics = metrics
    
    @property
    def accuracy(self) -> float:
        return self.metrics.get('accuracy', 0.0)
    
    @property
    def precision(self) -> float:
        return self.metrics.get('precision', 0.0)
    
    @property
    def recall(self) -> float:
        return self.metrics.get('recall', 0.0)
    
    @property
    def f1_score(self) -> float:
        return self.metrics.get('f1_score', 0.0)
    
    def get_metric(self, name: str, default: float = 0.0) -> float:
        return self.metrics.get(name, default)
    
    def to_dict(self) -> Dict[str, float]:
        return self.metrics.copy()


class BaseModel(ABC):
    """
    Abstract base class for all shape similarity models.
    
    Defines the interface that all models must implement for consistent
    training, prediction, and evaluation behavior.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the model
        
        Args:
            config: Model configuration dictionary
        """
        self.config = config or {}
        self.is_fitted = False
        self.feature_names = []
        self.training_metadata = {}
        self._model = None
    
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'BaseModel':
        """
        Train the model on the provided data
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: Labels of shape (n_samples,)
            
        Returns:
            Self for method chaining
        """
        pass
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions on the provided data
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Predictions of shape (n_samples,)
        """
        pass
    
    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Probabilities of shape (n_samples, n_classes)
        """
        pass
    
    def predict_similarity(self, 
                          contour1: np.ndarray, 
                          contour2: np.ndarray,
                          feature_extractor: 'BaseFeatureExtractor') -> PredictionResult:
        """
        Predict similarity between two contours
        
        Args:
            contour1: First contour
            contour2: Second contour  
            feature_extractor: Feature extractor to use
            
        Returns:
            PredictionResult object with prediction details
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before making predictions")
        
        # Extract features
        from ..features.base_extractor import compute_features_for_pair
        features = compute_features_for_pair((contour1, contour2), feature_extractor)
        features_array = np.array(features).reshape(1, -1)
        
        # Make prediction
        prediction = self.predict(features_array)[0]
        probabilities = self.predict_proba(features_array)[0]
        confidence = np.max(probabilities)
        
        # Create result
        return PredictionResult(
            prediction=int(prediction),
            confidence=float(confidence),
            probabilities=probabilities,
            features=np.array(features),
            metadata={
                'model_type': self.__class__.__name__,
                'feature_extractor': feature_extractor.__class__.__name__
            }
        )
    
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> ModelMetrics:
        """
        Evaluate model performance on test data
        
        Args:
            X: Test feature matrix
            y: Test labels
            
        Returns:
            ModelMetrics object with performance metrics
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before evaluation")
        
        from ...utils.metrics import calculate_similarity_metrics
        
        # Make predictions
        y_pred = self.predict(X)
        y_proba = None
        try:
            y_proba_full = self.predict_proba(X)
            y_proba = y_proba_full[:, 1] if y_proba_full.shape[1] > 1 else y_proba_full.flatten()
        except:
            pass
        
        # Calculate metrics
        metrics = calculate_similarity_metrics(y.tolist(), y_pred.tolist(), 
                                             y_proba.tolist() if y_proba is not None else None)
        
        return ModelMetrics(metrics)
    
    def get_feature_importance(self) -> Optional[np.ndarray]:
        """
        Get feature importance scores if available
        
        Returns:
            Feature importance array or None if not available
        """
        if hasattr(self._model, 'feature_importances_'):
            return self._model.feature_importances_
        elif hasattr(self._model, 'coef_'):
            return np.abs(self._model.coef_[0])  # For linear models
        else:
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the model
        
        Returns:
            Dictionary with model information
        """
        info = {
            'model_type': self.__class__.__name__,
            'is_fitted': self.is_fitted,
            'config': self.config.copy(),
            'feature_count': len(self.feature_names),
            'feature_names': self.feature_names.copy(),
            'training_metadata': self.training_metadata.copy()
        }
        
        # Add model-specific info if available
        if self._model is not None:
            if hasattr(self._model, 'n_estimators'):
                info['n_estimators'] = self._model.n_estimators
            if hasattr(self._model, 'max_depth'):
                info['max_depth'] = self._model.max_depth
            if hasattr(self._model, 'alpha'):
                info['alpha'] = self._model.alpha
        
        return info
    
    def save_model(self, filepath: Union[str, Path]) -> None:
        """
        Save the model to file
        
        Args:
            filepath: Path to save the model
        """
        if not self.is_fitted:
            raise ValueError("Cannot save unfitted model")
        
        filepath = Path(filepath)
        
        # Create save data
        save_data = {
            'model': self._model,
            'config': self.config,
            'is_fitted': self.is_fitted,
            'feature_names': self.feature_names,
            'training_metadata': self.training_metadata,
            'model_type': self.__class__.__name__,
            'save_timestamp': datetime.now().isoformat()
        }
        
        # Save using joblib for better sklearn compatibility
        joblib.dump(save_data, filepath)
    
    @classmethod
    def load_model(cls, filepath: Union[str, Path]) -> 'BaseModel':
        """
        Load a model from file
        
        Args:
            filepath: Path to the saved model
            
        Returns:
            Loaded model instance
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        # Load data
        save_data = joblib.load(filepath)
        
        # Create model instance
        model = cls(config=save_data.get('config', {}))
        model._model = save_data['model']
        model.is_fitted = save_data.get('is_fitted', True)
        model.feature_names = save_data.get('feature_names', [])
        model.training_metadata = save_data.get('training_metadata', {})
        
        return model
    
    def set_feature_names(self, feature_names: List[str]) -> None:
        """Set the feature names for this model"""
        self.feature_names = feature_names.copy()
    
    def get_training_history(self) -> Dict[str, Any]:
        """Get training history if available"""
        return self.training_metadata.get('training_history', {})
    
    def _validate_input(self, X: np.ndarray) -> None:
        """Validate input data"""
        if not isinstance(X, np.ndarray):
            raise TypeError("Input X must be a numpy array")
        
        if X.ndim != 2:
            raise ValueError(f"Input X must be 2D array, got shape {X.shape}")
        
        if self.feature_names and X.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Input features ({X.shape[1]}) don't match expected "
                f"number of features ({len(self.feature_names)})"
            )
    
    def _record_training_metadata(self, 
                                 X: np.ndarray, 
                                 y: np.ndarray,
                                 training_time: float = 0.0,
                                 **kwargs) -> None:
        """Record training metadata"""
        self.training_metadata = {
            'training_samples': X.shape[0],
            'feature_count': X.shape[1],
            'class_distribution': {
                int(label): int(count) for label, count in 
                zip(*np.unique(y, return_counts=True))
            },
            'training_time': training_time,
            'training_timestamp': datetime.now().isoformat(),
            **kwargs
        }
    
    def __str__(self) -> str:
        """String representation of the model"""
        status = "fitted" if self.is_fitted else "unfitted"
        return f"{self.__class__.__name__}({status}, {len(self.feature_names)} features)"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return self.__str__()


class ModelCompatibilityChecker:
    """
    Utility class for checking model compatibility with features and data
    """
    
    @staticmethod
    def check_feature_compatibility(model: BaseModel, 
                                  feature_extractor: 'BaseFeatureExtractor') -> bool:
        """
        Check if model is compatible with feature extractor
        
        Args:
            model: Model to check
            feature_extractor: Feature extractor to check against
            
        Returns:
            True if compatible
        """
        if not model.is_fitted:
            return False
        
        expected_features = len(model.feature_names)
        actual_features = feature_extractor.get_feature_count()
        
        return expected_features == actual_features
    
    @staticmethod
    def check_data_compatibility(model: BaseModel, X: np.ndarray) -> bool:
        """
        Check if model is compatible with input data
        
        Args:
            model: Model to check
            X: Input data to check
            
        Returns:
            True if compatible
        """
        if not model.is_fitted:
            return False
        
        if X.ndim != 2:
            return False
        
        if model.feature_names and X.shape[1] != len(model.feature_names):
            return False
        
        return True
    
    @staticmethod
    def get_compatibility_report(model: BaseModel, 
                               feature_extractor: 'BaseFeatureExtractor') -> Dict[str, Any]:
        """
        Get detailed compatibility report
        
        Args:
            model: Model to check
            feature_extractor: Feature extractor to check
            
        Returns:
            Compatibility report dictionary
        """
        report = {
            'compatible': False,
            'model_info': model.get_model_info(),
            'feature_extractor_info': feature_extractor.get_metadata(),
            'issues': []
        }
        
        if not model.is_fitted:
            report['issues'].append("Model is not fitted")
            return report
        
        expected_features = len(model.feature_names)
        actual_features = feature_extractor.get_feature_count()
        
        if expected_features != actual_features:
            report['issues'].append(
                f"Feature count mismatch: model expects {expected_features}, "
                f"extractor provides {actual_features}"
            )
        
        # Check feature names if available
        if hasattr(feature_extractor, 'get_feature_names'):
            extractor_names = feature_extractor.get_feature_names()
            if model.feature_names and model.feature_names != extractor_names:
                report['issues'].append("Feature names don't match")
                report['expected_features'] = model.feature_names
                report['actual_features'] = extractor_names
        
        report['compatible'] = len(report['issues']) == 0
        
        return report