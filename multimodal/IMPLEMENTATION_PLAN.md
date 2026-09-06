# MVP implementation plan and initial audit

Audited repository HEAD: `14583aa44bb6578ca3a41d39e261a43c9b3e8fa5`.
Before changes, `make test` passed all 20 tests (6.661 seconds), and
`make verify-docs` reported `Documentation consistency: OK`.

The matching checkout already had edits to `recsys/README.md`,
`recsys/RESUME_EVIDENCE.md`, and `recsys/results/run_metadata.json`.
Preserve these and all historical RecSys code, tests, configuration, and numbers.
The old suite regenerates some result files during its determinism check; verify
their contents remain identical after running it. No commits or pushes requested.

1. Deterministic public ABO subset: English listing metadata, preferred multiple
   views, original IDs, selected small S3 images, source and image checksums.
2. Pinned pretrained SigLIP2 inference on CPU/MPS, batches and content-addressed
   embedding caches; never train or fine-tune.
3. NumPy exact cosine reference and FAISS IndexFlatIP, distinct held-out image
   views, structured-attribute text queries, auditable relevance sets.
4. Save per-query outcomes and aggregate image/text metrics and latency.
5. Add isolated BM25 and RRF; measure complementarity on the same population.
6. Generate documentation claims from artifacts, run new methodology tests and
   unchanged historical checks. HNSW is optional only after the MVP works.

Use absolute package imports under `multimodal.src`, separate data and result
paths, and additive Make targets. Do not import the old RecSys modules: their
unqualified imports and fixed output paths belong to the historical experiment.

This is an exploratory development benchmark with fixed defaults, no training
split and no hyperparameter selection. Held-out means a distinct catalog image
view, not an unseen product or a temporal holdout. Text labels are exact metadata
matches, not human judgments; this is expected to favor lexical retrieval.
Do not claim external generalization or a tuned/frozen final test.

## Implementation adjustments observed before publication

- The first native benchmark attempt aborted because the macOS PyTorch and FAISS
  wheels each initialized a different OpenMP runtime. No result artifacts were
  published from that failed attempt. The implemented fix isolates the encoder
  in a persistent local worker; the retrieval process never imports PyTorch.
- ABO alternate views can be shared by different products. The initial manifest
  preserves those real records, but query-definition v2 excludes shared decoded
  query pixels from the single-product identity task. This rule was added before
  successful retrieval scores were observed, not chosen to optimize metrics.
- The final scope implements exact IndexFlatIP only. HNSW and the longer roadmap
  are deliberately deferred under the urgent MVP instruction.
