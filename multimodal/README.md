# Pretrained Multimodal Product Retrieval

An isolated public ABO extension to the existing marketplace search and
behavioral recommendation project. It performs pretrained image/text encoding,
NumPy exact retrieval, FAISS IndexFlatIP, BM25 metadata search, and reciprocal
rank fusion. The original retrieval MVP is preserved. A subsequent extension adds
grounded RAG, one bounded Product Search Agent, and a local JSON API. No training,
fine-tuning, learned reranking, cloud deployment, Docker, or new web UI is included.

## Run it

From the repository root, using Python 3.11:

```bash
python3.11 -m venv .venv-multimodal
.venv-multimodal/bin/python -m pip install -r multimodal/requirements.lock.txt
make multimodal-test
make multimodal-dev        # separate 500-product profile; downloads and benchmarks
make multimodal-benchmark  # 1,000-product MVP; reruns go to a fresh local result directory
```

The lock file records the actual Apple Silicon environment. On other platforms,
install `multimodal/requirements.txt` if an exact wheel is unavailable and retain
the environment versions in the new benchmark artifact. CPU and Apple MPS are
supported; CUDA auto-selection is implemented but has not been exercised here.
Use a copy of `config/default.json` with `encoder.device` set to `cpu` for CPU
inference. Retrieval alone requires no API key; the agent uses OpenAI. A first run needs public internet access for
ABO data and the pinned pretrained checkpoint. Subsequent runs reuse cached data
and vectors. `MULTIMODAL_PYTHON=/path/to/python` overrides the Make interpreter.

Published results are never overwritten by a rerun. When the profile already has
results, Make/CLI automatically select a fresh timestamped `results/local-*`
directory. You can also choose a new directory explicitly:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-multimodal/bin/python -m multimodal.src.benchmark \
  --profile mvp --output multimodal/results/local-check
```

Choose a fresh output directory for each repeated run. `standard` is a configurable
5,000-product target, not a claim of a completed benchmark. Standalone preparation
and embedding stages are also available:

```bash
.venv-multimodal/bin/python -m multimodal.src.build_catalog --profile mvp
.venv-multimodal/bin/python -m multimodal.src.build_embeddings --profile mvp
.venv-multimodal/bin/python -m multimodal.src.search --text 'modern wooden chair' --mode vector
.venv-multimodal/bin/python -m multimodal.src.search --text 'brown shoes' --mode hybrid
.venv-multimodal/bin/python -m multimodal.src.search --image /absolute/path/to/query.jpg --k 5
```

Search returns actual product metadata, similarity/fusion scores, source ranks,
and query latency. Image queries are encoded directly; text vectors search the
same image index. This is retrieval over products, not behavioral personalization.

## Ground truth and evaluation

Image queries use a different view of the same underlying item. Same bytes,
same decoded pixels, any indexed-image identity, and query images shared by
multiple products in the selected catalog are excluded. This is view holdout,
not a new-product generalization test. All methods see the identical catalog.

Text queries are deterministic conjunctions of product type and available
material/color/style. Short alphabetic attribute values are allowed; numeric
codes, model identifiers and copied entire titles are excluded. We enumerate
attribute groups, retain groups with at least two and at most the smaller of
50 or 10% of catalog products, then choose the most specific valid group per
product (lexicographic tie-break) and deduplicate. Relevance is the exact
conjunction of those fields; every catalog match is included. There is no
single designated target that incorrectly treats equivalent products as wrong.

Recall is macro-averaged `relevant hits / relevance-set size`. NDCG uses binary
relevance and an ideal ranking of `min(K, relevant count)` positives. Image MRR
uses full-catalog ranks; text MRR@50 uses the first 50 returned products for all
systems, including RRF. Empty lexical results are valid misses. The separate
`hit@K` values must not be mislabeled Recall when multiple positives exist.

BM25 uses rank-bm25's BM25Okapi, with k1=1.5 and b=0.75; positive-scoring results
only. It searches title, product type, material, color, style, brand, pattern
and finish. Tokens are lowercase alphabetic words. RRF uses `sum(1/(60+rank))`
over the two Top-50 lists; absent-source contributions are zero. Neither scores
nor query relevance labels enter the other retriever. Exact search breaks score
ties by product ID; FAISS ties are sorted within its returned set, with native
FAISS membership at the cutoff boundary.

All defaults were fixed before scoring. No hyperparameters were selected from
benchmark results. This is an exploratory development benchmark, not a frozen
final test. Text labels favor lexical matching and are not independent human
judgments. ABO categories and variants are imbalanced; unique-view filtering
changes the image-query population. No model-pretraining overlap audit was
performed. Statistical significance or online impact is not claimed.

## Runtime and reproducibility

SigLIP2 is pinned to the revision in `config/default.json`. It runs float32
inference with frozen weights, `torch.inference_mode`, fixed input ordering,
RGB/EXIF handling, model preprocessing, and L2 normalization. Embedding caches
key source content, model revision, preprocessing, device and library versions.
Cache entries include identity/checksum alignment and reject corrupt vectors.

The tested macOS wheels load different OpenMP runtimes for PyTorch and FAISS.
To avoid an actual observed native-library abort, neural inference runs in one
persistent local Python worker and returns vectors through private pipes.
FAISS stays in the parent process. No unsafe duplicate-runtime override or
installed-library patch is used. This is local process isolation, not distributed
serving. Encoding-inclusive latency includes worker communication.

FAISS uses one CPU thread. Warm retrieval and uncached single-query encoding
are measured separately. Reports preserve raw timings, exact populations,
configuration, source hashes, model information, Python/platform/library versions,
FAISS build time and serialized index size. A new completed run is required
before making a new latency claim. IndexFlatIP is exact; no ANN results are
claimed in the urgent MVP.

See [data attribution and subset rules](data/README.md),
[artifact definitions](results/README.md), and [initial audit](IMPLEMENTATION_PLAN.md).
Generate numerical documentation only from completed MVP artifacts:

```bash
.venv-multimodal/bin/python -m multimodal.src.report
make multimodal-verify-docs
make test
make verify-docs
```

The following generated section preserves the historical retrieval MVP and its phase-specific claim limits. The implemented RAG/agent extension and its separate evaluation follow below.

<!-- multimodal-results:start -->
## Multimodal Product Retrieval

A separate measured MVP over **1,000 public Amazon Berkeley Objects (ABO) products**, using pretrained `google/siglip2-base-patch16-224` with **768-dimensional**, L2-normalized image/text embeddings. No model was trained or fine-tuned. Inference used `mps`; model revision and preprocessing are recorded in [benchmark_config.json](results/mvp/benchmark_config.json).

The catalog retains 1,532 unique small images. Image evaluation uses **523 distinct, unambiguous held-out catalog views** against the full product index. 476 alternate-view queries shared across multiple products were excluded, in addition to missing or unusable views. The query image cannot match any indexed image by image ID, bytes, or decoded pixels. [Dataset and exclusions](results/mvp/dataset_summary.json).

| Image → product system | Queries | Recall@1 | Recall@5 | Recall@10 | MRR (full catalog) |
|---|---:|---:|---:|---:|---:|
| SigLIP2 + FAISS IndexFlatIP | 523 | 0.7151 | 0.8528 | 0.8929 | 0.7811 |

Source: [image_retrieval.csv](results/mvp/image_retrieval.csv). NumPy exact cosine and FAISS have identical reported image metrics. IndexFlatIP is exact search, not ANN.

Text evaluation uses **81 deterministic structured-attribute queries**, with 2–50 relevant products per query. Binary relevance means matching the query's product type and all supplied attributes. Queries contain no product IDs, model numbers, or copied complete titles. Recall measures the fraction of relevant products retrieved, not just any-hit success.

| Text → product system | Recall@10 | NDCG@10 | MRR@50 |
|---|---:|---:|---:|
| BM25 metadata | 0.9174 | 0.8888 | 0.8614 |
| SigLIP2 text → image vectors | 0.5898 | 0.4482 | 0.4757 |
| RRF hybrid | 0.8415 | 0.7437 | 0.7600 |

Source: [text_retrieval.csv](results/mvp/text_retrieval.csv). RRF fuses BM25 Top-50 and FAISS Top-50 with rank constant 60. Their candidate union recall is 0.9977. [Per-query source complementarity](results/mvp/source_complementarity.csv).

**Observed result:** RRF improves over the vector-only baseline but underperforms BM25 on these exact-attribute labels. This benchmark favors lexical matching; it does not establish general semantic-search improvement.

| Warm local latency scope | p50 (ms) | p95 (ms) | Timed samples |
|---|---:|---:|---:|
| FAISS image-vector retrieval only, K=10 | 0.0444 | 0.0475 | 1569 |
| Image decode + uncached encoder + IPC + FAISS | 8.7084 | 9.4678 | 20 |
| Text preprocessing + uncached encoder + IPC + FAISS | 5.4045 | 5.5870 | 20 |
| BM25 + FAISS + RRF only, K=10 | 0.3940 | 0.6001 | 243 |

Source: [latency.json](results/mvp/latency.json), with raw samples in [latency_samples.csv](results/mvp/latency_samples.csv). Retrieval-only timings use cached query vectors. Encoding-inclusive timings use the first 20 query IDs per modality, a warm model, single-query inference and local worker communication. Model loading, downloads, network serving, and concurrent load are excluded. These are local measurements, not production SLA or scale claims.

The serialized FAISS index is 3,072,045 bytes and its measured construction took 0.001582 seconds, excluding embedding generation. [Index provenance](results/mvp/benchmark_config.json).

Defaults were fixed before scoring. This is an exploratory development benchmark with held-out image views; products remain in the index. There is no model training split, no hyperparameter search, and no claim of a frozen final test. The largest catalog type is `CELLULAR_PHONE_CASE` (536/1000 products). Category imbalance, related variants, near-duplicate imagery, metadata-derived labels, and possible pretrained-data overlap limit generalization. These ABO results are independent of the historical synthetic behavioral RecSys metrics.

See the [module documentation](README.md) for commands, ground-truth construction, and limitations.
<!-- multimodal-results:end -->

Agent setup, CLI examples, local API and replay commands: [agent guide](AGENT.md).

<!-- agent-results:start -->
## Agentic Multimodal Product Search

One bounded tool-using agent and grounded RAG layer now extend the same 1,000-product ABO retrieval system. A completed **36-query development evaluation** uses `gpt-4.1-mini-2025-04-14`, temperature 0, with six cases in each of six categories. The LLM plans constraints and selects cited evidence; product-specific prose is rendered from validated fields. No training or fine-tuning.

Explicit lexical/category requests prefer BM25 because the historical structured-text benchmark favors it. Attached images use SigLIP2 + FAISS; mixed requests execute metadata filters. Ambiguous descriptions use RRF by default or the planner's vector route. This policy does not establish semantic relevance superiority.

Source: [frozen queries](results/agent_v2/agent_queries.jsonl), [per-query evaluation](results/agent_v2/agent_evaluation.csv), [full raw drafts, evidence and executed traces](results/agent_v2/agent_runs.jsonl), [configuration/source hashes](results/agent_v2/agent_benchmark_config.json).

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

Source: [rag_grounding_metrics.json](results/agent_v2/rag_grounding_metrics.json). Outcomes: **28 answered, 6 abstained, 2 errors**. Empty responses never earn grounding or constraint-coverage credit. These checks establish metadata fidelity on structured claims; answer relevance, real-world catalog accuracy and apartment suitability are not measured.

| Warm latency scope, 36 sequential queries | p50 (ms) | p95 (ms) |
|---|---:|---:|
| Local retrieval, including query encoding/IPC when used | 9.54 | 49.01 |
| Hosted LLM calls per query, excluding cached requests | 2561.05 | 3983.13 |
| LLM boundary including cache lookup | 2566.43 | 3985.49 |
| Total agent request | 2614.59 | 4009.38 |

Source: [agent_latency.json](results/agent_v2/agent_latency.json). 62 live API calls and 5 exact-request cache hits; shared image-only planning requests may hit the cache. Startup/model/index preparation (3269.07 ms) is excluded. Local timings and API/network timings are separate; the historical 9.47 ms image-only p95 is unchanged and is not total agent latency.

The same authored fixtures were used to diagnose and repair an initial run, retained in [agent_v1](results/agent_v1/rag_grounding_metrics.json), then evaluated as v2. This is development evaluation, not an independent held-out agent test. Image inputs reuse held-out views of indexed products. No online business impact, production-scale serving, model training, Azure, multi-agent autonomy, RRF superiority over BM25, or general elimination of hallucinations is claimed.
<!-- agent-results:end -->
