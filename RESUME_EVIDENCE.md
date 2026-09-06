# Resume Evidence — E-commerce Search & Recommendation Platform

## 1. Project scope

A portfolio implementation of public-source marketplace keyword retrieval and feature-based ranking alongside a reproducible offline recommendation benchmark, extended with a separately measured public ABO multimodal retrieval MVP. It is designed to demonstrate honest data provenance, retrieval-versus-ranking analysis, temporal evaluation, and experiment interpretation for Search/Recommendation MLE roles. Sections 2–14 below describe the historical systems; the distinct multimodal evidence appears afterward.

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
- The historical RecSys has no online recommender experiment, production traffic, distributed serving, real-time feature store, or latency/load benchmark. The separate ABO module reports local retrieval latency only.
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

The following generated section preserves the historical retrieval MVP and its phase-specific claim limits. The implemented RAG/agent extension and its separate evaluation follow below.

<!-- multimodal-results:start -->
## Multimodal Product Retrieval

A separate measured MVP over **1,000 public Amazon Berkeley Objects (ABO) products**, using pretrained `google/siglip2-base-patch16-224` with **768-dimensional**, L2-normalized image/text embeddings. No model was trained or fine-tuned. Inference used `mps`; model revision and preprocessing are recorded in [benchmark_config.json](multimodal/results/mvp/benchmark_config.json).

The catalog retains 1,532 unique small images. Image evaluation uses **523 distinct, unambiguous held-out catalog views** against the full product index. 476 alternate-view queries shared across multiple products were excluded, in addition to missing or unusable views. The query image cannot match any indexed image by image ID, bytes, or decoded pixels. [Dataset and exclusions](multimodal/results/mvp/dataset_summary.json).

| Image → product system | Queries | Recall@1 | Recall@5 | Recall@10 | MRR (full catalog) |
|---|---:|---:|---:|---:|---:|
| SigLIP2 + FAISS IndexFlatIP | 523 | 0.7151 | 0.8528 | 0.8929 | 0.7811 |

Source: [image_retrieval.csv](multimodal/results/mvp/image_retrieval.csv). NumPy exact cosine and FAISS have identical reported image metrics. IndexFlatIP is exact search, not ANN.

Text evaluation uses **81 deterministic structured-attribute queries**, with 2–50 relevant products per query. Binary relevance means matching the query's product type and all supplied attributes. Queries contain no product IDs, model numbers, or copied complete titles. Recall measures the fraction of relevant products retrieved, not just any-hit success.

| Text → product system | Recall@10 | NDCG@10 | MRR@50 |
|---|---:|---:|---:|
| BM25 metadata | 0.9174 | 0.8888 | 0.8614 |
| SigLIP2 text → image vectors | 0.5898 | 0.4482 | 0.4757 |
| RRF hybrid | 0.8415 | 0.7437 | 0.7600 |

Source: [text_retrieval.csv](multimodal/results/mvp/text_retrieval.csv). RRF fuses BM25 Top-50 and FAISS Top-50 with rank constant 60. Their candidate union recall is 0.9977. [Per-query source complementarity](multimodal/results/mvp/source_complementarity.csv).

**Observed result:** RRF improves over the vector-only baseline but underperforms BM25 on these exact-attribute labels. This benchmark favors lexical matching; it does not establish general semantic-search improvement.

| Warm local latency scope | p50 (ms) | p95 (ms) | Timed samples |
|---|---:|---:|---:|
| FAISS image-vector retrieval only, K=10 | 0.0444 | 0.0475 | 1569 |
| Image decode + uncached encoder + IPC + FAISS | 8.7084 | 9.4678 | 20 |
| Text preprocessing + uncached encoder + IPC + FAISS | 5.4045 | 5.5870 | 20 |
| BM25 + FAISS + RRF only, K=10 | 0.3940 | 0.6001 | 243 |

Source: [latency.json](multimodal/results/mvp/latency.json), with raw samples in [latency_samples.csv](multimodal/results/mvp/latency_samples.csv). Retrieval-only timings use cached query vectors. Encoding-inclusive timings use the first 20 query IDs per modality, a warm model, single-query inference and local worker communication. Model loading, downloads, network serving, and concurrent load are excluded. These are local measurements, not production SLA or scale claims.

The serialized FAISS index is 3,072,045 bytes and its measured construction took 0.001582 seconds, excluding embedding generation. [Index provenance](multimodal/results/mvp/benchmark_config.json).

Defaults were fixed before scoring. This is an exploratory development benchmark with held-out image views; products remain in the index. There is no model training split, no hyperparameter search, and no claim of a frozen final test. The largest catalog type is `CELLULAR_PHONE_CASE` (536/1000 products). Category imbalance, related variants, near-duplicate imagery, metadata-derived labels, and possible pretrained-data overlap limit generalization. These ABO results are independent of the historical synthetic behavioral RecSys metrics.

### Supported resume wording

- Extended an e-commerce search/recommendation platform with pretrained SigLIP2 image/text embeddings and FAISS exact vector retrieval over 1,000 public ABO listings; achieved 89.29% image-to-product Recall@10 on 523 distinct held-out views.
- Benchmarked BM25, vector retrieval, and Reciprocal Rank Fusion on 81 metadata-derived text queries; measured RRF Recall@10 of 0.8415 versus 0.5898 for vectors and 0.9174 for BM25.

### Multimodal claims I should NOT make

- Proprietary Amazon data, production-scale traffic, revenue impact, or online A/B improvement.
- Training/fine-tuning SigLIP2, a learned reranker, agent, VLM, grounded RAG, Azure deployment, or distributed serving.
- ANN or HNSW results: this MVP measures exact FAISS IndexFlatIP only.
- Hybrid beats the strongest baseline, human-judged relevance, or independent unseen-product generalization.
- Retrieval-only latency includes neural encoding, model startup, or network serving.

See the [module documentation](multimodal/README.md) for commands, ground-truth construction, and limitations.
<!-- multimodal-results:end -->

Agent setup, CLI examples, local API and replay commands: [agent guide](multimodal/AGENT.md).

<!-- agent-results:start -->
## Agentic Multimodal Product Search

One bounded tool-using agent and grounded RAG layer now extend the same 1,000-product ABO retrieval system. A completed **36-query development evaluation** uses `gpt-4.1-mini-2025-04-14`, temperature 0, with six cases in each of six categories. The LLM plans constraints and selects cited evidence; product-specific prose is rendered from validated fields. No training or fine-tuning.

Explicit lexical/category requests prefer BM25 because the historical structured-text benchmark favors it. Attached images use SigLIP2 + FAISS; mixed requests execute metadata filters. Ambiguous descriptions use RRF by default or the planner's vector route. This policy does not establish semantic relevance superiority.

Source: [frozen queries](multimodal/results/agent_v2/agent_queries.jsonl), [per-query evaluation](multimodal/results/agent_v2/agent_evaluation.csv), [full raw drafts, evidence and executed traces](multimodal/results/agent_v2/agent_runs.jsonl), [configuration/source hashes](multimodal/results/agent_v2/agent_benchmark_config.json).

| Deterministic measure | Measured result |
|---|---:|
| Expected first tool | 36/36 (100.00%) |
| Expected conditional tool sequence | 36/36 (100.00%) |
| Successful tool execution | 123/123 (100.00%) |
| Invalid tool calls | 0/123 (0.00%) |
| Mean tool calls per query | 3.42 |
| Raw recommendation ID validity / candidate coverage | 59/59 (100.00%) |
| Raw evidence field validity | 328/329 (99.70%) |
| Raw evidence value validity | 327/329 (99.39%) |
| Raw unsupported structured attributes | 1/329 (0.30%) |
| Raw fully grounded, nonempty responses / all queries | 28/36 (77.78%) |
| Delivered grounded, nonempty responses / all queries | 28/36 (77.78%) |
| Delivered grounding among answered queries | 28/28 (100.00%) |
| Constraint satisfaction among emitted constrained recommendations | 34/34 (100.00%) |
| Constraint queries answered with satisfying recommendations | 20/24 (83.33%) |
| Unsupported requests explicitly acknowledged | 8/8 (100.00%) |

Source: [rag_grounding_metrics.json](multimodal/results/agent_v2/rag_grounding_metrics.json). Outcomes: **28 answered, 6 abstained, 2 errors**. Empty responses never earn grounding or constraint-coverage credit. These checks establish metadata fidelity on structured claims; answer relevance, real-world catalog accuracy and apartment suitability are not measured.

| Warm latency scope, 36 sequential queries | p50 (ms) | p95 (ms) |
|---|---:|---:|
| Local retrieval, including query encoding/IPC when used | 9.54 | 49.01 |
| Hosted LLM calls per query, excluding cached requests | 2561.05 | 3983.13 |
| LLM boundary including cache lookup | 2566.43 | 3985.49 |
| Total agent request | 2614.59 | 4009.38 |

Source: [agent_latency.json](multimodal/results/agent_v2/agent_latency.json). 62 live API calls and 5 exact-request cache hits; shared image-only planning requests may hit the cache. Startup/model/index preparation (3269.07 ms) is excluded. Local timings and API/network timings are separate; the historical 9.47 ms image-only p95 is unchanged and is not total agent latency.

The same authored fixtures were used to diagnose and repair an initial run, retained in [agent_v1](multimodal/results/agent_v1/rag_grounding_metrics.json), then evaluated as v2. This is development evaluation, not an independent held-out agent test. Image inputs reuse held-out views of indexed products. No online business impact, production-scale serving, model training, Azure, multi-agent autonomy, RRF superiority over BM25, or general elimination of hallucinations is claimed.

### Supported agent resume wording

- Extended pretrained multimodal product retrieval with a bounded tool-using agent, structured LLM evidence selection and deterministic grounding checks; executed 36 development queries with 100% expected-tool routing and 28/36 nonempty grounded responses.
- Validated 329 structured evidence claims against retrieved ABO metadata; measured 34/34 constraint-satisfying emitted recommendations, with abstentions and coverage reported separately.
<!-- agent-results:end -->
