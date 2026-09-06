# Grounded product search: implementation and evaluation plan

Before coding, all historical checks passed: 20 RecSys tests, 22 multimodal
tests, and both documentation validators. MVP artifacts verify 1,000 products,
523 image queries (Recall@10 0.892925430210325, MRR 0.7810606259776887), 81 text
queries (BM25 0.9174385397867966, vector 0.5898158964296532, RRF
0.8415244432028446 Recall@10), and warm image encoding/retrieval p95
9.467830650000002 ms across 20 samples. These artifacts and all RecSys files
remain unchanged. Existing uncommitted work is preserved; no commit or push.

1. Project retrieved hits into an allowlisted evidence schema. Normalize numeric
   dimensions to inches with explicit unit conversion and retain source values.
2. Add an OpenAI Responses provider using the accessible pinned
   `gpt-4.1-mini-2025-04-14` snapshot, temperature 0, strict JSON schema, bounded
   output, request cache and provenance. Load only environment/ignored .env.local.
3. Validate every product ID, evidence field and value. Product-specific prose
   uses deterministic rendering of validated structured claims; raw LLM drafts
   are retained for evaluation. Never label free-text entailment as proven by a
   field-only validator. Separate raw and delivered-output grounding metrics.
4. Expose schema-checked search_text (BM25), search_vector, search_image,
   search_hybrid, filter_products, compare_products, get_product tools. Scope
   follow-up product IDs to the current retrieved set. Missing attributes fail
   constraints closed; no inference of material/size from titles or pixels.
5. One bounded agent: deterministic routing for clear lexical/image requests,
   optional structured LLM planning for ambiguous text, real retrieval/filter/
   comparison calls, result inspection and a bounded broad-category retry when
   appropriate. Record arguments, outcomes, errors and duration for each call.
6. Freeze 36 development evaluation queries across six categories before scoring.
   Record expected routes and constraints independently of planner outputs, full
   raw/delivered responses and traces, failures/abstentions, grounding counts,
   constraint checks, latency and provider/cache status. Cached replay gets its
   own timings; it is not a second live model evaluation or a held-out test.
7. Generate separate agent documentation/evidence only from completed artifacts.
   Re-run old/new tests, all validators, and hash-check historical artifacts.

No training, fine-tuning, learned reranker, multi-agent system, long-term memory,
Azure, or orchestration framework. The HTTP endpoint is optional after the core
evaluation works. The existing retrieval CLI and measured benchmark are preserved.

Primary API references: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [GPT-4.1 mini snapshots](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
