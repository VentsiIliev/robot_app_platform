"""
Validation Utilities Module

Provides data validation functions for contours, features, configurations,
and other inputs to ensure data quality and consistency.
"""

import cv2
import numpy as np
from typing import List, Any, Optional, Union, Tuple, Dict
from pathlib import Path


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


def validate_contour(contour: np.ndarray, 
                    min_points: int = 3,
                    max_points: Optional[int] = None,
                    min_area: float = 1.0,
                    max_area: Optional[float] = None) -> bool:
    """
    Validate that a contour meets basic requirements
    
    Args:
        contour: OpenCV contour array
        min_points: Minimum number of points required
        max_points: Maximum number of points allowed (optional)
        min_area: Minimum contour area required
        max_area: Maximum contour area allowed (optional)
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    # Check if contour exists
    if contour is None:
        raise ValidationError("Contour is None")
    
    # Check if it's a numpy array
    if not isinstance(contour, np.ndarray):
        raise ValidationError(f"Contour must be numpy array, got {type(contour)}")
    
    # Check shape
    if len(contour.shape) != 3 or contour.shape[2] != 2:
        if len(contour.shape) == 2 and contour.shape[1] == 2:
            # Reshape if needed (N, 2) -> (N, 1, 2)
            contour = contour.reshape(-1, 1, 2)
        else:
            raise ValidationError(f"Invalid contour shape: {contour.shape}. Expected (N, 1, 2) or (N, 2)")
    
    # Check number of points
    n_points = contour.shape[0]
    if n_points < min_points:
        raise ValidationError(f"Contour has {n_points} points, minimum required: {min_points}")
    
    if max_points is not None and n_points > max_points:
        raise ValidationError(f"Contour has {n_points} points, maximum allowed: {max_points}")
    
    # Check area
    try:
        area = cv2.contourArea(contour)
    except cv2.error as e:
        raise ValidationError(f"Cannot calculate contour area: {e}")
    
    if area < min_area:
        raise ValidationError(f"Contour area {area:.2f} is below minimum {min_area}")
    
    if max_area is not None and area > max_area:
        raise ValidationError(f"Contour area {area:.2f} is above maximum {max_area}")
    
    # Check for degenerate contours (all points the same)
    if np.all(contour == contour[0]):
        raise ValidationError("Contour has all identical points")
    
    # Check coordinate validity (no NaN or inf)
    if np.any(~np.isfinite(contour)):
        raise ValidationError("Contour contains NaN or infinite coordinates")
    
    return True


def validate_features(features: Union[List, np.ndarray],
                     expected_length: Optional[int] = None,
                     allow_nan: bool = False,
                     allow_inf: bool = False,
                     feature_names: Optional[List[str]] = None) -> bool:
    """
    Validate feature vector
    
    Args:
        features: Feature vector or list
        expected_length: Expected number of features
        allow_nan: Whether to allow NaN values
        allow_inf: Whether to allow infinite values
        feature_names: Names of features for detailed error messages
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    # Convert to numpy array if needed
    if isinstance(features, list):
        features = np.array(features)
    
    if not isinstance(features, np.ndarray):
        raise ValidationError(f"Features must be array or list, got {type(features)}")
    
    # Check dimensionality
    if features.ndim != 1:
        raise ValidationError(f"Features must be 1D array, got shape {features.shape}")
    
    # Check length
    if expected_length is not None and len(features) != expected_length:
        raise ValidationError(f"Expected {expected_length} features, got {len(features)}")
    
    # Check for NaN values
    nan_mask = np.isnan(features)
    if np.any(nan_mask) and not allow_nan:
        nan_indices = np.where(nan_mask)[0]
        if feature_names:
            nan_features = [feature_names[i] for i in nan_indices]
            raise ValidationError(f"NaN values found in features: {nan_features}")
        else:
            raise ValidationError(f"NaN values found at indices: {nan_indices.tolist()}")
    
    # Check for infinite values
    inf_mask = np.isinf(features)
    if np.any(inf_mask) and not allow_inf:
        inf_indices = np.where(inf_mask)[0]
        if feature_names:
            inf_features = [feature_names[i] for i in inf_indices]
            raise ValidationError(f"Infinite values found in features: {inf_features}")
        else:
            raise ValidationError(f"Infinite values found at indices: {inf_indices.tolist()}")
    
    return True


def validate_training_data(X: np.ndarray, 
                          y: np.ndarray,
                          min_samples: int = 10,
                          check_balance: bool = True,
                          balance_threshold: float = 0.1) -> bool:
    """
    Validate training data matrices
    
    Args:
        X: Feature matrix
        y: Label vector
        min_samples: Minimum number of samples required
        check_balance: Whether to check class balance
        balance_threshold: Maximum allowed imbalance ratio
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    # Check types
    if not isinstance(X, np.ndarray):
        raise ValidationError(f"X must be numpy array, got {type(X)}")
    if not isinstance(y, np.ndarray):
        raise ValidationError(f"y must be numpy array, got {type(y)}")
    
    # Check dimensions
    if X.ndim != 2:
        raise ValidationError(f"X must be 2D array, got shape {X.shape}")
    if y.ndim != 1:
        raise ValidationError(f"y must be 1D array, got shape {y.shape}")
    
    # Check matching sample sizes
    if X.shape[0] != len(y):
        raise ValidationError(f"X and y have different sample sizes: {X.shape[0]} vs {len(y)}")
    
    # Check minimum samples
    n_samples = X.shape[0]
    if n_samples < min_samples:
        raise ValidationError(f"Insufficient samples: {n_samples}, minimum required: {min_samples}")
    
    # Check for valid values
    if np.any(~np.isfinite(X)):
        raise ValidationError("X contains NaN or infinite values")
    
    # Check labels
    unique_labels = np.unique(y)
    if len(unique_labels) != 2:
        raise ValidationError(f"Expected binary labels, found {len(unique_labels)} classes: {unique_labels}")
    
    if not np.array_equal(unique_labels, [0, 1]):
        raise ValidationError(f"Labels must be 0 and 1, found: {unique_labels}")
    
    # Check class balance
    if check_balance:
        class_counts = np.bincount(y)
        minority_ratio = min(class_counts) / max(class_counts)
        
        if minority_ratio < balance_threshold:
            raise ValidationError(
                f"Severe class imbalance detected. "
                f"Minority class ratio: {minority_ratio:.3f}, "
                f"threshold: {balance_threshold}. "
                f"Class counts: {class_counts}"
            )
    
    return True


def validate_model_predictions(predictions: np.ndarray,
                             probabilities: Optional[np.ndarray] = None,
                             expected_classes: Tuple[int, ...] = (0, 1)) -> bool:
    """
    Validate model predictions and probabilities
    
    Args:
        predictions: Predicted class labels
        probabilities: Predicted probabilities (optional)
        expected_classes: Expected class labels
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    # Check predictions
    if not isinstance(predictions, np.ndarray):
        raise ValidationError(f"Predictions must be numpy array, got {type(predictions)}")
    
    if predictions.ndim != 1:
        raise ValidationError(f"Predictions must be 1D array, got shape {predictions.shape}")
    
    # Check prediction values
    unique_preds = np.unique(predictions)
    for pred in unique_preds:
        if pred not in expected_classes:
            raise ValidationError(f"Invalid prediction value: {pred}, expected one of {expected_classes}")
    
    # Check probabilities if provided
    if probabilities is not None:
        if not isinstance(probabilities, np.ndarray):
            raise ValidationError(f"Probabilities must be numpy array, got {type(probabilities)}")
        
        # Check shapes match
        if probabilities.ndim == 1:
            # Single class probabilities
            if len(probabilities) != len(predictions):
                raise ValidationError(f"Probability and prediction lengths don't match: {len(probabilities)} vs {len(predictions)}")
            
            # Check probability range
            if np.any((probabilities < 0) | (probabilities > 1)):
                raise ValidationError("Probabilities must be between 0 and 1")
                
        elif probabilities.ndim == 2:
            # Multi-class probabilities
            if probabilities.shape[0] != len(predictions):
                raise ValidationError(f"Probability and prediction sample counts don't match: {probabilities.shape[0]} vs {len(predictions)}")
            
            if probabilities.shape[1] != len(expected_classes):
                raise ValidationError(f"Probability classes don't match expected: {probabilities.shape[1]} vs {len(expected_classes)}")
            
            # Check probability range and sum
            if np.any((probabilities < 0) | (probabilities > 1)):
                raise ValidationError("Probabilities must be between 0 and 1")
            
            prob_sums = np.sum(probabilities, axis=1)
            if not np.allclose(prob_sums, 1.0, atol=1e-6):
                raise ValidationError("Probability rows must sum to 1.0")
        
        else:
            raise ValidationError(f"Probabilities must be 1D or 2D array, got shape {probabilities.shape}")
    
    return True


def validate_config(config_dict: Dict[str, Any],
                   required_keys: List[str],
                   optional_keys: Optional[List[str]] = None) -> bool:
    """
    Validate configuration dictionary
    
    Args:
        config_dict: Configuration dictionary to validate
        required_keys: List of required keys
        optional_keys: List of optional keys (default: allow any)
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(config_dict, dict):
        raise ValidationError(f"Config must be dictionary, got {type(config_dict)}")
    
    # Check required keys
    missing_keys = []
    for key in required_keys:
        if key not in config_dict:
            missing_keys.append(key)
    
    if missing_keys:
        raise ValidationError(f"Missing required configuration keys: {missing_keys}")
    
    # Check for unexpected keys if optional_keys is specified
    if optional_keys is not None:
        allowed_keys = set(required_keys + optional_keys)
        unexpected_keys = set(config_dict.keys()) - allowed_keys
        
        if unexpected_keys:
            raise ValidationError(f"Unexpected configuration keys: {list(unexpected_keys)}")
    
    return True


def validate_file_path(filepath: Union[str, Path],
                      must_exist: bool = True,
                      must_be_file: bool = True,
                      allowed_extensions: Optional[List[str]] = None) -> bool:
    """
    Validate file path
    
    Args:
        filepath: Path to validate
        must_exist: Whether file must exist
        must_be_file: Whether path must be a file (not directory)
        allowed_extensions: List of allowed file extensions (e.g., ['.pkl', '.json'])
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    filepath = Path(filepath)
    
    # Check existence
    if must_exist and not filepath.exists():
        raise ValidationError(f"File does not exist: {filepath}")
    
    # Check if it's a file
    if filepath.exists() and must_be_file and not filepath.is_file():
        raise ValidationError(f"Path is not a file: {filepath}")
    
    # Check extension
    if allowed_extensions is not None:
        extension = filepath.suffix.lower()
        if extension not in [ext.lower() for ext in allowed_extensions]:
            raise ValidationError(f"Invalid file extension '{extension}', allowed: {allowed_extensions}")
    
    return True


def validate_dataset_pairs(pairs: List[Tuple],
                          labels: List[int],
                          min_pairs: int = 10) -> bool:
    """
    Validate dataset pairs and labels
    
    Args:
        pairs: List of (contour1, contour2) tuples
        labels: List of corresponding labels
        min_pairs: Minimum number of pairs required
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    # Check types
    if not isinstance(pairs, list):
        raise ValidationError(f"Pairs must be a list, got {type(pairs)}")
    if not isinstance(labels, list):
        raise ValidationError(f"Labels must be a list, got {type(labels)}")
    
    # Check lengths match
    if len(pairs) != len(labels):
        raise ValidationError(f"Number of pairs ({len(pairs)}) doesn't match number of labels ({len(labels)})")
    
    # Check minimum count
    if len(pairs) < min_pairs:
        raise ValidationError(f"Insufficient pairs: {len(pairs)}, minimum required: {min_pairs}")
    
    # Validate each pair
    for i, (pair, label) in enumerate(zip(pairs, labels)):
        # Check pair structure
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValidationError(f"Pair {i} must be a tuple/list of 2 contours, got {type(pair)} with length {len(pair) if hasattr(pair, '__len__') else 'unknown'}")
        
        # Validate contours in pair
        contour1, contour2 = pair
        try:
            validate_contour(contour1)
            validate_contour(contour2)
        except ValidationError as e:
            raise ValidationError(f"Invalid contour in pair {i}: {e}")
        
        # Check label
        if label not in [0, 1]:
            raise ValidationError(f"Invalid label at index {i}: {label}, must be 0 or 1")
    
    return True


def validate_feature_matrix_consistency(feature_matrices: List[np.ndarray],
                                      tolerance: float = 1e-6) -> bool:
    """
    Validate that feature matrices have consistent dimensions and reasonable values
    
    Args:
        feature_matrices: List of feature matrices to compare
        tolerance: Tolerance for numerical comparisons
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if len(feature_matrices) < 2:
        return True  # Nothing to compare
    
    # Check all matrices have same number of features
    n_features = feature_matrices[0].shape[1]
    for i, matrix in enumerate(feature_matrices[1:], 1):
        if matrix.shape[1] != n_features:
            raise ValidationError(
                f"Feature matrix {i} has {matrix.shape[1]} features, "
                f"expected {n_features} (from matrix 0)"
            )
    
    # Check for consistent value ranges across matrices
    for feature_idx in range(n_features):
        feature_values = []
        for matrix in feature_matrices:
            feature_values.extend(matrix[:, feature_idx].tolist())
        
        feature_array = np.array(feature_values)
        
        # Check for extreme outliers (values more than 1000 times the median absolute deviation)
        median = np.median(feature_array)
        mad = np.median(np.abs(feature_array - median))
        
        if mad > 0:  # Avoid division by zero
            outliers = np.abs(feature_array - median) > 1000 * mad
            if np.any(outliers):
                n_outliers = np.sum(outliers)
                raise ValidationError(
                    f"Feature {feature_idx} has {n_outliers} extreme outliers "
                    f"(>1000 MAD from median). This suggests feature extraction issues."
                )
    
    return True