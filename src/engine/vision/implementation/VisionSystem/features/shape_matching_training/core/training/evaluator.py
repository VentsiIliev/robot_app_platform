"""
Model Evaluator Module

Provides comprehensive evaluation capabilities for trained models including
performance metrics, statistical tests, and comparative analysis.
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import confusion_matrix, roc_curve, precision_recall_curve

from ..models.base_model import BaseModel
from ...utils.metrics import (
    calculate_similarity_metrics, 
    calculate_confidence_metrics,
    perform_statistical_tests,
    analyze_error_patterns
)
from ...utils.visualization import (
    plot_confusion_matrix,
    plot_feature_importance, 
    create_classification_report_plot,
    plot_prediction_confidence_distribution
)


class ModelEvaluator:
    """
    Comprehensive model evaluation with statistical analysis and visualization
    """
    
    def __init__(self, save_visualizations: bool = True, output_dir: Optional[str] = None):
        """
        Initialize model evaluator
        
        Args:
            save_visualizations: Whether to save visualization plots
            output_dir: Directory to save outputs (optional)
        """
        self.save_visualizations = save_visualizations
        self.output_dir = output_dir
        self.evaluation_history = []
    
    def evaluate_single_model(self, 
                             model: BaseModel,
                             X_test: np.ndarray,
                             y_test: np.ndarray,
                             model_name: str = "Model") -> Dict[str, Any]:
        """
        Comprehensive evaluation of a single model
        
        Args:
            model: Trained model to evaluate
            X_test: Test features
            y_test: Test labels
            model_name: Name for the model
            
        Returns:
            Comprehensive evaluation results
        """
        if not model.is_fitted:
            raise ValueError("Model must be fitted before evaluation")
        
        print(f"🔍 Evaluating {model_name}...")
        
        # Basic predictions
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)
        y_proba_pos = y_proba[:, 1] if y_proba.shape[1] > 1 else y_proba.flatten()
        
        # Convert to numpy arrays if needed, then to lists
        y_test_list = np.array(y_test).tolist() if not isinstance(y_test, list) else y_test
        y_pred_list = np.array(y_pred).tolist() if not isinstance(y_pred, list) else y_pred
        y_proba_pos_list = np.array(y_proba_pos).tolist() if not isinstance(y_proba_pos, list) else y_proba_pos

        # Calculate comprehensive metrics
        metrics = calculate_similarity_metrics(y_test_list, y_pred_list, y_proba_pos_list)

        # Confidence analysis
        confidences = np.max(y_proba, axis=1)
        confidence_list = np.array(confidences).tolist() if not isinstance(confidences, list) else confidences
        confidence_metrics = calculate_confidence_metrics(
            confidence_list, y_pred_list, y_test_list
        )
        
        # Error pattern analysis
        feature_names = model.feature_names if hasattr(model, 'feature_names') and model.feature_names else None
        error_analysis = analyze_error_patterns(y_test, y_pred, X_test, feature_names or [f"feature_{i}" for i in range(X_test.shape[1])])
        
        # Confusion matrix analysis
        cm = confusion_matrix(y_test, y_pred)
        
        # Compile results
        results = {
            'model_name': model_name,
            'model_info': model.get_model_info(),
            'predictions': {
                'y_pred': y_pred,
                'y_proba': y_proba,
                'y_proba_pos': y_proba_pos,
                'confidences': confidences
            },
            'metrics': {
                'performance': metrics,
                'confidence': confidence_metrics
            },
            'confusion_matrix': cm,
            'error_analysis': error_analysis,
            'feature_importance': model.get_feature_importance()
        }
        
        # Generate visualizations if requested
        if self.save_visualizations:
            results['visualizations'] = self._create_visualizations(
                model, results, X_test, y_test, model_name
            )
        
        # Store in history
        self.evaluation_history.append(results)
        
        print(f"✅ {model_name} evaluation complete")
        print(f"   Accuracy: {metrics['accuracy']:.3f}")
        print(f"   Precision: {metrics['precision']:.3f}")
        print(f"   Recall: {metrics['recall']:.3f}")
        print(f"   F1-Score: {metrics['f1_score']:.3f}")
        
        return results
    
    def cross_validate_model(self, 
                           model: BaseModel,
                           X: np.ndarray,
                           y: np.ndarray,
                           cv_folds: int = 5,
                           scoring: List[str] = None) -> Dict[str, Any]:
        """
        Perform cross-validation evaluation
        
        Args:
            model: Model to evaluate (will be cloned for each fold)
            X: Features
            y: Labels
            cv_folds: Number of CV folds
            scoring: List of scoring metrics
            
        Returns:
            Cross-validation results
        """
        print(f"🔄 Performing {cv_folds}-fold cross-validation...")
        
        if scoring is None:
            scoring = ['accuracy', 'precision', 'recall', 'f1']
        
        cv_results = {}
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
        
        # Calculate scores for each metric
        for metric in scoring:
            try:
                scores = cross_val_score(model._model, X, y, cv=cv, scoring=metric)
                cv_results[metric] = {
                    'scores': scores.tolist(),
                    'mean': scores.mean(),
                    'std': scores.std(),
                    'min': scores.min(),
                    'max': scores.max()
                }
                
                print(f"   {metric.capitalize()}: {scores.mean():.3f} ± {scores.std():.3f}")
                
            except Exception as e:
                print(f"   Warning: Could not calculate {metric}: {e}")
                cv_results[metric] = None
        
        # Overall summary
        cv_results['summary'] = {
            'cv_folds': cv_folds,
            'total_samples': len(X),
            'samples_per_fold': len(X) // cv_folds
        }
        
        return cv_results
    
    def compare_models(self, 
                      model_results: Dict[str, Dict[str, Any]],
                      comparison_metrics: List[str] = None) -> Dict[str, Any]:
        """
        Compare multiple model evaluation results
        
        Args:
            model_results: Dictionary of model evaluation results
            comparison_metrics: Metrics to compare (default: main metrics)
            
        Returns:
            Comparison analysis results
        """
        if not model_results:
            raise ValueError("No model results provided for comparison")
        
        print(f"📊 Comparing {len(model_results)} models...")
        
        if comparison_metrics is None:
            comparison_metrics = ['accuracy', 'precision', 'recall', 'f1_score', 'roc_auc']
        
        comparison = {
            'model_names': list(model_results.keys()),
            'metric_comparison': {},
            'rankings': {},
            'statistical_tests': {},
            'best_model': None
        }
        
        # Extract metrics for comparison
        for metric in comparison_metrics:
            metric_values = {}
            for model_name, results in model_results.items():
                if metric in results['metrics']['performance']:
                    metric_values[model_name] = results['metrics']['performance'][metric]
            
            if metric_values:
                comparison['metric_comparison'][metric] = metric_values
                # Rank models by this metric
                ranked_models = sorted(metric_values.items(), key=lambda x: x[1], reverse=True)
                comparison['rankings'][metric] = ranked_models
        
        # Determine overall best model (by accuracy)
        if 'accuracy' in comparison['metric_comparison']:
            best_model_name = comparison['rankings']['accuracy'][0][0]
            best_accuracy = comparison['rankings']['accuracy'][0][1]
            comparison['best_model'] = {
                'name': best_model_name,
                'accuracy': best_accuracy
            }
            print(f"🏆 Best model: {best_model_name} (Accuracy: {best_accuracy:.3f})")
        
        # Statistical significance tests between models
        comparison['statistical_tests'] = self._perform_model_comparisons(model_results)
        
        # Generate comparison visualizations
        if self.save_visualizations:
            comparison['visualizations'] = self._create_comparison_visualizations(model_results)
        
        return comparison
    
    def evaluate_model_robustness(self, 
                                model: BaseModel,
                                X_test: np.ndarray,
                                y_test: np.ndarray,
                                noise_levels: List[float] = None) -> Dict[str, Any]:
        """
        Evaluate model robustness to input noise
        
        Args:
            model: Trained model
            X_test: Clean test data
            y_test: Test labels
            noise_levels: Levels of Gaussian noise to test
            
        Returns:
            Robustness evaluation results
        """
        if noise_levels is None:
            noise_levels = [0.0, 0.1, 0.2, 0.5, 1.0]
        
        print(f"🧪 Testing model robustness with {len(noise_levels)} noise levels...")
        
        robustness_results = {
            'noise_levels': noise_levels,
            'performance_degradation': {},
            'robustness_score': None
        }
        
        baseline_accuracy = None
        
        for noise_level in noise_levels:
            # Add noise to features
            if noise_level == 0.0:
                X_noisy = X_test
            else:
                noise = np.random.normal(0, noise_level, X_test.shape)
                X_noisy = X_test + noise
            
            # Evaluate with noisy data
            try:
                y_pred_noisy = model.predict(X_noisy)
                y_proba_noisy = model.predict_proba(X_noisy)
                
                metrics = calculate_similarity_metrics(
                    y_test.tolist(), y_pred_noisy.tolist(), 
                    y_proba_noisy[:, 1].tolist() if y_proba_noisy.shape[1] > 1 else y_proba_noisy.flatten().tolist()
                )
                
                robustness_results['performance_degradation'][noise_level] = metrics
                
                if noise_level == 0.0:
                    baseline_accuracy = metrics['accuracy']
                
                print(f"   Noise {noise_level:.1f}: Accuracy = {metrics['accuracy']:.3f}")
                
            except Exception as e:
                print(f"   Warning: Failed at noise level {noise_level}: {e}")
                robustness_results['performance_degradation'][noise_level] = None
        
        # Calculate robustness score (average relative performance)
        if baseline_accuracy is not None:
            relative_performances = []
            for noise_level, metrics in robustness_results['performance_degradation'].items():
                if metrics is not None and noise_level > 0:
                    relative_perf = metrics['accuracy'] / baseline_accuracy
                    relative_performances.append(relative_perf)
            
            if relative_performances:
                robustness_results['robustness_score'] = np.mean(relative_performances)
                print(f"🛡️ Robustness score: {robustness_results['robustness_score']:.3f}")
        
        return robustness_results
    
    def _create_visualizations(self, 
                             model: BaseModel,
                             results: Dict[str, Any],
                             X_test: np.ndarray,
                             y_test: np.ndarray,
                             model_name: str) -> Dict[str, str]:
        """Create evaluation visualizations"""
        visualizations = {}
        
        try:
            # Confusion matrix
            save_path = f"{self.output_dir}/{model_name}_confusion_matrix.png" if self.output_dir else None
            visualizations['confusion_matrix'] = plot_confusion_matrix(
                y_test, results['predictions']['y_pred'], model_name, 
                save_path=save_path, show_plot=False
            )
            
            # Classification report
            save_path = f"{self.output_dir}/{model_name}_classification_report.png" if self.output_dir else None
            visualizations['classification_report'] = create_classification_report_plot(
                y_test, results['predictions']['y_pred'], model_name,
                save_path=save_path, show_plot=False
            )
            
            # Feature importance (if available)
            if results['feature_importance'] is not None:
                feature_names = model.feature_names if hasattr(model, 'feature_names') and model.feature_names else None
                if feature_names:
                    save_path = f"{self.output_dir}/{model_name}_feature_importance.png" if self.output_dir else None
                    visualizations['feature_importance'] = plot_feature_importance(
                        results['feature_importance'], feature_names, model_name,
                        save_path=save_path, show_plot=False
                    )
            
            # Confidence distribution
            save_path = f"{self.output_dir}/{model_name}_confidence_distribution.png" if self.output_dir else None
            visualizations['confidence_distribution'] = plot_prediction_confidence_distribution(
                results['predictions']['confidences'].tolist(),
                results['predictions']['y_pred'].tolist(),
                save_path=save_path, show_plot=False
            )
            
        except Exception as e:
            print(f"Warning: Could not create some visualizations: {e}")
        
        return visualizations
    
    def _create_comparison_visualizations(self, model_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Create model comparison visualizations"""
        from ...utils.visualization import plot_model_comparison
        
        visualizations = {}
        
        try:
            # Performance comparison
            performance_data = {}
            for model_name, results in model_results.items():
                performance_data[model_name] = results['metrics']['performance']
            
            save_path = f"{self.output_dir}/model_comparison.png" if self.output_dir else None
            visualizations['performance_comparison'] = plot_model_comparison(
                performance_data, save_path=save_path, show_plot=False
            )
            
        except Exception as e:
            print(f"Warning: Could not create comparison visualizations: {e}")
        
        return visualizations
    
    def _perform_model_comparisons(self, model_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Perform statistical tests between models"""
        statistical_tests = {}
        
        model_names = list(model_results.keys())
        
        # Pairwise comparisons
        for i, name1 in enumerate(model_names):
            for name2 in model_names[i+1:]:
                try:
                    results1 = model_results[name1]
                    results2 = model_results[name2]
                    
                    # Perform statistical tests
                    tests = perform_statistical_tests(results1, results2)
                    
                    comparison_key = f"{name1}_vs_{name2}"
                    statistical_tests[comparison_key] = tests
                    
                except Exception as e:
                    print(f"Warning: Could not compare {name1} vs {name2}: {e}")
        
        return statistical_tests
    
    def generate_evaluation_report(self, 
                                 evaluation_results: Union[Dict[str, Any], List[Dict[str, Any]]],
                                 report_title: str = "Model Evaluation Report") -> str:
        """
        Generate a comprehensive evaluation report
        
        Args:
            evaluation_results: Single or multiple evaluation results
            report_title: Title for the report
            
        Returns:
            Formatted report string
        """
        report_lines = []
        report_lines.append("=" * len(report_title))
        report_lines.append(report_title)
        report_lines.append("=" * len(report_title))
        report_lines.append("")
        
        # Handle single or multiple results
        if isinstance(evaluation_results, dict):
            evaluation_results = [evaluation_results]
        
        for i, results in enumerate(evaluation_results):
            if i > 0:
                report_lines.append("\n" + "-" * 50 + "\n")
            
            model_name = results.get('model_name', f'Model_{i+1}')
            report_lines.append(f"Model: {model_name}")
            report_lines.append(f"Type: {results['model_info']['model_type']}")
            report_lines.append("")
            
            # Performance metrics
            metrics = results['metrics']['performance']
            report_lines.append("Performance Metrics:")
            report_lines.append(f"  Accuracy:  {metrics['accuracy']:.3f}")
            report_lines.append(f"  Precision: {metrics['precision']:.3f}")
            report_lines.append(f"  Recall:    {metrics['recall']:.3f}")
            report_lines.append(f"  F1-Score:  {metrics['f1_score']:.3f}")
            
            if 'roc_auc' in metrics:
                report_lines.append(f"  ROC AUC:   {metrics['roc_auc']:.3f}")
            
            # Confidence metrics
            if 'confidence' in results['metrics']:
                conf_metrics = results['metrics']['confidence']
                report_lines.append("")
                report_lines.append("Confidence Analysis:")
                report_lines.append(f"  Mean Confidence: {conf_metrics['mean_confidence']:.3f}")
                report_lines.append(f"  High Conf (>0.8): {conf_metrics['percent_above_0.8']:.1f}%")
            
            # Error analysis summary
            if 'error_analysis' in results:
                error_analysis = results['error_analysis']
                report_lines.append("")
                report_lines.append("Error Analysis:")
                report_lines.append(f"  False Positives: {error_analysis['false_positives']['count']} ({error_analysis['false_positives']['percentage']:.1f}%)")
                report_lines.append(f"  False Negatives: {error_analysis['false_negatives']['count']} ({error_analysis['false_negatives']['percentage']:.1f}%)")
        
        return "\n".join(report_lines)
    
    def export_results(self, results: Dict[str, Any], filepath: str):
        """Export evaluation results to file"""
        import json
        import pickle
        from pathlib import Path
        
        filepath = Path(filepath)
        
        # Prepare results for export (remove non-serializable items)
        export_data = results.copy()
        
        # Remove model object and other non-serializable items
        if 'model' in export_data:
            del export_data['model']
        
        # Convert numpy arrays to lists
        def convert_numpy(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            else:
                return obj
        
        export_data = convert_numpy(export_data)
        
        # Save based on file extension
        if filepath.suffix.lower() == '.json':
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
        else:
            # Default to pickle
            with open(filepath, 'wb') as f:
                pickle.dump(export_data, f)
        
        print(f"📄 Results exported to: {filepath}")

