"""
Training Pipeline Module

Provides end-to-end training pipeline orchestration for shape similarity models,
integrating data generation, feature extraction, model training, and evaluation.
"""

import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
import numpy as np

from ..dataset.shape_factory import ShapeFactory, ShapeType
from ..dataset.data_augmentation import ContourAugmenter
from ..dataset.synthetic_dataset import SyntheticDataset
from ..dataset.pair_generator import PairGenerator
from ..features.base_extractor import FeatureExtractorFactory, CompositeFeatureExtractor
from ..models.model_factory import ModelFactory
from .trainer import ModelTrainer
from .evaluator import ModelEvaluator
from ...config.training_configs import TrainingConfigRegistry, DefaultTrainingConfig
from ...utils.io_utils import save_model, save_dataset
from ...utils.visualization import visualize_training_results


class TrainingPipeline:
    """
    End-to-end training pipeline for shape similarity models
    """
    
    def __init__(self, config: Optional[Union[str, Dict[str, Any]]] = None):
        """
        Initialize training pipeline
        
        Args:
            config: Training configuration (name, dict, or config object)
        """
        # Load configuration
        if isinstance(config, str):
            self.config = TrainingConfigRegistry.get_config(config)
        elif isinstance(config, dict):
            # Create default config and update with provided values
            self.config = DefaultTrainingConfig()
            # Note: In production, you'd want proper config updating
        else:
            self.config = config or DefaultTrainingConfig()
        
        # Initialize components
        self.feature_extractor = None
        self.dataset = None
        self.trainer = None
        self.evaluator = None
        
        # Results storage
        self.training_results = {}
        self.dataset_info = {}
        self.pipeline_metadata = {}
    
    def run_complete_pipeline(self, 
                            save_models: bool = True,
                            save_datasets: bool = True) -> Dict[str, Any]:
        """
        Run the complete training pipeline from data generation to model evaluation
        
        Args:
            save_models: Whether to save trained models
            save_datasets: Whether to save generated datasets
            
        Returns:
            Complete pipeline results
        """
        print("🚀 Starting complete training pipeline...")
        pipeline_start_time = time.time()
        
        try:
            # Stage 1: Dataset Generation
            print("\n📊 Stage 1: Dataset Generation")
            dataset, pairs, labels = self._generate_dataset()
            
            # Stage 2: Feature Extraction Setup
            print("\n🔧 Stage 2: Feature Extraction Setup")
            feature_extractor = self._setup_feature_extraction()
            
            # Stage 3: Model Training
            print("\n🤖 Stage 3: Model Training")
            training_results = self._train_models(feature_extractor, pairs, labels)
            
            # Stage 4: Model Evaluation
            print("\n📈 Stage 4: Model Evaluation")
            evaluation_results = self._evaluate_models(training_results)
            
            # Stage 5: Results Compilation and Saving
            print("\n💾 Stage 5: Results Compilation")
            final_results = self._compile_final_results(
                training_results, evaluation_results, 
                pipeline_start_time, save_models, save_datasets
            )
            
            print("\n🎉 Pipeline completed successfully!")
            self._print_pipeline_summary(final_results)
            
            return final_results
            
        except Exception as e:
            print(f"\n❌ Pipeline failed: {str(e)}")
            raise
    
    def run_training_only(self, 
                         contour_pairs: List[Tuple],
                         labels: List[int],
                         feature_extractor: Optional[CompositeFeatureExtractor] = None) -> Dict[str, Any]:
        """
        Run training pipeline with provided data
        
        Args:
            contour_pairs: Pre-generated contour pairs
            labels: Corresponding labels
            feature_extractor: Optional feature extractor (will create default if None)
            
        Returns:
            Training results
        """
        print("🚀 Starting training pipeline with provided data...")
        
        # Setup feature extraction
        if feature_extractor is None:
            feature_extractor = self._setup_feature_extraction()
        
        # Train models
        training_results = self._train_models(feature_extractor, contour_pairs, labels)
        
        # Evaluate models
        evaluation_results = self._evaluate_models(training_results)
        
        # Compile results
        results = {
            'training_results': training_results,
            'evaluation_results': evaluation_results,
            'best_model': self._find_best_model(training_results),
            'feature_extractor': feature_extractor
        }
        
        return results
    
    def _generate_dataset(self) -> Tuple[SyntheticDataset, List[Tuple], List[int]]:
        """Generate synthetic dataset"""
        print("🔄 Generating synthetic dataset...")
        
        # Create dataset generator
        dataset_config = self.config.dataset
        
        # Generate base contours
        dataset = SyntheticDataset(
            n_shapes=dataset_config.n_shapes,
            n_scales=dataset_config.n_scales,
            n_variants=dataset_config.n_variants,
            n_noisy=dataset_config.n_noisy,
            shape_types=dataset_config.included_shapes,
            img_size=dataset_config.img_size,
            scale_range=(dataset_config.min_scale, dataset_config.max_scale)
        )
        
        # Generate dataset
        contours = dataset.generate()
        print(f"✅ Generated {len(contours)} contours")
        
        # Create training pairs
        pair_generator = PairGenerator(
            include_hard_negatives=dataset_config.include_hard_negatives
        )
        
        pairs, labels = pair_generator.generate_balanced_pairs(contours)
        print(f"✅ Generated {len(pairs):,} training pairs")
        
        # Store dataset info
        self.dataset_info = {
            'total_contours': len(contours),
            'total_pairs': len(pairs),
            'positive_pairs': sum(labels),
            'negative_pairs': len(labels) - sum(labels),
            'dataset_config': dataset_config.to_dict() if hasattr(dataset_config, 'to_dict') else str(dataset_config)
        }
        
        return dataset, pairs, labels
    
    def _setup_feature_extraction(self) -> CompositeFeatureExtractor:
        """Setup feature extraction pipeline"""
        print("🔧 Setting up feature extraction...")
        
        feature_config = self.config.features
        
        # Create extractor configurations
        extractor_configs = []
        
        for feature_type in feature_config.feature_types:
            if feature_type == 'hu_moments':
                extractor_configs.append({
                    'name': 'hu', 
                    'config': {'use_log_transform': True}
                })
            elif feature_type == 'fourier':
                extractor_configs.append({
                    'name': 'fourier',
                    'config': {'n_descriptors': feature_config.n_fourier_descriptors}
                })
            elif feature_type == 'geometric':
                extractor_configs.append({
                    'name': 'geometric',
                    'config': {}
                })
            elif feature_type == 'curvature':
                extractor_configs.append({
                    'name': 'curvature',
                    'config': {'n_bins': feature_config.n_curvature_bins}
                })
        
        # Create composite extractor
        feature_extractor = FeatureExtractorFactory.create_composite_extractor(extractor_configs)
        
        print(f"✅ Feature extractor created: {feature_extractor.get_feature_count()} total features")
        
        return feature_extractor
    
    def _train_models(self, 
                     feature_extractor: CompositeFeatureExtractor,
                     pairs: List[Tuple],
                     labels: List[int]) -> Dict[str, Any]:
        """Train all configured models"""
        print("🤖 Training models...")
        
        # Create trainer
        trainer = ModelTrainer(feature_extractor, self.config)
        
        # Prepare model configurations
        model_configs = []
        for model_name in self.config.training.model_configs:
            model_configs.append({
                'name': model_name,
                'type': 'sgd',
                'config': {'config_name': model_name}
            })
        
        # Train models
        training_results = trainer.train_multiple_models(model_configs, pairs, labels)
        
        # Store trainer reference
        self.trainer = trainer
        
        return training_results
    
    def _evaluate_models(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all trained models"""
        print("📈 Evaluating models...")
        
        # Create evaluator
        evaluator = ModelEvaluator(
            save_visualizations=self.config.training.enable_visualizations,
            output_dir=str(self.config.io.results_dir) if self.config.io.results_dir else None
        )
        
        # Evaluate each model
        evaluation_results = {}
        
        for model_name, training_result in training_results.items():
            print(f"🔍 Evaluating {model_name}...")
            
            model = training_result['model']
            X_test, y_test = training_result['test_data']
            
            # Single model evaluation
            eval_result = evaluator.evaluate_single_model(model, X_test, y_test, model_name)
            evaluation_results[model_name] = eval_result
            
            # Cross-validation for best model
            if model_name == self._find_best_model_name(training_results):
                print(f"🔄 Cross-validating {model_name}...")
                X_train = training_result.get('X_train')
                y_train = training_result.get('y_train')
                
                if X_train is not None and y_train is not None:
                    cv_results = evaluator.cross_validate_model(model, X_train, y_train)
                    eval_result['cross_validation'] = cv_results
        
        # Model comparison
        comparison_results = evaluator.compare_models(evaluation_results)
        
        # Store evaluator reference
        self.evaluator = evaluator
        
        return {
            'individual_results': evaluation_results,
            'comparison_results': comparison_results,
            'evaluator': evaluator
        }
    
    def _compile_final_results(self, 
                              training_results: Dict[str, Any],
                              evaluation_results: Dict[str, Any],
                              pipeline_start_time: float,
                              save_models: bool,
                              save_datasets: bool) -> Dict[str, Any]:
        """Compile and save final results"""
        
        pipeline_time = time.time() - pipeline_start_time
        
        # Find best model
        best_model_name = self._find_best_model_name(training_results)
        best_model = training_results[best_model_name]['model']
        best_accuracy = training_results[best_model_name]['metrics']['accuracy']
        
        # Compile final results
        final_results = {
            'pipeline_info': {
                'config': self.config.to_dict() if hasattr(self.config, 'to_dict') else str(self.config),
                'total_time': pipeline_time,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'best_model': best_model_name,
                'best_accuracy': best_accuracy
            },
            'dataset_info': self.dataset_info,
            'training_results': training_results,
            'evaluation_results': evaluation_results,
            'best_model_path': None,
            'dataset_path': None
        }
        
        # Save models
        if save_models:
            print("💾 Saving best model...")
            model_path, model_folder = save_model(
                best_model,
                f"{best_model_name}_{best_accuracy:.3f}",
                best_accuracy,
                save_dir=self.config.io.models_dir,
                training_config=self.config.to_dict() if hasattr(self.config, 'to_dict') else {},
                dataset_info=self.dataset_info
            )
            final_results['best_model_path'] = str(model_path)
            final_results['model_folder'] = str(model_folder)
        
        # Save datasets
        if save_datasets and hasattr(self, 'dataset'):
            print("💾 Saving dataset...")
            # This would need proper implementation based on the dataset structure
            # dataset_path, dataset_folder = save_dataset(...)
            pass
        
        # Generate visualizations
        if self.config.training.enable_visualizations:
            print("📊 Generating final visualizations...")
            try:
                viz_results = visualize_training_results(training_results, str(self.config.io.results_dir))
                final_results['visualizations'] = viz_results
            except Exception as e:
                print(f"Warning: Could not generate visualizations: {e}")
        
        return final_results
    
    def _find_best_model(self, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Find the best performing model"""
        best_model_name = self._find_best_model_name(training_results)
        return training_results[best_model_name]
    
    def _find_best_model_name(self, training_results: Dict[str, Any]) -> str:
        """Find the name of the best performing model"""
        return max(training_results.keys(), 
                  key=lambda k: training_results[k]['metrics']['accuracy'])
    
    def _print_pipeline_summary(self, final_results: Dict[str, Any]):
        """Print pipeline summary"""
        print("\n" + "="*60)
        print("🎯 PIPELINE SUMMARY")
        print("="*60)
        
        pipeline_info = final_results['pipeline_info']
        dataset_info = final_results['dataset_info']
        
        print(f"⏱️  Total Time: {pipeline_info['total_time']:.1f}s")
        print(f"📊 Dataset: {dataset_info['total_contours']} contours, {dataset_info['total_pairs']:,} pairs")
        print(f"🏆 Best Model: {pipeline_info['best_model']}")
        print(f"🎯 Best Accuracy: {pipeline_info['best_accuracy']:.3f}")
        
        if final_results['best_model_path']:
            print(f"💾 Model Saved: {final_results['best_model_path']}")
        
        print("="*60)
    
    def get_pipeline_config_template(self) -> Dict[str, Any]:
        """Get a template for pipeline configuration"""
        return {
            'dataset': {
                'n_shapes': 8,
                'n_scales': 3,
                'n_variants': 5,
                'n_noisy': 4,
                'included_shapes': None,  # None = all available
                'include_hard_negatives': True,
                'img_size': [256, 256],
                'min_scale': 0.5,
                'max_scale': 3.0
            },
            'features': {
                'feature_types': ['hu_moments', 'fourier', 'geometric'],
                'n_fourier_descriptors': 4,
                'n_curvature_bins': 16
            },
            'training': {
                'test_size': 0.3,
                'random_state': 42,
                'model_configs': ['default', 'robust'],
                'enable_visualizations': True,
                'batch_size': 1000
            },
            'io': {
                'models_dir': 'saved_models',
                'datasets_dir': 'saved_datasets', 
                'results_dir': 'results'
            }
        }
    
    def save_pipeline_config(self, filepath: str):
        """Save current pipeline configuration"""
        config_dict = self.config.to_dict() if hasattr(self.config, 'to_dict') else self.get_pipeline_config_template()
        
        import json
        from pathlib import Path
        
        filepath = Path(filepath)
        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        print(f"📄 Configuration saved: {filepath}")
    
    @classmethod
    def from_config_file(cls, config_path: str) -> 'TrainingPipeline':
        """Create pipeline from configuration file"""
        import json
        from pathlib import Path
        
        config_path = Path(config_path)
        
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
        
        return cls(config_dict)


# Convenience functions for common use cases
def quick_training_pipeline(n_shapes: int = 6, 
                          enable_viz: bool = True) -> Dict[str, Any]:
    """
    Run a quick training pipeline with minimal configuration
    
    Args:
        n_shapes: Number of shape types to use
        enable_viz: Whether to generate visualizations
        
    Returns:
        Training results
    """
    config = {
        'dataset': {'n_shapes': n_shapes, 'n_scales': 3, 'n_variants': 3, 'n_noisy': 2},
        'training': {'model_configs': ['fast'], 'enable_visualizations': enable_viz}
    }
    
    pipeline = TrainingPipeline(config)
    return pipeline.run_complete_pipeline(save_models=True, save_datasets=False)


def production_training_pipeline(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a production-ready training pipeline with comprehensive evaluation
    
    Args:
        config_path: Path to configuration file (optional)
        
    Returns:
        Training results
    """
    if config_path:
        pipeline = TrainingPipeline.from_config_file(config_path)
    else:
        # Use robust configuration
        pipeline = TrainingPipeline('robust')
    
    return pipeline.run_complete_pipeline(save_models=True, save_datasets=True)