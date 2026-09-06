# Interview Notes — E-commerce Search & Recommendation Platform

The opening explanation describes the original Marketplace/RecSys work. The
subsequent public-ABO retrieval and agent extension is covered in the final section.

## 60-second project explanation

I built two related systems around retrieval, ranking, and evidence quality. The Marketplace web app expands multilingual product queries, gathers public suggestions and uploaded report evidence, extracts and categorizes keywords, and ranks them with transparent features without pretending that the score is search volume. The RecSys module uses deterministic synthetic behavioral data and product content modeled after that keyword/category schema. It retrieves candidates with item-item Collaborative, TF-IDF Content, and Popularity sources, unions them, normalizes scores per user, and applies a validated Hybrid ranker. I separated inner temporal model selection from a frozen later test, reconstructed metrics from per-user outcomes, and used bootstrap and paired tests. Hybrid had modest mean gains, but the overall comparison was not significant at 0.05, which I report directly.

## Why Candidate Retrieval + Ranking?

Retrieval and ranking solve different problems. Retrieval must place the relevant item in a manageable candidate set; ranking must move it into the displayed positions. Separate retrievers also let behavior, metadata, and a robust fallback contribute without forcing their raw scores onto one scale. The architecture exposes failure location: on the final Hybrid evaluation, 547 targets were never retrieved, while 2,356 were retrieved but remained below rank ten. Ranking is the larger measured source of missed Top-10 targets.

## Why collaborative + content?

Collaborative similarity captures behavioral co-occurrence and is the strongest standalone personalized source here. Content retrieval can operate from a user's weighted history and product metadata, so it offers a different signal and a route toward item cold-start support. Its standalone accuracy is lower, and final Hybrid top-ten lists contain no content-only items, but on inner validation Content uniquely retrieved 4.74% of union target hits. That distinction matters: validation justified testing the component, while the frozen audit shows its final-list contribution is mostly score/order diversification rather than unique rescue.

## Why Hybrid gains were modest

Collaborative and Content Top-100 sets overlap heavily: their mean validation Jaccard is 56.88%, and 97.01% of final Hybrid Top-10 items appear in both source pools. The selected Content weight is only 0.1, the component has weaker standalone ranking, and per-user min-max normalization changes score geometry. Popularity adds stability but can also promote globally common items; removing it helps 277 users and hurts 306. Hybrid therefore changes many orderings without creating a large number of new successful top-ten placements.

## Retrieval vs Ranking bottleneck

Hybrid retrieves 86.17% of final targets but Recall@10 is 26.58%. Perfectly ranking the existing candidate set therefore has about 59.59 percentage points of headroom, compared with 13.83% of targets unavailable to the ranker. I would prioritize ranking diagnostics—calibration, pairwise errors, position-sensitive features, and validation by history/category—while still monitoring candidate recall and latency.

## Sparse-history behavior

For 518 users with 3–5 historical products, Hybrid Recall@10 improves from 0.19498 to 0.21815, with paired CI `[0.00579, 0.04054]`; NDCG@10 also improves. This is the strongest segment result, but it is exploratory. It does not prove new-user cold start because all evaluated users have at least three historical products, and multiple segments were inspected.

## Why temporal split matters

A random interaction split can let later behavior or the target product leak into training and can make offline results unrealistically optimistic. I use an earlier inner split for selecting candidate sizes and weights, then rebuild on all eligible pre-final history and evaluate once against later unseen targets. Tests confirm timestamps, unseen targets, disjoint validation/final pairs, fixed configuration provenance, and identical model populations.

## What I would do at production scale

I would define online objectives and guardrails first, instrument exposure and position bias, and build a point-in-time-correct feature pipeline. Candidate retrieval would move to approximate nearest-neighbor indexes or a managed retrieval service, with cached Popularity and category fallbacks. Ranking would add calibrated behavioral, content, freshness, price, availability, and locale features, followed by unbiased offline evaluation and staged online experiments. I would add monitoring for coverage, diversity, data drift, retrieval latency, empty results, and segment regressions. Marketplace ingestion would use permitted provider APIs, explicit freshness metadata, retry/rate-limit policies, and source-level quality monitoring.

## Limitations

The recommendation benchmark, product metadata, and A/B outcome are synthetic. Marketplace inputs are public suggestions or user-provided reports, not proprietary platform data. The keyword ranker is heuristic, the recommendation models are lightweight, and there is no production serving, traffic, online recommender test, distributed training, or true zero-history evaluation.

## Agentic Multimodal Product Search

I extended the separate public ABO retrieval module with one bounded agent and
grounded generation. Explicit category/text requests use BM25 because it beat
SigLIP2 text vectors and RRF on the existing structured-text benchmark. Attached
images use pretrained SigLIP2 plus FAISS. Ambiguous descriptions use semantic
retrieval; mixed requests execute metadata filters. The LLM plans and selects
evidence, while actual tool functions perform search, filtering and comparison.

I restricted the LLM's factual output to product IDs and field/value citations.
A deterministic validator checks candidate membership, field availability and
normalized values; the application renders factual reasons and width comparisons.
This avoids pretending that matching citations validates arbitrary free-form prose.
The source catalog is sparse and sometimes inconsistent, so even a grounded claim
is only faithful to ABO metadata. A small-apartment preference cannot become an
invented width threshold or a promise that furniture fits.

The evaluation is an authored development set, not an independent held-out agent
test. I preserved the first run, repaired failures, reran the same fixtures, and
verified exact cached replay. I report raw model failures, withheld drafts,
abstentions and answer coverage alongside citation fidelity. The first run exposed
an unused image fallback validation error and a unit-equivalence false rejection;
the later run still exposed unsupported and malformed citations, which were
withheld. It also shows limitations in LLM constraint extraction, including overly
strict material matching and inferred categories. Routing success does not prove
the recommended products are relevant.

Use the generated [resume evidence](RESUME_EVIDENCE.md#agentic-multimodal-product-search)
for the measured numerators, denominators and latency. The [per-query traces](multimodal/results/agent_v2/agent_runs.jsonl)
show real calls; [the replay audit](multimodal/results/agent_v2_replay/replay_validation.json)
shows semantic output equality without another live model evaluation. Local
retrieval and hosted LLM/API time are separate. The optional loopback JSON API is
a demo service, not a cloud deployment.

I should not claim model training, proprietary Amazon search access, production
scale, online impact, Azure, multi-agent autonomy, general hallucination elimination,
unseen-product generalization, or that RRF beat BM25 on the original text benchmark.

## A/B test result and why non-significance is acceptable

Treatment purchase conversion is 32.94% versus 31.83% for control, an observed +1.12 percentage-point difference with CI `[-0.38, 2.61]` percentage points and `p=0.1445`. Non-significance is an acceptable and important conclusion: the experiment implementation works, but this sample does not provide enough evidence to reject equal conversion rates. I would report effect size and uncertainty, avoid shipping claims based on the point estimate alone, and use a prospective power calculation before the next test.
