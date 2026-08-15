# Resume Evidence Audit

This file lists facts verified from the latest successful pipeline run. It is deliberately not written as polished resume copy.

## Dataset scale

| Fact | Verified value | Source |
|---|---:|---|
| Users | 15,000 | `data/raw/dataset_metadata.json` |
| Sessions | 58,591 | `data/raw/dataset_metadata.json` |
| Products | 600 | `data/raw/dataset_metadata.json` |
| Total event rows | 330,270 | `data/raw/dataset_metadata.json` |
| Pre-cutoff training event rows | 267,536 | `results/recommendation_diagnostics.csv` |
| Held-out interactions / evaluated users | 3,954 | `results/recommendation_diagnostics.csv` |

"Training event rows" means events strictly before the global cutoff. A held-out interaction is one unseen, post-cutoff, high-intent target for an eligible user; it is not a count of all post-cutoff events.

## Funnel results

| Fact | Verified value | Source |
|---|---:|---|
| View events | 240,784 | `results/funnel_metrics.csv` (`overall`, `all`) |
| Click events | 58,215 | `results/funnel_metrics.csv` (`overall`, `all`) |
| Add-to-cart events | 20,709 | `results/funnel_metrics.csv` (`overall`, `all`) |
| Purchase events | 10,562 | `results/funnel_metrics.csv` (`overall`, `all`) |
| View → click rate | 24.18% | `results/funnel_metrics.csv` (`overall`, `all`) |
| Click → cart rate | 35.57% | `results/funnel_metrics.csv` (`overall`, `all`) |
| Cart → purchase rate | 51.00% | `results/funnel_metrics.csv` (`overall`, `all`) |
| View → purchase rate | 4.39% | `results/funnel_metrics.csv` (`overall`, `all`) |

These are event-count ratios, not unique-user transition probabilities. Category and experiment-group rows are in the same source file.

## A/B test

| Fact | Verified value | Source |
|---|---:|---|
| Control users | 7,396 | `results/ab_test_results.csv` |
| Treatment users | 7,604 | `results/ab_test_results.csv` |
| Control purchase conversion | 31.83% | `results/ab_test_results.csv` |
| Treatment purchase conversion | 32.94% | `results/ab_test_results.csv` |
| Absolute uplift | 1.12 percentage points | `results/ab_test_results.csv` |
| Relative uplift | 3.50% | `results/ab_test_results.csv` |
| Two-sided p-value | 0.1445 | `results/ab_test_results.csv` |
| 95% CI, absolute uplift | [-0.38, 2.61] percentage points | `results/ab_test_results.csv` |

Result: the observed uplift is **not statistically significant** at the 0.05 level. It must not be described as a proven online conversion lift.

## Recommendation results

| Model | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 | Source |
|---|---:|---:|---:|---:|---|
| popularity | 0.0273 | 0.0539 | 0.0165 | 0.0248 | `results/recommendation_metrics.csv` |
| item_item_cosine | 0.1624 | 0.2597 | 0.1036 | 0.1349 | `results/recommendation_metrics.csv` |
| content | 0.0610 | 0.1222 | 0.0352 | 0.0547 | `results/recommendation_metrics.csv` |
| hybrid | 0.1651 | 0.2658 | 0.1052 | 0.1374 | `results/recommendation_metrics.csv` |

Additional verified diagnostics:

- Popularity catalog coverage@10 = 3.00%. Source: `results/recommendation_diagnostics.csv`.
- Item-item cosine catalog coverage@10 = 54.33%. Source: `results/recommendation_diagnostics.csv`.
- Content catalog coverage@10 = 100.00%. Source: `results/recommendation_diagnostics.csv`.
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
- Random seed: `2027` (source: `src/config.py`; recorded in `data/raw/dataset_metadata.json`)
- Recorded core pipeline runtime: 13.93 seconds (source: `results/run_metadata.json`)
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

1. **Temporal recommendation evaluation:** trained on 267,536 pre-cutoff events and evaluated on 3,954 unseen post-cutoff targets. Source: `results/recommendation_diagnostics.csv`.
2. **Personalized ranking quality:** item-item cosine achieved Recall@10 = 0.2597 and NDCG@10 = 0.1349. Source: `results/recommendation_metrics.csv`.
3. **Baseline comparison:** popularity achieved Recall@10 = 0.0539 and NDCG@10 = 0.0248 under the identical candidate and holdout protocol. Source: `results/recommendation_metrics.csv`.
4. **Data pipeline scale:** generated 330,270 ordered events across 15,000 users, 58,591 sessions, and 600 products. Source: `data/raw/dataset_metadata.json`.
5. **Experiment analysis:** measured 1.12 percentage points of observed purchase-conversion uplift with p = 0.1445 and explicitly reported the non-significant result. Source: `results/ab_test_results.csv`.
6. **Catalog-bias analysis:** measured catalog coverage@10 of 3.00% for popularity and 54.33% for personalized cosine ranking. Source: `results/recommendation_diagnostics.csv`.
