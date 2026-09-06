"""BM25Okapi over public metadata; unrelated to the old TF-IDF recommender."""
import re

import numpy as np
from rank_bm25 import BM25Okapi

from .exact_index import Hit


def tokenize(text):
    return re.findall(r"[a-z]+", text.lower())


def product_document(product):
    return " ".join(str(product.get(field, "")).replace("_", " ") for field in
                    ("title", "product_type", "material", "color", "style", "brand", "pattern", "finish_type"))


class LexicalIndex:
    source = "lexical_bm25"

    def __init__(self, catalog, k1=1.5, b=0.75):
        self.ids = [p["product_id"] for p in catalog]
        if not self.ids or len(self.ids) != len(set(self.ids)):
            raise ValueError("Lexical catalog must have unique products")
        self.model = BM25Okapi([tokenize(product_document(p)) for p in catalog], k1=k1, b=b)

    def search(self, query, k=10):
        if k < 1:
            raise ValueError("k must be positive")
        scores = self.model.get_scores(tokenize(query))
        order = [i for i in np.lexsort((self.ids, -scores)) if scores[i] > 0][:k]
        return [Hit(self.ids[i], float(scores[i]), self.source, {self.source: rank}) for rank, i in enumerate(order, 1)]
