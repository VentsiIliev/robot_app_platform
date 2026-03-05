"""
Model Trainer Module

Provides the core training functionality for shape similarity models
with comprehensive logging, monitoring, and evaluation capabilities.
"""

import time
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union
from sklearn.model_selection import train_test_split
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from functools import partial

from ..models.base_model import BaseModel
from ..models.model_factory import ModelFactory
from ..features.base_extractor import BaseFeatureExtractor, compute_features_parallel, compute_features_for_pair
from ...utils.metrics import calculate_similarity_metrics, evaluate_model_performance
from ...utils.validation import validate_training_data, validate_dataset_pairs
from ...config.training_configs import TrainingConfig, DefaultTrainingConfig


class TrainingProgress:
    """Container for tracking training progress"""
    
    def __init__(self):
        self.start_time = None
        self.current_stage = "Initializing"
        self.progress_percentage = 0.0
        self.stages_completed = []
        self.current_stage_info = {}
        self.warnings = []
        self.errors = []
    
    def start(self):
        """Mark training start"""
        self.start_time = time.time()
        self.current_stage = "Starting"
    
    def update_stage(self, stage: str, progress: float = None, **info):
        """Update current training stage"""
        if self.current_stage != "Starting":
            self.stages_completed.append({
                'stage': self.current_stage,
                'duration': time.time() - self.stage_start_time if hasattr(self, 'stage_start_time') else 0,
                'info': self.current_stage_info.copy()
            })
        
        self.current_stage = stage
        self.stage_start_time = time.time()
        self.current_stage_info = info
        
        if progress is not None:
            self.progress_percentage = progress
    
    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append({
            'timestamp': time.time(),
            'stage': self.current_stage,
            'message': warning
        })
    
    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append({
            'timestamp': time.time(),
            'stage': self.current_stage,
            'message': error
        })
    
    def get_elapsed_time(self) -> float:
        """Get elapsed training time"""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'elapsed_time': self.get_elapsed_time(),
            'current_stage': self.current_stage,
            'progress_percentage': self.progress_percentage,
            'stages_completed': self.stages_completed,
            'warnings': self.warnings,
            'errors': self.errors,
            'n_warnings': len(self.warnings),
            'n_errors': len(self.errors)
        }


class ModelTrainer:
    """
    Core trainer class for shape similarity models
    """
    
    def __init__(self, 
                 feature_extractor: BaseFeatureExtractor,
                 config: Optional[Union[Dict[str, Any], TrainingConfig]] = None):
        """
        Initialize model trainer
        
        Args:
            feature_extractor: Feature extractor to use
            config: Training configuration
        """
        self.feature_extractor = feature_extractor
        
        # Handle configuration
        if isinstance(config, TrainingConfig):
            self.config = config
        elif isinstance(config, dict):
            self.config = DefaultTrainingConfig()
            # Update with provided values (this would need proper implementation)
        else:
            self.config = DefaultTrainingConfig()
        
        self.progress = TrainingProgress()
        self.training_results = {}
    
    def train_model(self, 
                   model_config: Dict[str, Any],
                   contour_pairs: List[Tuple],
                   labels: List[int],
                   validation_split: Optional[float] = None) -> Dict[str, Any]:
        """
        Train a single model
        
        Args:
            model_config: Model configuration dictionary
            contour_pairs: List of (contour1, contour2) tuples
            labels: Corresponding labels
            validation_split: Validation set size (optional)
            
        Returns:
            Training results dictionary
        """
        self.progress.start()
        
        try:
            # Stage 1: Data Validation
            self.progress.update_stage("Validating Data", 5)
            self._validate_training_data(contour_pairs, labels)
            
            # Stage 2: Feature Extraction
            self.progress.update_stage("Extracting Features", 15)
            features = self._extract_features_parallel(contour_pairs)
            
            # Stage 3: Data Splitting
            self.progress.update_stage("Splitting Data", 25)
            train_data, test_data = self._split_data(features, labels, validation_split)
            X_train, X_test, y_train, y_test = train_data + test_data
            
            # Stage 4: Model Creation
            self.progress.update_stage("Creating Model", 30)
            model = self._create_model(model_config)
            
            # Stage 5: Model Training
            self.progress.update_stage("Training Model", 50)
            training_start_time = time.time()
            model.fit(X_train, y_train)
            training_time = time.time() - training_start_time
            
            # Stage 6: Model Evaluation
            self.progress.update_stage("Evaluating Model", 80)
            evaluation_results = self._evaluate_model(model, X_test, y_test)
            
            # Stage 7: Results Compilation
            self.progress.update_stage("Compiling Results", 95)
            results = self._compile_results(
                model, evaluation_results, training_time,
                X_train, X_test, y_train, y_test
            )
            
            self.progress.update_stage("Complete", 100)
            
            return results
            
        except Exception as e:
            self.progress.add_error(f"Training failed: {str(e)}")
            raise
    
    def train_multiple_models(self, 
                            model_configs: List[Dict[str, Any]],
                            contour_pairs: List[Tuple],
                            labels: List[int]) -> Dict[str, Dict[str, Any]]:
        """
        Train multiple models and compare results
        
        Args:
            model_configs: List of model configurations
            contour_pairs: Training data
            labels: Training labels
            
        Returns:
            Dictionary of results for each model
        """
        self.progress.start()
        all_results = {}
        
        # Extract features once for all models
        self.progress.update_stage("Extracting Features for All Models", 10)
        features = self._extract_features_parallel(contour_pairs)
        
        # Split data once
        self.progress.update_stage("Splitting Data", 15)
        X_train, X_test, y_train, y_test = self._split_data(features, labels)

        # Train each model
        total_models = len(model_configs)
        for i, model_config in enumerate(model_configs):
            model_name = model_config.get('name', f"Model_{i+1}")
            
            try:
                progress = 20 + (i * 70 / total_models)
                self.progress.update_stage(f"Training {model_name}", progress)
                
                # Create and train model
                model = self._create_model(model_config)
                
                training_start_time = time.time()
                model.fit(X_train, y_train)
                training_time = time.time() - training_start_time
                
                # Evaluate model
                evaluation_results = self._evaluate_model(model, X_test, y_test)
                
                # Compile results
                results = self._compile_results(
                    model, evaluation_results, training_time,
                    X_train, X_test, y_train, y_test
                )
                
                all_results[model_name] = results
                
                print(f"✅ {model_name} complete - Accuracy: {results['metrics']['accuracy']:.3f}")
                
            except Exception as e:
                error_msg = f"Failed to train {model_name}: {str(e)}"
                self.progress.add_error(error_msg)
                print(f"❌ {error_msg}")
                continue
        
        self.progress.update_stage("All Models Complete", 100)
        
        # Find best model
        if all_results:
            best_model_name = max(all_results.keys(), 
                                key=lambda k: all_results[k]['metrics']['accuracy'])
            print(f"🏆 Best model: {best_model_name} (Accuracy: {all_results[best_model_name]['metrics']['accuracy']:.3f})")
        
        return all_results
    
    def _validate_training_data(self, contour_pairs: List[Tuple], labels: List[int]):
        """Validate training data"""
        try:
            validate_dataset_pairs(contour_pairs, labels)
            
            # Check class balance
            unique_labels, counts = np.unique(labels, return_counts=True)
            balance_ratio = min(counts) / max(counts)
            
            if balance_ratio < 0.3:
                warning = f"Class imbalance detected: ratio {balance_ratio:.3f}"
                self.progress.add_warning(warning)
                print(f"⚠️ {warning}")
            
            print(f"📊 Dataset validated: {len(contour_pairs)} pairs, balance ratio: {balance_ratio:.3f}")
            
        except Exception as e:
            raise ValueError(f"Data validation failed: {e}")
    
    def _extract_features_parallel(self, contour_pairs: List[Tuple]) -> np.ndarray:
        """Extract features from contour pairs in parallel"""
        try:
            print(f"🔄 Extracting features from {len(contour_pairs):,} pairs...")
            
            # Use parallel processing
            n_cores = min(mp.cpu_count(), 8)
            batch_size = 1000
            
            features = []
            completed = 0
            total_pairs = len(contour_pairs)
            
            # Create a partial function that's picklable
            worker_func = partial(compute_features_for_pair, extractor=self.feature_extractor)

            for i in range(0, total_pairs, batch_size):
                batch_pairs = contour_pairs[i:i+batch_size]
                
                with ProcessPoolExecutor(max_workers=n_cores) as executor:
                    batch_features = list(executor.map(worker_func, batch_pairs))
                    features.extend(batch_features)
                
                completed += len(batch_pairs)
                progress_pct = (completed / total_pairs) * 100
                print(f"   📈 Progress: {completed:,}/{total_pairs:,} pairs ({progress_pct:.1f}%)")
            
            features_array = np.array(features)
            print(f"✅ Feature extraction complete: {features_array.shape}")
            
            return features_array
            
        except Exception as e:
            raise RuntimeError(f"Feature extraction failed: {e}")
    
    def _split_data(self, 
                   features: np.ndarray, 
                   labels: List[int], 
                   validation_split: Optional[float] = None) -> Tuple:
        """Split data into train/test sets"""
        try:
            test_size = validation_split or self.config.training.test_size
            random_state = self.config.training.random_state
            
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, 
                test_size=test_size, 
                random_state=random_state,
                stratify=labels
            )
            
            # Validate split data
            validate_training_data(X_train, np.array(y_train))
            validate_training_data(X_test, np.array(y_test))
            
            print(f"📊 Data split: Train={len(X_train):,}, Test={len(X_test):,}")
            
            return X_train, X_test, y_train, y_test
            
        except Exception as e:
            raise RuntimeError(f"Data splitting failed: {e}")
    
    def _create_model(self, model_config: Dict[str, Any]) -> BaseModel:
        """Create model from configuration"""
        try:
            model_type = model_config.get('type', 'sgd')
            config = model_config.get('config', {})
            
            model = ModelFactory.create_model(model_type, config)
            
            # Set feature names if available
            if hasattr(self.feature_extractor, 'get_feature_names'):
                feature_names = self.feature_extractor.get_feature_names()
                model.set_feature_names(feature_names)
            
            return model
            
        except Exception as e:
            raise RuntimeError(f"Model creation failed: {e}")
    
    def _evaluate_model(self, model: BaseModel, X_test: np.ndarray, y_test: List[int]) -> Dict[str, Any]:
        """Evaluate trained model"""
        try:
            # Get evaluation results
            evaluation = evaluate_model_performance(model, X_test, y_test)
            
            # Add prediction timing
            start_time = time.time()
            _ = model.predict(X_test[:100])  # Time 100 predictions
            prediction_time = (time.time() - start_time) / 100
            
            evaluation['prediction_time_per_sample'] = prediction_time
            
            return evaluation
            
        except Exception as e:
            raise RuntimeError(f"Model evaluation failed: {e}")
    
    def _compile_results(self, 
                        model: BaseModel,
                        evaluation_results: Dict[str, Any],
                        training_time: float,
                        X_train: np.ndarray,
                        X_test: np.ndarray,
                        y_train: List[int],
                        y_test: List[int]) -> Dict[str, Any]:
        """Compile comprehensive training results"""
        
        results = {
            'model': model,
            'model_info': model.get_model_info(),
            'metrics': evaluation_results['metrics'],
            'predictions': evaluation_results['predictions'],
            'test_data': (X_test, y_test),
            'training_time': training_time,
            'feature_extractor_info': self.feature_extractor.get_metadata(),
            'data_info': {
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'feature_count': X_train.shape[1],
                'train_class_distribution': dict(zip(*np.unique(y_train, return_counts=True))),
                'test_class_distribution': dict(zip(*np.unique(y_test, return_counts=True)))
            },
            'training_progress': self.progress.to_dict()
        }
        
        # Add feature importance if available
        feature_importance = model.get_feature_importance()
        if feature_importance is not None:
            results['feature_importance'] = feature_importance
            
            # Get feature names if available
            if hasattr(self.feature_extractor, 'get_feature_names'):
                feature_names = self.feature_extractor.get_feature_names()
                results['feature_names'] = feature_names
        
        return results
    
    def get_training_summary(self, results: Dict[str, Any]) -> str:
        """Generate human-readable training summary"""
        summary_lines = []
        
        # Model info
        model_info = results['model_info']
        summary_lines.append(f"Model: {model_info['model_type']}")
        summary_lines.append(f"Training Time: {results['training_time']:.2f}s")
        
        # Performance metrics
        metrics = results['metrics']
        summary_lines.append(f"Accuracy: {metrics['accuracy']:.3f}")
        summary_lines.append(f"Precision: {metrics['precision']:.3f}")
        summary_lines.append(f"Recall: {metrics['recall']:.3f}")
        summary_lines.append(f"F1-Score: {metrics['f1_score']:.3f}")
        
        # Data info
        data_info = results['data_info']
        summary_lines.append(f"Training Samples: {data_info['train_samples']:,}")
        summary_lines.append(f"Test Samples: {data_info['test_samples']:,}")
        summary_lines.append(f"Features: {data_info['feature_count']}")
        
        # Warnings and errors
        progress = results['training_progress']
        if progress['n_warnings'] > 0:
            summary_lines.append(f"Warnings: {progress['n_warnings']}")
        if progress['n_errors'] > 0:
            summary_lines.append(f"Errors: {progress['n_errors']}")
        
        return "\n".join(summary_lines)