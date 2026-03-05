"""
I/O Utilities Module

Provides utilities for loading and saving models, datasets, and configurations
with comprehensive metadata management and versioning.
"""

import os
import json
import pickle
import joblib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import shutil


class ModelMetadata:
    """
    Manages model metadata including feature extraction requirements,
    training information, and compatibility details.
    """
    
    def __init__(self, 
                 model_name: str,
                 accuracy: float,
                 training_config: Optional[Dict] = None,
                 feature_metadata: Optional[Dict] = None,
                 dataset_info: Optional[Dict] = None):
        self.model_id = self._generate_model_id()
        self.model_name = model_name
        self.accuracy = accuracy
        self.timestamp = datetime.now()
        self.training_config = training_config or {}
        self.feature_metadata = feature_metadata or {}
        self.dataset_info = dataset_info or {}
    
    def _generate_model_id(self) -> str:
        """Generate unique model ID based on timestamp"""
        return f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for serialization"""
        return {
            'model_info': {
                'model_id': self.model_id,
                'model_name': self.model_name,
                'accuracy': self.accuracy,
                'timestamp': self.model_id.split('_', 1)[1],
                'training_date': self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            },
            'feature_extraction': self.feature_metadata,
            'dataset_info': self.dataset_info,
            'training_config': self.training_config,
            'compatibility': {
                'required_features': self.feature_metadata.get('total_features', 'unknown'),
                'feature_version': self.feature_metadata.get('feature_extraction_version', 'unknown'),
                'curvature_bins': self.feature_metadata.get('curvature_bins', 'unknown')
            }
        }
    
    @classmethod
    def from_dict(cls, metadata_dict: Dict[str, Any]) -> 'ModelMetadata':
        """Create metadata from dictionary"""
        model_info = metadata_dict.get('model_info', {})
        
        metadata = cls(
            model_name=model_info.get('model_name', 'Unknown'),
            accuracy=model_info.get('accuracy', 0.0),
            training_config=metadata_dict.get('training_config', {}),
            feature_metadata=metadata_dict.get('feature_extraction', {}),
            dataset_info=metadata_dict.get('dataset_info', {})
        )
        
        # Restore original model_id and timestamp if available
        if 'model_id' in model_info:
            metadata.model_id = model_info['model_id']
        if 'training_date' in model_info:
            try:
                metadata.timestamp = datetime.strptime(
                    model_info['training_date'], "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                pass  # Keep current timestamp
        
        return metadata


def save_model(model: Any, 
               model_name: str, 
               accuracy: float,
               save_dir: Union[str, Path] = "saved_models",
               training_config: Optional[Dict] = None,
               feature_metadata: Optional[Dict] = None,
               dataset_info: Optional[Dict] = None) -> Tuple[Path, Path]:
    """
    Save trained model with comprehensive metadata in timestamped folder
    
    Args:
        model: Trained model object to save
        model_name: Name/type of the model
        accuracy: Model accuracy for filename
        save_dir: Directory to save models in
        training_config: Training configuration used
        feature_metadata: Feature extraction metadata
        dataset_info: Dataset generation information
        
    Returns:
        Tuple of (model_filepath, model_folder_path)
    """
    # Ensure save_dir is Path object
    save_dir = Path(save_dir)
    
    # Create metadata
    metadata = ModelMetadata(
        model_name=model_name,
        accuracy=accuracy,
        training_config=training_config,
        feature_metadata=feature_metadata,
        dataset_info=dataset_info
    )
    
    # Create timestamped folder
    model_folder = save_dir / metadata.model_id
    model_folder.mkdir(parents=True, exist_ok=True)
    
    # Create filename  
    safe_model_name = model_name.replace(' ', '_').replace('(', '').replace(')', '')
    filename = f"{safe_model_name}_acc{accuracy:.3f}.pkl"
    model_filepath = model_folder / filename
    
    # Save model
    joblib.dump(model, model_filepath)
    
    # Save metadata
    metadata_file = model_folder / "metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata.to_dict(), f, indent=2, default=str)
    
    # Save summary file for quick reference
    summary_file = model_folder / "summary.txt"
    _save_model_summary(summary_file, metadata, filename, dataset_info)
    
    print(f"💾 Model saved in folder: {model_folder}")
    print(f"📄 Files created:")
    print(f"   - {filename} (trained model)")
    print(f"   - metadata.json (detailed metadata)")
    print(f"   - summary.txt (quick summary)")
    
    return model_filepath, model_folder


def _save_model_summary(summary_file: Path, 
                       metadata: ModelMetadata,
                       filename: str, 
                       dataset_info: Optional[Dict]) -> None:
    """Save a human-readable summary file"""
    with open(summary_file, 'w') as f:
        f.write(f"Model Summary\n")
        f.write(f"=============\n")
        f.write(f"Model: {metadata.model_name}\n")
        f.write(f"Accuracy: {metadata.accuracy:.3f}\n")
        f.write(f"Trained: {metadata.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Features: {metadata.feature_metadata.get('total_features', 'unknown')}\n")
        f.write(f"Feature Version: {metadata.feature_metadata.get('feature_extraction_version', 'unknown')}\n")
        
        if dataset_info:
            f.write(f"Dataset: {dataset_info.get('pairs_file', 'unknown')}\n")
            f.write(f"Training pairs: {dataset_info.get('total_training_pairs', 'unknown')}\n")
        else:
            f.write(f"Dataset: unknown\n")
            f.write(f"Training pairs: unknown\n")


def load_model(filepath: Union[str, Path]) -> Any:
    """
    Load a saved model from file
    
    Args:
        filepath: Path to the model file
        
    Returns:
        Loaded model object
        
    Raises:
        FileNotFoundError: If model file doesn't exist
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"Model file not found: {filepath}")
    
    model = joblib.load(filepath)
    print(f"📂 Model loaded: {filepath}")
    
    return model


def list_saved_models(save_dir: Union[str, Path] = "saved_models") -> List[Dict[str, Any]]:
    """
    List all saved models with their metadata
    
    Args:
        save_dir: Directory containing saved models
        
    Returns:
        List of model information dictionaries
    """
    save_dir = Path(save_dir)
    
    if not save_dir.exists():
        print(f"No saved models directory found in {save_dir}.")
        return []
    
    model_info = []
    
    # Look for timestamped model folders
    model_folders = [
        f for f in save_dir.iterdir() 
        if f.is_dir() and f.name.startswith('model_')
    ]
    
    for folder in model_folders:
        # Find .pkl files in the folder
        pkl_files = list(folder.glob('*.pkl'))
        
        for pkl_file in pkl_files:
            # Load metadata if available
            metadata_file = folder / "metadata.json"
            metadata = None
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                except Exception as e:
                    print(f"Warning: Could not read metadata for {pkl_file}: {e}")
            
            # Extract timestamp from folder name for sorting
            timestamp = folder.name.replace('model_', '')
            
            model_info.append({
                'path': pkl_file,
                'filename': pkl_file.name,
                'folder': folder.name,
                'timestamp': timestamp,
                'metadata': metadata,
                'format': 'timestamped'
            })
    
    # Also look for direct .pkl files (backward compatibility)
    direct_files = [f for f in save_dir.glob('*.pkl')]
    for pkl_file in direct_files:
        timestamp = str(int(pkl_file.stat().st_mtime))
        model_info.append({
            'path': pkl_file,
            'filename': pkl_file.name,
            'folder': None,
            'timestamp': timestamp,
            'metadata': None,
            'format': 'direct'
        })
    
    # Sort by timestamp (most recent first)
    model_info.sort(key=lambda x: x['timestamp'], reverse=True)
    
    print(f"📋 Found {len(model_info)} saved models:")
    for i, info in enumerate(model_info, 1):
        if info['format'] == 'timestamped':
            acc = 'unknown'
            if info['metadata'] and 'model_info' in info['metadata']:
                acc = info['metadata']['model_info'].get('accuracy', 'unknown')
            print(f"   {i}. {info['filename']} (acc: {acc}, in {info['folder']})")
        else:
            print(f"   {i}. {info['filename']} (direct file)")
    
    return model_info


def get_latest_model(save_dir: Union[str, Path] = "saved_models") -> Path:
    """
    Get the path to the most recently saved model
    
    Args:
        save_dir: Directory containing saved models
        
    Returns:
        Path to the latest model file
        
    Raises:
        FileNotFoundError: If no models are found
    """
    model_info = list_saved_models(save_dir)
    if not model_info:
        raise FileNotFoundError("No saved models found. Please run training first to create a model.")
    
    latest_info = model_info[0]  # Already sorted by timestamp (most recent first)
    filepath = latest_info['path']
    
    print(f"📂 Latest model: {latest_info['filename']}")
    if latest_info['format'] == 'timestamped':
        print(f"   Located in: {latest_info['folder']}")
    
    return filepath


def load_latest_model(save_dir: Union[str, Path] = "saved_models") -> Any:
    """
    Load the most recently saved model
    
    Args:
        save_dir: Directory containing saved models
        
    Returns:
        Loaded model object
    """
    latest_path = get_latest_model(save_dir)
    return load_model(latest_path)


def get_model_metadata(model_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Get metadata for a saved model
    
    Args:
        model_path: Path to model file
        
    Returns:
        Model metadata dictionary
    """
    model_path = Path(model_path)
    model_dir = model_path.parent
    
    # Look for metadata.json in the same directory
    metadata_file = model_dir / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read metadata.json: {e}")
    
    # Fallback: extract basic info from filename
    return {
        'filename': model_path.name,
        'timestamp': 'Unknown',
        'model_name': 'Unknown',
        'accuracy': 'Unknown',
        'note': 'No metadata file found'
    }


def cleanup_old_models(save_dir: Union[str, Path] = "saved_models", 
                      keep_latest: int = 5) -> int:
    """
    Delete old models, keeping only the most recent ones
    
    Args:
        save_dir: Directory containing saved models
        keep_latest: Number of latest models to keep
        
    Returns:
        Number of models deleted
    """
    model_info = list_saved_models(save_dir)
    
    if len(model_info) <= keep_latest:
        print(f"📋 Only {len(model_info)} models found, nothing to delete")
        return 0
    
    models_to_delete = model_info[keep_latest:]
    deleted_count = 0
    
    for info in models_to_delete:
        try:
            if info['format'] == 'timestamped':
                # Delete entire folder
                folder_path = Path(save_dir) / info['folder']
                shutil.rmtree(folder_path)
                print(f"   🗑️ Deleted folder: {info['folder']}")
            else:
                # Delete direct file
                info['path'].unlink()
                print(f"   🗑️ Deleted file: {info['filename']}")
            
            deleted_count += 1
            
        except Exception as e:
            item_name = info['folder'] if info['format'] == 'timestamped' else info['filename']
            print(f"   ❌ Failed to delete {item_name}: {e}")
    
    print(f"🧹 Cleanup complete: deleted {deleted_count} old models, kept {keep_latest} latest")
    return deleted_count


def save_dataset(dataset: Any,
                 pairs: List,
                 labels: List,
                 save_dir: Union[str, Path] = "saved_datasets",
                 dataset_config: Optional[Dict] = None) -> Tuple[Path, Path]:
    """
    Save dataset with metadata in timestamped folder
    
    Args:
        dataset: Original dataset object
        pairs: Training pairs
        labels: Corresponding labels
        save_dir: Directory to save datasets
        dataset_config: Dataset generation configuration
        
    Returns:
        Tuple of (dataset_filepath, dataset_folder_path)
    """
    save_dir = Path(save_dir)
    
    # Create timestamped folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_folder = save_dir / f"dataset_{timestamp}"
    dataset_folder.mkdir(parents=True, exist_ok=True)
    
    # Save training pairs
    pairs_file = dataset_folder / "training_pairs.pkl"
    with open(pairs_file, 'wb') as f:
        pickle.dump({'pairs': pairs, 'labels': labels}, f)
    
    # Save metadata
    metadata = {
        'dataset_info': {
            'timestamp': timestamp,
            'creation_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_pairs': len(pairs),
            'positive_pairs': sum(labels),
            'negative_pairs': len(labels) - sum(labels)
        },
        'generation_config': dataset_config or {},
        'files': {
            'pairs_file': 'training_pairs.pkl'
        }
    }
    
    metadata_file = dataset_folder / "metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)
    
    # Save summary
    summary_file = dataset_folder / "summary.txt"
    with open(summary_file, 'w') as f:
        f.write(f"Dataset Summary\n")
        f.write(f"===============\n")
        f.write(f"Created: {metadata['dataset_info']['creation_date']}\n")
        f.write(f"Total pairs: {metadata['dataset_info']['total_pairs']:,}\n")
        f.write(f"Positive pairs: {metadata['dataset_info']['positive_pairs']:,}\n")
        f.write(f"Negative pairs: {metadata['dataset_info']['negative_pairs']:,}\n")
    
    print(f"💾 Dataset saved in folder: {dataset_folder}")
    return pairs_file, dataset_folder


def load_dataset(filepath: Union[str, Path]) -> Tuple[List, List]:
    """
    Load saved dataset
    
    Args:
        filepath: Path to the dataset file
        
    Returns:
        Tuple of (pairs, labels)
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"Dataset file not found: {filepath}")
    
    with open(filepath, 'rb') as f:
        data = pickle.load(f)
    
    return data['pairs'], data['labels']


def predict_similarity(model, contour1, contour2):
    """
    Compatibility function for the old predict_similarity interface.
    
    Use trained model to predict similarity between two contours.
    
    Args:
        model: Trained model (should have predict and predict_proba methods)
        contour1: First contour (numpy array)
        contour2: Second contour (numpy array)
        
    Returns:
        Tuple of (result, confidence, features) where:
        - result: "SAME", "DIFFERENT", or "UNCERTAIN"
        - confidence: Confidence score (0-1)
        - features: Extracted features used for prediction
    """
    from ..core.features.base_extractor import FeatureExtractorFactory
    
    # Create feature extractor (using same features as original system)
    extractor_configs = [
        {'name': 'geometric'},
        {'name': 'hu', 'config': {'use_log_transform': True}}
    ]
    extractor = FeatureExtractorFactory.create_composite_extractor(extractor_configs)
    
    # Extract features from both contours
    features1 = extractor.extract_features(contour1)
    features2 = extractor.extract_features(contour2)
    
    # Combine features (same as old compute_enhanced_features)
    features = features1 + features2
    
    # Make prediction
    prediction = model.predict([features])[0]
    probability = model.predict_proba([features])[0]
    confidence = max(probability)
    
    # Apply confidence thresholds (same logic as old system)
    if prediction == 1:  # SAME
        conf_low = 0.8
        conf_high = 0.95
        
        if conf_low < confidence < conf_high:
            return "UNCERTAIN", confidence, features
        elif confidence < conf_low:
            return "DIFFERENT", confidence, features
        else:
            return "SAME", confidence, features
    else:  # DIFFERENT
        conf_low = 0.8
        conf_high = 0.95
        
        if conf_low < confidence < conf_high:
            return "UNCERTAIN", confidence, features
        elif confidence < conf_low:
            return "SAME", confidence, features
        else:
            return "DIFFERENT", confidence, features