"""
Metrics Utilities Module

Provides custom metrics and evaluation functions for shape similarity models,
including performance analysis and statistical tests.
"""

import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score, precision_recall_curve,
    classification_report
)
import scipy.stats as stats


def calculate_similarity_metrics(y_true: List[int], 
                               y_pred: List[int],
                               y_proba: Optional[List[float]] = None) -> Dict[str, float]:
    """
    Calculate comprehensive similarity metrics
    
    Args:
        y_true: True labels (0 for different, 1 for same)
        y_pred: Predicted labels
        y_proba: Predicted probabilities for positive class (optional)
        
    Returns:
        Dictionary of calculated metrics
    """
    metrics = {}
    
    # Basic classification metrics
    metrics['accuracy'] = accuracy_score(y_true, y_pred)
    metrics['precision'] = precision_score(y_true, y_pred)
    metrics['recall'] = recall_score(y_true, y_pred)
    metrics['f1_score'] = f1_score(y_true, y_pred)
    
    # Calculate per-class metrics
    precision_per_class = precision_score(y_true, y_pred, average=None)
    recall_per_class = recall_score(y_true, y_pred, average=None)
    f1_per_class = f1_score(y_true, y_pred, average=None)
    
    metrics['precision_different'] = precision_per_class[0]
    metrics['precision_same'] = precision_per_class[1]
    metrics['recall_different'] = recall_per_class[0]
    metrics['recall_same'] = recall_per_class[1]
    metrics['f1_different'] = f1_per_class[0]
    metrics['f1_same'] = f1_per_class[1]
    
    # Confusion matrix components
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    
    metrics['true_negatives'] = tn
    metrics['false_positives'] = fp
    metrics['false_negatives'] = fn
    metrics['true_positives'] = tp
    
    # Rates
    metrics['true_positive_rate'] = tp / (tp + fn) if (tp + fn) > 0 else 0
    metrics['true_negative_rate'] = tn / (tn + fp) if (tn + fp) > 0 else 0
    metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
    metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0
    
    # Additional metrics
    metrics['specificity'] = metrics['true_negative_rate']
    metrics['sensitivity'] = metrics['true_positive_rate']
    
    # Balanced accuracy (useful for imbalanced datasets)
    metrics['balanced_accuracy'] = (metrics['sensitivity'] + metrics['specificity']) / 2
    
    # Matthews Correlation Coefficient
    mcc_numerator = (tp * tn) - (fp * fn)
    mcc_denominator = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    metrics['mcc'] = mcc_numerator / mcc_denominator if mcc_denominator > 0 else 0
    
    # ROC AUC if probabilities are provided
    if y_proba is not None:
        metrics['roc_auc'] = roc_auc_score(y_true, y_proba)
        
        # Average precision (area under precision-recall curve)
        precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_proba)
        metrics['average_precision'] = np.trapz(precision_curve, recall_curve)
    
    return metrics


def evaluate_model_performance(model: Any,
                              X_test: np.ndarray,
                              y_test: List[int],
                              model_name: str = "Model") -> Dict[str, Any]:
    """
    Comprehensive model performance evaluation
    
    Args:
        model: Trained model with predict and predict_proba methods
        X_test: Test features
        y_test: Test labels
        model_name: Name of the model for reporting
        
    Returns:
        Dictionary with comprehensive evaluation results
    """
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Get probabilities if available
    y_proba = None
    if hasattr(model, 'predict_proba'):
        y_proba_full = model.predict_proba(X_test)
        y_proba = y_proba_full[:, 1]  # Probability of positive class
    
    # Calculate metrics
    metrics = calculate_similarity_metrics(y_test, y_pred, y_proba)
    
    # Add model-specific information
    results = {
        'model_name': model_name,
        'metrics': metrics,
        'predictions': y_pred.tolist(),
        'test_labels': y_test,
        'test_features': X_test
    }
    
    if y_proba is not None:
        results['probabilities'] = y_proba.tolist()
        results['max_probability'] = np.max(y_proba)
        results['min_probability'] = np.min(y_proba)
        results['mean_probability'] = np.mean(y_proba)
        results['std_probability'] = np.std(y_proba)
    
    return results


def calculate_confidence_metrics(confidences: List[float],
                               predictions: List[int],
                               true_labels: List[int]) -> Dict[str, float]:
    """
    Calculate metrics related to prediction confidence
    
    Args:
        confidences: List of confidence scores
        predictions: List of predicted labels
        true_labels: List of true labels
        
    Returns:
        Dictionary of confidence-related metrics
    """
    confidences = np.array(confidences)
    predictions = np.array(predictions)
    true_labels = np.array(true_labels)
    
    metrics = {}
    
    # Basic confidence statistics
    metrics['mean_confidence'] = np.mean(confidences)
    metrics['std_confidence'] = np.std(confidences)
    metrics['min_confidence'] = np.min(confidences)
    metrics['max_confidence'] = np.max(confidences)
    metrics['median_confidence'] = np.median(confidences)
    
    # Confidence by prediction class
    same_mask = predictions == 1
    different_mask = predictions == 0
    
    if np.any(same_mask):
        metrics['mean_confidence_same'] = np.mean(confidences[same_mask])
        metrics['std_confidence_same'] = np.std(confidences[same_mask])
    else:
        metrics['mean_confidence_same'] = 0
        metrics['std_confidence_same'] = 0
    
    if np.any(different_mask):
        metrics['mean_confidence_different'] = np.mean(confidences[different_mask])
        metrics['std_confidence_different'] = np.std(confidences[different_mask])
    else:
        metrics['mean_confidence_different'] = 0
        metrics['std_confidence_different'] = 0
    
    # Confidence by correctness
    correct_mask = predictions == true_labels
    incorrect_mask = predictions != true_labels
    
    if np.any(correct_mask):
        metrics['mean_confidence_correct'] = np.mean(confidences[correct_mask])
    else:
        metrics['mean_confidence_correct'] = 0
    
    if np.any(incorrect_mask):
        metrics['mean_confidence_incorrect'] = np.mean(confidences[incorrect_mask])
    else:
        metrics['mean_confidence_incorrect'] = 0
    
    # Confidence thresholds analysis
    for threshold in [0.7, 0.8, 0.9, 0.95]:
        high_conf_mask = confidences >= threshold
        n_high_conf = np.sum(high_conf_mask)
        
        metrics[f'count_above_{threshold}'] = n_high_conf
        metrics[f'percent_above_{threshold}'] = (n_high_conf / len(confidences)) * 100
        
        if n_high_conf > 0:
            high_conf_accuracy = np.mean(predictions[high_conf_mask] == true_labels[high_conf_mask])
            metrics[f'accuracy_above_{threshold}'] = high_conf_accuracy
        else:
            metrics[f'accuracy_above_{threshold}'] = 0
    
    return metrics


def perform_statistical_tests(results1: Dict[str, Any], 
                             results2: Dict[str, Any],
                             alpha: float = 0.05) -> Dict[str, Any]:
    """
    Perform statistical significance tests between two models
    
    Args:
        results1: Results from first model
        results2: Results from second model
        alpha: Significance level for tests
        
    Returns:
        Dictionary with statistical test results
    """
    # Extract predictions and true labels
    pred1 = np.array(results1['predictions'])
    pred2 = np.array(results2['predictions'])
    true_labels = np.array(results1['test_labels'])
    
    # Ensure same test set
    assert len(pred1) == len(pred2) == len(true_labels), "Results must be from same test set"
    
    tests = {}
    
    # McNemar's test for comparing two classifiers
    # Create contingency table: correct1_correct2, correct1_wrong2, wrong1_correct2, wrong1_wrong2
    correct1 = pred1 == true_labels
    correct2 = pred2 == true_labels
    
    both_correct = np.sum(correct1 & correct2)
    model1_only = np.sum(correct1 & ~correct2)
    model2_only = np.sum(~correct1 & correct2)
    both_wrong = np.sum(~correct1 & ~correct2)
    
    # McNemar's test
    if model1_only + model2_only > 0:
        mcnemar_statistic = ((model1_only - model2_only) ** 2) / (model1_only + model2_only)
        mcnemar_p_value = 1 - stats.chi2.cdf(mcnemar_statistic, 1)
        
        tests['mcnemar'] = {
            'statistic': mcnemar_statistic,
            'p_value': mcnemar_p_value,
            'significant': mcnemar_p_value < alpha,
            'model1_only_correct': model1_only,
            'model2_only_correct': model2_only,
            'both_correct': both_correct,
            'both_wrong': both_wrong
        }
    else:
        tests['mcnemar'] = {
            'statistic': 0,
            'p_value': 1.0,
            'significant': False,
            'note': 'No disagreement between models'
        }
    
    # Compare confidence distributions if available
    if 'probabilities' in results1 and 'probabilities' in results2:
        conf1 = np.array(results1['probabilities'])
        conf2 = np.array(results2['probabilities'])
        
        # Wilcoxon signed-rank test for confidence differences
        statistic, p_value = stats.wilcoxon(conf1, conf2)
        
        tests['confidence_comparison'] = {
            'statistic': statistic,
            'p_value': p_value,
            'significant': p_value < alpha,
            'test': 'Wilcoxon signed-rank test'
        }
    
    return tests


def analyze_error_patterns(y_true: List[int],
                          y_pred: List[int],
                          feature_matrix: np.ndarray,
                          feature_names: List[str]) -> Dict[str, Any]:
    """
    Analyze patterns in prediction errors
    
    Args:
        y_true: True labels
        y_pred: Predicted labels  
        feature_matrix: Feature matrix used for predictions
        feature_names: Names of features
        
    Returns:
        Dictionary with error analysis results
    """
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    # Find errors
    false_positive_mask = (y_true == 0) & (y_pred == 1)  # Predicted same, actually different
    false_negative_mask = (y_true == 1) & (y_pred == 0)  # Predicted different, actually same
    
    analysis = {
        'false_positives': {
            'count': np.sum(false_positive_mask),
            'percentage': np.mean(false_positive_mask) * 100
        },
        'false_negatives': {
            'count': np.sum(false_negative_mask),
            'percentage': np.mean(false_negative_mask) * 100
        }
    }
    
    # Analyze feature characteristics of errors
    if np.any(false_positive_mask):
        fp_features = feature_matrix[false_positive_mask]
        correct_features = feature_matrix[~(false_positive_mask | false_negative_mask)]
        
        # Compare feature distributions
        fp_analysis = {}
        for i, feature_name in enumerate(feature_names):
            fp_values = fp_features[:, i]
            correct_values = correct_features[:, i]
            
            # Statistical comparison
            if len(fp_values) > 1 and len(correct_values) > 1:
                statistic, p_value = stats.mannwhitneyu(fp_values, correct_values)
                fp_analysis[feature_name] = {
                    'fp_mean': np.mean(fp_values),
                    'correct_mean': np.mean(correct_values),
                    'difference': np.mean(fp_values) - np.mean(correct_values),
                    'p_value': p_value
                }
        
        analysis['false_positive_features'] = fp_analysis
    
    # Similar analysis for false negatives
    if np.any(false_negative_mask):
        fn_features = feature_matrix[false_negative_mask]
        correct_features = feature_matrix[~(false_positive_mask | false_negative_mask)]
        
        fn_analysis = {}
        for i, feature_name in enumerate(feature_names):
            fn_values = fn_features[:, i]
            correct_values = correct_features[:, i]
            
            if len(fn_values) > 1 and len(correct_values) > 1:
                statistic, p_value = stats.mannwhitneyu(fn_values, correct_values)
                fn_analysis[feature_name] = {
                    'fn_mean': np.mean(fn_values),
                    'correct_mean': np.mean(correct_values),
                    'difference': np.mean(fn_values) - np.mean(correct_values),
                    'p_value': p_value
                }
        
        analysis['false_negative_features'] = fn_analysis
    
    return analysis


def calculate_feature_stability(feature_matrices: List[np.ndarray],
                               feature_names: List[str]) -> Dict[str, float]:
    """
    Calculate stability of features across multiple runs or datasets
    
    Args:
        feature_matrices: List of feature matrices from different runs
        feature_names: Names of features
        
    Returns:
        Dictionary with stability metrics per feature
    """
    stability_metrics = {}
    
    n_matrices = len(feature_matrices)
    n_features = len(feature_names)
    
    for i, feature_name in enumerate(feature_names):
        # Extract feature values across all matrices
        feature_values = []
        for matrix in feature_matrices:
            feature_values.append(matrix[:, i])
        
        # Calculate coefficient of variation for each sample across runs
        feature_array = np.array(feature_values).T  # Shape: (n_samples, n_runs)
        
        # Calculate CV for each sample
        cvs = []
        for sample_values in feature_array:
            mean_val = np.mean(sample_values)
            std_val = np.std(sample_values)
            if mean_val != 0:
                cv = std_val / abs(mean_val)
            else:
                cv = 0 if std_val == 0 else np.inf
            cvs.append(cv)
        
        # Average CV across all samples for this feature
        stability_metrics[feature_name] = {
            'mean_cv': np.mean(cvs),
            'median_cv': np.median(cvs),
            'std_cv': np.std(cvs),
            'max_cv': np.max(cvs)
        }
    
    return stability_metrics