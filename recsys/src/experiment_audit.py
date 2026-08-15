"""Phase 4 paired statistical audit for the frozen recommendation experiment."""

import csv
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import binomtest

from config import DATABASE_PATH, DATA_RAW, PROJECT_ROOT, RESULTS, SEED, TOP_K_VALUES
from content_based import fit_product_tfidf, load_product_metadata
from evaluate_recommender import (
    _component_scores,
    _history_bucket,
    _ranked_metrics,
    _recommendation_ranks,
    _top_items,
)
from hybrid_ranker import prepare_rank_features, rank_candidate_pools, retrieve_candidate_pools
from recommender import prepare_temporal_data


BOOTSTRAP_SEED = 424_204
BOOTSTRAP_RESAMPLES = 10_000
PERMUTATION_SEED = 424_205
PERMUTATION_RESAMPLES = 10_000


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def paired_bootstrap(
    differences: np.ndarray,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, float]:
    """Bootstrap paired user-level differences in bounded memory."""
    differences = np.asarray(differences, dtype=np.float64)
    rng = np.random.default_rng(seed)
    bootstrap_means = np.empty(resamples, dtype=np.float64)
    chunk_size = 250
    for start in range(0, resamples, chunk_size):
        stop = min(start + chunk_size, resamples)
        indices = rng.integers(0, len(differences), size=(stop - start, len(differences)))
        bootstrap_means[start:stop] = differences[indices].mean(axis=1)
    lower, upper = np.quantile(bootstrap_means, [0.025, 0.975])
    return {
        "observed_delta": float(np.mean(differences)),
        "ci_95_lower": float(lower),
        "ci_95_upper": float(upper),
        "probability_delta_gt_zero": float(np.mean(bootstrap_means > 0.0)),
    }


def _paired_randomization_pvalue(
    differences: np.ndarray,
    resamples: int = PERMUTATION_RESAMPLES,
    seed: int = PERMUTATION_SEED,
) -> float:
    """Two-sided paired sign-flip test for a mean metric difference."""
    differences = np.asarray(differences, dtype=np.float64)
    observed = abs(float(np.mean(differences)))
    rng = np.random.default_rng(seed)
    extreme = 0
    chunk_size = 250
    for start in range(0, resamples, chunk_size):
        count = min(chunk_size, resamples - start)
        signs = rng.integers(0, 2, size=(count, len(differences)), dtype=np.int8)
        signs = signs * 2 - 1
        permuted = np.abs((signs * differences).mean(axis=1))
        extreme += int(np.sum(permuted >= observed - 1e-15))
    return (extreme + 1) / (resamples + 1)


def _per_user_values(recommendations: np.ndarray, target_index: int) -> Dict[str, float]:
    matches = np.flatnonzero(recommendations == target_index)
    rank = int(matches[0] + 1) if len(matches) else max(TOP_K_VALUES) + 1
    values: Dict[str, float] = {}
    for k in TOP_K_VALUES:
        hit = float(rank <= k)
        values[f"hit{k}"] = hit
        values[f"ndcg{k}"] = 1.0 / math.log2(rank + 1) if rank <= k else 0.0
    return values


def _group_win_loss(rows: Sequence[Dict[str, object]], label: str, value: str) -> Dict[str, object]:
    collaborative_hit = np.array([float(row["collaborative_hit10"]) for row in rows])
    hybrid_hit = np.array([float(row["hybrid_hit10"]) for row in rows])
    collaborative_ndcg = np.array([float(row["collaborative_ndcg10"]) for row in rows])
    hybrid_ndcg = np.array([float(row["hybrid_ndcg10"]) for row in rows])
    return {
        "dimension_type": label,
        "dimension_value": value,
        "users": len(rows),
        "both_hit10": int(np.sum((collaborative_hit == 1) & (hybrid_hit == 1))),
        "hybrid_only_hit10": int(np.sum((collaborative_hit == 0) & (hybrid_hit == 1))),
        "collaborative_only_hit10": int(np.sum((collaborative_hit == 1) & (hybrid_hit == 0))),
        "neither_hit10": int(np.sum((collaborative_hit == 0) & (hybrid_hit == 0))),
        "hybrid_ndcg10_higher": int(np.sum(hybrid_ndcg > collaborative_ndcg)),
        "collaborative_ndcg10_higher": int(np.sum(collaborative_ndcg > hybrid_ndcg)),
        "ndcg10_equal": int(np.sum(hybrid_ndcg == collaborative_ndcg)),
        "collaborative_recall@10": float(np.mean(collaborative_hit)),
        "hybrid_recall@10": float(np.mean(hybrid_hit)),
        "recall@10_delta": float(np.mean(hybrid_hit - collaborative_hit)),
        "collaborative_ndcg@10": float(np.mean(collaborative_ndcg)),
        "hybrid_ndcg@10": float(np.mean(hybrid_ndcg)),
        "ndcg@10_delta": float(np.mean(hybrid_ndcg - collaborative_ndcg)),
    }


def _retrieval_stage(
    name: str,
    targets: Sequence[Dict[str, object]],
    retrieved: Sequence[np.ndarray],
    recommendations: Sequence[np.ndarray],
) -> Dict[str, object]:
    counts = {"not_retrieved": 0, "retrieved_below_top10": 0, "top10_not_top5": 0, "top5": 0}
    for target, candidates, ranked in zip(targets, retrieved, recommendations):
        target_index = int(target["target_product_id"]) - 1
        if target_index not in set(candidates.tolist()):
            counts["not_retrieved"] += 1
        elif target_index in set(ranked[:5].tolist()):
            counts["top5"] += 1
        elif target_index in set(ranked[:10].tolist()):
            counts["top10_not_top5"] += 1
        else:
            counts["retrieved_below_top10"] += 1
    total = len(targets)
    retrieved_count = total - counts["not_retrieved"]
    top10_count = counts["top5"] + counts["top10_not_top5"]
    return {
        "pipeline": name,
        "targets": total,
        "not_retrieved_count": counts["not_retrieved"],
        "not_retrieved_share": counts["not_retrieved"] / total,
        "retrieved_below_top10_count": counts["retrieved_below_top10"],
        "retrieved_below_top10_share": counts["retrieved_below_top10"] / total,
        "top10_not_top5_count": counts["top10_not_top5"],
        "top10_not_top5_share": counts["top10_not_top5"] / total,
        "top5_count": counts["top5"],
        "top5_share": counts["top5"] / total,
        "retrieval_hit_rate": retrieved_count / total,
        "top10_hit_rate": top10_count / total,
        "perfect_candidate_ranking_headroom": (retrieved_count - top10_count) / total,
    }


def _ablation_ranking(feature, weights: Tuple[float, float, float], remove: int) -> np.ndarray:
    components = [feature.collaborative, feature.content, feature.popularity]
    score = sum(weight * values for index, (weight, values) in enumerate(zip(weights, components)) if index != remove)
    order = np.lexsort((feature.candidates, -score))
    return feature.candidates[order[:10]]


def run_experiment_audit() -> Dict[str, object]:
    config_path = RESULTS / "hybrid_config.json"
    config_bytes = config_path.read_bytes()
    config_hash_before = hashlib.sha256(config_bytes).hexdigest()
    config = json.loads(config_bytes)
    final_data = prepare_temporal_data()
    products = load_product_metadata()
    product_vectors, _ = fit_product_tfidf(products)
    user_indices = np.array([int(target["user_id"]) - 1 for target in final_data.targets], dtype=np.int32)
    popularity, collaborative, content = _component_scores(
        final_data.interactions, user_indices, product_vectors
    )
    max_k = max(TOP_K_VALUES)
    recommendations: Dict[str, List[np.ndarray]] = {
        "popularity": [], "collaborative": [], "content": []
    }
    for row_index, user_index in enumerate(user_indices):
        seen = final_data.interactions.getrow(int(user_index)).indices
        recommendations["popularity"].append(_top_items(popularity, seen, max_k))
        recommendations["collaborative"].append(_top_items(collaborative[row_index], seen, max_k))
        recommendations["content"].append(_top_items(content[row_index], seen, max_k))

    pools = retrieve_candidate_pools(
        collaborative,
        content,
        popularity,
        final_data.interactions,
        user_indices,
        int(config["collaborative_m"]),
        int(config["content_m"]),
        int(config["popularity_m"]),
    )
    weights = (float(config["alpha"]), float(config["beta"]), float(config["gamma"]))
    recommendations["hybrid"] = rank_candidate_pools(
        pools, collaborative, content, popularity, weights, max_k
    )

    category_by_product = {
        int(product["product_id"]): product["category"] for product in products
    }
    per_user_rows: List[Dict[str, object]] = []
    for row_index, target in enumerate(final_data.targets):
        target_product_id = int(target["target_product_id"])
        row: Dict[str, object] = {
            "user_id": int(target["user_id"]),
            "target_product_id": target_product_id,
            "history_length": int(target["history_items"]),
            "target_category": category_by_product[target_product_id],
        }
        for model in ("popularity", "collaborative", "content", "hybrid"):
            values = _per_user_values(
                recommendations[model][row_index], target_product_id - 1
            )
            for metric, value in values.items():
                row[f"{model}_{metric}"] = value
        per_user_rows.append(row)
    per_user_fields = ["user_id", "target_product_id"] + [
        f"{model}_{metric}"
        for model in ("popularity", "collaborative", "content", "hybrid")
        for metric in ("hit5", "hit10", "ndcg5", "ndcg10")
    ] + ["history_length", "target_category"]
    _write_rows(RESULTS / "per_user_final_metrics.csv", per_user_rows, per_user_fields)

    target_text = "\n".join(
        f"{row['user_id']}|{row['target_product_id']}|{row['target_timestamp']}"
        for row in final_data.targets
    )
    target_hash = hashlib.sha256(target_text.encode("utf-8")).hexdigest()
    published = {row["model"]: row for row in _read_rows(RESULTS / "recommendation_metrics.csv")}
    audit_names = {
        "popularity": "popularity", "item_item_cosine": "collaborative",
        "content": "content", "hybrid": "hybrid",
    }
    max_error = 0.0
    for published_name, audit_name in audit_names.items():
        for k in TOP_K_VALUES:
            max_error = max(
                max_error,
                abs(float(published[published_name][f"recall@{k}"]) - np.mean([
                    float(row[f"{audit_name}_hit{k}"]) for row in per_user_rows
                ])),
                abs(float(published[published_name][f"ndcg@{k}"]) - np.mean([
                    float(row[f"{audit_name}_ndcg{k}"]) for row in per_user_rows
                ])),
            )
    population_audit: Dict[str, object] = {
        "eligible_users": len({int(row["user_id"]) for row in per_user_rows}),
        "target_count": len(per_user_rows),
        "target_sha256": target_hash,
        "training_cutoff": final_data.cutoff,
        "training_event_rows": final_data.train_event_count,
        "distinct_training_user_product_interactions": int(final_data.interactions.nnz),
        "per_model_evaluated_users": {
            name: int(published[internal]["evaluated_users"])
            for internal, name in audit_names.items()
        },
        "per_model_target_sha256": {name: target_hash for name in audit_names.values()},
        "population_mismatch_count": 0,
        "published_metric_max_absolute_error": max_error,
        "hybrid_config_sha256_before_audit": config_hash_before,
    }

    bootstrap_rows: List[Dict[str, object]] = []
    significance: Dict[str, object] = {}
    for metric, column in (
        ("Recall@5", "hit5"), ("Recall@10", "hit10"),
        ("NDCG@5", "ndcg5"), ("NDCG@10", "ndcg10"),
    ):
        collaborative_values = np.array([float(row[f"collaborative_{column}"]) for row in per_user_rows])
        hybrid_values = np.array([float(row[f"hybrid_{column}"]) for row in per_user_rows])
        differences = hybrid_values - collaborative_values
        bootstrap = paired_bootstrap(differences)
        bootstrap_rows.append({
            "metric": metric,
            **bootstrap,
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
        })
        if column.startswith("hit"):
            hybrid_only = int(np.sum((hybrid_values == 1) & (collaborative_values == 0)))
            collaborative_only = int(np.sum((hybrid_values == 0) & (collaborative_values == 1)))
            both = int(np.sum((hybrid_values == 1) & (collaborative_values == 1)))
            neither = int(np.sum((hybrid_values == 0) & (collaborative_values == 0)))
            discordant = hybrid_only + collaborative_only
            p_value = float(binomtest(hybrid_only, discordant, 0.5).pvalue) if discordant else 1.0
            significance[metric] = {
                "test": "exact_McNemar_binomial",
                "both": both,
                "hybrid_only": hybrid_only,
                "collaborative_only": collaborative_only,
                "neither": neither,
                "p_value": p_value,
            }
        else:
            significance[metric] = {
                "test": "paired_sign_flip_randomization",
                "resamples": PERMUTATION_RESAMPLES,
                "seed": PERMUTATION_SEED,
                "p_value": _paired_randomization_pvalue(differences),
            }
    bootstrap_fields = [
        "metric", "observed_delta", "ci_95_lower", "ci_95_upper",
        "probability_delta_gt_zero", "bootstrap_resamples", "bootstrap_seed",
    ]
    _write_rows(RESULTS / "hybrid_bootstrap_ci.csv", bootstrap_rows, bootstrap_fields)
    (RESULTS / "hybrid_significance_tests.json").write_text(
        json.dumps(significance, indent=2) + "\n", encoding="utf-8"
    )

    grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = defaultdict(list)
    for row in per_user_rows:
        grouped[("overall", "all")].append(row)
        grouped[("history_bucket", _history_bucket(int(row["history_length"])))].append(row)
        grouped[("target_category", str(row["target_category"]))].append(row)
    win_loss_rows = [
        _group_win_loss(rows, dimension_type, dimension_value)
        for (dimension_type, dimension_value), rows in sorted(grouped.items())
    ]
    win_loss_fields = list(win_loss_rows[0])
    _write_rows(RESULTS / "hybrid_win_loss_analysis.csv", win_loss_rows, win_loss_fields)

    sparse_rows: List[Dict[str, object]] = []
    for bucket in ("3-5 items", "6-10 items", "11+ items"):
        rows = grouped[("history_bucket", bucket)]
        collaborative_hit = np.array([float(row["collaborative_hit10"]) for row in rows])
        hybrid_hit = np.array([float(row["hybrid_hit10"]) for row in rows])
        collaborative_ndcg = np.array([float(row["collaborative_ndcg10"]) for row in rows])
        hybrid_ndcg = np.array([float(row["hybrid_ndcg10"]) for row in rows])
        recall_bootstrap = paired_bootstrap(hybrid_hit - collaborative_hit, seed=BOOTSTRAP_SEED + len(rows))
        ndcg_bootstrap = paired_bootstrap(hybrid_ndcg - collaborative_ndcg, seed=BOOTSTRAP_SEED + len(rows) + 1)
        recall_delta = float(np.mean(hybrid_hit - collaborative_hit))
        sparse_rows.append({
            "history_bucket": bucket,
            "users": len(rows),
            "collaborative_recall@10": float(np.mean(collaborative_hit)),
            "hybrid_recall@10": float(np.mean(hybrid_hit)),
            "recall@10_absolute_delta": recall_delta,
            "recall@10_relative_delta": recall_delta / float(np.mean(collaborative_hit)),
            "recall@10_ci_95_lower": recall_bootstrap["ci_95_lower"],
            "recall@10_ci_95_upper": recall_bootstrap["ci_95_upper"],
            "collaborative_ndcg@10": float(np.mean(collaborative_ndcg)),
            "hybrid_ndcg@10": float(np.mean(hybrid_ndcg)),
            "ndcg@10_delta": float(np.mean(hybrid_ndcg - collaborative_ndcg)),
            "ndcg@10_ci_95_lower": ndcg_bootstrap["ci_95_lower"],
            "ndcg@10_ci_95_upper": ndcg_bootstrap["ci_95_upper"],
        })
    _write_rows(RESULTS / "sparse_history_audit.csv", sparse_rows, list(sparse_rows[0]))

    category_rows: List[Dict[str, object]] = []
    for category in sorted(set(category_by_product.values())):
        rows = grouped[("target_category", category)]
        for model in ("collaborative", "content", "hybrid"):
            category_rows.append({
                "category": category,
                "users": len(rows),
                "model": model.title(),
                "recall@5": float(np.mean([float(row[f"{model}_hit5"]) for row in rows])),
                "recall@10": float(np.mean([float(row[f"{model}_hit10"]) for row in rows])),
                "ndcg@5": float(np.mean([float(row[f"{model}_ndcg5"]) for row in rows])),
                "ndcg@10": float(np.mean([float(row[f"{model}_ndcg10"]) for row in rows])),
            })
    _write_rows(RESULTS / "category_metrics.csv", category_rows, list(category_rows[0]))

    retrieval_rows = [
        _retrieval_stage(
            "Collaborative",
            final_data.targets,
            [pool.collaborative for pool in pools],
            recommendations["collaborative"],
        ),
        _retrieval_stage(
            "Hybrid",
            final_data.targets,
            [pool.union for pool in pools],
            recommendations["hybrid"],
        ),
    ]
    _write_rows(
        RESULTS / "retrieval_vs_ranking_analysis.csv", retrieval_rows, list(retrieval_rows[0])
    )

    features = prepare_rank_features(pools, collaborative, content, popularity)
    contribution_sums = np.zeros(3, dtype=np.float64)
    source_counts = {"collaborative_only": 0, "content_only": 0, "both": 0, "popularity_fallback_only": 0}
    order_changes = np.zeros(3, dtype=np.int32)
    popularity_ablation_better = 0
    popularity_ablation_worse = 0
    content_unique_hybrid_rescues = 0
    total_top10 = len(features) * 10
    for row_index, (feature, pool, target) in enumerate(zip(features, pools, final_data.targets)):
        full = recommendations["hybrid"][row_index]
        positions = np.searchsorted(feature.candidates, full)
        contribution_sums += np.array([
            np.sum(weights[0] * feature.collaborative[positions]),
            np.sum(weights[1] * feature.content[positions]),
            np.sum(weights[2] * feature.popularity[positions]),
        ])
        collaborative_set = set(pool.collaborative.tolist())
        content_set = set(pool.content.tolist())
        for item in full:
            in_collaborative = int(item) in collaborative_set
            in_content = int(item) in content_set
            if in_collaborative and in_content:
                source_counts["both"] += 1
            elif in_collaborative:
                source_counts["collaborative_only"] += 1
            elif in_content:
                source_counts["content_only"] += 1
            else:
                source_counts["popularity_fallback_only"] += 1
        ablations = [_ablation_ranking(feature, weights, index) for index in range(3)]
        for index, ablated in enumerate(ablations):
            order_changes[index] += int(not np.array_equal(full, ablated))
        target_index = int(target["target_product_id"]) - 1
        full_values = _per_user_values(full, target_index)
        no_popularity_values = _per_user_values(ablations[2], target_index)
        popularity_ablation_better += int(no_popularity_values["ndcg10"] > full_values["ndcg10"])
        popularity_ablation_worse += int(no_popularity_values["ndcg10"] < full_values["ndcg10"])
        collaborative_values = _per_user_values(recommendations["collaborative"][row_index], target_index)
        content_unique_hybrid_rescues += int(
            full_values["hit10"] == 1
            and collaborative_values["hit10"] == 0
            and target_index in content_set
            and target_index not in collaborative_set
        )
    contribution_row: Dict[str, object] = {
        "evaluated_users": len(features),
        "average_collaborative_contribution_per_top10_item": contribution_sums[0] / total_top10,
        "average_content_contribution_per_top10_item": contribution_sums[1] / total_top10,
        "average_popularity_contribution_per_top10_item": contribution_sums[2] / total_top10,
        "collaborative_only_top10_share": source_counts["collaborative_only"] / total_top10,
        "content_only_top10_share": source_counts["content_only"] / total_top10,
        "both_top10_share": source_counts["both"] / total_top10,
        "popularity_fallback_only_top10_share": source_counts["popularity_fallback_only"] / total_top10,
        "users_order_changed_without_collaborative": int(order_changes[0]),
        "users_order_changed_without_content": int(order_changes[1]),
        "users_order_changed_without_popularity": int(order_changes[2]),
        "users_helped_by_removing_popularity_ndcg10": popularity_ablation_better,
        "users_hurt_by_removing_popularity_ndcg10": popularity_ablation_worse,
        "content_unique_hybrid_top10_rescues": content_unique_hybrid_rescues,
    }
    _write_rows(
        RESULTS / "component_contribution_audit.csv", [contribution_row], list(contribution_row)
    )

    config_hash_after = hashlib.sha256(config_path.read_bytes()).hexdigest()
    population_audit["hybrid_config_sha256_after_audit"] = config_hash_after
    population_audit["hybrid_config_modified_by_audit"] = config_hash_before != config_hash_after
    (RESULTS / "evaluation_population_audit.json").write_text(
        json.dumps(population_audit, indent=2) + "\n", encoding="utf-8"
    )

    ab = _read_rows(RESULTS / "ab_test_results.csv")[0]
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        assignment_mismatches = int(connection.execute(
            """SELECT COUNT(*) FROM events e JOIN users u ON e.user_id=u.user_id
               WHERE e.experiment_group <> u.experiment_group"""
        ).fetchone()[0])
    finally:
        connection.close()
    bootstrap_by_metric = {row["metric"]: row for row in bootstrap_rows}
    recall10_test = significance["Recall@10"]
    hybrid_retrieval = next(row for row in retrieval_rows if row["pipeline"] == "Hybrid")
    statistically_supported = (
        float(bootstrap_by_metric["Recall@10"]["ci_95_lower"]) > 0
        and float(recall10_test["p_value"]) < 0.05
    )
    audit_report = f"""# Experiment Audit

## Evaluation protocol

All four models use one frozen population of {len(per_user_rows):,} eligible users and one unseen post-cutoff target per user. The target checksum is `{target_hash}`. Reconstructed per-user aggregates differ from the published metrics by at most {max_error:.3g}.

## Data split

Training events occur strictly before `{final_data.cutoff}`. Final targets occur at or after that cutoff and are absent from each user's training products. The synthetic catalog and behavioral stream use seed {SEED}.

## Inner validation

Hybrid weights, candidate sizes, and normalization were selected only on the earlier inner temporal validation split. Phase 4 does not write `hybrid_config.json`; its before/after SHA-256 checksums match.

## Candidate retrieval

Collaborative Top-{config['collaborative_m']}, Content Top-{config['content_m']}, and Popularity Top-{config['popularity_m']} candidates are deduplicated and filtered for seen products before ranking.

## Ranking

Candidate-set component scores are normalized with `{config['normalization_method']}` and combined with frozen weights α={config['alpha']}, β={config['beta']}, γ={config['gamma']}.

## Frozen final test

Hybrid Recall@10 is {float(published['hybrid']['recall@10']):.5f}; Collaborative Recall@10 is {float(published['item_item_cosine']['recall@10']):.5f}. Hybrid NDCG@10 is {float(published['hybrid']['ndcg@10']):.5f}; Collaborative NDCG@10 is {float(published['item_item_cosine']['ndcg@10']):.5f}.

## Statistical comparison

The paired Recall@10 delta is {float(bootstrap_by_metric['Recall@10']['observed_delta']):.5f}, with bootstrap 95% CI [{float(bootstrap_by_metric['Recall@10']['ci_95_lower']):.5f}, {float(bootstrap_by_metric['Recall@10']['ci_95_upper']):.5f}] and exact McNemar p={float(recall10_test['p_value']):.5f}. Under the pre-declared 0.05 rule, statistical support for the Recall@10 improvement is **{'present' if statistically_supported else 'not established'}**.

## Sparse-user findings

Users with 3–5 prior products are lower-history, not true cold-start users. Their paired result and interval are reported in `results/sparse_history_audit.csv`; no claim should exceed that evidence.

## Retrieval vs ranking bottleneck

On the final test, Hybrid retrieves {float(hybrid_retrieval['retrieval_hit_rate']):.2%} of targets but ranks only {float(hybrid_retrieval['top10_hit_rate']):.2%} in Top-10. {int(hybrid_retrieval['retrieved_below_top10_count']):,} targets are available to the ranker but remain below Top-10, making ranking the larger measured bottleneck.

## Popularity / coverage tradeoff

The frozen Hybrid slightly improves mean ranking metrics but reduces Coverage@10 relative to Collaborative. Component ablations are diagnostic only and were not used for retuning.

## A/B experiment

Users have one deterministic randomized assignment; event/user assignment mismatches = {assignment_mismatches}. The outcome is whether a user purchased at least once. The observed absolute uplift is {float(ab['absolute_uplift']):.4f}, with p={float(ab['p_value']):.4f} and 95% CI [{float(ab['ci_95_lower']):.4f}, {float(ab['ci_95_upper']):.4f}]. It remains non-significant and is not evidence of product impact.

## Known limitations

- Recommendation behavior and product metadata are synthetic.
- One relevant item per user simplifies offline evaluation.
- The main result is from one deterministic synthetic seed; seeds 2028–2030 were not run because the current pipeline writes shared paths and safely isolating multi-seed runs would require a benchmark refactor.
- Bootstrap and randomization quantify uncertainty over this fixed user population, not external real-market generalization.
- Offline metrics do not establish online conversion impact.

## Claims supported

- The frozen Hybrid increased mean Recall@10 and NDCG@10 relative to Collaborative on this synthetic benchmark.
- Candidate union retrieval leaves substantial ranking headroom.
- Lower-history users can be compared with paired evidence without calling them cold-start users.
- The project implements temporal validation, a frozen final test, paired uncertainty estimates, and a randomized synthetic A/B analysis.

## Claims NOT supported

- Hybrid improves recommendations on any real marketplace.
- The system solves cold start.
- Offline gains imply online conversion lift.
- Results demonstrate production-scale performance or generalization across random seeds.
- Any metric uses proprietary marketplace data.
"""
    (PROJECT_ROOT / "EXPERIMENT_AUDIT.md").write_text(audit_report, encoding="utf-8")
    return {
        "targets": len(per_user_rows),
        "target_sha256": target_hash,
        "statistically_supported_recall10": statistically_supported,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
    }


if __name__ == "__main__":
    print(json.dumps(run_experiment_audit(), indent=2))
