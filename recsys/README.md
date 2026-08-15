# E-commerce Funnel & Recommendation Analytics

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

The pipeline ran in **13.93 seconds** on the recorded local run. Generation, experiment assignment, and modeling use seed **2027**.

## Dataset

| Entity / event | Generated count |
|---|---:|
| Users | 15,000 |
| Products | 600 |
| Categories | 10 |
| Sessions | 58,591 |
| Total events | 330,270 |
| Views | 240,784 |
| Clicks | 58,215 |
| Add-to-carts | 20,709 |
| Purchases | 10,562 |

Users vary in category preferences, activity, conversion propensity, and lifecycle segment. Products vary in category, price, quality, long-tailed popularity, and deterministic synthetic listing metadata. That metadata includes titles, keyword and feature terms, use cases, audiences, specifications, and category fields; it is generated for this project and is not marketplace data. The event stream spans `2026-01-05 02:26:54` through `2026-03-01 22:51:28`.

## Funnel Analysis

Funnel rates below are event-count ratios. Every click is generated after a view, every add-to-cart after a click, and every purchase after an add-to-cart for the same session-product impression.

| Stage | Unique users | Events |
|---|---:|---:|
| View | 15,000 | 240,784 |
| Click | 12,057 | 58,215 |
| Add to cart | 7,319 | 20,709 |
| Purchase | 4,859 | 10,562 |

| Transition | Conversion |
|---|---:|
| View → click | 24.18% |
| Click → cart | 35.57% |
| Cart → purchase | 51.00% |
| View → purchase | 4.39% |

The SQL also computes the complete funnel by product category and randomized experiment group in `results/funnel_metrics.csv`.

| Group | Views | Clicks | Carts | Purchases | View → purchase |
|---|---:|---:|---:|---:|---:|
| control | 119,112 | 28,174 | 10,096 | 4,990 | 4.19% |
| treatment | 121,672 | 30,041 | 10,613 | 5,572 | 4.58% |

## Retention / User Behavior

A user's acquisition timestamp is their first event. **Week +1 retention** means an eligible user has at least one event from day 7 (inclusive) to day 14 (exclusive) after that timestamp; **week +2 retention** uses day 14 (inclusive) to day 21 (exclusive). Eligibility requires that the observation window extends through the full return window. Cohorts are the Monday-starting calendar week of first activity.

| Cohort | Users | Week +1 eligible | Week +1 retention | Week +2 eligible | Week +2 retention |
|---|---:|---:|---:|---:|---:|
| 2026-01-05 | 3,579 | 3,579 | 35.29% | 3,579 | 31.60% |
| 2026-01-12 | 3,611 | 3,611 | 38.69% | 3,611 | 34.59% |
| 2026-01-19 | 3,706 | 3,706 | 41.45% | 3,706 | 37.08% |
| 2026-01-26 | 3,621 | 3,621 | 45.43% | 3,621 | 40.57% |
| 2026-02-02 | 483 | 483 | 48.65% | 483 | 39.96% |

## A/B Experiment

Eligible users are independently assigned once to control or treatment. The primary metric is **user purchase conversion**: whether a user made at least one purchase during the observation window. The analysis uses an independent two-proportion z-test with a pooled null standard error; the two-sided confidence interval for the absolute difference uses the unpooled standard error. It assumes independent randomized users and a sufficiently large normal approximation.

| Metric | Result |
|---|---:|
| Control users | 7,396 |
| Treatment users | 7,604 |
| Control conversion | 31.83% |
| Treatment conversion | 32.94% |
| Absolute uplift | 1.12 percentage points |
| Relative uplift | 3.50% |
| p-value | 0.1445 |
| 95% CI for absolute uplift | [-0.38, 2.61] percentage points |

The observed treatment effect is **not statistically significant** at the pre-specified 0.05 level. The synthetic treatment modestly changes ranking affinity, click probability, and purchase probability; the analysis does not read or hardcode those parameters.

## Recommendation

The popularity baseline ranks products by summed pre-cutoff implicit weights. The collaborative model computes item-item cosine similarity from a sparse user-item matrix. The content model uses TF-IDF vectors from synthetic product listing metadata and creates each user profile as a weighted sum of only their pre-cutoff product vectors. Interaction weights are `view` = 1, `click` = 2, `add_to_cart` = 4, `purchase` = 6.

All training events occur before `2026-02-15 22:51:28`. Each evaluated user has at least three distinct training products and one unseen click, add-to-cart, or purchase after the cutoff. The highest-intent unseen event is the single held-out target, candidates already seen during training are removed, and post-cutoff events never enter any model.

| Model | Evaluated users | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 |
|---|---:|---:|---:|---:|---:|
| popularity | 3,954 | 0.0273 | 0.0539 | 0.0165 | 0.0248 |
| item_item_cosine | 3,954 | 0.1624 | 0.2597 | 0.1036 | 0.1349 |
| content | 3,954 | 0.0610 | 0.1222 | 0.0352 | 0.0547 |
| hybrid | 3,954 | 0.1651 | 0.2658 | 0.1052 | 0.1374 |

With one relevant item per user, Recall@K is the hit rate, NDCG@K rewards higher target ranks, and Precision@K is also saved in `results/recommendation_metrics.csv`.

### History-length analysis and bias

| Model | Training-history segment | Users | Recall@10 | NDCG@10 |
|---|---|---:|---:|---:|
| content | 11+ items | 2,493 | 0.1235 | 0.0547 |
| content | 3-5 items | 518 | 0.1081 | 0.0483 |
| content | 6-10 items | 943 | 0.1262 | 0.0582 |
| hybrid | 11+ items | 2,493 | 0.2792 | 0.1465 |
| hybrid | 3-5 items | 518 | 0.2181 | 0.1053 |
| hybrid | 6-10 items | 943 | 0.2566 | 0.1308 |
| item_item_cosine | 11+ items | 2,493 | 0.2752 | 0.1449 |
| item_item_cosine | 3-5 items | 518 | 0.1950 | 0.0962 |
| item_item_cosine | 6-10 items | 943 | 0.2545 | 0.1298 |
| popularity | 11+ items | 2,493 | 0.0550 | 0.0255 |
| popularity | 3-5 items | 518 | 0.0483 | 0.0249 |
| popularity | 6-10 items | 943 | 0.0541 | 0.0228 |

The evaluation includes 3,954 held-out interactions. 681 post-cutoff positive users are excluded because they lack the minimum history or an unseen target. At ten recommendations, catalog coverage is 3.00% for popularity, 54.33% for item-item cosine, and 100.00% for content. Mean popularity percentile (where larger is more popular) is also recorded for all three models in `results/recommendation_diagnostics.csv`.

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
