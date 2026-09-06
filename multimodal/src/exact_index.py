"""Exact NumPy reference and native FAISS IndexFlatIP over normalized vectors."""
from dataclasses import dataclass, field

import numpy as np

from .build_embeddings import EmbeddingTable


@dataclass
class Hit:
    product_id: str
    score: float
    source: str
    ranks: dict = field(default_factory=dict)


def validate_query(query, dimension):
    query = np.asarray(query, dtype=np.float32)
    if query.shape != (dimension,) or not np.isfinite(query).all() or not np.isclose(np.linalg.norm(query), 1, atol=1e-5):
        raise ValueError("Query must be a finite normalized vector of the index dimension")
    return np.ascontiguousarray(query)


class ExactIndex:
    source = "numpy_exact"

    def __init__(self, table):
        table.validate()
        if not table.ids:
            raise ValueError("Cannot index an empty catalog")
        self.ids = list(table.ids)
        self.vectors = np.array(table.vectors, dtype=np.float32, order="C", copy=True)
        self.dimension = self.vectors.shape[1]

    def search(self, query, k=10):
        if k < 1:
            raise ValueError("k must be positive")
        scores = self.vectors @ validate_query(query, self.dimension)
        order = np.lexsort((self.ids, -scores))[:k]
        return [Hit(self.ids[i], float(scores[i]), self.source, {self.source: rank}) for rank, i in enumerate(order, 1)]


class FaissFlatIndex(ExactIndex):
    source = "faiss_flat"

    def __init__(self, table):
        import faiss

        super().__init__(table)
        faiss.omp_set_num_threads(1)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(self.vectors)

    def search(self, query, k=10):
        if k < 1:
            raise ValueError("k must be positive")
        vector = validate_query(query, self.dimension)
        scores, positions = self.index.search(vector[None, :], min(k, len(self.ids)))
        ranked = sorted(((int(i), float(s)) for i, s in zip(positions[0], scores[0]) if i >= 0), key=lambda pair: (-pair[1], self.ids[pair[0]]))
        return [Hit(self.ids[i], s, self.source, {self.source: rank}) for rank, (i, s) in enumerate(ranked, 1)]

    def save(self, path):
        import faiss
        faiss.write_index(self.index, str(path))
