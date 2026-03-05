"""
Pair Generator Module

Provides functionality for generating balanced training pairs from contour datasets
with configurable positive/negative pair strategies.
"""

import random
import itertools
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from .synthetic_dataset import SyntheticContour


class PairGenerator:
    """
    Generates balanced positive and negative pairs from contour datasets
    for training shape similarity models.
    """
    
    def __init__(self, 
                 include_hard_negatives: bool = True,
                 balance_strategy: str = 'downsample',
                 max_pairs_per_object: Optional[int] = None,
                 random_state: int = 42):
        """
        Initialize pair generator
        
        Args:
            include_hard_negatives: Whether to prioritize hard negative pairs
            balance_strategy: Strategy for balancing pairs ('downsample', 'upsample', 'weighted')
            max_pairs_per_object: Maximum pairs per object ID (None = no limit)
            random_state: Random seed for reproducibility
        """
        self.include_hard_negatives = include_hard_negatives
        self.balance_strategy = balance_strategy
        self.max_pairs_per_object = max_pairs_per_object
        self.random_state = random_state
        random.seed(random_state)
    
    def generate_balanced_pairs(self, 
                              contours: List[SyntheticContour]) -> Tuple[List[Tuple], List[int]]:
        """
        Generate balanced positive and negative pairs from contour dataset
        
        Args:
            contours: List of synthetic contours with metadata
            
        Returns:
            Tuple of (pairs, labels) where pairs are (contour1, contour2) tuples
        """
        print("🔄 Generating balanced training pairs...")
        
        # Group contours by object ID
        grouped = self._group_by_object_id(contours)
        object_ids = list(grouped.keys())
        
        print(f"📊 Found {len(object_ids)} unique object types")
        print(f"📊 Object distribution: {[(oid, len(contours)) for oid, contours in grouped.items()]}")
        
        # Generate positive pairs
        pairs_pos = self._generate_positive_pairs(grouped)
        print(f"   ✅ Generated {len(pairs_pos):,} positive pairs")
        
        # Generate negative pairs
        pairs_neg = self._generate_negative_pairs(grouped, object_ids)
        print(f"   ✅ Generated {len(pairs_neg):,} negative pairs")
        
        # Balance the dataset
        balanced_pairs, labels = self._balance_pairs(pairs_pos, pairs_neg)
        
        print(f"✅ Final dataset: {len(balanced_pairs):,} pairs")
        print(f"   Positive: {sum(labels):,} ({sum(labels)/len(labels)*100:.1f}%)")
        print(f"   Negative: {len(labels)-sum(labels):,} ({(len(labels)-sum(labels))/len(labels)*100:.1f}%)")
        
        return balanced_pairs, labels
    
    def generate_hard_negative_pairs(self, 
                                   contours: List[SyntheticContour],
                                   hard_negative_ratio: float = 0.3) -> Tuple[List[Tuple], List[int]]:
        """
        Generate pairs with emphasis on hard negatives (similar-looking different shapes)
        
        Args:
            contours: List of synthetic contours
            hard_negative_ratio: Proportion of negative pairs that should be hard negatives
            
        Returns:
            Tuple of (pairs, labels)
        """
        from ..shape_factory import ShapeFactory
        
        print(f"🎯 Generating pairs with {hard_negative_ratio*100:.0f}% hard negatives...")
        
        grouped = self._group_by_object_id(contours)
        object_ids = list(grouped.keys())
        
        # Get hard negative shape pairs
        hard_negative_shapes = ShapeFactory.get_hard_negative_pairs()
        
        # Generate positive pairs (same as before)
        pairs_pos = self._generate_positive_pairs(grouped)
        
        # Generate hard negative pairs
        hard_negative_pairs = []
        for shape1, shape2 in hard_negative_shapes:
            shape1_objects = [oid for oid in object_ids if shape1.value in oid]
            shape2_objects = [oid for oid in object_ids if shape2.value in oid]
            
            for oid1 in shape1_objects:
                for oid2 in shape2_objects:
                    contours1 = grouped[oid1]
                    contours2 = grouped[oid2]
                    
                    # Sample pairs between these hard negative shapes
                    n_pairs = min(len(contours1) * len(contours2), 50)  # Limit pairs
                    for _ in range(n_pairs):
                        c1 = random.choice(contours1)
                        c2 = random.choice(contours2)
                        hard_negative_pairs.append((c1.contour, c2.contour))
        
        print(f"   Generated {len(hard_negative_pairs):,} hard negative pairs")
        
        # Generate regular negative pairs
        total_negative_needed = len(pairs_pos)
        hard_negative_count = int(total_negative_needed * hard_negative_ratio)
        regular_negative_count = total_negative_needed - hard_negative_count
        
        # Sample from hard negatives
        sampled_hard_negatives = random.sample(
            hard_negative_pairs, 
            min(hard_negative_count, len(hard_negative_pairs))
        )
        
        # Generate regular negatives to fill the rest
        regular_negatives = self._generate_regular_negative_pairs(
            grouped, object_ids, regular_negative_count, exclude_hard_negatives=True
        )
        
        # Combine all pairs
        all_negative_pairs = sampled_hard_negatives + regular_negatives
        all_pairs = pairs_pos + all_negative_pairs
        labels = [1] * len(pairs_pos) + [0] * len(all_negative_pairs)
        
        # Shuffle
        combined = list(zip(all_pairs, labels))
        random.shuffle(combined)
        final_pairs, final_labels = zip(*combined)
        
        print(f"✅ Hard negative dataset: {len(final_pairs):,} pairs")
        print(f"   Hard negatives: {len(sampled_hard_negatives):,}")
        print(f"   Regular negatives: {len(regular_negatives):,}")
        
        return list(final_pairs), list(final_labels)
    
    def generate_stratified_pairs(self, 
                                contours: List[SyntheticContour],
                                pairs_per_object: int = 100) -> Tuple[List[Tuple], List[int]]:
        """
        Generate stratified pairs ensuring equal representation per object type
        
        Args:
            contours: List of synthetic contours
            pairs_per_object: Number of positive pairs per object type
            
        Returns:
            Tuple of (pairs, labels)
        """
        print(f"📊 Generating stratified pairs ({pairs_per_object} per object)...")
        
        grouped = self._group_by_object_id(contours)
        
        all_pairs = []
        all_labels = []
        
        # Generate equal positive pairs per object
        for object_id, object_contours in grouped.items():
            if len(object_contours) < 2:
                continue
            
            # Generate positive pairs for this object
            object_pairs = []
            for c1, c2 in itertools.combinations(object_contours, 2):
                object_pairs.append((c1.contour, c2.contour))
            
            # Sample desired number
            if len(object_pairs) > pairs_per_object:
                object_pairs = random.sample(object_pairs, pairs_per_object)
            
            all_pairs.extend(object_pairs)
            all_labels.extend([1] * len(object_pairs))
        
        # Generate equal negative pairs
        negative_pairs_needed = len(all_pairs)
        negative_pairs = self._generate_random_negative_pairs(
            grouped, list(grouped.keys()), negative_pairs_needed
        )
        
        all_pairs.extend(negative_pairs)
        all_labels.extend([0] * len(negative_pairs))
        
        # Shuffle
        combined = list(zip(all_pairs, all_labels))
        random.shuffle(combined)
        final_pairs, final_labels = zip(*combined)
        
        print(f"✅ Stratified dataset: {len(final_pairs):,} pairs")
        
        return list(final_pairs), list(final_labels)
    
    def _group_by_object_id(self, contours: List[SyntheticContour]) -> Dict[str, List[SyntheticContour]]:
        """Group contours by their object ID"""
        grouped = {}
        for contour in contours:
            grouped.setdefault(contour.object_id, []).append(contour)
        return grouped
    
    def _generate_positive_pairs(self, grouped: Dict[str, List[SyntheticContour]]) -> List[Tuple]:
        """Generate positive pairs (same object ID)"""
        pairs_pos = []
        
        for object_id, object_contours in grouped.items():
            # Generate all combinations within this object
            object_pairs = []
            for c1, c2 in itertools.combinations(object_contours, 2):
                object_pairs.append((c1.contour, c2.contour))
            
            # Apply max pairs limit if set
            if self.max_pairs_per_object and len(object_pairs) > self.max_pairs_per_object:
                object_pairs = random.sample(object_pairs, self.max_pairs_per_object)
            
            pairs_pos.extend(object_pairs)
        
        return pairs_pos
    
    def _generate_negative_pairs(self, 
                               grouped: Dict[str, List[SyntheticContour]], 
                               object_ids: List[str]) -> List[Tuple]:
        """Generate negative pairs (different object IDs)"""
        pairs_neg = []
        
        # Calculate total possible combinations
        total_combinations = sum(
            len(grouped[object_ids[i]]) * len(grouped[object_ids[j]])
            for i in range(len(object_ids))
            for j in range(i + 1, len(object_ids))
        )
        
        print(f"   Total possible negative combinations: {total_combinations:,}")
        
        # Generate negative pairs
        pair_count = 0
        for i in range(len(object_ids)):
            for j in range(i + 1, len(object_ids)):
                contours_i = grouped[object_ids[i]]
                contours_j = grouped[object_ids[j]]
                
                # Generate all combinations between these two objects
                for c1 in contours_i:
                    for c2 in contours_j:
                        pairs_neg.append((c1.contour, c2.contour))
                        pair_count += 1
            
            # Progress update
            if (i + 1) % 5 == 0:
                progress = pair_count / total_combinations * 100 if total_combinations > 0 else 0
                print(f"   📈 Progress: {pair_count:,}/{total_combinations:,} pairs ({progress:.1f}%)")
        
        return pairs_neg
    
    def _generate_regular_negative_pairs(self, 
                                       grouped: Dict[str, List[SyntheticContour]],
                                       object_ids: List[str],
                                       count: int,
                                       exclude_hard_negatives: bool = False) -> List[Tuple]:
        """Generate regular negative pairs, optionally excluding hard negatives"""
        from ..shape_factory import ShapeFactory
        
        pairs_neg = []
        hard_negative_shapes = set()
        
        if exclude_hard_negatives:
            # Get shape pairs that are hard negatives
            for shape1, shape2 in ShapeFactory.get_hard_negative_pairs():
                hard_negative_shapes.add((shape1.value, shape2.value))
                hard_negative_shapes.add((shape2.value, shape1.value))
        
        attempts = 0
        max_attempts = count * 10  # Prevent infinite loop
        
        while len(pairs_neg) < count and attempts < max_attempts:
            # Randomly select two different objects
            obj1, obj2 = random.sample(object_ids, 2)
            
            # Check if this is a hard negative pair (if excluding)
            if exclude_hard_negatives:
                shape1 = obj1.split('_')[0]  # Extract shape from object_id
                shape2 = obj2.split('_')[0]
                if (shape1, shape2) in hard_negative_shapes:
                    attempts += 1
                    continue
            
            # Select random contours from each object
            c1 = random.choice(grouped[obj1])
            c2 = random.choice(grouped[obj2])
            
            pairs_neg.append((c1.contour, c2.contour))
            attempts += 1
        
        return pairs_neg
    
    def _generate_random_negative_pairs(self, 
                                      grouped: Dict[str, List[SyntheticContour]],
                                      object_ids: List[str],
                                      count: int) -> List[Tuple]:
        """Generate random negative pairs"""
        pairs_neg = []
        
        for _ in range(count):
            # Randomly select two different objects
            obj1, obj2 = random.sample(object_ids, 2)
            
            # Select random contours from each object
            c1 = random.choice(grouped[obj1])
            c2 = random.choice(grouped[obj2])
            
            pairs_neg.append((c1.contour, c2.contour))
        
        return pairs_neg
    
    def _balance_pairs(self, 
                      pairs_pos: List[Tuple], 
                      pairs_neg: List[Tuple]) -> Tuple[List[Tuple], List[int]]:
        """Balance positive and negative pairs according to strategy"""
        
        if self.balance_strategy == 'downsample':
            # Downsample to the smaller set
            n = min(len(pairs_pos), len(pairs_neg))
            balanced_pos = random.sample(pairs_pos, n)
            balanced_neg = random.sample(pairs_neg, n)
            
        elif self.balance_strategy == 'upsample':
            # Upsample the smaller set
            n = max(len(pairs_pos), len(pairs_neg))
            
            if len(pairs_pos) < n:
                # Upsample positive pairs
                additional_needed = n - len(pairs_pos)
                additional_pos = random.choices(pairs_pos, k=additional_needed)
                balanced_pos = pairs_pos + additional_pos
                balanced_neg = pairs_neg
            else:
                # Upsample negative pairs
                additional_needed = n - len(pairs_neg)
                additional_neg = random.choices(pairs_neg, k=additional_needed)
                balanced_pos = pairs_pos
                balanced_neg = pairs_neg + additional_neg
                
        else:  # weighted or other strategies
            # For now, just use downsampling as default
            n = min(len(pairs_pos), len(pairs_neg))
            balanced_pos = random.sample(pairs_pos, n)
            balanced_neg = random.sample(pairs_neg, n)
        
        # Combine and shuffle
        all_pairs = balanced_pos + balanced_neg
        labels = [1] * len(balanced_pos) + [0] * len(balanced_neg)
        
        # Shuffle pairs and labels together
        combined = list(zip(all_pairs, labels))
        random.shuffle(combined)
        shuffled_pairs, shuffled_labels = zip(*combined)
        
        return list(shuffled_pairs), list(shuffled_labels)
    
    def get_pair_statistics(self, 
                          pairs: List[Tuple], 
                          labels: List[int],
                          contours: List[SyntheticContour]) -> Dict[str, Any]:
        """Get statistics about generated pairs"""
        
        stats = {
            'total_pairs': len(pairs),
            'positive_pairs': sum(labels),
            'negative_pairs': len(labels) - sum(labels),
            'balance_ratio': sum(labels) / len(labels) if labels else 0,
            'unique_contours_used': len(set(id(c) for pair in pairs for c in pair)),
            'shape_pair_distribution': {}
        }
        
        # Analyze shape pair distribution
        contour_to_shape = {}
        for contour in contours:
            contour_id = id(contour.contour)  # Use object id as unique identifier
            contour_to_shape[contour_id] = contour.shape_type.value
        
        for pair, label in zip(pairs, labels):
            c1_id, c2_id = id(pair[0]), id(pair[1])
            shape1 = contour_to_shape.get(c1_id, 'unknown')
            shape2 = contour_to_shape.get(c2_id, 'unknown')
            
            # Create consistent shape pair key
            if shape1 <= shape2:
                shape_pair = f"{shape1}_vs_{shape2}"
            else:
                shape_pair = f"{shape2}_vs_{shape1}"
            
            pair_type = 'positive' if label == 1 else 'negative'
            
            if shape_pair not in stats['shape_pair_distribution']:
                stats['shape_pair_distribution'][shape_pair] = {'positive': 0, 'negative': 0}
            
            stats['shape_pair_distribution'][shape_pair][pair_type] += 1
        
        return stats