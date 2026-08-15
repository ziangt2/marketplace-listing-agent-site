#!/usr/bin/env python3
"""Verify that root documentation agrees with generated RecSys evidence."""

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECSYS = ROOT / "recsys"
README = (ROOT / "README.md").read_text(encoding="utf-8")


def csv_rows(name: str):
    with (RECSYS / "results" / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require(fragment: str, description: str, errors: list[str]) -> None:
    if fragment not in README:
        errors.append(f"missing {description}: {fragment!r}")


def main() -> int:
    errors: list[str] = []
    metadata = json.loads(
        (RECSYS / "data" / "raw" / "dataset_metadata.json").read_text(encoding="utf-8")
    )
    population = json.loads(
        (RECSYS / "results" / "evaluation_population_audit.json").read_text(encoding="utf-8")
    )
    config = json.loads(
        (RECSYS / "results" / "hybrid_config.json").read_text(encoding="utf-8")
    )
    significance = json.loads(
        (RECSYS / "results" / "hybrid_significance_tests.json").read_text(encoding="utf-8")
    )
    model_rows = csv_rows("model_comparison.csv")
    bootstrap = {row["metric"]: row for row in csv_rows("hybrid_bootstrap_ci.csv")}
    retrieval = {row["metric"]: row["value"] for row in csv_rows("retrieval_diagnostics.csv")}
    ab = csv_rows("ab_test_results.csv")[0]

    require("# E-commerce Search & Recommendation Platform", "project title", errors)
    for key in ("users", "products", "categories", "sessions", "total_events"):
        require(f"{int(metadata[key]):,}", f"dataset field {key}", errors)
    require(f"{int(population['target_count']):,}", "final target count", errors)
    require(f"{int(config['validation_users']):,}", "validation target count", errors)

    for row in model_rows:
        for metric in ("recall@5", "ndcg@5", "recall@10", "ndcg@10", "catalog_coverage@10"):
            require(f"{float(row[metric]):.4f}", f"{row['model']} {metric}", errors)

    require(
        f"Collaborative Top-{int(config['collaborative_m'])}",
        "Collaborative candidate size",
        errors,
    )
    require(f"Content Top-{int(config['content_m'])}", "Content candidate size", errors)
    require(f"Popularity Top-{int(config['popularity_m'])}", "Popularity candidate size", errors)
    require(
        f"α={config['alpha']}, β={config['beta']}, γ={config['gamma']}",
        "Hybrid weights",
        errors,
    )
    require(
        f"{float(retrieval['average_candidate_union_size']):.2f}",
        "average validation candidate union",
        errors,
    )
    require(
        f"{100 * float(retrieval['union_candidate_recall']):.2f}%",
        "validation candidate retrieval",
        errors,
    )

    recall_ci = bootstrap["Recall@10"]
    ndcg_ci = bootstrap["NDCG@10"]
    require(
        f"[{float(recall_ci['ci_95_lower']):.5f}, {float(recall_ci['ci_95_upper']):.5f}]",
        "Recall@10 confidence interval",
        errors,
    )
    require(
        f"[{float(ndcg_ci['ci_95_lower']):.5f}, {float(ndcg_ci['ci_95_upper']):.5f}]",
        "NDCG@10 confidence interval",
        errors,
    )
    require(f"p={float(significance['Recall@10']['p_value']):.5f}", "Recall@10 p-value", errors)
    require(f"p={float(significance['NDCG@10']['p_value']):.5f}", "NDCG@10 p-value", errors)
    require(f"{100 * float(ab['treatment_rate']):.2f}%", "A/B treatment conversion", errors)
    require(f"{100 * float(ab['control_rate']):.2f}%", "A/B control conversion", errors)
    require(f"p={float(ab['p_value']):.4f}", "A/B p-value", errors)
    require("not established overall statistical superiority", "statistical caveat", errors)
    require("live marketplace data is not used", "synthetic/live-data boundary", errors)

    if errors:
        print("Documentation consistency: FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Documentation consistency: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
