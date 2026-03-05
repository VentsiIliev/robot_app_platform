"""
Visualization Utilities Module

Provides plotting and visualization functions for model evaluation,
training progress, and result analysis.
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd


def plot_confusion_matrix(y_true: List[int], 
                         y_pred: List[int], 
                         model_name: str = "Model",
                         normalize: bool = False,
                         save_path: Optional[str] = None,
                         show_plot: bool = True) -> plt.Figure:
    """
    Create an enhanced confusion matrix visualization
    
    Args:
        y_true: True labels
        y_pred: Predicted labels  
        model_name: Name of the model for title
        normalize: Whether to normalize the confusion matrix
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    cm = confusion_matrix(y_true, y_pred)
    
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        fmt = '.2%'
        title_suffix = ' (Normalized)'
    else:
        fmt = 'd'
        title_suffix = ''
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Create heatmap
    sns.heatmap(cm, annot=True, fmt=fmt, cmap='Blues', ax=ax,
                xticklabels=['Different', 'Same'],
                yticklabels=['Different', 'Same'])
    
    ax.set_title(f'Confusion Matrix - {model_name}{title_suffix}', fontsize=16, fontweight='bold')
    ax.set_xlabel('Predicted Label', fontsize=14)
    ax.set_ylabel('True Label', fontsize=14)
    
    # Add descriptive text in each cell
    if not normalize:
        labels = [["True Negatives\\n(Correctly Different)", "False Positives\\n(Wrong: Called Same)"],
                  ["False Negatives\\n(Wrong: Called Different)", "True Positives\\n(Correctly Same)"]]
        
        total_samples = np.sum(cm)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                count = cm[i, j]
                percentage = (count / total_samples) * 100
                ax.text(j + 0.5, i + 0.7, f'({percentage:.1f}%)', 
                       ha='center', va='center', color='red', fontsize=10, fontweight='bold')
                ax.text(j + 0.5, i + 0.3, labels[i][j], 
                       ha='center', va='center', color='darkblue', fontsize=9)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig


def plot_feature_importance(feature_importances: np.ndarray,
                          feature_names: List[str],
                          model_name: str = "Model",
                          top_k: int = 15,
                          save_path: Optional[str] = None,
                          show_plot: bool = True) -> plt.Figure:
    """
    Plot feature importance ranking
    
    Args:
        feature_importances: Array of feature importance values
        feature_names: List of feature names
        model_name: Name of the model for title
        top_k: Number of top features to display
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    # Sort features by importance
    indices = np.argsort(feature_importances)[::-1][:top_k]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create horizontal bar plot
    y_pos = np.arange(len(indices))
    bars = ax.barh(y_pos, feature_importances[indices], color='skyblue', edgecolor='navy', alpha=0.7)
    
    # Customize plot
    ax.set_yticks(y_pos)
    ax.set_yticklabels([feature_names[i] for i in indices])
    ax.invert_yaxis()  # Most important at top
    ax.set_xlabel('Feature Importance', fontsize=12)
    ax.set_title(f'Top {top_k} Feature Importance - {model_name}', fontsize=14, fontweight='bold')
    
    # Add value labels on bars
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width + 0.001, bar.get_y() + bar.get_height()/2,
                f'{width:.3f}', ha='left', va='center', fontsize=10)
    
    # Add grid for easier reading
    ax.grid(True, axis='x', alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig


def plot_model_comparison(results: Dict[str, Dict[str, Any]],
                         metric: str = 'accuracy',
                         save_path: Optional[str] = None,
                         show_plot: bool = True) -> plt.Figure:
    """
    Create comparison plot of multiple models
    
    Args:
        results: Dictionary of model results with metrics
        metric: Metric to compare (e.g., 'accuracy', 'f1_score')
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    model_names = list(results.keys())
    metric_values = [results[name].get(metric, 0) for name in model_names]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Create bar plot with different colors
    colors = plt.cm.Set3(np.linspace(0, 1, len(model_names)))
    bars = ax.bar(model_names, metric_values, color=colors, edgecolor='black', alpha=0.8)
    
    # Customize plot
    ax.set_title(f'Model Performance Comparison - {metric.title()}', fontsize=16, fontweight='bold')
    ax.set_ylabel(metric.title(), fontsize=12)
    
    # Set y-axis limits for better visualization
    if metric == 'accuracy':
        ax.set_ylim(0.85, 1.0)
    
    # Add value labels on bars
    for bar, value in zip(bars, metric_values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.001,
                f'{value:.3f}', ha='center', va='bottom', fontweight='bold', fontsize=11)
    
    # Rotate x-axis labels if needed
    if len(max(model_names, key=len)) > 10:
        plt.xticks(rotation=45, ha='right')
    
    # Add grid
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig


def plot_training_history(history: Dict[str, List[float]],
                         save_path: Optional[str] = None,
                         show_plot: bool = True) -> plt.Figure:
    """
    Plot training history (loss, accuracy over epochs)
    
    Args:
        history: Dictionary with training history data
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    
    epochs = range(1, len(history['loss']) + 1)
    
    # Plot training & validation loss
    axes[0].plot(epochs, history['loss'], 'b-', label='Training Loss', linewidth=2)
    if 'val_loss' in history:
        axes[0].plot(epochs, history['val_loss'], 'r-', label='Validation Loss', linewidth=2)
    axes[0].set_title('Model Loss', fontsize=14, fontweight='bold')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Plot training & validation accuracy
    if 'accuracy' in history:
        axes[1].plot(epochs, history['accuracy'], 'b-', label='Training Accuracy', linewidth=2)
    if 'val_accuracy' in history:
        axes[1].plot(epochs, history['val_accuracy'], 'r-', label='Validation Accuracy', linewidth=2)
    axes[1].set_title('Model Accuracy', fontsize=14, fontweight='bold')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Accuracy')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig


def plot_prediction_confidence_distribution(confidences: List[float],
                                           predictions: List[int],
                                           save_path: Optional[str] = None,
                                           show_plot: bool = True) -> plt.Figure:
    """
    Plot distribution of prediction confidences
    
    Args:
        confidences: List of confidence scores
        predictions: List of predictions (0/1)
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    
    # Overall confidence distribution
    axes[0].hist(confidences, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
    axes[0].axvline(np.mean(confidences), color='red', linestyle='--', 
                    label=f'Mean: {np.mean(confidences):.3f}')
    axes[0].set_title('Prediction Confidence Distribution', fontsize=14, fontweight='bold')
    axes[0].set_xlabel('Confidence Score')
    axes[0].set_ylabel('Frequency')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Confidence by prediction class
    conf_different = [conf for conf, pred in zip(confidences, predictions) if pred == 0]
    conf_same = [conf for conf, pred in zip(confidences, predictions) if pred == 1]
    
    axes[1].hist(conf_different, bins=20, alpha=0.7, color='lightcoral', 
                label=f'Different (n={len(conf_different)})', edgecolor='black')
    axes[1].hist(conf_same, bins=20, alpha=0.7, color='lightgreen',
                label=f'Same (n={len(conf_same)})', edgecolor='black')
    axes[1].set_title('Confidence Distribution by Prediction Class', fontsize=14, fontweight='bold')
    axes[1].set_xlabel('Confidence Score')
    axes[1].set_ylabel('Frequency')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig


def create_classification_report_plot(y_true: List[int],
                                     y_pred: List[int],
                                     model_name: str = "Model",
                                     save_path: Optional[str] = None,
                                     show_plot: bool = True) -> plt.Figure:
    """
    Create a visual classification report
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        model_name: Name of the model
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    # Get classification report as dict
    report = classification_report(y_true, y_pred, output_dict=True,
                                 target_names=['Different', 'Same'])
    
    # Convert to DataFrame for easier plotting
    df = pd.DataFrame(report).transpose()
    
    # Remove support column and accuracy row for heatmap
    df_heatmap = df.iloc[:-3, :-1]  # Remove macro avg, weighted avg, accuracy rows and support column
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Heatmap of precision, recall, f1-score
    sns.heatmap(df_heatmap, annot=True, cmap='Blues', ax=ax1, cbar_kws={'label': 'Score'})
    ax1.set_title(f'Classification Metrics - {model_name}', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Metrics')
    ax1.set_ylabel('Classes')
    
    # Bar plot of overall metrics
    metrics = ['precision', 'recall', 'f1-score']
    macro_avg_values = [df.loc['macro avg', metric] for metric in metrics]
    
    bars = ax2.bar(metrics, macro_avg_values, color=['lightblue', 'lightgreen', 'lightcoral'])
    ax2.set_title(f'Macro Average Metrics - {model_name}', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Score')
    ax2.set_ylim(0, 1.1)
    
    # Add value labels on bars
    for bar, value in zip(bars, macro_avg_values):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{value:.3f}', ha='center', va='bottom', fontweight='bold')
    
    # Add accuracy as text
    accuracy = df.loc['accuracy', 'precision']  # Accuracy is stored in precision column
    ax2.text(0.5, 0.95, f'Accuracy: {accuracy:.3f}', 
             transform=ax2.transAxes, ha='center', va='top',
             bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7),
             fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig


def visualize_training_results(results: Dict[str, Dict[str, Any]], 
                              save_dir: Optional[str] = None) -> Dict[str, plt.Figure]:
    """
    Create comprehensive visualization of training results
    
    Args:
        results: Training results from all models
        save_dir: Optional directory to save plots
        
    Returns:
        Dictionary of created figure objects
    """
    figures = {}
    
    # Model comparison plot
    figures['comparison'] = plot_model_comparison(
        results, 
        save_path=f"{save_dir}/model_comparison.png" if save_dir else None,
        show_plot=bool(save_dir is None)
    )
    
    # Individual model analysis
    for model_name, model_results in results.items():
        if 'test_data' in model_results and 'predictions' in model_results:
            y_true, y_test = model_results['test_data']
            y_pred = model_results['predictions']
            
            # Confusion matrix
            figures[f'{model_name}_confusion'] = plot_confusion_matrix(
                y_true, y_pred, model_name,
                save_path=f"{save_dir}/{model_name}_confusion_matrix.png" if save_dir else None,
                show_plot=bool(save_dir is None)
            )
            
            # Classification report
            figures[f'{model_name}_classification'] = create_classification_report_plot(
                y_true, y_pred, model_name,
                save_path=f"{save_dir}/{model_name}_classification_report.png" if save_dir else None,
                show_plot=bool(save_dir is None)
            )
            
            # Feature importance (if available)
            model = model_results.get('model')
            if hasattr(model, 'feature_importances_'):
                # This would need feature names from the feature extractor
                feature_names = [f'feature_{i}' for i in range(len(model.feature_importances_))]
                figures[f'{model_name}_importance'] = plot_feature_importance(
                    model.feature_importances_, feature_names, model_name,
                    save_path=f"{save_dir}/{model_name}_feature_importance.png" if save_dir else None,
                    show_plot=bool(save_dir is None)
                )
    
    return figures


def create_shape_similarity_showcase(contour_pairs: List[Tuple],
                                   predictions: List[str],
                                   confidences: List[float],
                                   n_examples: int = 6,
                                   save_path: Optional[str] = None,
                                   show_plot: bool = True) -> plt.Figure:
    """
    Create a showcase of shape similarity predictions
    
    Args:
        contour_pairs: List of (contour1, contour2) tuples
        predictions: List of prediction strings ('SAME', 'DIFFERENT')
        confidences: List of confidence scores
        n_examples: Number of examples to show
        save_path: Optional path to save the plot
        show_plot: Whether to display the plot
        
    Returns:
        Matplotlib figure object
    """
    import cv2
    
    n_examples = min(n_examples, len(contour_pairs))
    
    fig, axes = plt.subplots(2, n_examples, figsize=(3*n_examples, 6))
    if n_examples == 1:
        axes = axes.reshape(2, 1)
    
    for i in range(n_examples):
        contour1, contour2 = contour_pairs[i]
        prediction = predictions[i]
        confidence = confidences[i]
        
        # Create images from contours
        img1 = np.zeros((200, 200), dtype=np.uint8)
        img2 = np.zeros((200, 200), dtype=np.uint8)
        
        cv2.drawContours(img1, [contour1], -1, 255, -1)
        cv2.drawContours(img2, [contour2], -1, 255, -1)
        
        # Plot contours
        axes[0, i].imshow(img1, cmap='gray')
        axes[0, i].set_title(f'Shape 1', fontsize=10)
        axes[0, i].axis('off')
        
        axes[1, i].imshow(img2, cmap='gray')
        axes[1, i].set_title(f'Shape 2', fontsize=10)
        axes[1, i].axis('off')
        
        # Add prediction info
        color = 'green' if prediction == 'SAME' else 'red'
        fig.text(0.1 + i*0.8/n_examples, 0.02, f'{prediction}\\n{confidence:.2f}',
                ha='center', va='bottom', color=color, fontweight='bold')
    
    plt.suptitle('Shape Similarity Prediction Examples', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    if show_plot:
        plt.show()
    
    return fig