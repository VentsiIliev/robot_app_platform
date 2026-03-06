"""
Pair Generator Module

Provides functionality for generating balanced training pairs from contour datasets
with configurable positive/negative pair strategies.
"""

import logging
import random
import itertools
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from .synthetic_dataset import SyntheticContour
from .shape_factory import ShapeFactory

_logger = logging.getLogger(__name__)


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
        self.include_hard_negatives = include_hard_negatives
        self.balance_strategy = balance_strategy
        self.max_pairs_per_object = max_pairs_per_object
        self.random_state = random_state
        random.seed(random_state)

    def generate_balanced_pairs(self,
                                contours: List[SyntheticContour]) -> Tuple[List[Tuple], List[int]]:
        _logger.info("Generating balanced training pairs...")

        grouped = self._group_by_object_id(contours)
        object_ids = list(grouped.keys())

        _logger.debug("Found %d unique object types", len(object_ids))
        _logger.debug("Object distribution: %s", [(oid, len(c)) for oid, c in grouped.items()])

        pairs_pos = self._generate_positive_pairs(grouped)
        _logger.info("Generated %d positive pairs", len(pairs_pos))

        pairs_neg = self._generate_negative_pairs(grouped, object_ids)
        _logger.info("Generated %d negative pairs", len(pairs_neg))

        balanced_pairs, labels = self._balance_pairs(pairs_pos, pairs_neg)

        n_pos = sum(labels)
        n_neg = len(labels) - n_pos
        _logger.info(
            "Final dataset: %d pairs — positive: %d (%.1f%%), negative: %d (%.1f%%)",
            len(balanced_pairs),
            n_pos, n_pos / len(labels) * 100,
            n_neg, n_neg / len(labels) * 100,
        )

        return balanced_pairs, labels

    def generate_hard_negative_pairs(self,
                                     contours: List[SyntheticContour],
                                     hard_negative_ratio: float = 0.3) -> Tuple[List[Tuple], List[int]]:
        _logger.info("Generating pairs with %.0f%% hard negatives...", hard_negative_ratio * 100)

        grouped = self._group_by_object_id(contours)
        object_ids = list(grouped.keys())

        hard_negative_shapes = ShapeFactory.get_hard_negative_pairs()

        pairs_pos = self._generate_positive_pairs(grouped)

        hard_negative_pairs = []
        for shape1, shape2 in hard_negative_shapes:
            shape1_objects = [oid for oid in object_ids if shape1.value in oid]
            shape2_objects = [oid for oid in object_ids if shape2.value in oid]

            for oid1 in shape1_objects:
                for oid2 in shape2_objects:
                    contours1 = grouped[oid1]
                    contours2 = grouped[oid2]

                    n_pairs = min(len(contours1) * len(contours2), 50)
                    for _ in range(n_pairs):
                        c1 = random.choice(contours1)
                        c2 = random.choice(contours2)
                        hard_negative_pairs.append((c1.contour, c2.contour))

        _logger.debug("Generated %d hard negative pairs", len(hard_negative_pairs))

        total_negative_needed = len(pairs_pos)
        hard_negative_count = int(total_negative_needed * hard_negative_ratio)
        regular_negative_count = total_negative_needed - hard_negative_count

        sampled_hard_negatives = random.sample(
            hard_negative_pairs,
            min(hard_negative_count, len(hard_negative_pairs))
        )

        regular_negatives = self._generate_regular_negative_pairs(
            grouped, object_ids, regular_negative_count, exclude_hard_negatives=True
        )

        all_negative_pairs = sampled_hard_negatives + regular_negatives
        all_pairs = pairs_pos + all_negative_pairs
        labels = [1] * len(pairs_pos) + [0] * len(all_negative_pairs)

        combined = list(zip(all_pairs, labels))
        random.shuffle(combined)
        final_pairs, final_labels = zip(*combined)

        _logger.info(
            "Hard negative dataset: %d pairs — hard negatives: %d, regular negatives: %d",
            len(final_pairs), len(sampled_hard_negatives), len(regular_negatives),
        )

        return list(final_pairs), list(final_labels)

    def generate_stratified_pairs(self,
                                  contours: List[SyntheticContour],
                                  pairs_per_object: int = 100) -> Tuple[List[Tuple], List[int]]:
        _logger.info("Generating stratified pairs (%d per object)...", pairs_per_object)

        grouped = self._group_by_object_id(contours)

        all_pairs = []
        all_labels = []

        for object_id, object_contours in grouped.items():
            if len(object_contours) < 2:
                continue

            object_pairs = [
                (c1.contour, c2.contour)
                for c1, c2 in itertools.combinations(object_contours, 2)
            ]

            if len(object_pairs) > pairs_per_object:
                object_pairs = random.sample(object_pairs, pairs_per_object)

            all_pairs.extend(object_pairs)
            all_labels.extend([1] * len(object_pairs))

        negative_pairs_needed = len(all_pairs)
        negative_pairs = self._generate_random_negative_pairs(
            grouped, list(grouped.keys()), negative_pairs_needed
        )

        all_pairs.extend(negative_pairs)
        all_labels.extend([0] * len(negative_pairs))

        combined = list(zip(all_pairs, all_labels))
        random.shuffle(combined)
        final_pairs, final_labels = zip(*combined)

        _logger.info("Stratified dataset: %d pairs", len(final_pairs))

        return list(final_pairs), list(final_labels)

    def _group_by_object_id(self, contours: List[SyntheticContour]) -> Dict[str, List[SyntheticContour]]:
        grouped = {}
        for contour in contours:
            grouped.setdefault(contour.object_id, []).append(contour)
        return grouped

    def _generate_positive_pairs(self, grouped: Dict[str, List[SyntheticContour]]) -> List[Tuple]:
        pairs_pos = []

        for object_id, object_contours in grouped.items():
            object_pairs = [
                (c1.contour, c2.contour)
                for c1, c2 in itertools.combinations(object_contours, 2)
            ]

            if self.max_pairs_per_object and len(object_pairs) > self.max_pairs_per_object:
                object_pairs = random.sample(object_pairs, self.max_pairs_per_object)

            pairs_pos.extend(object_pairs)

        return pairs_pos

    def _generate_negative_pairs(self,
                                  grouped: Dict[str, List[SyntheticContour]],
                                  object_ids: List[str]) -> List[Tuple]:
        pairs_neg = []

        total_combinations = sum(
            len(grouped[object_ids[i]]) * len(grouped[object_ids[j]])
            for i in range(len(object_ids))
            for j in range(i + 1, len(object_ids))
        )

        _logger.debug("Total possible negative combinations: %d", total_combinations)

        pair_count = 0
        for i in range(len(object_ids)):
            for j in range(i + 1, len(object_ids)):
                contours_i = grouped[object_ids[i]]
                contours_j = grouped[object_ids[j]]

                for c1 in contours_i:
                    for c2 in contours_j:
                        pairs_neg.append((c1.contour, c2.contour))
                        pair_count += 1

            if (i + 1) % 5 == 0:
                progress = pair_count / total_combinations * 100 if total_combinations > 0 else 0
                _logger.debug("Negative pairs progress: %d/%d (%.1f%%)", pair_count, total_combinations, progress)

        return pairs_neg

    def _generate_regular_negative_pairs(self,
                                          grouped: Dict[str, List[SyntheticContour]],
                                          object_ids: List[str],
                                          count: int,
                                          exclude_hard_negatives: bool = False) -> List[Tuple]:
        pairs_neg = []
        hard_negative_shapes = set()

        if exclude_hard_negatives:
            for shape1, shape2 in ShapeFactory.get_hard_negative_pairs():
                hard_negative_shapes.add((shape1.value, shape2.value))
                hard_negative_shapes.add((shape2.value, shape1.value))

        attempts = 0
        max_attempts = count * 10

        while len(pairs_neg) < count and attempts < max_attempts:
            obj1, obj2 = random.sample(object_ids, 2)

            if exclude_hard_negatives:
                shape1 = obj1.split('_')[0]
                shape2 = obj2.split('_')[0]
                if (shape1, shape2) in hard_negative_shapes:
                    attempts += 1
                    continue

            c1 = random.choice(grouped[obj1])
            c2 = random.choice(grouped[obj2])
            pairs_neg.append((c1.contour, c2.contour))
            attempts += 1

        return pairs_neg

    def _generate_random_negative_pairs(self,
                                         grouped: Dict[str, List[SyntheticContour]],
                                         object_ids: List[str],
                                         count: int) -> List[Tuple]:
        pairs_neg = []

        for _ in range(count):
            obj1, obj2 = random.sample(object_ids, 2)
            c1 = random.choice(grouped[obj1])
            c2 = random.choice(grouped[obj2])
            pairs_neg.append((c1.contour, c2.contour))

        return pairs_neg

    def _balance_pairs(self,
                       pairs_pos: List[Tuple],
                       pairs_neg: List[Tuple]) -> Tuple[List[Tuple], List[int]]:
        if self.balance_strategy == 'downsample':
            n = min(len(pairs_pos), len(pairs_neg))
            balanced_pos = random.sample(pairs_pos, n)
            balanced_neg = random.sample(pairs_neg, n)

        elif self.balance_strategy == 'upsample':
            n = max(len(pairs_pos), len(pairs_neg))

            if len(pairs_pos) < n:
                additional_needed = n - len(pairs_pos)
                balanced_pos = pairs_pos + random.choices(pairs_pos, k=additional_needed)
                balanced_neg = pairs_neg
            else:
                additional_needed = n - len(pairs_neg)
                balanced_pos = pairs_pos
                balanced_neg = pairs_neg + random.choices(pairs_neg, k=additional_needed)

        else:
            n = min(len(pairs_pos), len(pairs_neg))
            balanced_pos = random.sample(pairs_pos, n)
            balanced_neg = random.sample(pairs_neg, n)

        all_pairs = balanced_pos + balanced_neg
        labels = [1] * len(balanced_pos) + [0] * len(balanced_neg)

        combined = list(zip(all_pairs, labels))
        random.shuffle(combined)
        shuffled_pairs, shuffled_labels = zip(*combined)

        return list(shuffled_pairs), list(shuffled_labels)

    def get_pair_statistics(self,
                            pairs: List[Tuple],
                            labels: List[int],
                            contours: List[SyntheticContour]) -> Dict[str, Any]:
        stats = {
            'total_pairs': len(pairs),
            'positive_pairs': sum(labels),
            'negative_pairs': len(labels) - sum(labels),
            'balance_ratio': sum(labels) / len(labels) if labels else 0,
            'unique_contours_used': len(set(id(c) for pair in pairs for c in pair)),
            'shape_pair_distribution': {}
        }

        contour_to_shape = {id(c.contour): c.shape_type.value for c in contours}

        for pair, label in zip(pairs, labels):
            shape1 = contour_to_shape.get(id(pair[0]), 'unknown')
            shape2 = contour_to_shape.get(id(pair[1]), 'unknown')

            shape_pair = f"{min(shape1, shape2)}_vs_{max(shape1, shape2)}"
            pair_type = 'positive' if label == 1 else 'negative'

            if shape_pair not in stats['shape_pair_distribution']:
                stats['shape_pair_distribution'][shape_pair] = {'positive': 0, 'negative': 0}

            stats['shape_pair_distribution'][shape_pair][pair_type] += 1

        return stats
