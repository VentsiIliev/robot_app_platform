"""
SGD Model Implementation

Provides SGD (Stochastic Gradient Descent) classifier implementation
with calibrated probability outputs for shape similarity detection.
"""

import numpy as np
import time
from typing import Dict, Any, Optional, List
from sklearn.linear_model import SGDClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler

from .base_model import BaseModel
from ...config.model_configs import SGDCalibratedConfig, ModelConfigRegistry


class SGDModel(BaseModel):
    """
    SGD classifier implementation with probability calibration
    for shape similarity detection.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize SGD model
        
        Args:
            config: Model configuration dictionary or SGDCalibratedConfig
        """
        super().__init__(config)
        
        # Handle both dict and config object inputs
        if isinstance(config, SGDCalibratedConfig):
            self.model_config = config
        elif isinstance(config, dict):
            # Try to create from dict or use defaults
            config_name = config.get('config_name', 'default')
            try:
                self.model_config = ModelConfigRegistry.get_config(config_name)
                # Override with any provided parameters
                if 'sgd_params' in config:
                    for key, value in config['sgd_params'].items():
                        setattr(self.model_config.sgd_config, key, value)
                if 'calibration_params' in config:
                    for key, value in config['calibration_params'].items():
                        setattr(self.model_config.calibration_config, key, value)
            except ValueError:
                # Fallback to default config
                self.model_config = ModelConfigRegistry.get_default_sgd_calibrated()
        else:
            self.model_config = ModelConfigRegistry.get_default_sgd_calibrated()
        
        # Initialize components
        self.scaler = StandardScaler()
        self.use_scaling = config.get('use_scaling', True) if isinstance(config, dict) else True
        self._base_model = None
        self._calibrated_model = None
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'SGDModel':
        """
        Fit the SGD model with calibration
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: Labels of shape (n_samples,)
            
        Returns:
            Self for method chaining
        """
        self._validate_input(X)
        
        if len(np.unique(y)) != 2:
            raise ValueError("SGD model requires binary classification (2 classes)")
        
        start_time = time.time()
        
        # Scale features if enabled
        if self.use_scaling:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = X
        
        # Create base SGD classifier
        self._base_model = SGDClassifier(
            loss=self.model_config.sgd_config.loss,
            penalty=self.model_config.sgd_config.penalty,
            alpha=self.model_config.sgd_config.alpha,
            l1_ratio=self.model_config.sgd_config.l1_ratio,
            fit_intercept=self.model_config.sgd_config.fit_intercept,
            max_iter=self.model_config.sgd_config.max_iter,
            tol=self.model_config.sgd_config.tol,
            shuffle=self.model_config.sgd_config.shuffle,
            verbose=self.model_config.sgd_config.verbose,
            epsilon=self.model_config.sgd_config.epsilon,
            learning_rate=self.model_config.sgd_config.learning_rate,
            eta0=self.model_config.sgd_config.eta0,
            power_t=self.model_config.sgd_config.power_t,
            early_stopping=self.model_config.sgd_config.early_stopping,
            validation_fraction=self.model_config.sgd_config.validation_fraction,
            n_iter_no_change=self.model_config.sgd_config.n_iter_no_change,
            class_weight=self.model_config.sgd_config.class_weight,
            warm_start=self.model_config.sgd_config.warm_start,
            average=self.model_config.sgd_config.average,
            random_state=self.model_config.sgd_config.random_state
        )
        
        # Create calibrated classifier
        self._calibrated_model = CalibratedClassifierCV(
            estimator=self._base_model,
            method=self.model_config.calibration_config.method,
            cv=self.model_config.calibration_config.cv,
            n_jobs=self.model_config.calibration_config.n_jobs,
            ensemble=self.model_config.calibration_config.ensemble
        )
        
        # Fit the calibrated model
        self._calibrated_model.fit(X_scaled, y)
        
        # Set the main model reference
        self._model = self._calibrated_model
        
        # Record training metadata
        training_time = time.time() - start_time
        self._record_training_metadata(
            X, y, 
            training_time=training_time,
            scaling_used=self.use_scaling,
            model_config=self.model_config.get_model_info(),
            convergence_info=self._get_convergence_info()
        )
        
        self.is_fitted = True
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Predictions of shape (n_samples,)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before making predictions")
        
        self._validate_input(X)
        
        # Scale features if scaling was used during training
        if self.use_scaling:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        return self._calibrated_model.predict(X_scaled)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Probabilities of shape (n_samples, 2)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before making predictions")
        
        self._validate_input(X)
        
        # Scale features if scaling was used during training
        if self.use_scaling:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        return self._calibrated_model.predict_proba(X_scaled)
    
    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        """
        Return the mean accuracy on the given test data and labels

        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: True labels of shape (n_samples,)

        Returns:
            Mean accuracy score
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before scoring")

        self._validate_input(X)

        # Scale features if scaling was used during training
        if self.use_scaling:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X

        return self._calibrated_model.score(X_scaled, y)

    def predict_with_confidence(self, X: np.ndarray,
                              confidence_threshold: float = 0.8) -> tuple:
        """
        Make predictions with confidence filtering
        
        Args:
            X: Feature matrix
            confidence_threshold: Minimum confidence for predictions
            
        Returns:
            Tuple of (predictions, confidences, high_confidence_mask)
        """
        probabilities = self.predict_proba(X)
        confidences = np.max(probabilities, axis=1)
        predictions = self.predict(X)
        high_confidence_mask = confidences >= confidence_threshold
        
        return predictions, confidences, high_confidence_mask
    
    def get_feature_importance(self) -> Optional[np.ndarray]:
        """
        Get feature importance based on coefficient magnitudes
        
        Returns:
            Feature importance array or None
        """
        if not self.is_fitted:
            return None
        
        # For calibrated classifiers, we need to access the base estimator
        try:
            if hasattr(self._calibrated_model, 'calibrated_classifiers_'):
                # Get coefficients from the first calibrated classifier
                base_clf = self._calibrated_model.calibrated_classifiers_[0].estimator
                if hasattr(base_clf, 'coef_'):
                    return np.abs(base_clf.coef_[0])
            elif hasattr(self._base_model, 'coef_'):
                return np.abs(self._base_model.coef_[0])
        except:
            import traceback
            traceback.print_exc()

        return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information"""
        info = super().get_model_info()
        
        # Add SGD-specific information
        info.update({
            'model_config': self.model_config.get_model_info(),
            'use_scaling': self.use_scaling,
            'is_calibrated': True,
            'calibration_method': self.model_config.calibration_config.method
        })
        
        # Add training info if available
        if self.is_fitted:
            info['convergence_info'] = self._get_convergence_info()
        
        return info
    
    def _get_convergence_info(self) -> Dict[str, Any]:
        """Get convergence information from the trained model"""
        convergence_info = {}
        
        try:
            if hasattr(self._base_model, 'n_iter_'):
                convergence_info['n_iterations'] = self._base_model.n_iter_
            
            if hasattr(self._base_model, 'loss_curve_'):
                convergence_info['final_loss'] = self._base_model.loss_curve_[-1]
                convergence_info['loss_curve_length'] = len(self._base_model.loss_curve_)
            
            # Check for convergence warnings
            if hasattr(self._base_model, 'n_iter_') and hasattr(self._base_model, 'max_iter'):
                if self._base_model.n_iter_ >= self._base_model.max_iter:
                    convergence_info['convergence_warning'] = "Model may not have converged"
        except:
            pass
        
        return convergence_info
    
    def partial_fit(self, X: np.ndarray, y: np.ndarray, classes: Optional[List] = None):
        """
        Perform incremental learning on a batch of data
        
        Args:
            X: Feature matrix
            y: Labels
            classes: Array of possible classes (required for first call)
        """
        if not self.is_fitted and classes is None:
            raise ValueError("classes must be provided for first call to partial_fit")
        
        self._validate_input(X)
        
        # Scale features
        if self.use_scaling:
            if not self.is_fitted:
                X_scaled = self.scaler.fit_transform(X)
            else:
                X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        # Initialize base model if needed
        if not self.is_fitted:
            self._base_model = SGDClassifier(
                loss=self.model_config.sgd_config.loss,
                penalty=self.model_config.sgd_config.penalty,
                alpha=self.model_config.sgd_config.alpha,
                l1_ratio=self.model_config.sgd_config.l1_ratio,
                fit_intercept=self.model_config.sgd_config.fit_intercept,
                max_iter=self.model_config.sgd_config.max_iter,
                tol=self.model_config.sgd_config.tol,
                shuffle=self.model_config.sgd_config.shuffle,
                verbose=self.model_config.sgd_config.verbose,
                epsilon=self.model_config.sgd_config.epsilon,
                learning_rate=self.model_config.sgd_config.learning_rate,
                eta0=self.model_config.sgd_config.eta0,
                power_t=self.model_config.sgd_config.power_t,
                early_stopping=self.model_config.sgd_config.early_stopping,
                validation_fraction=self.model_config.sgd_config.validation_fraction,
                n_iter_no_change=self.model_config.sgd_config.n_iter_no_change,
                class_weight=self.model_config.sgd_config.class_weight,
                warm_start=self.model_config.sgd_config.warm_start,
                average=self.model_config.sgd_config.average,
                random_state=self.model_config.sgd_config.random_state
            )
            
            # For partial fit, we use the base model directly (no calibration)
            self._model = self._base_model
            self.is_fitted = True
        
        # Perform partial fit
        self._base_model.partial_fit(X_scaled, y, classes)
    
    def get_decision_function(self, X: np.ndarray) -> np.ndarray:
        """
        Get decision function values
        
        Args:
            X: Feature matrix
            
        Returns:
            Decision function values
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before getting decision function")
        
        self._validate_input(X)
        
        # Scale features if scaling was used during training
        if self.use_scaling:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        # Get decision function from base model
        if hasattr(self._calibrated_model, 'calibrated_classifiers_'):
            base_clf = self._calibrated_model.calibrated_classifiers_[0].estimator
            if hasattr(base_clf, 'decision_function'):
                return base_clf.decision_function(X_scaled)
        
        raise NotImplementedError("Decision function not available for this model configuration")


class OnlineSGDModel(SGDModel):
    """
    SGD model optimized for online/incremental learning
    without calibration for faster updates.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize online SGD model"""
        super().__init__(config)
        self._use_calibration = False
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'OnlineSGDModel':
        """
        Fit the online SGD model (without calibration)
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: Labels of shape (n_samples,)
            
        Returns:
            Self for method chaining
        """
        self._validate_input(X)
        
        if len(np.unique(y)) != 2:
            raise ValueError("SGD model requires binary classification (2 classes)")
        
        start_time = time.time()
        
        # Scale features if enabled
        if self.use_scaling:
            X_scaled = self.scaler.fit_transform(X)
        else:
            X_scaled = X
        
        # Create base SGD classifier (no calibration)
        self._base_model = SGDClassifier(
            loss=self.model_config.sgd_config.loss,
            penalty=self.model_config.sgd_config.penalty,
            alpha=self.model_config.sgd_config.alpha,
            l1_ratio=self.model_config.sgd_config.l1_ratio,
            fit_intercept=self.model_config.sgd_config.fit_intercept,
            max_iter=self.model_config.sgd_config.max_iter,
            tol=self.model_config.sgd_config.tol,
            shuffle=self.model_config.sgd_config.shuffle,
            verbose=self.model_config.sgd_config.verbose,
            epsilon=self.model_config.sgd_config.epsilon,
            learning_rate=self.model_config.sgd_config.learning_rate,
            eta0=self.model_config.sgd_config.eta0,
            power_t=self.model_config.sgd_config.power_t,
            early_stopping=self.model_config.sgd_config.early_stopping,
            validation_fraction=self.model_config.sgd_config.validation_fraction,
            n_iter_no_change=self.model_config.sgd_config.n_iter_no_change,
            class_weight=self.model_config.sgd_config.class_weight,
            warm_start=self.model_config.sgd_config.warm_start,
            average=self.model_config.sgd_config.average,
            random_state=self.model_config.sgd_config.random_state
        )
        
        # Fit the base model
        self._base_model.fit(X_scaled, y)
        
        # Set the main model reference
        self._model = self._base_model
        
        # Record training metadata
        training_time = time.time() - start_time
        self._record_training_metadata(
            X, y, 
            training_time=training_time,
            scaling_used=self.use_scaling,
            model_config=self.model_config.get_model_info(),
            convergence_info=self._get_convergence_info(),
            online_mode=True
        )
        
        self.is_fitted = True
        return self
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities (may not be well-calibrated)
        
        Args:
            X: Feature matrix of shape (n_samples, n_features)
            
        Returns:
            Probabilities of shape (n_samples, 2)
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before making predictions")
        
        self._validate_input(X)
        
        # Scale features if scaling was used during training
        if self.use_scaling:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X
        
        # Use decision function to estimate probabilities
        if hasattr(self._base_model, 'predict_proba'):
            return self._base_model.predict_proba(X_scaled)
        else:
            # Fallback: convert decision function to probabilities using sigmoid
            decision = self._base_model.decision_function(X_scaled)
            proba_pos = 1 / (1 + np.exp(-decision))
            proba_neg = 1 - proba_pos
            return np.column_stack([proba_neg, proba_pos])
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        info = super().get_model_info()
        info['online_mode'] = True
        info['is_calibrated'] = False
        return info

