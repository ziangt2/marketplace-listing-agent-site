# Experiment Audit

## Evaluation protocol

All four models use one frozen population of 3,954 eligible users and one unseen post-cutoff target per user. The target checksum is `6f73cc0d93be8f20cbcb732f9cecef24697991e3d858c9dbf62f17cbc792ad73`. Reconstructed per-user aggregates differ from the published metrics by at most 0.

## Data split

Training events occur strictly before `2026-02-15 22:51:28`. Final targets occur at or after that cutoff and are absent from each user's training products. The synthetic catalog and behavioral stream use seed 2027.

## Inner validation

Hybrid weights, candidate sizes, and normalization were selected only on the earlier inner temporal validation split. Phase 4 does not write `hybrid_config.json`; its before/after SHA-256 checksums match.

## Candidate retrieval

Collaborative Top-100, Content Top-100, and Popularity Top-10 candidates are deduplicated and filtered for seen products before ranking.

## Ranking

Candidate-set component scores are normalized with `per_user_candidate_minmax` and combined with frozen weights α=0.6, β=0.1, γ=0.3.

## Frozen final test

Hybrid Recall@10 is 0.26581; Collaborative Recall@10 is 0.25974. Hybrid NDCG@10 is 0.13740; Collaborative NDCG@10 is 0.13491.

## Statistical comparison

The paired Recall@10 delta is 0.00607, with bootstrap 95% CI [0.00000, 0.01214] and exact McNemar p=0.06694. Under the pre-declared 0.05 rule, statistical support for the Recall@10 improvement is **not established**.

## Sparse-user findings

Users with 3–5 prior products are lower-history, not true cold-start users. Their paired result and interval are reported in `results/sparse_history_audit.csv`; no claim should exceed that evidence.

## Retrieval vs ranking bottleneck

On the final test, Hybrid retrieves 86.17% of targets but ranks only 26.58% in Top-10. 2,356 targets are available to the ranker but remain below Top-10, making ranking the larger measured bottleneck.

## Popularity / coverage tradeoff

The frozen Hybrid slightly improves mean ranking metrics but reduces Coverage@10 relative to Collaborative. Component ablations are diagnostic only and were not used for retuning.

## A/B experiment

Users have one deterministic randomized assignment; event/user assignment mismatches = 0. The outcome is whether a user purchased at least once. The observed absolute uplift is 0.0112, with p=0.1445 and 95% CI [-0.0038, 0.0261]. It remains non-significant and is not evidence of product impact.

## Known limitations

- Recommendation behavior and product metadata are synthetic.
- One relevant item per user simplifies offline evaluation.
- The main result is from one deterministic synthetic seed; seeds 2028–2030 were not run because the current pipeline writes shared paths and safely isolating multi-seed runs would require a benchmark refactor.
- Bootstrap and randomization quantify uncertainty over this fixed user population, not external real-market generalization.
- Offline metrics do not establish online conversion impact.

## Claims supported

- The frozen Hybrid increased mean Recall@10 and NDCG@10 relative to Collaborative on this synthetic benchmark.
- Candidate union retrieval leaves substantial ranking headroom.
- Lower-history users can be compared with paired evidence without calling them cold-start users.
- The project implements temporal validation, a frozen final test, paired uncertainty estimates, and a randomized synthetic A/B analysis.

## Claims NOT supported

- Hybrid improves recommendations on any real marketplace.
- The system solves cold start.
- Offline gains imply online conversion lift.
- Results demonstrate production-scale performance or generalization across random seeds.
- Any metric uses proprietary marketplace data.
