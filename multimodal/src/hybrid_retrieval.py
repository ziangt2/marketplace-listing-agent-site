"""Reciprocal rank fusion, never addition of incompatible raw scores."""
from collections import defaultdict

from .exact_index import Hit


def reciprocal_rank_fusion(lists, k=10, rrf_k=60):
    if k < 1 or rrf_k < 0:
        raise ValueError("Invalid RRF parameters")
    scores, ranks = defaultdict(float), defaultdict(dict)
    for source, hits in lists.items():
        seen = set()
        rank = 0
        for hit in hits:
            if hit.product_id in seen:
                continue
            seen.add(hit.product_id)
            rank += 1
            scores[hit.product_id] += 1.0 / (rrf_k + rank)
            ranks[hit.product_id][source] = rank
    order = sorted(scores, key=lambda product_id: (-scores[product_id], product_id))[:k]
    return [Hit(product_id, scores[product_id], "hybrid_rrf", ranks[product_id]) for product_id in order]


def source_complementarity(lexical, vector, relevant):
    lexical_ids = {hit.product_id for hit in lexical}
    vector_ids = {hit.product_id for hit in vector}
    relevant = set(relevant)
    if not relevant:
        raise ValueError("Relevance set cannot be empty")
    return {
        "lexical_only_relevant_hits": len((lexical_ids - vector_ids) & relevant),
        "vector_only_relevant_hits": len((vector_ids - lexical_ids) & relevant),
        "overlap_relevant_hits": len(lexical_ids & vector_ids & relevant),
        "union_relevant_hits": len((lexical_ids | vector_ids) & relevant),
        "union_candidate_recall": len((lexical_ids | vector_ids) & relevant) / len(relevant),
        "union_size": len(lexical_ids | vector_ids),
    }
