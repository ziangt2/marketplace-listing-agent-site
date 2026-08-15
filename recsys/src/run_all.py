"""Regenerate the complete project pipeline with one command."""

import json
import platform
import time

from ab_test import analyze_ab_test
from build_database import build_database, run_sql_analyses
from config import DATA_PROCESSED, DATA_RAW, PROJECT_ROOT, RESULTS, SEED, ensure_directories
from evaluate_recommender import evaluate_recommenders
from experiment_audit import run_experiment_audit
from generate_data import generate_dataset
from write_documentation import write_documentation


GENERATED_FILES = (
    DATA_RAW / "users.csv",
    DATA_RAW / "products.csv",
    DATA_RAW / "sessions.csv",
    DATA_RAW / "events.csv",
    DATA_RAW / "dataset_metadata.json",
    DATA_PROCESSED / "ecommerce.sqlite",
    DATA_PROCESSED / "ecommerce.sqlite-shm",
    DATA_PROCESSED / "ecommerce.sqlite-wal",
    DATA_PROCESSED / "recommendation_holdout.csv",
    DATA_PROCESSED / "hybrid_validation_holdout.csv",
    RESULTS / "funnel_metrics.csv",
    RESULTS / "retention_metrics.csv",
    RESULTS / "ab_test_results.csv",
    RESULTS / "recommendation_metrics.csv",
    RESULTS / "recommendation_segment_metrics.csv",
    RESULTS / "recommendation_diagnostics.csv",
    RESULTS / "model_comparison.csv",
    RESULTS / "content_history_metrics.csv",
    RESULTS / "hybrid_validation_grid.csv",
    RESULTS / "hybrid_config.json",
    RESULTS / "retrieval_diagnostics.csv",
    RESULTS / "hybrid_improvements.csv",
    RESULTS / "history_bucket_metrics.csv",
    RESULTS / "popularity_bias_diagnostics.csv",
    RESULTS / "evaluation_population_audit.json",
    RESULTS / "per_user_final_metrics.csv",
    RESULTS / "hybrid_bootstrap_ci.csv",
    RESULTS / "hybrid_significance_tests.json",
    RESULTS / "hybrid_win_loss_analysis.csv",
    RESULTS / "sparse_history_audit.csv",
    RESULTS / "category_metrics.csv",
    RESULTS / "retrieval_vs_ranking_analysis.csv",
    RESULTS / "component_contribution_audit.csv",
    RESULTS / "run_metadata.json",
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "RESUME_EVIDENCE.md",
    PROJECT_ROOT / "EXPERIMENT_AUDIT.md",
)


def clean_generated_files() -> None:
    for path in GENERATED_FILES:
        if path.exists() and path.is_file():
            path.unlink()


def run_pipeline() -> None:
    ensure_directories()
    clean_generated_files()
    started = time.perf_counter()

    print("[1/7] Generating deterministic synthetic data")
    metadata = generate_dataset()
    print(f"      {metadata['total_events']:,} events across {metadata['sessions']:,} sessions")

    print("[2/7] Building SQLite database")
    build_database()

    print("[3/7] Running SQL funnel and retention analyses")
    run_sql_analyses()

    print("[4/7] Analyzing randomized experiment")
    ab_result = analyze_ab_test()
    print(f"      p-value={float(ab_result['p_value']):.4f}")

    print("[5/7] Training and evaluating recommendation models")
    recommendation_metrics, diagnostics = evaluate_recommenders()
    print(f"      {int(diagnostics['heldout_interactions']):,} temporal holdout users")

    print("[6/7] Running paired experiment audit")
    audit = run_experiment_audit()
    print(
        f"      {int(audit['bootstrap_resamples']):,} paired bootstrap resamples; "
        f"Recall@10 support={audit['statistically_supported_recall10']}"
    )

    core_runtime = time.perf_counter() - started
    run_metadata = {
        "seed": SEED,
        "pipeline_runtime_seconds": round(core_runtime, 4),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    (RESULTS / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8"
    )

    print("[7/7] Rendering README and resume evidence from results")
    write_documentation()
    print(f"Complete in {core_runtime:.2f} seconds")
    for metric in recommendation_metrics:
        print(
            f"      {metric['model']}: Recall@10={float(metric['recall@10']):.4f}, "
            f"NDCG@10={float(metric['ndcg@10']):.4f}"
        )


if __name__ == "__main__":
    run_pipeline()
