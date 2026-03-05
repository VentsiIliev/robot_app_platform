"""
Integration tests for Training Pipeline
"""

import pytest
import numpy as np
from pathlib import Path

from core.training.pipeline import TrainingPipeline, quick_training_pipeline
from core.dataset.synthetic_dataset import SyntheticDataset
from core.dataset.pair_generator import PairGenerator
from core.features.base_extractor import FeatureExtractorFactory
from config.training_configs import DefaultTrainingConfig, FastTrainingConfig


@pytest.mark.integration
class TestTrainingPipelineIntegration:
    """Integration tests for the complete training pipeline."""
    
    def test_complete_pipeline_execution(self, temp_dir):
        """Test complete pipeline from dataset generation to model evaluation."""
        # Create a minimal configuration
        config = FastTrainingConfig()
        config.dataset.n_shapes = 2
        config.dataset.n_scales = 2
        config.dataset.n_variants = 2
        config.dataset.n_noisy = 2
        config.io.models_dir = temp_dir / "models"
        config.io.results_dir = temp_dir / "results"
        
        pipeline = TrainingPipeline(config)
        
        # Run complete pipeline
        results = pipeline.run_complete_pipeline(save_models=True, save_datasets=False)
        
        # Verify results structure
        assert 'pipeline_info' in results
        assert 'dataset_info' in results
        assert 'training_results' in results
        assert 'evaluation_results' in results
        
        # Verify pipeline completed successfully
        assert results['pipeline_info']['best_model'] is not None
        assert results['pipeline_info']['best_accuracy'] > 0
        
        # Verify at least one model was trained
        assert len(results['training_results']) > 0
        
        # Verify model file was saved
        assert results['best_model_path'] is not None
        assert Path(results['best_model_path']).exists()
    
    def test_dataset_generation_integration(self):
        """Test dataset generation and pair creation integration."""
        # Create dataset
        dataset = SyntheticDataset(
            n_shapes=2,
            n_scales=2,
            n_variants=2,
            n_noisy=2,
            shape_types=None,  # Auto-select
            img_size=(128, 128)
        )
        
        contours = dataset.generate()
        assert len(contours) > 0
        
        # Generate pairs
        pair_generator = PairGenerator(random_state=42)
        pairs, labels = pair_generator.generate_balanced_pairs(contours)
        
        assert len(pairs) > 0
        assert len(pairs) == len(labels)
        assert sum(labels) > 0  # Some positive pairs
        assert sum(labels) < len(labels)  # Some negative pairs
    
    def test_feature_extraction_integration(self, synthetic_contours):
        """Test feature extraction integration with different extractors."""
        # Create composite feature extractor
        configs = [
            {'name': 'geometric'},
            {'name': 'hu', 'config': {'use_log_transform': True}}
        ]
        
        extractor = FeatureExtractorFactory.create_composite_extractor(configs)
        
        # Extract features from all contours
        features = []
        for contour in synthetic_contours:
            feat = extractor.extract_features(contour.contour)
            features.append(feat)
        
        assert len(features) == len(synthetic_contours)
        assert all(len(f) == extractor.get_feature_count() for f in features)
        assert all(all(np.isfinite(val) for val in f) for f in features)
    
    def test_training_only_pipeline(self, training_pairs, composite_extractor):
        """Test training pipeline with provided data."""
        pairs, labels = training_pairs
        
        # Create pipeline
        pipeline = TrainingPipeline(DefaultTrainingConfig())
        
        # Run training only
        results = pipeline.run_training_only(pairs, labels, composite_extractor)
        
        # Verify results
        assert 'training_results' in results
        assert 'evaluation_results' in results
        assert 'best_model' in results
        
        # Verify model was trained
        best_model = results['best_model']['model']
        assert best_model.is_fitted()
    
    @pytest.mark.slow
    def test_pipeline_with_different_configurations(self, temp_dir):
        """Test pipeline with different training configurations."""
        configurations = [
            DefaultTrainingConfig(),
            FastTrainingConfig()
        ]
        
        results_list = []
        
        for config in configurations:
            # Adjust config for testing
            config.dataset.n_shapes = 2
            config.dataset.n_scales = 2
            config.dataset.n_variants = 2
            config.dataset.n_noisy = 2
            config.io.models_dir = temp_dir / f"models_{config.__class__.__name__}"
            
            pipeline = TrainingPipeline(config)
            results = pipeline.run_complete_pipeline(save_models=False, save_datasets=False)
            results_list.append(results)
        
        # All configurations should complete successfully
        assert all('pipeline_info' in r for r in results_list)
        assert all(r['pipeline_info']['best_accuracy'] > 0 for r in results_list)
    
    def test_quick_training_pipeline(self):
        """Test quick training pipeline convenience function."""
        results = quick_training_pipeline(n_shapes=2, enable_viz=False)
        
        assert results is not None
        assert 'pipeline_info' in results
        assert results['pipeline_info']['best_accuracy'] > 0
    
    def test_pipeline_error_handling(self):
        """Test pipeline error handling and recovery."""
        # Create pipeline with invalid configuration
        config = DefaultTrainingConfig()
        config.dataset.n_shapes = 0  # Invalid
        
        pipeline = TrainingPipeline(config)
        
        # Should raise an error
        with pytest.raises((ValueError, AssertionError)):
            pipeline.run_complete_pipeline()
    
    def test_pipeline_reproducibility(self):
        """Test that pipeline results are reproducible with same random state."""
        config1 = DefaultTrainingConfig()
        config1.dataset.n_shapes = 2
        config1.dataset.n_scales = 2
        config1.dataset.n_variants = 2
        config1.dataset.n_noisy = 2
        config1.training.random_state = 42
        
        config2 = DefaultTrainingConfig()
        config2.dataset.n_shapes = 2
        config2.dataset.n_scales = 2
        config2.dataset.n_variants = 2
        config2.dataset.n_noisy = 2
        config2.training.random_state = 42
        
        pipeline1 = TrainingPipeline(config1)
        pipeline2 = TrainingPipeline(config2)
        
        results1 = pipeline1.run_complete_pipeline(save_models=False, save_datasets=False)
        results2 = pipeline2.run_complete_pipeline(save_models=False, save_datasets=False)
        
        # Should have same number of training samples
        assert results1['dataset_info']['total_pairs'] == results2['dataset_info']['total_pairs']


@pytest.mark.integration
class TestEndToEndWorkflow:
    """End-to-end workflow integration tests."""
    
    def test_shape_generation_to_prediction_workflow(self):
        """Test complete workflow from shape generation to prediction."""
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        from core.features.geometric_features import GeometricFeatureExtractor
        from core.models.sgd_model import SGDModel
        
        # 1. Generate training shapes
        training_contours = []
        training_labels = []
        
        # Generate positive pairs (same shape)
        for _ in range(10):
            contour1 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.0)
            contour2 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.1)
            training_contours.append((contour1, contour2))
            training_labels.append(1)
        
        # Generate negative pairs (different shapes)
        for _ in range(10):
            contour1 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.0)
            contour2 = ShapeFactory.generate_shape(ShapeType.SQUARE, 1.0)
            training_contours.append((contour1, contour2))
            training_labels.append(0)
        
        # 2. Extract features
        extractor = GeometricFeatureExtractor()
        features = []
        
        for contour1, contour2 in training_contours:
            feat1 = extractor.extract_features(contour1)
            feat2 = extractor.extract_features(contour2)
            combined = feat1 + feat2
            features.append(combined)
        
        X = np.array(features)
        y = np.array(training_labels)
        
        # 3. Train model
        model = SGDModel()
        model.fit(X, y)
        
        # 4. Test prediction
        test_contour1 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.0)
        test_contour2 = ShapeFactory.generate_shape(ShapeType.CIRCLE, 1.05)
        
        test_feat1 = extractor.extract_features(test_contour1)
        test_feat2 = extractor.extract_features(test_contour2)
        test_combined = np.array([test_feat1 + test_feat2])
        
        prediction = model.predict(test_combined)
        probability = model.predict_proba(test_combined)
        
        # Should predict similar shapes as positive
        assert prediction[0] == 1  # Same shape type should be predicted as similar
        assert probability[0][1] > 0.5  # High probability for positive class
    
    def test_data_augmentation_to_training_workflow(self):
        """Test workflow including data augmentation."""
        from core.dataset.shape_factory import ShapeFactory, ShapeType
        from core.dataset.data_augmentation import ContourAugmenter
        from core.features.moment_features import HuMomentExtractor
        from core.models.sgd_model import SGDModel
        
        # 1. Generate base shape
        base_contour = ShapeFactory.generate_shape(ShapeType.SQUARE, 1.0)
        
        # 2. Apply augmentations
        augmenter = ContourAugmenter()
        augmented_contours = []
        
        for _ in range(5):
            augmented = augmenter.augment_contour(base_contour)
            augmented_contours.append(augmented)
        
        # 3. Extract features (should be similar due to invariance)
        extractor = HuMomentExtractor()
        features = []
        
        for contour in augmented_contours:
            feat = extractor.extract_features(contour)
            features.append(feat)
        
        # Features should be relatively similar for augmented versions
        features_array = np.array(features)
        feature_std = np.std(features_array, axis=0)
        
        # Most features should have low variance (due to invariance properties)
        assert np.mean(feature_std) < 1.0  # Reasonable threshold
    
    def test_configuration_to_results_workflow(self, temp_dir):
        """Test workflow from configuration loading to results."""
        import json
        
        # 1. Create configuration file
        config_data = {
            'dataset': {
                'n_shapes': 2,
                'n_scales': 2, 
                'n_variants': 2,
                'n_noisy': 2,
                'img_size': [128, 128]
            },
            'features': {
                'feature_types': ['geometric', 'hu_moments']
            },
            'training': {
                'model_configs': ['fast'],
                'test_size': 0.3
            },
            'io': {
                'models_dir': str(temp_dir / "models"),
                'results_dir': str(temp_dir / "results")
            }
        }
        
        config_file = temp_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # 2. Load configuration and run pipeline
        pipeline = TrainingPipeline.from_config_file(str(config_file))
        results = pipeline.run_complete_pipeline(save_models=True)
        
        # 3. Verify results
        assert results['pipeline_info']['best_accuracy'] > 0
        assert Path(results['best_model_path']).exists()
        
        # 4. Load and test saved model
        from utils.io_utils import load_latest_model
        
        loaded_model, metadata = load_latest_model(temp_dir / "models")
        assert loaded_model.is_fitted()
        assert metadata.accuracy > 0


@pytest.mark.integration
@pytest.mark.slow
class TestPipelinePerformance:
    """Integration tests for pipeline performance."""
    
    def test_pipeline_scalability(self, performance_tracker):
        """Test pipeline performance with larger datasets."""
        config = FastTrainingConfig()
        config.dataset.n_shapes = 3
        config.dataset.n_scales = 3
        config.dataset.n_variants = 3
        config.dataset.n_noisy = 3
        
        pipeline = TrainingPipeline(config)
        
        performance_tracker.start("large_pipeline")
        results = pipeline.run_complete_pipeline(save_models=False, save_datasets=False)
        duration = performance_tracker.stop()
        
        assert results['pipeline_info']['best_accuracy'] > 0
        # Should complete in reasonable time even with larger dataset
        performance_tracker.assert_performance("large_pipeline", 30.0)  # 30 seconds max
    
    def test_parallel_feature_extraction_performance(self, performance_tracker):
        """Test performance of parallel feature extraction."""
        from core.dataset.synthetic_dataset import SyntheticDataset
        from core.dataset.pair_generator import PairGenerator
        from core.features.base_extractor import FeatureExtractorFactory
        
        # Generate larger dataset
        dataset = SyntheticDataset(n_shapes=3, n_scales=3, n_variants=3, n_noisy=3)
        contours = dataset.generate()
        
        pair_generator = PairGenerator()
        pairs, labels = pair_generator.generate_balanced_pairs(contours)
        
        # Create composite extractor
        configs = [{'name': 'geometric'}, {'name': 'hu'}]
        extractor = FeatureExtractorFactory.create_composite_extractor(configs)
        
        performance_tracker.start("parallel_feature_extraction")
        
        # Extract features
        features = []
        for contour1, contour2 in pairs[:100]:  # Test with first 100 pairs
            feat1 = extractor.extract_features(contour1)
            feat2 = extractor.extract_features(contour2)
            features.append(feat1 + feat2)
        
        duration = performance_tracker.stop()
        
        assert len(features) == 100
        # Should extract features reasonably quickly
        performance_tracker.assert_performance("parallel_feature_extraction", 10.0)


@pytest.mark.integration
class TestPipelineErrorRecovery:
    """Test pipeline error handling and recovery."""
    
    def test_invalid_shape_type_recovery(self):
        """Test recovery from invalid shape types."""
        config = DefaultTrainingConfig()
        config.dataset.n_shapes = 2
        # Set invalid shape types
        from core.dataset.shape_factory import ShapeType
        config.dataset.included_shapes = [ShapeType.CIRCLE]  # Only one valid shape
        
        pipeline = TrainingPipeline(config)
        
        # Should either handle gracefully or raise informative error
        try:
            results = pipeline.run_complete_pipeline(save_models=False)
            # If it succeeds, should have valid results
            assert results['pipeline_info']['best_accuracy'] >= 0
        except (ValueError, AssertionError) as e:
            # Should provide informative error message
            assert "shape" in str(e).lower() or "contour" in str(e).lower()
    
    def test_insufficient_data_handling(self):
        """Test handling of insufficient training data."""
        config = DefaultTrainingConfig()
        config.dataset.n_shapes = 1  # Very small dataset
        config.dataset.n_scales = 1
        config.dataset.n_variants = 1
        config.dataset.n_noisy = 1
        
        pipeline = TrainingPipeline(config)
        
        # Should handle small dataset gracefully or raise appropriate error
        try:
            results = pipeline.run_complete_pipeline(save_models=False)
            # If successful, should have some results
            assert 'pipeline_info' in results
        except (ValueError, AssertionError):
            # Expected for insufficient data
            pass