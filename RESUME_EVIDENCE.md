# Resume Evidence — E-commerce Search & Recommendation Platform

## 1. Project scope

A portfolio implementation of public-source marketplace keyword retrieval and feature-based ranking alongside a reproducible offline recommendation benchmark. It is designed to demonstrate honest data provenance, retrieval-versus-ranking analysis, temporal evaluation, and experiment interpretation for Search/Recommendation MLE roles.

## 2. My implemented system

- Node.js browser application and Vercel-compatible APIs for query expansion, source collection, report parsing, keyword extraction/ranking, and exports.
- Python/NumPy/SciPy recommendation pipeline with synthetic data generation, SQLite analysis, Popularity, item-item Collaborative, TF-IDF Content, and Hybrid models.
- Inner temporal validation, a frozen final test, paired statistical audit, segment diagnostics, deterministic A/B analysis, documentation generation, and automated tests.

## 3. Marketplace Search / Ranking

The Marketplace application expands market-, language-, intent-, and long-tail-aware queries. It collects public Bing and Google suggestions and, in Amazon mode, bounded DuckDuckGo public results. It supports English, German, and Spanish locale behavior across US, UK, Canada, Australia, Germany, and Spanish-language market options. Collection uses concurrency 8 and a 4.5-second timeout.

The frontend deduplicates evidence, extracts tokens, phrases, hashtags, and Chinese sequences, assigns rule-based categories, and ranks with observed frequency, query coverage, source coverage, real uploaded trend heat, intent/category, and specificity signals. `Weight` is an internal ranking score, not search volume. Primary APIs are `/api/marketplace-collect`, `/api/parse-upload`, and `/api/export-keyword-xlsx`; the export path produces CSV/audit output and multi-sheet XLSX workbooks.

## 4. Recommendation benchmark scale

The seed-2027 benchmark contains 15,000 users, 600 products, 10 categories, 58,591 sessions, and 330,270 events. There are 267,536 pre-final training event rows and 163,208 distinct training user-product interactions. Inner validation contains 4,580 targets, and the frozen final evaluation contains 3,954 targets.

Sources: `recsys/data/raw/dataset_metadata.json`, `recsys/results/evaluation_population_audit.json`, `recsys/results/hybrid_config.json`, and `recsys/results/retrieval_diagnostics.csv`.

## 5. Candidate retrieval

The selected retrievers contribute Collaborative Top-100, Content Top-100, and Popularity Top-10 candidates. The validation union averages 134.081 products and retrieves 83.908% of targets. Collaborative/Content lists have 56.875% mean Jaccard overlap, while Content uniquely accounts for 4.736% of retrieved validation target hits.

Source: `recsys/results/hybrid_config.json` and `recsys/results/retrieval_diagnostics.csv`.

## 6. Hybrid ranking

The Hybrid ranker applies per-user candidate min-max normalization and scores the candidate union with α=0.6 Collaborative, β=0.1 Content, and γ=0.3 Popularity. Missing, non-finite, and zero-variance component scores resolve deterministically to zero. The configuration came from inner temporal validation; final test metrics were not used for selection.

Source: `recsys/results/hybrid_config.json`.

## 7. Final model metrics

| Model | Recall@5 | NDCG@5 | Recall@10 | NDCG@10 | Coverage@10 |
|---|---:|---:|---:|---:|---:|
| Popularity | 0.0273 | 0.0165 | 0.0539 | 0.0248 | 0.0300 |
| Collaborative | 0.1624 | 0.1036 | 0.2597 | 0.1349 | 0.5433 |
| Content | 0.0610 | 0.0352 | 0.1222 | 0.0547 | 1.0000 |
| Hybrid | 0.1651 | 0.1052 | 0.2658 | 0.1374 | 0.5050 |

Source: `recsys/results/model_comparison.csv`.

## 8. Hybrid vs Collaborative

Hybrid improves mean Recall@10 by 0.00607 and NDCG@10 by 0.00249. The paired Recall@10 bootstrap CI is `[0.00000, 0.01214]` with exact McNemar `p=0.06694`; the NDCG@10 CI is `[0.00003, 0.00495]` with paired-randomization `p=0.05099`. Overall statistical superiority is therefore not established at `p<0.05`. Hybrid Coverage@10 is 0.5050 versus 0.5433 for Collaborative, a −3.83 percentage-point tradeoff.

Sources: `recsys/results/hybrid_bootstrap_ci.csv`, `recsys/results/hybrid_significance_tests.json`, and `recsys/results/model_comparison.csv`.

## 9. Sparse-history result

For 518 users with 3–5 historical products, Hybrid Recall@10 is 0.21815 versus 0.19498 for Collaborative, a +0.02317 difference with 95% CI `[0.00579, 0.04054]`. NDCG@10 rises from 0.09616 to 0.10534 with CI `[0.00267, 0.01614]`. This is exploratory lower-history evidence, not a true cold-start result.

Source: `recsys/results/sparse_history_audit.csv`.

## 10. Experimentation

The system selects Hybrid weights and candidate sizes on 4,580 inner temporal targets, then rebuilds models and evaluates once on 3,954 later frozen targets. Automated tests verify time boundaries, unseen-target isolation, configuration provenance, candidate filtering, population equality, target checksums, and aggregate reconstruction. The separate user-level synthetic A/B test measures purchase conversion: 31.83% control versus 32.94% treatment, `p=0.1445`, so its observed uplift is non-significant. The final suite contains 20 tests.

Sources: `recsys/results/hybrid_config.json`, `recsys/results/evaluation_population_audit.json`, and `recsys/results/ab_test_results.csv`.

## 11. Engineering

- Python pipeline orchestration, deterministic data generation, sparse matrices, TF-IDF, item-item cosine retrieval, Hybrid ranking, paired inference, and generated evidence.
- SQL/SQLite funnel and retention analyses.
- JavaScript and dependency-free Node HTTP APIs, concurrent external collection, browser-side extraction/ranking, XLSX ZIP/XML parsing, and workbook export.
- Root Make targets, compact result artifacts, automatic documentation consistency validation, and an end-to-end test suite.

## 12. Limitations

- Recommendation behavior, product content, and experiment outcomes are synthetic.
- Marketplace evidence comes from public sources or user uploads; there is no proprietary Amazon or TikTok dataset.
- There is no online recommender experiment, production traffic, distributed serving, real-time feature store, or latency/load benchmark.
- Recommendation metrics are offline and do not establish revenue or engagement impact.
- Hybrid's overall mean gains are modest and do not meet the prespecified `p<0.05` significance threshold.
- The lower-history segment is exploratory and does not represent zero-history cold start.

## 13. Top 8 Resume Facts

1. Built a deterministic offline recommendation benchmark spanning 15,000 users, 600 products, 58,591 sessions, and 330,270 implicit-feedback events. Source: `recsys/data/raw/dataset_metadata.json`.
2. Enforced model selection on 4,580 inner temporal targets and final reporting on 3,954 later frozen targets with zero population mismatch. Source: `recsys/results/hybrid_config.json` and `recsys/results/evaluation_population_audit.json`.
3. Implemented three-source candidate retrieval using Collaborative Top-100, Content Top-100, and Popularity Top-10, producing an average 134.081-candidate validation union and 83.908% target retrieval. Source: `recsys/results/hybrid_config.json` and `recsys/results/retrieval_diagnostics.csv`.
4. Delivered Hybrid Recall@10 of 0.2658 and NDCG@10 of 0.1374 on the frozen final test, versus 0.2597 and 0.1349 for Collaborative. Source: `recsys/results/model_comparison.csv`.
5. Quantified the final Hybrid bottleneck: 86.166% target retrieval but 26.581% Top-10 recall, with 2,356 targets retrieved below rank ten. Source: `recsys/results/retrieval_vs_ranking_analysis.csv`.
6. Found exploratory gains for 518 lower-history users: +0.02317 Recall@10 with 95% CI `[0.00579, 0.04054]`. Source: `recsys/results/sparse_history_audit.csv`.
7. Audited overall Hybrid gains with 10,000 paired bootstrap resamples and paired significance tests, correctly retaining the non-significant Recall@10 result at `p=0.06694`. Source: `recsys/results/hybrid_bootstrap_ci.csv` and `recsys/results/hybrid_significance_tests.json`.
8. Implemented and interpreted a 15,000-user randomized synthetic A/B test whose +1.12 percentage-point conversion difference was non-significant at `p=0.1445`. Source: `recsys/results/ab_test_results.csv`.

## 14. Claims I should NOT make

- That the project uses proprietary Amazon or TikTok data, official search volume, official platform heat, GMV, sales, reviews, or growth metrics.
- That Marketplace `Weight` is a demand estimate or that the keyword ranker is learned-to-rank, an NLP model, or an internal marketplace search engine.
- That the recommender uses live Marketplace collections in its reported benchmark.
- That Hybrid is statistically superior overall, solves cold start, or is proven to improve online conversion.
- That the A/B result is statistically significant or based on production users.
- That the system is a deep recommender, transformer ranker, distributed trainer, production serving stack, or real-time feature platform.

## Candidate Resume Bullets

- Built a reproducible Search and Recommendation benchmark with 15,000 synthetic users, 330,270 events, temporal validation, and a frozen 3,954-target final test.
- Implemented Collaborative Top-100, TF-IDF Content Top-100, and Popularity Top-10 candidate retrieval with per-user normalized Hybrid ranking, reaching 0.2658 Recall@10.
- Audited Hybrid ranking with paired per-user outcomes, 10,000 bootstrap resamples, confidence intervals, and significance tests while documenting the non-significant overall gain.
- Engineered a Node.js marketplace keyword pipeline with multilingual query expansion, concurrent public-source retrieval, feature-based ranking, strict metric provenance, and CSV/XLSX export.
