"""Tune hybrid retrieval/ranking on inner validation, then run the frozen final test."""

import csv
import json
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix

from config import RESULTS, TOP_K_VALUES
from content_based import fit_product_tfidf, load_product_metadata, score_content_candidates
from hybrid_ranker import (
    prepare_rank_features,
    rank_candidate_pools,
    rank_prepared_candidates,
    retrieval_diagnostics,
    retrieve_candidate_pools,
)
from recommender import (
    ValidationData,
    item_item_cosine,
    popularity_scores,
    prepare_inner_validation,
    prepare_temporal_data,
)


CANDIDATE_SIZES = (25, 50, 100)
POPULARITY_CANDIDATES = 10
NORMALIZATION_METHOD = "per_user_candidate_minmax"


def _history_bucket(history_items: int) -> str:
    if history_items <= 5:
        return "3-5 items"
    if history_items <= 10:
        return "6-10 items"
    return "11+ items"


def _ranked_metrics(ranks: Sequence[int], model: str, segment: str = "all") -> Dict[str, object]:
    result: Dict[str, object] = {
        "model": model,
        "segment": segment,
        "evaluated_users": len(ranks),
    }
    rank_array = np.asarray(ranks, dtype=np.int32)
    for k in TOP_K_VALUES:
        hits = rank_array <= k
        result[f"recall@{k}"] = float(np.mean(hits))
        result[f"precision@{k}"] = float(np.mean(hits / k))
        discounted = np.where(hits, 1.0 / np.log2(rank_array + 1), 0.0)
        result[f"ndcg@{k}"] = float(np.mean(discounted))
    return result


def _top_items(scores: np.ndarray, seen: np.ndarray, k: int) -> np.ndarray:
    candidate_scores = scores.copy()
    candidate_scores[seen] = -np.inf
    product_indices = np.arange(len(candidate_scores))
    order = np.lexsort((product_indices, -candidate_scores))
    return order[:k]


def _component_scores(
    interactions: csr_matrix,
    user_indices: np.ndarray,
    product_vectors: csr_matrix,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute the unchanged Phase 2 component scores for one temporal matrix."""
    popularity = popularity_scores(interactions)
    similarities, log_interactions = item_item_cosine(interactions)
    normalized_popularity = popularity / max(float(popularity.max()), 1.0)
    collaborative = np.asarray(log_interactions[user_indices].dot(similarities))
    collaborative += 0.01 * normalized_popularity
    content = score_content_candidates(interactions, product_vectors, user_indices)
    return popularity, collaborative, content


def _recommendation_ranks(
    targets: Sequence[Dict[str, object]], recommendations: Sequence[np.ndarray]
) -> List[int]:
    max_k = max(TOP_K_VALUES)
    ranks: List[int] = []
    for target, recommended in zip(targets, recommendations):
        target_index = int(target["target_product_id"]) - 1
        matches = np.flatnonzero(recommended == target_index)
        ranks.append(int(matches[0] + 1) if len(matches) else max_k + 1)
    return ranks


def _catalog_coverage(recommendations: Sequence[np.ndarray], n_products: int) -> float:
    return len(np.unique(np.concatenate(recommendations))) / n_products


def _weight_grid() -> List[Tuple[float, float, float]]:
    weights: List[Tuple[float, float, float]] = []
    for alpha_units in range(11):
        for beta_units in range(11 - alpha_units):
            gamma_units = 10 - alpha_units - beta_units
            weights.append((alpha_units / 10, beta_units / 10, gamma_units / 10))
    return weights


def _tune_hybrid(
    validation: ValidationData, product_vectors: csr_matrix
) -> Tuple[Dict[str, object], List[Dict[str, object]], Dict[str, object]]:
    """Select retrieval size and weights using inner-validation labels only."""
    user_indices = np.array(
        [int(target["user_id"]) - 1 for target in validation.targets], dtype=np.int32
    )
    popularity, collaborative, content = _component_scores(
        validation.interactions, user_indices, product_vectors
    )
    grid_rows: List[Dict[str, object]] = []
    pools_by_size = {}
    best_row: Dict[str, object] = {}
    best_key = None
    for candidate_size in CANDIDATE_SIZES:
        pools = retrieve_candidate_pools(
            collaborative,
            content,
            popularity,
            validation.interactions,
            user_indices,
            candidate_size,
            candidate_size,
            POPULARITY_CANDIDATES,
        )
        pools_by_size[candidate_size] = pools
        features = prepare_rank_features(pools, collaborative, content, popularity)
        for alpha, beta, gamma in _weight_grid():
            recommendations = rank_prepared_candidates(
                features, (alpha, beta, gamma), max(TOP_K_VALUES)
            )
            ranks = _recommendation_ranks(validation.targets, recommendations)
            metrics = _ranked_metrics(ranks, "hybrid_validation")
            coverage = _catalog_coverage(recommendations, validation.interactions.shape[1])
            row: Dict[str, object] = {
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "collaborative_m": candidate_size,
                "content_m": candidate_size,
                "popularity_m": POPULARITY_CANDIDATES,
                "normalization": NORMALIZATION_METHOD,
                "validation_users": len(validation.targets),
                "recall@5": metrics["recall@5"],
                "precision@5": metrics["precision@5"],
                "ndcg@5": metrics["ndcg@5"],
                "recall@10": metrics["recall@10"],
                "precision@10": metrics["precision@10"],
                "ndcg@10": metrics["ndcg@10"],
                "catalog_coverage@10": coverage,
            }
            grid_rows.append(row)
            key = (
                float(row["ndcg@10"]),
                float(row["recall@10"]),
                float(row["catalog_coverage@10"]),
                -candidate_size,
                alpha,
                beta,
                gamma,
            )
            if best_key is None or key > best_key:
                best_key = key
                best_row = row

    selected_size = int(best_row["collaborative_m"])
    selected_pools = pools_by_size[selected_size]
    retrieval = retrieval_diagnostics(selected_pools, validation.targets)
    config: Dict[str, object] = {
        "alpha": best_row["alpha"],
        "beta": best_row["beta"],
        "gamma": best_row["gamma"],
        "collaborative_m": selected_size,
        "content_m": int(best_row["content_m"]),
        "popularity_m": int(best_row["popularity_m"]),
        "normalization_method": NORMALIZATION_METHOD,
        "zero_variance_handling": "all normalized component scores are zero",
        "missing_score_handling": "non-finite component scores normalize to zero",
        "selection_source": "inner_temporal_validation",
        "validation_grid_file": "results/hybrid_validation_grid.csv",
        "final_test_metrics_used_for_selection": False,
        "validation_users": len(validation.targets),
        "validation_ndcg@10": best_row["ndcg@10"],
        "validation_recall@10": best_row["recall@10"],
        "validation_catalog_coverage@10": best_row["catalog_coverage@10"],
        "inner_cutoff": validation.inner_cutoff,
        "final_cutoff": validation.final_cutoff,
    }
    return config, grid_rows, retrieval


def _write_rows(path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate_recommenders() -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    # The final split is constructed first only to obtain its fixed cutoff. Its
    # targets are never passed into the validation-only tuning function.
    final_data = prepare_temporal_data()
    product_vectors, _ = fit_product_tfidf(load_product_metadata())
    validation = prepare_inner_validation(final_data.cutoff)
    hybrid_config, validation_grid, retrieval = _tune_hybrid(validation, product_vectors)

    grid_fields = [
        "alpha", "beta", "gamma", "collaborative_m", "content_m", "popularity_m",
        "normalization", "validation_users", "recall@5", "precision@5", "ndcg@5",
        "recall@10", "precision@10", "ndcg@10", "catalog_coverage@10",
    ]
    _write_rows(RESULTS / "hybrid_validation_grid.csv", validation_grid, grid_fields)
    (RESULTS / "hybrid_config.json").write_text(
        json.dumps(hybrid_config, indent=2) + "\n", encoding="utf-8"
    )
    retrieval_output: Dict[str, object] = {
        "inner_cutoff": validation.inner_cutoff,
        "final_cutoff": validation.final_cutoff,
        "inner_train_event_rows": validation.train_event_count,
        "collaborative_m": hybrid_config["collaborative_m"],
        "content_m": hybrid_config["content_m"],
        "popularity_m": hybrid_config["popularity_m"],
        **retrieval,
    }
    with (RESULTS / "retrieval_diagnostics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(retrieval_output.items())

    # All choices are now frozen. Component models are rebuilt from the full
    # original pre-final matrix and the final targets are evaluated once.
    interactions = final_data.interactions
    user_indices = np.array(
        [int(target["user_id"]) - 1 for target in final_data.targets], dtype=np.int32
    )
    popularity, collaborative, content = _component_scores(
        interactions, user_indices, product_vectors
    )
    max_k = max(TOP_K_VALUES)
    model_recommendations: Dict[str, List[np.ndarray]] = {
        "popularity": [],
        "item_item_cosine": [],
        "content": [],
    }
    for row_index, user_index in enumerate(user_indices):
        seen = interactions.getrow(int(user_index)).indices
        model_recommendations["popularity"].append(_top_items(popularity, seen, max_k))
        model_recommendations["item_item_cosine"].append(
            _top_items(collaborative[row_index], seen, max_k)
        )
        model_recommendations["content"].append(_top_items(content[row_index], seen, max_k))

    final_pools = retrieve_candidate_pools(
        collaborative,
        content,
        popularity,
        interactions,
        user_indices,
        int(hybrid_config["collaborative_m"]),
        int(hybrid_config["content_m"]),
        int(hybrid_config["popularity_m"]),
    )
    weights = (
        float(hybrid_config["alpha"]),
        float(hybrid_config["beta"]),
        float(hybrid_config["gamma"]),
    )
    model_recommendations["hybrid"] = rank_candidate_pools(
        final_pools, collaborative, content, popularity, weights, max_k
    )

    model_names = ("popularity", "item_item_cosine", "content", "hybrid")
    model_ranks: Dict[str, List[int]] = {
        model: _recommendation_ranks(final_data.targets, model_recommendations[model])
        for model in model_names
    }
    metrics = [_ranked_metrics(model_ranks[model], model) for model in model_names]
    coverage_by_model = {
        model: _catalog_coverage(model_recommendations[model], interactions.shape[1])
        for model in model_names
    }
    for row in metrics:
        row["catalog_coverage@10"] = coverage_by_model[str(row["model"])]

    metric_fields = [
        "model", "segment", "evaluated_users", "recall@5", "precision@5", "ndcg@5",
        "recall@10", "precision@10", "ndcg@10", "catalog_coverage@10",
    ]
    _write_rows(RESULTS / "recommendation_metrics.csv", metrics, metric_fields)

    segment_ranks: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for model in model_names:
        for target, rank in zip(final_data.targets, model_ranks[model]):
            segment_ranks[(model, _history_bucket(int(target["history_items"])))].append(rank)
    segment_metrics = [
        _ranked_metrics(ranks, model, segment)
        for (model, segment), ranks in sorted(segment_ranks.items())
    ]
    for row in segment_metrics:
        row["catalog_coverage@10"] = ""
    _write_rows(RESULTS / "recommendation_segment_metrics.csv", segment_metrics, metric_fields)
    _write_rows(
        RESULTS / "content_history_metrics.csv",
        [row for row in segment_metrics if row["model"] == "content"],
        metric_fields,
    )

    display_names = {
        "popularity": "Popularity",
        "item_item_cosine": "Collaborative",
        "content": "Content",
        "hybrid": "Hybrid",
    }
    comparison_fields = [
        "model", "recall@5", "precision@5", "ndcg@5", "recall@10",
        "precision@10", "ndcg@10", "catalog_coverage@10",
    ]
    comparison_rows = [
        {
            field: display_names[str(row["model"])] if field == "model" else row[field]
            for field in comparison_fields
        }
        for row in metrics
    ]
    _write_rows(RESULTS / "model_comparison.csv", comparison_rows, comparison_fields)

    history_rows = []
    for row in segment_metrics:
        history_row = dict(row)
        history_row["model"] = display_names[str(row["model"])]
        history_rows.append(history_row)
    _write_rows(RESULTS / "history_bucket_metrics.csv", history_rows, metric_fields)

    popularity_order = np.lexsort((np.arange(len(popularity)), -popularity))
    popularity_percentile = np.empty(len(popularity), dtype=np.float64)
    popularity_percentile[popularity_order] = np.linspace(1.0, 0.0, len(popularity))
    bias_rows: List[Dict[str, object]] = []
    for model in model_names:
        flat = np.concatenate(model_recommendations[model])
        bias_rows.append(
            {
                "model": display_names[model],
                "catalog_coverage@10": coverage_by_model[model],
                "mean_popularity_percentile@10": float(np.mean(popularity_percentile[flat])),
                "long_tail_share@10": float(np.mean(popularity_percentile[flat] < 0.5)),
                "long_tail_definition": "bottom 50% of products by pre-final training popularity",
            }
        )
    bias_fields = [
        "model", "catalog_coverage@10", "mean_popularity_percentile@10",
        "long_tail_share@10", "long_tail_definition",
    ]
    _write_rows(RESULTS / "popularity_bias_diagnostics.csv", bias_rows, bias_fields)

    metrics_by_model = {str(row["model"]): row for row in metrics}
    hybrid = metrics_by_model["hybrid"]
    improvement_rows = []
    for baseline_name in ("popularity", "item_item_cosine", "content"):
        baseline = metrics_by_model[baseline_name]
        recall_delta = float(hybrid["recall@10"]) - float(baseline["recall@10"])
        ndcg_delta = float(hybrid["ndcg@10"]) - float(baseline["ndcg@10"])
        improvement_rows.append(
            {
                "baseline": display_names[baseline_name],
                "recall@10_ratio": float(hybrid["recall@10"]) / float(baseline["recall@10"]),
                "ndcg@10_ratio": float(hybrid["ndcg@10"]) / float(baseline["ndcg@10"]),
                "recall@10_absolute_delta": recall_delta,
                "recall@10_relative_delta": recall_delta / float(baseline["recall@10"]),
                "ndcg@10_absolute_delta": ndcg_delta,
                "ndcg@10_relative_delta": ndcg_delta / float(baseline["ndcg@10"]),
                "catalog_coverage@10_delta": float(hybrid["catalog_coverage@10"])
                - float(baseline["catalog_coverage@10"]),
            }
        )
    improvement_fields = [
        "baseline", "recall@10_ratio", "ndcg@10_ratio", "recall@10_absolute_delta",
        "recall@10_relative_delta", "ndcg@10_absolute_delta", "ndcg@10_relative_delta",
        "catalog_coverage@10_delta",
    ]
    _write_rows(RESULTS / "hybrid_improvements.csv", improvement_rows, improvement_fields)

    diagnostics: Dict[str, object] = {
        "temporal_cutoff": final_data.cutoff,
        "train_event_rows": final_data.train_event_count,
        "heldout_interactions": len(final_data.targets),
        "test_positive_users": final_data.test_positive_users,
        "users_with_unseen_test_positive": final_data.users_with_unseen_test_positive,
        "excluded_for_history_or_no_unseen_target": final_data.test_positive_users
        - len(final_data.targets),
        "inner_validation_cutoff": validation.inner_cutoff,
        "inner_validation_users": len(validation.targets),
    }
    for model in model_names:
        row = next(item for item in bias_rows if item["model"] == display_names[model])
        diagnostics[f"{model}_catalog_coverage@10"] = row["catalog_coverage@10"]
        diagnostics[f"{model}_mean_popularity_percentile@10"] = row[
            "mean_popularity_percentile@10"
        ]
        diagnostics[f"{model}_long_tail_share@10"] = row["long_tail_share@10"]
    with (RESULTS / "recommendation_diagnostics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(diagnostics.items())
    return metrics, diagnostics


if __name__ == "__main__":
    model_metrics, model_diagnostics = evaluate_recommenders()
    print(model_metrics)
    print(model_diagnostics)
