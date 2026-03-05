#!/usr/bin/env python3
"""
Production Model Training Script

This script trains a production-ready shape matching model using robust configuration
and saves it for deployment.
"""

import sys
from pathlib import Path

from datetime import datetime

from .config import RobustTrainingConfig
from .core.training.pipeline import TrainingPipeline

def train_production_model():
    """
    Train a production-ready shape matching model
    """
    print("=" * 80)
    print("🚀 PRODUCTION MODEL TRAINING")
    print("=" * 80)

    # Step 1: Create robust configuration
    print("\n📋 Step 1: Setting up configuration...")
    config = RobustTrainingConfig()

    # Customize for production (optional)
    config.dataset.n_shapes = 10  # More shapes for better generalization
    config.dataset.n_scales = 10  # More scale variations
    config.dataset.n_variants = 10  # More shape variants
    config.dataset.n_noisy = 10  # More noisy samples

    # Set up output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("./production_models") / timestamp
    config.io.models_dir = output_dir / "models"
    config.io.results_dir = output_dir / "results"
    config.io.datasets_dir = output_dir / "datasets"

    # Create output directories
    config.io.models_dir.mkdir(parents=True, exist_ok=True)
    config.io.results_dir.mkdir(parents=True, exist_ok=True)
    config.io.datasets_dir.mkdir(parents=True, exist_ok=True)

    print(f"   ✓ Configuration: {config.dataset.n_shapes} shapes, {config.dataset.n_scales} scales")
    print(f"   ✓ Output directory: {output_dir}")

    # Step 2: Create and run training pipeline
    print("\n🔧 Step 2: Creating training pipeline...")
    pipeline = TrainingPipeline(config)

    print("\n🏋️  Step 3: Training model (this may take a few minutes)...")
    results = pipeline.run_complete_pipeline(
        save_models=True,
        save_datasets=True
    )

    # Step 4: Display results
    print("\n" + "=" * 80)
    print("📊 TRAINING RESULTS")
    print("=" * 80)

    pipeline_info = results['pipeline_info']
    dataset_info = results['dataset_info']
    training_results = results['training_results']

    print(f"\n✅ Training completed in {pipeline_info['total_time']:.1f} seconds")
    print(f"\n📦 Dataset Statistics:")
    print(f"   • Total contours: {dataset_info['total_contours']}")
    print(f"   • Total pairs: {dataset_info['total_pairs']:,}")
    print(f"   • Positive pairs: {dataset_info['positive_pairs']:,}")
    print(f"   • Negative pairs: {dataset_info['negative_pairs']:,}")

    print(f"\n🏆 Best Model: {pipeline_info['best_model']}")
    print(f"   • Accuracy: {pipeline_info['best_accuracy']:.4f}")

    print("\n📈 All Model Results:")
    for model_name, model_result in training_results.items():
        metrics = model_result['metrics']
        print(f"\n   {model_name}:")
        print(f"      Accuracy:  {metrics['accuracy']:.4f}")
        print(f"      Precision: {metrics['precision']:.4f}")
        print(f"      Recall:    {metrics['recall']:.4f}")
        print(f"      F1 Score:  {metrics['f1_score']:.4f}")
        if 'model_path' in model_result:
            print(f"      Saved to:  {model_result['model_path']}")

    # Step 5: Save best model info
    best_model_info = {
        'model_name': pipeline_info['best_model'],
        'accuracy': pipeline_info['best_accuracy'],
        'trained_at': timestamp,
        'config': config.to_dict(),
        'dataset_info': dataset_info
    }

    import json
    info_path = output_dir / "model_info.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)
    with open(info_path, 'w') as f:
        json.dump(best_model_info, f, indent=2, default=str)

    print(f"\n💾 Model information saved to: {info_path}")

    # Step 6: Show how to load the model
    print("\n" + "=" * 80)
    print("📖 HOW TO USE THE TRAINED MODEL")
    print("=" * 80)
    print("\nTo load and use the trained model in your application:")
    print(f"""
from modules.shape_matching_training.core.models import SGDModel
from pathlib import Path

# Load the best model
model_path = Path("{results.get('best_model_path', 'path/to/model.joblib')}")
model = SGDModel.load_model(model_path)

# Use for predictions
# features = extract_features_from_your_contours(contour1, contour2)
# prediction = model.predict(features)
# probability = model.predict_proba(features)
""")

    return results


if __name__ == '__main__':
    try:
        results = train_production_model()
        print("\n✅ Production model training completed successfully!")
        exit(0)
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
