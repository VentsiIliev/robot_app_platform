"""
Model Factory

Provides factory pattern for creating and managing different types of
machine learning models for shape similarity detection.
"""

import numpy as np
from typing import Dict, Type, Any, List, Optional, Union
from .base_model import BaseModel
from .sgd_model import SGDModel, OnlineSGDModel
from ...config.model_configs import ModelConfigRegistry


class ModelFactory:
    """
    Factory for creating and managing model instances
    """
    
    _models: Dict[str, Type[BaseModel]] = {}
    
    @classmethod
    def register_model(cls, name: str, model_class: Type[BaseModel]) -> None:
        """
        Register a model class
        
        Args:
            name: Name to register the model under
            model_class: Model class to register
        """
        cls._models[name] = model_class
    
    @classmethod
    def create_model(cls, model_type: str, config: Optional[Dict[str, Any]] = None) -> BaseModel:
        """
        Create a model instance
        
        Args:
            model_type: Type of model to create
            config: Model configuration
            
        Returns:
            Model instance
            
        Raises:
            ValueError: If model type is unknown
        """
        if model_type not in cls._models:
            available = list(cls._models.keys())
            raise ValueError(f"Unknown model type '{model_type}'. Available: {available}")
        
        model_class = cls._models[model_type]
        return model_class(config)
    
    @classmethod
    def create_sgd_model(cls, config_name: str = 'default', **kwargs) -> SGDModel:
        """
        Create SGD model with predefined configuration
        
        Args:
            config_name: Name of predefined configuration ('default', 'robust', 'fast')
            **kwargs: Additional configuration overrides
            
        Returns:
            SGD model instance
        """
        try:
            base_config = ModelConfigRegistry.get_config(config_name)
        except ValueError:
            base_config = ModelConfigRegistry.get_default_sgd_calibrated()
        
        # Create config dict with overrides
        config = {
            'config_name': config_name,
            **kwargs
        }
        
        return SGDModel(config)
    
    @classmethod
    def create_online_sgd_model(cls, config_name: str = 'fast', **kwargs) -> OnlineSGDModel:
        """
        Create online SGD model optimized for incremental learning
        
        Args:
            config_name: Name of predefined configuration
            **kwargs: Additional configuration overrides
            
        Returns:
            Online SGD model instance
        """
        try:
            base_config = ModelConfigRegistry.get_config(config_name)
        except ValueError:
            base_config = ModelConfigRegistry.get_fast_sgd_calibrated()
        
        config = {
            'config_name': config_name,
            **kwargs
        }
        
        return OnlineSGDModel(config)
    
    @classmethod
    def create_ensemble_model(cls, 
                            model_configs: List[Dict[str, Any]],
                            ensemble_method: str = 'voting') -> 'EnsembleModel':
        """
        Create ensemble model from multiple base models
        
        Args:
            model_configs: List of model configurations
            ensemble_method: Method for ensemble ('voting', 'weighted', 'stacking')
            
        Returns:
            Ensemble model instance
        """
        models = []
        for config in model_configs:
            model_type = config.pop('model_type', 'sgd')
            model = cls.create_model(model_type, config)
            models.append(model)
        
        return EnsembleModel(models, ensemble_method)
    
    @classmethod
    def list_available_models(cls) -> Dict[str, str]:
        """
        List all available model types with descriptions
        
        Returns:
            Dictionary mapping model names to descriptions
        """
        descriptions = {
            'sgd': 'SGD classifier with probability calibration',
            'online_sgd': 'Online SGD classifier for incremental learning',
            'ensemble': 'Ensemble of multiple models'
        }
        
        return {name: descriptions.get(name, 'No description available') 
                for name in cls._models.keys()}
    
    @classmethod
    def get_model_info(cls, model_type: str) -> Dict[str, Any]:
        """
        Get information about a model type
        
        Args:
            model_type: Type of model to get info for
            
        Returns:
            Model information dictionary
        """
        if model_type not in cls._models:
            raise ValueError(f"Unknown model type: {model_type}")
        
        model_class = cls._models[model_type]
        
        return {
            'model_type': model_type,
            'class_name': model_class.__name__,
            'docstring': model_class.__doc__,
            'supports_online_learning': hasattr(model_class, 'partial_fit'),
            'supports_probability': True,  # All our models support probability
            'supports_feature_importance': True
        }
    
    @classmethod
    def create_model_from_config_file(cls, config_path: str) -> BaseModel:
        """
        Create model from configuration file
        
        Args:
            config_path: Path to configuration file (JSON or YAML)
            
        Returns:
            Model instance
        """
        import json
        import yaml
        from pathlib import Path
        
        config_path = Path(config_path)
        
        # Load configuration
        if config_path.suffix.lower() == '.json':
            with open(config_path, 'r') as f:
                config = json.load(f)
        elif config_path.suffix.lower() in ['.yml', '.yaml']:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported config file format: {config_path.suffix}")
        
        # Extract model type and create model
        model_type = config.pop('model_type', 'sgd')
        return cls.create_model(model_type, config)


class EnsembleModel(BaseModel):
    """
    Ensemble model that combines multiple base models
    """
    
    def __init__(self, 
                 models: List[BaseModel],
                 ensemble_method: str = 'voting',
                 weights: Optional[List[float]] = None):
        """
        Initialize ensemble model
        
        Args:
            models: List of base models
            ensemble_method: Ensemble method ('voting', 'weighted', 'average')
            weights: Weights for weighted ensemble (optional)
        """
        super().__init__()
        self.models = models
        self.ensemble_method = ensemble_method
        self.weights = weights or [1.0] * len(models)
        
        if len(self.weights) != len(models):
            raise ValueError("Number of weights must match number of models")
        
        # Normalize weights
        total_weight = sum(self.weights)
        self.weights = [w / total_weight for w in self.weights]
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'EnsembleModel':
        """
        Fit all models in the ensemble
        
        Args:
            X: Feature matrix
            y: Labels
            
        Returns:
            Self for method chaining
        """
        import time
        
        start_time = time.time()
        
        # Fit each model
        for i, model in enumerate(self.models):
            print(f"Training model {i+1}/{len(self.models)}: {model.__class__.__name__}")
            model.fit(X, y)
        
        # Record metadata
        training_time = time.time() - start_time
        self._record_training_metadata(
            X, y,
            training_time=training_time,
            ensemble_method=self.ensemble_method,
            n_models=len(self.models),
            model_types=[model.__class__.__name__ for model in self.models]
        )
        
        self.is_fitted = True
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make ensemble predictions
        
        Args:
            X: Feature matrix
            
        Returns:
            Predictions
        """
        if not self.is_fitted:
            raise ValueError("Ensemble must be fitted before making predictions")
        
        if self.ensemble_method == 'voting':
            return self._voting_predict(X)
        elif self.ensemble_method == 'weighted':
            return self._weighted_predict(X)
        elif self.ensemble_method == 'average':
            return self._average_predict(X)
        else:
            raise ValueError(f"Unknown ensemble method: {self.ensemble_method}")
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities using ensemble
        
        Args:
            X: Feature matrix
            
        Returns:
            Probabilities
        """
        if not self.is_fitted:
            raise ValueError("Ensemble must be fitted before making predictions")
        
        # Get probabilities from all models
        all_probas = []
        for model in self.models:
            probas = model.predict_proba(X)
            all_probas.append(probas)
        
        # Combine probabilities
        if self.ensemble_method in ['weighted', 'average']:
            # Weighted average of probabilities
            weighted_probas = np.zeros_like(all_probas[0])
            for probas, weight in zip(all_probas, self.weights):
                weighted_probas += probas * weight
            return weighted_probas
        else:
            # Simple average
            return np.mean(all_probas, axis=0)
    
    def _voting_predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using majority voting"""
        all_predictions = []
        for model in self.models:
            preds = model.predict(X)
            all_predictions.append(preds)
        
        # Majority vote
        all_predictions = np.array(all_predictions).T
        votes = []
        for sample_preds in all_predictions:
            unique, counts = np.unique(sample_preds, return_counts=True)
            majority_class = unique[np.argmax(counts)]
            votes.append(majority_class)
        
        return np.array(votes)
    
    def _weighted_predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using weighted voting"""
        probas = self.predict_proba(X)
        return np.argmax(probas, axis=1)
    
    def _average_predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using average probabilities"""
        return self._weighted_predict(X)  # Same as weighted with equal weights
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get ensemble model information"""
        info = super().get_model_info()
        info.update({
            'ensemble_method': self.ensemble_method,
            'n_models': len(self.models),
            'weights': self.weights,
            'base_models': [model.get_model_info() for model in self.models]
        })
        return info
    
    def get_feature_importance(self) -> Optional[np.ndarray]:
        """
        Get averaged feature importance from all models
        
        Returns:
            Average feature importance or None
        """
        importances = []
        
        for model in self.models:
            model_importance = model.get_feature_importance()
            if model_importance is not None:
                importances.append(model_importance)
        
        if not importances:
            return None
        
        # Weight and average the importances
        weighted_importance = np.zeros_like(importances[0])
        total_weight = 0
        
        for importance, weight in zip(importances, self.weights[:len(importances)]):
            weighted_importance += importance * weight
            total_weight += weight
        
        if total_weight > 0:
            weighted_importance /= total_weight
        
        return weighted_importance


# Register available models
ModelFactory.register_model('sgd', SGDModel)
ModelFactory.register_model('online_sgd', OnlineSGDModel)
ModelFactory.register_model('ensemble', EnsembleModel)

