# Result artifacts

`mvp/` is the measured 1,000-product run; sizes for unexecuted profiles are only
configuration targets. No generated recommendation data from `recsys/` enters
these files. Local reruns use a fresh `local*` folder, ignored by Git.

- `dataset_summary.json`: source, license, selection, product/image counts,
  category counts, exclusions, and checksum provenance.
- `image_retrieval.csv`: same-item image retrieval with a distinct, unambiguous
  query view. Full-catalog MRR and Recall/Hit/NDCG cutoffs.
- `text_retrieval.csv`: BM25, exact NumPy, exact FAISS, and RRF comparison on
  one identical metadata-derived query/qrel population. MRR is truncated at 50.
- `hybrid_retrieval.csv`: the lexical/vector/hybrid comparison subset.
- `source_complementarity.csv`: relevant lexical-only/vector-only/overlap counts,
  candidate union size and recall for each text query at retrieval depth 50.
- `query_segment_metrics.csv`: product-type breakdowns with at least ten queries.
- `per_query_metrics.csv`: denominators and outcomes for aggregate reconstruction.
- `retrieval_runs.jsonl`: Top-10 product IDs and first relevant rank per query/system.
- `latency.json`: warm retrieval-only and query-encoding-inclusive percentiles,
  sample counts and measurement scope. Timings include Python result construction.
- `latency_samples.csv`: every timing observation, enabling percentile reconstruction.
- `benchmark_config.json`: successful-run marker, frozen defaults, model/revision,
  preprocessing, cache alignment, population hashes, code hashes and environment.

The exact NumPy and FAISS implementations are compared on actual same-query
results. IndexFlatIP is exhaustive, not approximate. Index files and embeddings
are reproducible ignored outputs; no weights or raw image archives are tracked.

Published metrics are descriptive development results. The data-derived text
labels favor BM25; do not claim hybrid superiority over BM25 when the artifact
shows a lower score. Images/query identities held out by this task do not imply
unseen products, independent variants, or unseen pretrained data.

## Grounded agent evaluation

The original `mvp/`, `dev/` and `validation.json` remain unchanged.

- `agent_v1/`: the initial 36-case development evaluation, including failures and
  snapshots of its six core agent source files. It is retained as an audit.
- `agent_v2/`: the measured repaired implementation, using the identical fixtures.
  `agent_queries.jsonl` is a copy of the frozen source manifest;
  `agent_runs.jsonl` retains every raw selection, evidence window, actual tool
  argument/result, error, delivered response and latency. `agent_evaluation.csv`
  records per-query measures. `rag_grounding_metrics.json` retains numerators,
  denominators, abstentions and category results. `agent_latency.json` separates
  local retrieval, all tools, LLM API, LLM wall time and total request time.
  `agent_benchmark_config.json` records model/prompt versions, environment, source
  hashes and excluded startup. `historical_preservation.json` audits prior files.
- `agent_v2_replay/`: cache-only repetition, with its own latency and a
  `replay_validation.json` equality check. These are replay timings, not another
  set of live model measurements.

`make agent-verify-docs` reconstructs the final aggregate/CSV/latency from query
runs, checks the raw claims against original ABO evidence, checks evaluated source
hashes, and validates the generated documentation. Source and request fingerprints
make changes visible. Ignored LLM cache records include full request/response JSON
without API credentials; shared result traces retain parsed raw outputs and usage
metadata. A new checkout needs a provider key to populate that private local cache.

Grounding rates apply to structured citations. Raw unsupported fields and invalid
values are distinct from emitted claims; withholding a bad response does not earn
nonempty grounding credit. Constraint satisfaction is reported both per emitted
recommendation and per constrained query, so empty results cannot inflate coverage.
There are no independent human relevance labels or LLM-judge scores. Agent v2 was
repaired using the same development fixtures, so do not call it a held-out test.

`publication_preservation.json` records the Git publication boundary: three
pre-existing local RecSys runtime edits are excluded, and the repository's existing
CSV LF policy changes line endings only. Preservation checks accept the recorded
development bytes or published baseline bytes. `publication_validation.json`
records tests and validators run against the staged publication snapshot.
