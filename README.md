# E-commerce Search & Recommendation Platform

> An end-to-end e-commerce ML project covering recommendation, multimodal retrieval, and grounded product search.

## What it does

- Builds personalized recommendations from collaborative, content, and popularity candidate sources followed by hybrid ranking.
- Retrieves products from text or images using BM25, SigLIP2 embeddings, and FAISS.
- Supports grounded product search with constraint checking and cited product evidence.
- Includes temporal evaluation, leakage checks, reproducible experiments, and automated tests.

## Results

**Recommendation**

- 330,270 events across 15,000 users and 600 products
- Hybrid Recall@10: **0.2658**
- Hybrid NDCG@10: **0.1374**

**Multimodal retrieval**

- Evaluated on 1,000 public Amazon Berkeley Objects products
- Image → product Recall@10: **0.8929**
- Image → product MRR: **0.7811**

**Product search agent**

- 36/36 correct initial routes
- 123/123 successful tool calls
- Invalid or unsupported answers are withheld rather than returned

## Tech

Python · PyTorch · FAISS · SigLIP2 · SQL · BM25 · Node.js

## Architecture

This repository combines three implemented systems: a Node.js web application for public-source marketplace keyword intelligence, a Python behavioral recommendation benchmark, and pretrained multimodal product retrieval over public ABO listings, now extended with grounded RAG and one tool-using Product Search Agent. The shared theme is evidence-driven search and recommendation: collect observable signals, distinguish retrieval from ranking, preserve data provenance, and evaluate with explicit task boundaries. Temporal splits apply to the behavioral RecSys; the separate ABO benchmark uses held-out image views and metadata-derived text queries. Agent evaluation uses authored development queries.

The systems are related conceptually but not joined by live production data. The offline recommender uses deterministic **synthetic** product metadata modeled after the Marketplace Agent's keyword/category feature schema; live marketplace data is not used in the reported recommendation metrics. The new [multimodal module](multimodal/README.md) uses real public ABO catalog images and metadata, with its own manifests, tests, and results. Its measurements are reported separately below.

```text
Marketplace Search / Keyword Intelligence

Marketplace Query
      ↓
Query Expansion (market, language, intent, long tail)
      ↓
Public Suggestions / Public Sources + Uploaded Reports
      ↓
Deduplication → Keyword Extraction → Rule Categories
      ↓
Feature-Based Keyword Ranking
      ↓
CSV / XLSX / Source Audit

Recommendation Benchmark

Synthetic User Events → Temporal Training History
                           ├─ Collaborative Top-100 ─┐
                           ├─ Content Top-100 ───────┼─ Candidate Union
                           └─ Popularity Top-10 ─────┘
                                                      ↓
                                      Per-user Min-Max Normalization
                                                      ↓
                                  Hybrid Score (0.6 / 0.1 / 0.3)
                                                      ↓
                                             Top-K Offline Evaluation
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation boundaries, API flow, provenance, and limitations.

## Marketplace Search & Ranking

The web application supports Amazon- and TikTok Shop-oriented keyword research using accessible public sources and user-uploaded reports. It does **not** represent either marketplace's internal search system.

### Ingestion and query expansion

`api/marketplace-collect.js` builds keyword seeds and modifiers for US, UK, Canada, Australia, Germany, multiple Spanish-language markets, and a US/Spain/Mexico bundle. English, German, and Spanish locale parameters are propagated to public providers; several common product phrases also receive explicit Spanish seed variants. Collection runs with concurrency 8, a 4.5-second fetch timeout, and bounded query counts.

The implemented providers are Bing and Google public search suggestions. Amazon mode can additionally use bounded DuckDuckGo public search results. TikTok Shop mode currently prioritizes public suggestion queries: direct public-page and general-search execution limits are set to zero for reliability, so this project does not claim comprehensive TikTok product-page crawling.

Collected records retain source query, provider, URL, region, language, and source type. Normalized URL/title keys remove duplicates before the frontend converts source text into candidate terms.

### Extraction, categories, and Weight

The browser extracts English-style tokens, 2–4 token phrases, hashtags, and 2–4 character Chinese sequences. Candidates are assigned rule-based roles such as core keyword, audience, material, specification, variant, use case, functional feature, pain point, content scene, hashtag, or uploaded-report term.

Final keyword `Weight` is an internal 1–100 priority score:

- log-scaled observed frequency: up to 45 points;
- source-query coverage: up to 15 points;
- source-type coverage: up to 10 points;
- real uploaded trend heat, when present: up to 15 points;
- category/intent weighting and long-tail specificity: remaining contribution.

Ties use observed count and then lexical order. **Weight is not marketplace search volume, official heat, sales, or demand.** Uploaded trend/volume/growth values affect output only when a real report contains those fields.

### Reports and exports

Users can paste text or upload CSV, TSV, TXT, XLS, and XLSX reports. The server includes a dependency-free XLSX ZIP/XML reader and writer. Exports include the keyword template, summary, agent analysis, and a real-trend sheet; CSV and plain-text source audits are also available.

## Personalized Recommendation

The RecSys module generates a seeded implicit-feedback event stream with views, clicks, add-to-carts, and purchases weighted 1, 2, 4, and 6. It evaluates:

- **Popularity:** globally summed pre-cutoff interaction weight.
- **Collaborative:** log-scaled sparse user-item histories and item-item cosine similarity.
- **Content:** L2-normalized TF-IDF product vectors and weighted training-only user profiles.
- **Hybrid:** explicit candidate union followed by normalized weighted scoring.

Content features include synthetic title, category, subcategory, keywords, tags, price bucket, use case, audience, and attributes. Singleton terms are excluded from TF-IDF so a unique synthetic token cannot become a product identifier. Products already seen in training are filtered from every recommendation list.

## Dataset

The deterministic seed-2027 benchmark contains 15,000 users, 600 products, 10 categories, 58,591 sessions, and 330,270 events. Of those events, 267,536 occur before the final cutoff and form 163,208 distinct training user-product interactions. Recommendation behavior, product content, and the simulated experiment are synthetic; no collected marketplace record enters these metrics.

## Evaluation Protocol

The recommender uses two temporal boundaries:

1. **Inner training and validation:** 175,589 earlier events train candidate sources; 4,580 unseen later targets select candidate size and Hybrid weights through a deterministic 198-configuration grid.
2. **Frozen final test:** models are rebuilt on all 267,536 pre-final events and evaluated once on the same 3,954 unseen targets. Final labels never enter selection or normalization.

Every model shares the identical user population, target checksum, cutoff, seen-item exclusion, and metric implementation. Automated checks verify temporal isolation, profile construction, candidate deduplication, configuration provenance, per-user aggregate reconstruction, and population equality. The full methodology is in [recsys/EXPERIMENT_AUDIT.md](recsys/EXPERIMENT_AUDIT.md).

## Results

Authoritative source: [recsys/results/model_comparison.csv](recsys/results/model_comparison.csv).

| Model | Recall@5 | NDCG@5 | Recall@10 | NDCG@10 | Coverage@10 |
|---|---:|---:|---:|---:|---:|
| Popularity | 0.0273 | 0.0165 | 0.0539 | 0.0248 | 0.0300 |
| Collaborative | 0.1624 | 0.1036 | 0.2597 | 0.1349 | 0.5433 |
| Content | 0.0610 | 0.0352 | 0.1222 | 0.0547 | 1.0000 |
| Hybrid | 0.1651 | 0.1052 | 0.2658 | 0.1374 | 0.5050 |

Hybrid's observed Recall@10 delta over Collaborative is +0.00607 and its NDCG@10 delta is +0.00249. These are modest mean improvements, not established overall statistical superiority: Recall@10 has paired-bootstrap 95% CI `[0.00000, 0.01214]` and exact McNemar `p=0.06694`; NDCG@10 has CI `[0.00003, 0.00495]` and paired-randomization `p=0.05099`.

## Hybrid Analysis

The selected validation configuration is Collaborative Top-100, Content Top-100, Popularity Top-10, per-user candidate min-max normalization, and weights α=0.6, β=0.1, γ=0.3. Its validation candidate union averages 134.08 products, retrieves 83.91% of validation targets, and has 56.88% mean Collaborative/Content Jaccard overlap. Content uniquely recovers 4.74% of validation union hits.

On the final test, Hybrid retrieves 86.17% of targets but ranks only 26.58% in Top-10. Of 3,954 targets, 547 are not retrieved and 2,356 are retrieved but ranked below ten. Ranking is therefore the larger measured bottleneck. Hybrid also trades breadth for ranking concentration: Coverage@10 falls 3.83 percentage points below Collaborative.

## Sparse-History Analysis

Among 518 users with 3–5 prior products, Hybrid Recall@10 is 0.21815 versus 0.19498 for Collaborative, a +0.02317 absolute difference; paired CI is `[0.00579, 0.04054]`. NDCG@10 increases from 0.09616 to 0.10534 with CI `[0.00267, 0.01614]`. This is an exploratory lower-history result, not evidence that the system solves cold start; every evaluated user has at least three prior products.

## A/B Experiment

The pipeline also implements deterministic user-level random assignment and a two-proportion test for whether a user purchased at least once. Treatment conversion is 32.94% versus 31.83% for control, an observed +1.12 percentage-point difference with 95% CI `[-0.38, 2.61]` percentage points and `p=0.1445`. The result is non-significant and demonstrates experiment implementation, not product impact.

## APIs / Web Application

The Node server serves the static frontend and these primary keyword routes:

- `POST /api/marketplace-collect` — expand and collect public-source keyword evidence;
- `POST /api/parse-upload` — convert uploaded XLSX content to auditable text;
- `POST /api/export-keyword-xlsx` — create a multi-sheet XLSX workbook.

The repository retains optional image/video experiment routes, but they are outside the reported search and recommendation benchmark. Vercel rewrites preserve `/api/*` handlers and route other requests to the frontend.

## Reproducing Results

Python 3.9+ with NumPy and SciPy is required for RecSys. Node.js runs the dependency-free Marketplace app.

```bash
python3 -m pip install -r recsys/requirements.txt
make recsys       # rebuild data, SQL analyses, models, statistical audit, and evidence
make test         # run all RecSys tests
make verify-docs  # confirm README values match result artifacts
```

Run the web application separately:

```bash
npm run dev
# http://127.0.0.1:8066
```

API keys are optional for keyword functionality. Keep real keys in ignored `.env.local` or managed deployment variables; never commit them.

## Tests

The historical RecSys suite contains 20 tests covering event integrity, assignment consistency, temporal leakage, Content profiles, seen-item exclusion, deterministic metrics, candidate retrieval, normalization, validation/final separation, configuration provenance, paired bootstrap reproducibility, McNemar counts, population equality, per-user metric reconstruction, result ranges, and documentation consistency.

## Data Integrity & Limitations

- Public suggestions and accessible public pages are discovery evidence, not official marketplace metrics.
- Search volume, official platform heat, ABA values, GMV, sales, reviews, and growth are never fabricated; absent real uploads, those fields stay blank.
- The recommendation benchmark and A/B treatment are synthetic and use one deterministic seed.
- The project has no proprietary Amazon/TikTok data, online recommender test, production traffic, distributed serving, or real-time feature store.
- Offline ranking metrics and the non-significant synthetic A/B result do not establish online business impact.
- The keyword ranker is feature-based code, not a learned-to-rank or NLP model; the recommender is lightweight sparse/TF-IDF modeling, not a neural or deep recommender.

## Repository Structure

```text
api/                         Node/Vercel keyword, upload, export, and auxiliary APIs
app.js, index.html, styles.css
                             Browser application and keyword ranking
collector-server.js          Local static/API server
recsys/src/                  Data, SQL, models, evaluation, statistical audit
recsys/results/              Compact reproducible evidence artifacts
recsys/tests/                End-to-end and methodology tests
multimodal/                  Public ABO pretrained image/text retrieval and benchmark
ARCHITECTURE.md              Detailed system boundaries and data flow
RESUME_EVIDENCE.md           Claim-by-claim recruiting evidence
INTERVIEW_NOTES.md           Technical talking points
```

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
<!-- agent-results:end -->
