# Agentic Multimodal Product Search

This extension uses the existing ABO manifest, BM25, pretrained SigLIP2,
FAISS IndexFlatIP and RRF. It has one bounded agent and a hosted OpenAI provider.
No model is trained. See [measured results](README.md#agentic-multimodal-product-search)
and [the implementation plan](AGENT_PLAN.md).

## Run a query

Use the Python 3.11 environment from the retrieval setup. Restore the real catalog
and image files on a new checkout with `make multimodal-benchmark` before running
image queries. Existing manifests and caches are reused.

Place `OPENAI_API_KEY` in the environment or the repository's ignored `.env.local`.
Do not put a real credential in `.env.example`. Optional settings:

```text
AGENT_LLM_PROVIDER=openai
AGENT_LLM_MODEL=gpt-4.1-mini-2025-04-14
```

Only OpenAI is implemented in this iteration; the small `LLMProvider` boundary
permits later provider adapters. The benchmark pins temperature 0, a dated model,
prompt versions, full request hashes, response IDs, timestamps and usage. Strict
JSON uses the [Responses API structured-output format](https://developers.openai.com/api/docs/guides/structured-outputs).
Model reference: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

From the repository root:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-multimodal/bin/python -m multimodal.src.product_agent \
  --query 'Find a wooden chair narrower than 25 inches.'

OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-multimodal/bin/python -m multimodal.src.product_agent \
  --query 'Find similar chairs, but wooden and narrower than 25 inches.' \
  --image /absolute/path/to/chair.jpg

.venv-multimodal/bin/python -m multimodal.src.product_agent \
  --query 'Compare the top three chairs for a compact apartment using reported width.'
```

The JSON response contains `answer`, `recommendations` with explicit IDs, reasons,
citations, dimension provenance, `comparison`, `limitations`, `plan`, raw output,
grounding counts, executed `tool_trace`, LLM telemetry and latency scopes.

## Tools and grounding contract

| Tool | Arguments | Actual implementation |
|---|---|---|
| `search_text` | query, top_k | Existing BM25 metadata index |
| `search_vector` | query, top_k | SigLIP2 text encoder → FAISS image vectors |
| `search_image` | image=`attached`, top_k | Attached image → SigLIP2 → FAISS |
| `search_hybrid` | query, top_k | Existing BM25 + vector RRF |
| `filter_products` | product_ids, constraints | Deterministic metadata predicates |
| `compare_products` | product_ids | Source field table and reported-width ordering |
| `get_product` | product_id | Evidence from current retrieval context |

Every call validates its name, complete argument set, types and bounds. Follow-up
IDs must come from this request's retrieved set. Default retrieval is Top-50;
one empty-result lexical retry may expand to Top-100. The LLM sees at most eight
eligible records and can recommend at most three. The controller permits at most
eight calls. Tool errors withhold the answer and remain visible in the trace.

Supported filters are `product_type` (also the category mapping), `material`,
`color`, `style`, `width`, `height`, `depth`. Text supports `eq` and `contains`;
dimensions support `eq`, `lt`, `lte`, `gt`, `gte` with explicit in/cm/mm units.
Text matching normalizes case and punctuation. Material wood/wooden matches the
reported labels containing wood, ash, pine, solidpine, bamboo, MDF or hardwood.
Composite materials may therefore match; the answer cites the original label.
It does not assert that every component is solid wood.

Missing fields fail constraints. The implementation never derives material or
dimensions from product titles or pixels. ABO axis labels can be inconsistent;
width is exactly its reported width, height its reported height, and depth maps
to length. Source units/values remain visible. For example, a title may advertise
a different width from the structured width. We disclose this limitation rather
than reconciling it without evidence. Numeric citations are converted to inches
and checked within 0.000001 inch to account for six-decimal formatting.

Price, ratings, availability, sales, popularity, comfort, sustainability and room
suitability cannot be established by these records. Requested unsupported fields
are explicitly listed, while recommendations may satisfy the supported portion.
The narrowest reported width is only a comparison among selected candidates with
available widths; it is not a claim that a product will fit the user's apartment.

The LLM returns product IDs and field/value citations. Arbitrary answer/reason
fields are not accepted. A whole draft is withheld on an invalid ID, absent field,
incorrect value, duplicate or malformed claim. The application renders product
facts from validated citations and computes comparisons directly from metadata.
Raw failures remain measurable. Grounding is metadata fidelity, not relevance
judgment, factual verification of ABO itself, or a general hallucination guarantee.

## Evaluation and replay

```bash
make test
make multimodal-test
make agent-test
make verify-docs
make multimodal-verify-docs
make agent-verify-docs

# A fresh measured run; uses a new ignored local-agent timestamp directory.
make agent-benchmark

# Re-execute tools, use exact cached LLM outputs, compare all semantic results.
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-multimodal/bin/python -m multimodal.src.agent_benchmark \
  --cache-only --output multimodal/results/local-agent-replay \
  --replay-of multimodal/results/agent_v2
```

The exact-request LLM cache lives under ignored `data/cache/agent_llm`. Fresh
checkouts require an API key to populate it. Temperature 0 alone does not promise
identical provider output; cached replay does. Cache misses in `--cache-only`
mode produce explicit errors, never synthetic LLM successes. Replay re-executes
retrieval/filter/comparison and checks plan, citations, answers, candidate evidence
and traces, excluding timing/cache telemetry. Replay timings are not live API timings.

The 36 fixtures were authored before the first agent evaluation, six per category:
lexical text, semantic text, image similarity, image plus filters, comparison and
unavailable properties. The same fixtures informed repairs after the first run,
so these are development results. The 12 attached images are existing held-out
ABO views, not unseen product identities. Routing labels and constraint annotations
are independent of planner output. A separate oracle checks constraints directly
against original catalog fields. No human relevance labels or LLM judge are used.

`results/agent_v1` preserves the initial run and its six core source files. Its
image-only fallback validation failures, BM25 semantic routing, and an overly
strict rejection of a valid equivalent dimension prompted the v2 fixes. The v2
planner also separates color/material phrases explicitly. Neither the fixtures
nor historical retrieval/RecSys metrics were changed to improve the scores.

## Local API

```bash
make agent-serve
```

In another terminal:

```bash
curl -sS http://127.0.0.1:8067/api/agent/search \
  -H 'Content-Type: application/json' \
  --data '{"query":"Find a brown chair made of ash.","debug":true}'
```

Optional `image` is an ABO `image_id` from the catalog's index/query image records,
not a URL or arbitrary server-side file path. The CLI supports user-supplied local
images. `debug:true` includes the plan, raw selection, grounding audit and tool
trace. The server is sequential and loopback-only; browser-origin requests are
disabled. No production authentication, remote deployment or frontend was added.
The existing Node endpoints keep their behavior.

## Claims to avoid

Do not claim training/fine-tuning, a learned reranker, production Amazon search,
proprietary marketplace access, unrestricted autonomous action, multi-agent work,
Azure deployment, production scale, online impact, independent held-out agent
quality, or universal elimination of hallucinations. The historical result that
BM25 beats RRF on structured text remains valid. The LLM has no authoritative
product information beyond the retrieved evidence supplied to it.
