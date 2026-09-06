"""Macro-averaged retrieval metrics with explicit multi-positive denominators."""
import math


def retrieval_metrics(ranked_ids, relevant_ids, ks=(1, 5, 10, 50)):
    relevant = set(relevant_ids)
    if not relevant:
        raise ValueError("Cannot evaluate an empty relevance set")
    if len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("Duplicate results would inflate ranking metrics")
    first_rank = next((i for i, item in enumerate(ranked_ids, 1) if item in relevant), None)
    result = {"mrr": 1 / first_rank if first_rank else 0.0, "first_relevant_rank": first_rank or 0}
    for k in ks:
        if k < 1:
            raise ValueError("Metric cutoff must be positive")
        hits = [i for i, item in enumerate(ranked_ids[:k], 1) if item in relevant]
        result[f"recall@{k}"] = len(hits) / len(relevant)
        result[f"hit@{k}"] = float(bool(hits))
        dcg = sum(1 / math.log2(rank + 1) for rank in hits)
        ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
        result[f"ndcg@{k}"] = dcg / ideal
    return result


def aggregate(rows):
    if not rows:
        raise ValueError("Cannot report metrics for zero queries")
    keys = [key for key in rows[0] if key == "mrr" or key.startswith(("recall@", "ndcg@", "hit@"))]
    return {"queries": len(rows), **{key: sum(row[key] for row in rows) / len(rows) for key in keys}}
