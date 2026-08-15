"""Render README and resume evidence directly from generated result files."""

import csv
import json
from pathlib import Path
from typing import Dict, List

from config import DATA_RAW, EVENT_WEIGHTS, PROJECT_ROOT, RESULTS, SEED


def _read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _percent(value: object, decimals: int = 2) -> str:
    return f"{float(value) * 100:.{decimals}f}%"


def _decimal(value: object, decimals: int = 4) -> str:
    return f"{float(value):.{decimals}f}"


def write_documentation() -> None:
    metadata = json.loads((DATA_RAW / "dataset_metadata.json").read_text(encoding="utf-8"))
    runtime = json.loads((RESULTS / "run_metadata.json").read_text(encoding="utf-8"))
    funnel_rows = _read_rows(RESULTS / "funnel_metrics.csv")
    retention_rows = _read_rows(RESULTS / "retention_metrics.csv")
    ab = _read_rows(RESULTS / "ab_test_results.csv")[0]
    rec_rows = _read_rows(RESULTS / "recommendation_metrics.csv")
    segment_rows = _read_rows(RESULTS / "recommendation_segment_metrics.csv")
    diagnostics = {
        row["metric"]: row["value"] for row in _read_rows(RESULTS / "recommendation_diagnostics.csv")
    }
    overall = next(row for row in funnel_rows if row["dimension_type"] == "overall")
    experiment_funnel = [row for row in funnel_rows if row["dimension_type"] == "experiment_group"]
    significant = ab["statistically_significant_0_05"].lower() == "true"
    significance_text = "statistically significant" if significant else "not statistically significant"

    retention_table = "\n".join(
        f"| {row['cohort']} | {int(row['users']):,} | {int(row['week_1_eligible_users']):,} | "
        f"{_percent(row['week_1_retention'])} | {int(row['week_2_eligible_users']):,} | "
        f"{_percent(row['week_2_retention'])} |"
        for row in retention_rows
    )
    experiment_table = "\n".join(
        f"| {row['dimension_value']} | {int(row['view_events']):,} | {int(row['click_events']):,} | "
        f"{int(row['cart_events']):,} | {int(row['purchase_events']):,} | "
        f"{_percent(row['view_to_purchase_rate'])} |"
        for row in experiment_funnel
    )
    rec_table = "\n".join(
        f"| {row['model']} | {int(row['evaluated_users']):,} | {_decimal(row['recall@5'])} | "
        f"{_decimal(row['recall@10'])} | {_decimal(row['ndcg@5'])} | {_decimal(row['ndcg@10'])} |"
        for row in rec_rows
    )
    segment_table = "\n".join(
        f"| {row['model']} | {row['segment']} | {int(row['evaluated_users']):,} | "
        f"{_decimal(row['recall@10'])} | {_decimal(row['ndcg@10'])} |"
        for row in segment_rows
    )
    weights_text = ", ".join(f"`{event}` = {weight:g}" for event, weight in EVENT_WEIGHTS.items())

    readme = f"""# E-commerce Funnel & Recommendation Analytics

An end-to-end, locally runnable machine learning and analytics project built on a deterministic **synthetic** e-commerce event stream. It connects SQL product analytics, randomized-experiment analysis, implicit-feedback recommendation, and leakage-safe offline ranking evaluation.

## Motivation

This project studies how users move through an e-commerce funnel, return after acquisition, respond to a simulated ranking treatment, and interact with personalized recommendations. The data is entirely synthetic and the implementation makes no claim of production deployment or affiliation with any commerce platform.

## System / Data Pipeline

```text
Synthetic User Events
        ↓
SQLite / SQL Analytics
        ├── Funnel Metrics
        ├── Retention
        └── A/B Experiment
        ↓
Implicit User-Item Interactions
        ↓
Popularity + Item-Item Cosine + Content Models
        ↓
Temporal Offline Ranking Evaluation
```

The pipeline ran in **{float(runtime['pipeline_runtime_seconds']):.2f} seconds** on the recorded local run. Generation, experiment assignment, and modeling use seed **{metadata['seed']}**.

## Dataset

| Entity / event | Generated count |
|---|---:|
| Users | {metadata['users']:,} |
| Products | {metadata['products']:,} |
| Categories | {metadata['categories']:,} |
| Sessions | {metadata['sessions']:,} |
| Total events | {metadata['total_events']:,} |
| Views | {metadata['views']:,} |
| Clicks | {metadata['clicks']:,} |
| Add-to-carts | {metadata['add_to_carts']:,} |
| Purchases | {metadata['purchases']:,} |

Users vary in category preferences, activity, conversion propensity, and lifecycle segment. Products vary in category, price, quality, long-tailed popularity, and deterministic synthetic listing metadata. That metadata includes titles, keyword and feature terms, use cases, audiences, specifications, and category fields; it is generated for this project and is not marketplace data. The event stream spans `{metadata['observation_start']}` through `{metadata['observation_end']}`.

## Funnel Analysis

Funnel rates below are event-count ratios. Every click is generated after a view, every add-to-cart after a click, and every purchase after an add-to-cart for the same session-product impression.

| Stage | Unique users | Events |
|---|---:|---:|
| View | {int(overall['view_users']):,} | {int(overall['view_events']):,} |
| Click | {int(overall['click_users']):,} | {int(overall['click_events']):,} |
| Add to cart | {int(overall['cart_users']):,} | {int(overall['cart_events']):,} |
| Purchase | {int(overall['purchase_users']):,} | {int(overall['purchase_events']):,} |

| Transition | Conversion |
|---|---:|
| View → click | {_percent(overall['view_to_click_rate'])} |
| Click → cart | {_percent(overall['click_to_cart_rate'])} |
| Cart → purchase | {_percent(overall['cart_to_purchase_rate'])} |
| View → purchase | {_percent(overall['view_to_purchase_rate'])} |

The SQL also computes the complete funnel by product category and randomized experiment group in `results/funnel_metrics.csv`.

| Group | Views | Clicks | Carts | Purchases | View → purchase |
|---|---:|---:|---:|---:|---:|
{experiment_table}

## Retention / User Behavior

A user's acquisition timestamp is their first event. **Week +1 retention** means an eligible user has at least one event from day 7 (inclusive) to day 14 (exclusive) after that timestamp; **week +2 retention** uses day 14 (inclusive) to day 21 (exclusive). Eligibility requires that the observation window extends through the full return window. Cohorts are the Monday-starting calendar week of first activity.

| Cohort | Users | Week +1 eligible | Week +1 retention | Week +2 eligible | Week +2 retention |
|---|---:|---:|---:|---:|---:|
{retention_table}

## A/B Experiment

Eligible users are independently assigned once to control or treatment. The primary metric is **user purchase conversion**: whether a user made at least one purchase during the observation window. The analysis uses an independent two-proportion z-test with a pooled null standard error; the two-sided confidence interval for the absolute difference uses the unpooled standard error. It assumes independent randomized users and a sufficiently large normal approximation.

| Metric | Result |
|---|---:|
| Control users | {int(ab['control_users']):,} |
| Treatment users | {int(ab['treatment_users']):,} |
| Control conversion | {_percent(ab['control_rate'])} |
| Treatment conversion | {_percent(ab['treatment_rate'])} |
| Absolute uplift | {float(ab['absolute_uplift']) * 100:.2f} percentage points |
| Relative uplift | {_percent(ab['relative_uplift'])} |
| p-value | {_decimal(ab['p_value'])} |
| 95% CI for absolute uplift | [{float(ab['ci_95_lower']) * 100:.2f}, {float(ab['ci_95_upper']) * 100:.2f}] percentage points |

The observed treatment effect is **{significance_text}** at the pre-specified 0.05 level. The synthetic treatment modestly changes ranking affinity, click probability, and purchase probability; the analysis does not read or hardcode those parameters.

## Recommendation

The popularity baseline ranks products by summed pre-cutoff implicit weights. The collaborative model computes item-item cosine similarity from a sparse user-item matrix. The content model uses TF-IDF vectors from synthetic product listing metadata and creates each user profile as a weighted sum of only their pre-cutoff product vectors. Interaction weights are {weights_text}.

All training events occur before `{diagnostics['temporal_cutoff']}`. Each evaluated user has at least three distinct training products and one unseen click, add-to-cart, or purchase after the cutoff. The highest-intent unseen event is the single held-out target, candidates already seen during training are removed, and post-cutoff events never enter any model.

| Model | Evaluated users | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 |
|---|---:|---:|---:|---:|---:|
{rec_table}

With one relevant item per user, Recall@K is the hit rate, NDCG@K rewards higher target ranks, and Precision@K is also saved in `results/recommendation_metrics.csv`.

### History-length analysis and bias

| Model | Training-history segment | Users | Recall@10 | NDCG@10 |
|---|---|---:|---:|---:|
{segment_table}

The evaluation includes {int(diagnostics['heldout_interactions']):,} held-out interactions. {int(diagnostics['excluded_for_history_or_no_unseen_target']):,} post-cutoff positive users are excluded because they lack the minimum history or an unseen target. At ten recommendations, catalog coverage is {_percent(diagnostics['popularity_catalog_coverage@10'])} for popularity, {_percent(diagnostics['item_item_cosine_catalog_coverage@10'])} for item-item cosine, and {_percent(diagnostics['content_catalog_coverage@10'])} for content. Mean popularity percentile (where larger is more popular) is also recorded for all three models in `results/recommendation_diagnostics.csv`.

## Engineering

- Deterministic synthetic generation with isolated random streams for experiment assignment and behavioral generation.
- Normalized SQLite tables with foreign keys, checks, indexes, actual SQL CTEs, conditional aggregation, and a retention cohort query.
- A one-command pipeline that recreates raw data, the database, analyses, model evaluation, result CSVs, and documentation.
- A global temporal cutoff, unseen target constraint, and automated leakage assertions.
- Sparse implicit-feedback modeling, lightweight catalog TF-IDF, weighted training-only user profiles, and deterministic tie-breaking.
- Automated tests for data integrity, metric ranges, experiment consistency, output completeness, documentation values, and temporal isolation.

## Limitations

- The data and treatment effect are simulated; findings are not evidence about a real marketplace.
- The recommender is a lightweight offline candidate ranker, not a production retrieval-and-ranking stack.
- A single held-out positive simplifies evaluation and does not model multiple relevant items or counterfactual exposure.
- Offline metrics do not establish online business impact.
- There is no feature store, online serving path, distributed training, monitoring, or production infrastructure.
- Cold-start users without enough pre-cutoff history are excluded from personalized evaluation; popularity remains the fallback.

## Running the project

From the repository root:

```bash
python3 -m pip install -r requirements.txt
python3 src/run_all.py
python3 -m unittest discover -s tests -v
```

Or run the pipeline and tests together:

```bash
make all
```

Generated results live in `results/`; raw CSVs and the SQLite database live in `data/`. `RESUME_EVIDENCE.md` contains an audit of defensible claims and their exact sources.
"""
    (PROJECT_ROOT / "README.md").write_text(readme, encoding="utf-8")

    evidence = f"""# Resume Evidence Audit

This file lists facts verified from the latest successful pipeline run. It is deliberately not written as polished resume copy.

## Dataset scale

| Fact | Verified value | Source |
|---|---:|---|
| Users | {metadata['users']:,} | `data/raw/dataset_metadata.json` |
| Sessions | {metadata['sessions']:,} | `data/raw/dataset_metadata.json` |
| Products | {metadata['products']:,} | `data/raw/dataset_metadata.json` |
| Total event rows | {metadata['total_events']:,} | `data/raw/dataset_metadata.json` |
| Pre-cutoff training event rows | {int(diagnostics['train_event_rows']):,} | `results/recommendation_diagnostics.csv` |
| Held-out interactions / evaluated users | {int(diagnostics['heldout_interactions']):,} | `results/recommendation_diagnostics.csv` |

"Training event rows" means events strictly before the global cutoff. A held-out interaction is one unseen, post-cutoff, high-intent target for an eligible user; it is not a count of all post-cutoff events.

## Funnel results

| Fact | Verified value | Source |
|---|---:|---|
| View events | {int(overall['view_events']):,} | `results/funnel_metrics.csv` (`overall`, `all`) |
| Click events | {int(overall['click_events']):,} | `results/funnel_metrics.csv` (`overall`, `all`) |
| Add-to-cart events | {int(overall['cart_events']):,} | `results/funnel_metrics.csv` (`overall`, `all`) |
| Purchase events | {int(overall['purchase_events']):,} | `results/funnel_metrics.csv` (`overall`, `all`) |
| View → click rate | {_percent(overall['view_to_click_rate'])} | `results/funnel_metrics.csv` (`overall`, `all`) |
| Click → cart rate | {_percent(overall['click_to_cart_rate'])} | `results/funnel_metrics.csv` (`overall`, `all`) |
| Cart → purchase rate | {_percent(overall['cart_to_purchase_rate'])} | `results/funnel_metrics.csv` (`overall`, `all`) |
| View → purchase rate | {_percent(overall['view_to_purchase_rate'])} | `results/funnel_metrics.csv` (`overall`, `all`) |

These are event-count ratios, not unique-user transition probabilities. Category and experiment-group rows are in the same source file.

## A/B test

| Fact | Verified value | Source |
|---|---:|---|
| Control users | {int(ab['control_users']):,} | `results/ab_test_results.csv` |
| Treatment users | {int(ab['treatment_users']):,} | `results/ab_test_results.csv` |
| Control purchase conversion | {_percent(ab['control_rate'])} | `results/ab_test_results.csv` |
| Treatment purchase conversion | {_percent(ab['treatment_rate'])} | `results/ab_test_results.csv` |
| Absolute uplift | {float(ab['absolute_uplift']) * 100:.2f} percentage points | `results/ab_test_results.csv` |
| Relative uplift | {_percent(ab['relative_uplift'])} | `results/ab_test_results.csv` |
| Two-sided p-value | {_decimal(ab['p_value'])} | `results/ab_test_results.csv` |
| 95% CI, absolute uplift | [{float(ab['ci_95_lower']) * 100:.2f}, {float(ab['ci_95_upper']) * 100:.2f}] percentage points | `results/ab_test_results.csv` |

Result: the observed uplift is **{significance_text}** at the 0.05 level. It must not be described as a proven online conversion lift.

## Recommendation results

| Model | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 | Source |
|---|---:|---:|---:|---:|---|
""" + "\n".join(
        f"| {row['model']} | {_decimal(row['recall@5'])} | {_decimal(row['recall@10'])} | "
        f"{_decimal(row['ndcg@5'])} | {_decimal(row['ndcg@10'])} | `results/recommendation_metrics.csv` |"
        for row in rec_rows
    ) + f"""

Additional verified diagnostics:

- Popularity catalog coverage@10 = {_percent(diagnostics['popularity_catalog_coverage@10'])}. Source: `results/recommendation_diagnostics.csv`.
- Item-item cosine catalog coverage@10 = {_percent(diagnostics['item_item_cosine_catalog_coverage@10'])}. Source: `results/recommendation_diagnostics.csv`.
- Content catalog coverage@10 = {_percent(diagnostics['content_catalog_coverage@10'])}. Source: `results/recommendation_diagnostics.csv`.
- Results split by 3–5, 6–10, and 11+ distinct training items are in `results/recommendation_segment_metrics.csv`.

## Technical implementation

- `src/generate_data.py`: seeded synthetic users, products, sessions, ordered funnel events, category affinity, long-tailed item popularity, heterogeneous behavior, and a modest simulated treatment.
- `src/build_database.py`: CSV-to-SQLite pipeline, constraints, indexes, referential checks, and SQL result export.
- `src/funnel_analysis.sql`: CTE-based overall, category, and experiment-group funnel aggregation.
- `src/retention_analysis.sql`: first-active cohorts, observation-window eligibility, and explicitly bounded return windows.
- `src/ab_test.py`: user-level purchase conversion, two-proportion z-test, relative/absolute uplift, and unpooled confidence interval.
- `src/recommender.py`: weighted sparse user-item data, global temporal cutoff, unseen post-cutoff targets, popularity scores, and item-item cosine similarity.
- `src/content_based.py`: target-independent catalog TF-IDF, training-only weighted user profiles, cosine scoring, and seen-item exclusion.
- `src/evaluate_recommender.py`: shared deterministic Top-K ranking, seen-item filtering, Recall, Precision, NDCG, history segments, catalog coverage, and popularity-bias diagnostics.
- `tests/test_pipeline.py`: integrity, leakage, metric, result, and documentation checks.

## Reproducibility

- Pipeline command: `python3 src/run_all.py`
- Pipeline plus tests: `make all`
- Random seed: `{SEED}` (source: `src/config.py`; recorded in `data/raw/dataset_metadata.json`)
- Recorded core pipeline runtime: {float(runtime['pipeline_runtime_seconds']):.2f} seconds (source: `results/run_metadata.json`)
- Primary outputs: `results/funnel_metrics.csv`, `results/retention_metrics.csv`, `results/ab_test_results.csv`, `results/model_comparison.csv`, `results/content_history_metrics.csv`, and `results/recommendation_diagnostics.csv`.

## Limitations

- Do not claim the data is real, proprietary, or collected from an operating marketplace.
- Do not claim the A/B result is statistically significant; the generated p-value and interval do not support that statement.
- Do not claim online lift from offline ranking metrics.
- Do not claim a production recommender, real-time serving, distributed training, deep learning, causal treatment-effect identification beyond randomization, or production monitoring.
- Personalized evaluation excludes users without at least three distinct pre-cutoff products and users without an unseen post-cutoff positive.
- Metrics come from one deterministic synthetic data-generating process and one temporal split.

## Suggested resume facts

Ranked by relevance to a machine learning engineering internship; each is factual, not polished resume prose.

1. **Temporal recommendation evaluation:** trained on {int(diagnostics['train_event_rows']):,} pre-cutoff events and evaluated on {int(diagnostics['heldout_interactions']):,} unseen post-cutoff targets. Source: `results/recommendation_diagnostics.csv`.
2. **Personalized ranking quality:** item-item cosine achieved Recall@10 = {_decimal(rec_rows[1]['recall@10'])} and NDCG@10 = {_decimal(rec_rows[1]['ndcg@10'])}. Source: `results/recommendation_metrics.csv`.
3. **Baseline comparison:** popularity achieved Recall@10 = {_decimal(rec_rows[0]['recall@10'])} and NDCG@10 = {_decimal(rec_rows[0]['ndcg@10'])} under the identical candidate and holdout protocol. Source: `results/recommendation_metrics.csv`.
4. **Data pipeline scale:** generated {metadata['total_events']:,} ordered events across {metadata['users']:,} users, {metadata['sessions']:,} sessions, and {metadata['products']:,} products. Source: `data/raw/dataset_metadata.json`.
5. **Experiment analysis:** measured {float(ab['absolute_uplift']) * 100:.2f} percentage points of observed purchase-conversion uplift with p = {_decimal(ab['p_value'])} and explicitly reported the non-significant result. Source: `results/ab_test_results.csv`.
6. **Catalog-bias analysis:** measured catalog coverage@10 of {_percent(diagnostics['popularity_catalog_coverage@10'])} for popularity and {_percent(diagnostics['item_item_cosine_catalog_coverage@10'])} for personalized cosine ranking. Source: `results/recommendation_diagnostics.csv`.
"""
    (PROJECT_ROOT / "RESUME_EVIDENCE.md").write_text(evidence, encoding="utf-8")


if __name__ == "__main__":
    write_documentation()
