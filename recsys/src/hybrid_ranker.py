"""Explicit multi-source candidate retrieval and explainable hybrid ranking."""

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix


@dataclass
class CandidatePool:
    collaborative: np.ndarray
    content: np.ndarray
    popularity: np.ndarray
    union: np.ndarray


@dataclass
class CandidateRankFeatures:
    candidates: np.ndarray
    collaborative: np.ndarray
    content: np.ndarray
    popularity: np.ndarray


def _top_unseen(scores: np.ndarray, seen: np.ndarray, size: int) -> np.ndarray:
    candidate_scores = np.asarray(scores, dtype=np.float64).copy()
    candidate_scores[seen] = -np.inf
    product_indices = np.arange(len(candidate_scores))
    order = np.lexsort((product_indices, -candidate_scores))
    return order[: min(size, len(order) - len(seen))]


def retrieve_candidate_pools(
    collaborative_scores: np.ndarray,
    content_scores: np.ndarray,
    popularity_scores: np.ndarray,
    training_interactions: csr_matrix,
    user_indices: Sequence[int],
    collaborative_m: int,
    content_m: int,
    popularity_m: int,
) -> List[CandidatePool]:
    """Retrieve, deduplicate, and filter candidates without target information."""
    pools: List[CandidatePool] = []
    for row_index, user_index in enumerate(user_indices):
        seen = training_interactions.getrow(int(user_index)).indices
        collaborative = _top_unseen(
            collaborative_scores[row_index], seen, collaborative_m
        )
        content = _top_unseen(content_scores[row_index], seen, content_m)
        popularity = _top_unseen(popularity_scores, seen, popularity_m)
        union = np.array(
            sorted(set(collaborative) | set(content) | set(popularity)),
            dtype=np.int32,
        )
        pools.append(
            CandidatePool(
                collaborative=collaborative,
                content=content,
                popularity=popularity,
                union=union,
            )
        )
    return pools


def minmax_normalize(values: np.ndarray) -> np.ndarray:
    """Normalize finite candidate scores; missing or zero-variance values map to zero."""
    values = np.asarray(values, dtype=np.float64)
    normalized = np.zeros_like(values)
    finite = np.isfinite(values)
    if not np.any(finite):
        return normalized
    minimum = float(np.min(values[finite]))
    maximum = float(np.max(values[finite]))
    if maximum <= minimum:
        return normalized
    normalized[finite] = (values[finite] - minimum) / (maximum - minimum)
    return normalized


def rank_candidate_pools(
    pools: Sequence[CandidatePool],
    collaborative_scores: np.ndarray,
    content_scores: np.ndarray,
    popularity_scores: np.ndarray,
    weights: Tuple[float, float, float],
    k: int = 10,
) -> List[np.ndarray]:
    """Rank each candidate union after per-user, per-component min-max scaling."""
    features = prepare_rank_features(
        pools, collaborative_scores, content_scores, popularity_scores
    )
    return rank_prepared_candidates(features, weights, k)


def prepare_rank_features(
    pools: Sequence[CandidatePool],
    collaborative_scores: np.ndarray,
    content_scores: np.ndarray,
    popularity_scores: np.ndarray,
) -> List[CandidateRankFeatures]:
    """Normalize component scores once so a validation weight grid can reuse them."""
    features: List[CandidateRankFeatures] = []
    for row_index, pool in enumerate(pools):
        candidates = pool.union
        features.append(
            CandidateRankFeatures(
                candidates=candidates,
                collaborative=minmax_normalize(collaborative_scores[row_index, candidates]),
                content=minmax_normalize(content_scores[row_index, candidates]),
                popularity=minmax_normalize(popularity_scores[candidates]),
            )
        )
    return features


def rank_prepared_candidates(
    features: Sequence[CandidateRankFeatures],
    weights: Tuple[float, float, float],
    k: int = 10,
) -> List[np.ndarray]:
    """Rank normalized candidate features for one deterministic weight tuple."""
    alpha, beta, gamma = weights
    if min(weights) < 0.0 or not np.isclose(alpha + beta + gamma, 1.0):
        raise ValueError("Hybrid weights must be nonnegative and sum to one")
    recommendations: List[np.ndarray] = []
    for row in features:
        hybrid_scores = (
            alpha * row.collaborative + beta * row.content + gamma * row.popularity
        )
        order = np.lexsort((row.candidates, -hybrid_scores))
        recommendations.append(row.candidates[order[:k]])
    return recommendations


def retrieval_diagnostics(
    pools: Sequence[CandidatePool], targets: Sequence[Dict[str, object]]
) -> Dict[str, float]:
    """Measure validation target retrieval and source complementarity."""
    source_hits = {"collaborative": 0, "content": 0, "popularity": 0, "union": 0}
    union_sizes: List[int] = []
    jaccards: List[float] = []
    collaborative_only = 0
    content_only = 0
    both = 0
    popularity_fallback = 0
    content_unique_target_hits = 0
    for pool, target in zip(pools, targets):
        target_index = int(target["target_product_id"]) - 1
        collaborative = set(pool.collaborative.tolist())
        content = set(pool.content.tolist())
        popularity = set(pool.popularity.tolist())
        union = set(pool.union.tolist())
        source_hits["collaborative"] += int(target_index in collaborative)
        source_hits["content"] += int(target_index in content)
        source_hits["popularity"] += int(target_index in popularity)
        source_hits["union"] += int(target_index in union)
        content_unique_target_hits += int(
            target_index in content and target_index not in collaborative
        )
        union_sizes.append(len(union))
        jaccards.append(len(collaborative & content) / max(len(collaborative | content), 1))
        collaborative_only += len(collaborative - content)
        content_only += len(content - collaborative)
        both += len(collaborative & content)
        popularity_fallback += len(popularity - collaborative - content)

    total_candidates = sum(union_sizes)
    union_hits = source_hits["union"]
    n_users = max(len(targets), 1)
    return {
        "validation_users": float(len(targets)),
        "collaborative_candidate_recall": source_hits["collaborative"] / n_users,
        "content_candidate_recall": source_hits["content"] / n_users,
        "popularity_candidate_recall": source_hits["popularity"] / n_users,
        "union_candidate_recall": union_hits / n_users,
        "average_candidate_union_size": float(np.mean(union_sizes)),
        "collaborative_only_candidate_fraction": collaborative_only / total_candidates,
        "content_only_candidate_fraction": content_only / total_candidates,
        "collaborative_content_both_fraction": both / total_candidates,
        "popularity_fallback_only_fraction": popularity_fallback / total_candidates,
        "mean_collaborative_content_jaccard": float(np.mean(jaccards)),
        "content_unique_target_hit_share": content_unique_target_hits / max(union_hits, 1),
    }
