"""Explainable TF-IDF recommendation from synthetic product-listing metadata."""

import csv
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix

from config import DATA_RAW


CONTENT_FIELDS = (
    "title",
    "category",
    "subcategory",
    "keywords",
    "tags",
    "price_bucket",
    "use_case",
    "audience",
    "attributes",
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")


def load_product_metadata(path: Path = DATA_RAW / "products.csv") -> List[Dict[str, str]]:
    """Load catalog rows in product-id order and verify their dense indexing."""
    with path.open(newline="", encoding="utf-8") as handle:
        products = sorted(csv.DictReader(handle), key=lambda row: int(row["product_id"]))
    expected_ids = list(range(1, len(products) + 1))
    if [int(row["product_id"]) for row in products] != expected_ids:
        raise ValueError("Content model requires contiguous product IDs beginning at one")
    return products


def _document_tokens(product: Dict[str, str]) -> List[str]:
    tokens: List[str] = []
    for field in CONTENT_FIELDS:
        values = TOKEN_PATTERN.findall(product[field].lower())
        tokens.extend(f"{field}_{value}" for value in values)
    return tokens


def fit_product_tfidf(
    products: Sequence[Dict[str, str]], min_document_frequency: int = 2
) -> Tuple[csr_matrix, List[str]]:
    """Fit L2-normalized TF-IDF on static catalog metadata only.

    Features occurring in just one listing are intentionally removed so a
    synthetic identifier-like token cannot make a product trivially unique.
    The fit has no interaction, user, cutoff, or held-out target inputs.
    """
    documents = [_document_tokens(product) for product in products]
    document_frequency: Counter = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))
    vocabulary = sorted(
        token for token, frequency in document_frequency.items()
        if frequency >= min_document_frequency
    )
    vocabulary_index = {token: index for index, token in enumerate(vocabulary)}
    row_indices: List[int] = []
    column_indices: List[int] = []
    values: List[float] = []
    n_documents = len(documents)
    for row_index, tokens in enumerate(documents):
        counts = Counter(token for token in tokens if token in vocabulary_index)
        for token, count in counts.items():
            inverse_document_frequency = math.log(
                (1.0 + n_documents) / (1.0 + document_frequency[token])
            ) + 1.0
            row_indices.append(row_index)
            column_indices.append(vocabulary_index[token])
            values.append((1.0 + math.log(count)) * inverse_document_frequency)
    matrix = csr_matrix(
        (values, (row_indices, column_indices)),
        shape=(n_documents, len(vocabulary)),
        dtype=np.float64,
    )
    row_norms = np.sqrt(np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel())
    row_norms[row_norms == 0.0] = 1.0
    matrix = matrix.multiply((1.0 / row_norms)[:, None]).tocsr()
    return matrix, vocabulary


def build_user_profiles(
    training_interactions: csr_matrix,
    product_vectors: csr_matrix,
    user_indices: Sequence[int],
) -> csr_matrix:
    """Create cosine-normalized profiles solely from weighted training history."""
    selected_interactions = training_interactions[np.asarray(user_indices, dtype=np.int32)]
    profiles = selected_interactions.dot(product_vectors).tocsr()
    profile_norms = np.sqrt(np.asarray(profiles.multiply(profiles).sum(axis=1)).ravel())
    profile_norms[profile_norms == 0.0] = 1.0
    return profiles.multiply((1.0 / profile_norms)[:, None]).tocsr()


def score_content_candidates(
    training_interactions: csr_matrix,
    product_vectors: csr_matrix,
    user_indices: Sequence[int],
) -> np.ndarray:
    """Return cosine similarities for requested users against every product."""
    profiles = build_user_profiles(training_interactions, product_vectors, user_indices)
    return profiles.dot(product_vectors.T).toarray()


def recommend_top_k(
    scores: np.ndarray,
    training_interactions: csr_matrix,
    user_indices: Sequence[int],
    k: int,
) -> List[np.ndarray]:
    """Rank unseen products with deterministic product-index tie-breaking."""
    recommendations: List[np.ndarray] = []
    product_indices = np.arange(scores.shape[1])
    for row_index, user_index in enumerate(user_indices):
        candidate_scores = scores[row_index].copy()
        seen = training_interactions.getrow(int(user_index)).indices
        candidate_scores[seen] = -np.inf
        order = np.lexsort((product_indices, -candidate_scores))
        recommendations.append(order[:k])
    return recommendations
