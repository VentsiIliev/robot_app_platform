#!/usr/bin/env python3
"""
Basic Usage Example

This example demonstrates the most common use cases for the shape matching
training module, including dataset generation, model training, and evaluation.
"""

import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split

from .. import DefaultTrainingConfig
from ..core.dataset.shape_factory import ShapeType, ShapeFactory
from ..core.features import GeometricFeatureExtractor, FourierFeatureExtractor
from ..core.features.moment_features import HuMomentExtractor
from ..core.models import SGDModel
from ..core.training.pipeline import quick_training_pipeline, TrainingPipeline
from ..utils import plot_confusion_matrix


def example_1_quick_start():
    """
    Example 1: Quick start with minimal configuration
    
    This is the fastest way to get started. The quick_training_pipeline
    function handles all the setup and provides reasonable defaults.
    """
    print("=" * 60)
    print("EXAMPLE 1: Quick Start")
    print("=" * 60)
    
    # Run a quick training pipeline with minimal configuration
    print("🚀 Starting quick training pipeline...")
    
    results = quick_training_pipeline(
        n_shapes=4,         # Use 4 different shape types
        enable_viz=False    # Disable visualizations for speed
    )
    
    # Display results
    pipeline_info = results['pipeline_info']
    dataset_info = results['dataset_info']
    
    print(f"✅ Training completed in {pipeline_info['total_time']:.1f} seconds")
    print(f"📊 Dataset: {dataset_info['total_contours']} contours, {dataset_info['total_pairs']:,} pairs")
    print(f"🏆 Best model: {pipeline_info['best_model']}")
    print(f"🎯 Best accuracy: {pipeline_info['best_accuracy']:.3f}")
    
    if results.get('best_model_path'):
        print(f"💾 Model saved to: {results['best_model_path']}")
    
    return results


def example_2_custom_configuration():
    """
    Example 2: Custom configuration and full pipeline
    
    This example shows how to create a custom training configuration
    and run the complete training pipeline.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Custom Configuration")
    print("=" * 60)
    
    # Create a custom training configuration
    config = DefaultTrainingConfig()
    
    # Customize dataset generation
    config.dataset.n_shapes = 6
    config.dataset.n_scales = 3
    config.dataset.n_variants = 4
    config.dataset.n_noisy = 3
    config.dataset.included_shapes = [
        ShapeType.CIRCLE, 
        ShapeType.SQUARE, 
        ShapeType.TRIANGLE,
        ShapeType.PENTAGON,
        ShapeType.HEXAGON,
        ShapeType.STAR
    ]
    
    # Customize feature extraction
    config.features.feature_types = ['geometric', 'hu_moments', 'fourier']
    config.features.n_fourier_descriptors = 6
    
    # Customize training
    config.training.model_configs = ['default', 'robust']
    config.training.test_size = 0.25
    config.training.enable_visualizations = False
    
    # Set up output directories
    output_dir = Path("./example_output")
    config.io.models_dir = output_dir / "models"
    config.io.results_dir = output_dir / "results"
    
    print(f"📋 Configuration:")
    print(f"   Dataset: {config.dataset.n_shapes} shapes, {config.dataset.n_scales} scales")
    print(f"   Features: {config.features.feature_types}")
    print(f"   Models: {config.training.model_configs}")
    
    # Create and run pipeline
    pipeline = TrainingPipeline(config)
    
    print("🚀 Starting custom training pipeline...")
    results = pipeline.run_complete_pipeline(save_models=True, save_datasets=True)
    
    # Display detailed results
    print(f"✅ Training completed successfully!")
    
    training_results = results['training_results']
    for model_name, model_result in training_results.items():
        metrics = model_result['metrics']
        print(f"   📊 {model_name}: Accuracy={metrics['accuracy']:.3f}, "
              f"F1={metrics['f1_score']:.3f}")
    
    return results


def example_3_step_by_step():
    """
    Example 3: Step-by-step manual process
    
    This example shows how to use individual components to build
    a custom training workflow step by step.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Step-by-Step Manual Process")
    print("=" * 60)
    
    # Step 1: Generate shapes manually
    print("📐 Step 1: Generating shapes...")
    
    shapes = []
    shape_types = [ShapeType.CIRCLE, ShapeType.SQUARE, ShapeType.TRIANGLE]
    
    for shape_type in shape_types:
        for scale in [0.8, 1.0, 1.2]:
            contour = ShapeFactory.generate_shape(shape_type, scale, img_size=(256, 256))
            shapes.append((contour, shape_type))
    
    print(f"   Generated {len(shapes)} shapes")
    
    # Step 2: Create training pairs manually
    print("🔗 Step 2: Creating training pairs...")
    
    pairs = []
    labels = []
    
    # Positive pairs (same shape type)
    for i, (contour1, shape_type1) in enumerate(shapes):
        for j, (contour2, shape_type2) in enumerate(shapes[i+1:], i+1):
            if shape_type1 == shape_type2:
                pairs.append((contour1, contour2))
                labels.append(1)  # Positive pair
    
    # Negative pairs (different shape types)
    import random
    random.seed(42)
    
    negative_count = len([l for l in labels if l == 1])  # Match positive count
    negative_added = 0
    
    for i, (contour1, shape_type1) in enumerate(shapes):
        if negative_added >= negative_count:
            break
        for j, (contour2, shape_type2) in enumerate(shapes[i+1:], i+1):
            if shape_type1 != shape_type2 and negative_added < negative_count:
                pairs.append((contour1, contour2))
                labels.append(0)  # Negative pair
                negative_added += 1
    
    print(f"   Created {len(pairs)} pairs ({sum(labels)} positive, {len(labels)-sum(labels)} negative)")
    
    # Step 3: Extract features manually
    print("🔬 Step 3: Extracting features...")
    
    extractor = GeometricFeatureExtractor()
    features = []
    
    for contour1, contour2 in pairs:
        # Extract features from both contours
        feat1 = extractor.extract_features(contour1)
        feat2 = extractor.extract_features(contour2)
        
        # Combine features (simple concatenation)
        combined_features = feat1 + feat2
        features.append(combined_features)
    
    X = np.array(features)
    y = np.array(labels)
    
    print(f"   Extracted features: {X.shape}")
    print(f"   Feature names: {extractor.get_feature_names()}")
    
    # Step 4: Train model manually
    print("🤖 Step 4: Training model...")

    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    
    # Create and train model
    model = SGDModel()
    model.fit(X_train, y_train)
    
    # Evaluate model
    train_accuracy = model.score(X_train, y_train)
    test_accuracy = model.score(X_test, y_test)
    
    print(f"   ✅ Model trained successfully!")
    print(f"   📊 Training accuracy: {train_accuracy:.3f}")
    print(f"   📊 Test accuracy: {test_accuracy:.3f}")
    
    # Step 5: Make predictions
    print("🔮 Step 5: Making predictions...")
    
    # Test on a few examples
    test_predictions = model.predict(X_test[:5])
    test_probabilities = model.predict_proba(X_test[:5])
    
    print("   Sample predictions:")
    for i, (pred, prob, true_label) in enumerate(zip(test_predictions, test_probabilities, y_test[:5])):
        confidence = max(prob)
        print(f"   Sample {i+1}: Predicted={pred}, True={true_label}, "
              f"Confidence={confidence:.3f}, Correct={pred==true_label}")
    
    return {
        'model': model,
        'features': X,
        'labels': y,
        'train_accuracy': train_accuracy,
        'test_accuracy': test_accuracy
    }


def example_4_feature_analysis():
    """
    Example 4: Feature analysis and comparison
    
    This example demonstrates how to analyze different feature types
    and their effectiveness for shape matching.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Feature Analysis")
    print("=" * 60)
    
    # Generate test shapes
    print("📐 Generating test shapes for feature analysis...")
    
    test_contours = []
    test_shapes = [ShapeType.CIRCLE, ShapeType.SQUARE, ShapeType.TRIANGLE]
    
    for shape_type in test_shapes:
        contour = ShapeFactory.generate_shape(shape_type, 1.0)
        test_contours.append((contour, shape_type))
    

    extractors = {
        'Geometric': GeometricFeatureExtractor(),
        'Hu Moments': HuMomentExtractor(),
        'Fourier': FourierFeatureExtractor(n_descriptors=4)
    }
    
    print("🔬 Analyzing features for different extractors...")

    for extractor_name, extractor in extractors.items():
        print(f"\n   {extractor_name} Features:")
        
        features_by_shape = {}

        for contour, shape_type in test_contours:
            features = extractor.extract_features(contour)
            features_by_shape[shape_type.value] = features
            
            print(f"   {shape_type.value}: {len(features)} features")
            print(f"      Range: [{min(features):.3f}, {max(features):.3f}]")
            print(f"      Mean: {np.mean(features):.3f}, Std: {np.std(features):.3f}")
        
        # Analyze feature similarity within shape types
        if len(features_by_shape) > 1:
            shape_names = list(features_by_shape.keys())
            feat1 = np.array(features_by_shape[shape_names[0]])
            feat2 = np.array(features_by_shape[shape_names[1]])
            
            # Calculate feature distance
            distance = np.linalg.norm(feat1 - feat2)
            print(f"   Distance between {shape_names[0]} and {shape_names[1]}: {distance:.3f}")
    
    return features_by_shape


def example_5_visualization():
    """
    Example 5: Visualization and analysis
    
    This example shows how to create visualizations for model analysis
    and debugging.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Visualization and Analysis")
    print("=" * 60)
    
    try:

        print("📊 Creating visualizations...")
        
        # Create a simple confusion matrix visualization
        y_true = np.array([0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1])
        y_pred = np.array([0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0])

        print("   Creating confusion matrix...")
        fig = plot_confusion_matrix(y_true, y_pred, model_name="Example Model", show_plot=False)

        output_dir = Path("./example_output")
        output_dir.mkdir(exist_ok=True)

        plt.savefig(output_dir / "confusion_matrix.png", dpi=150, bbox_inches='tight')
        print(f"   💾 Saved confusion matrix to {output_dir / 'confusion_matrix.png'}")
        
        plt.close('all')  # Clean up figures
        
        print("   ✅ Visualization created successfully!")

    except ImportError as e:
        print(f"   ⚠️  Visualization skipped: Missing dependency ({e})")
        print("   To enable visualizations, install: pip install matplotlib seaborn")

    except Exception as e:
        print(f"   ⚠️  Visualization failed: {e}")
        import traceback
        traceback.print_exc()

    print("   ✅ Visualization example completed")


def main():
    """
    Run all examples in sequence
    """
    print("🎯 Shape Matching Training - Basic Usage Examples")
    print("=" * 80)
    
    try:
        # Run all examples
        results_1 = example_1_quick_start()
        results_2 = example_2_custom_configuration()
        results_3 = example_3_step_by_step()
        results_4 = example_4_feature_analysis()
        example_5_visualization()
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 EXAMPLES SUMMARY")
        print("=" * 60)
        
        print("✅ All examples completed successfully!")
        print("\nResults summary:")
        print(f"   Quick start accuracy: {results_1['pipeline_info']['best_accuracy']:.3f}")
        print(f"   Custom config accuracy: {results_2['pipeline_info']['best_accuracy']:.3f}")
        print(f"   Step-by-step accuracy: {results_3['test_accuracy']:.3f}")
        print(f"   Feature types analyzed: {len(results_4)} extractors")
        
        print("\n💡 Next steps:")
        print("   - Experiment with different configurations")
        print("   - Try ensemble methods for better accuracy")
        print("   - Analyze feature importance")
        print("   - Test on your own contour data")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())