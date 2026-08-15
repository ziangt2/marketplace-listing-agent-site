"""Sparse implicit-feedback recommenders and temporal data preparation."""

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
from scipy.sparse import csr_matrix

from config import (
    DATABASE_PATH,
    DATA_PROCESSED,
    EVENT_WEIGHTS,
    HOLDOUT_DAYS,
    MIN_HISTORY_ITEMS,
)


@dataclass
class RecommendationData:
    interactions: csr_matrix
    cutoff: str
    targets: List[Dict[str, object]]
    train_event_count: int
    test_positive_users: int
    users_with_unseen_test_positive: int


@dataclass
class ValidationData:
    interactions: csr_matrix
    inner_cutoff: str
    final_cutoff: str
    targets: List[Dict[str, object]]
    train_event_count: int


def prepare_temporal_data() -> RecommendationData:
    """Build a global pre-cutoff matrix and one unseen post-cutoff target per user."""
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        max_timestamp = connection.execute("SELECT MAX(event_timestamp) FROM events").fetchone()[0]
        cutoff_dt = datetime.fromisoformat(max_timestamp) - timedelta(days=HOLDOUT_DAYS)
        cutoff = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
        n_users = int(connection.execute("SELECT MAX(user_id) FROM users").fetchone()[0])
        n_products = int(connection.execute("SELECT MAX(product_id) FROM products").fetchone()[0])
        train_event_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM events WHERE event_timestamp < ?", (cutoff,)
            ).fetchone()[0]
        )
        aggregate_rows = connection.execute(
            """
            SELECT
                user_id,
                product_id,
                SUM(CASE event_type
                    WHEN 'view' THEN ?
                    WHEN 'click' THEN ?
                    WHEN 'add_to_cart' THEN ?
                    WHEN 'purchase' THEN ?
                END) AS interaction_strength
            FROM events
            WHERE event_timestamp < ?
            GROUP BY user_id, product_id
            """,
            (
                EVENT_WEIGHTS["view"],
                EVENT_WEIGHTS["click"],
                EVENT_WEIGHTS["add_to_cart"],
                EVENT_WEIGHTS["purchase"],
                cutoff,
            ),
        ).fetchall()
        row_indices = np.fromiter((row[0] - 1 for row in aggregate_rows), dtype=np.int32)
        column_indices = np.fromiter((row[1] - 1 for row in aggregate_rows), dtype=np.int32)
        strengths = np.fromiter((row[2] for row in aggregate_rows), dtype=np.float64)
        interactions = csr_matrix(
            (strengths, (row_indices, column_indices)), shape=(n_users, n_products)
        )

        test_positive_users = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM events
                WHERE event_timestamp >= ?
                  AND event_type IN ('click', 'add_to_cart', 'purchase')
                """,
                (cutoff,),
            ).fetchone()[0]
        )
        target_rows = connection.execute(
            """
            WITH train_history AS (
                SELECT user_id, COUNT(DISTINCT product_id) AS history_items
                FROM events
                WHERE event_timestamp < :cutoff
                GROUP BY user_id
            ),
            unseen_test_positives AS (
                SELECT
                    e.user_id,
                    e.product_id,
                    e.event_type,
                    e.event_timestamp,
                    COALESCE(h.history_items, 0) AS history_items,
                    ROW_NUMBER() OVER (
                        PARTITION BY e.user_id
                        ORDER BY
                            CASE e.event_type
                                WHEN 'purchase' THEN 3
                                WHEN 'add_to_cart' THEN 2
                                ELSE 1
                            END DESC,
                            e.event_timestamp ASC,
                            e.product_id ASC
                    ) AS target_rank
                FROM events AS e
                LEFT JOIN train_history AS h ON e.user_id = h.user_id
                WHERE e.event_timestamp >= :cutoff
                  AND e.event_type IN ('click', 'add_to_cart', 'purchase')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM events AS prior
                      WHERE prior.user_id = e.user_id
                        AND prior.product_id = e.product_id
                        AND prior.event_timestamp < :cutoff
                  )
            )
            SELECT user_id, product_id, event_type, event_timestamp, history_items
            FROM unseen_test_positives
            WHERE target_rank = 1
            ORDER BY user_id
            """,
            {"cutoff": cutoff},
        ).fetchall()
    finally:
        connection.close()

    users_with_unseen_test_positive = len(target_rows)
    targets = [
        {
            "user_id": int(user_id),
            "target_product_id": int(product_id),
            "target_event_type": event_type,
            "target_timestamp": event_timestamp,
            "history_items": int(history_items),
        }
        for user_id, product_id, event_type, event_timestamp, history_items in target_rows
        if int(history_items) >= MIN_HISTORY_ITEMS
    ]
    assert targets, "No eligible temporal holdout targets were found"

    holdout_path = DATA_PROCESSED / "recommendation_holdout.csv"
    with holdout_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(targets[0]))
        writer.writeheader()
        writer.writerows(targets)

    return RecommendationData(
        interactions=interactions,
        cutoff=cutoff,
        targets=targets,
        train_event_count=train_event_count,
        test_positive_users=test_positive_users,
        users_with_unseen_test_positive=users_with_unseen_test_positive,
    )


def prepare_inner_validation(final_cutoff: str) -> ValidationData:
    """Create an inner temporal split using only events before the final cutoff."""
    inner_cutoff_dt = datetime.fromisoformat(final_cutoff) - timedelta(days=HOLDOUT_DAYS)
    inner_cutoff = inner_cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        n_users = int(connection.execute("SELECT MAX(user_id) FROM users").fetchone()[0])
        n_products = int(connection.execute("SELECT MAX(product_id) FROM products").fetchone()[0])
        train_event_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM events WHERE event_timestamp < ?", (inner_cutoff,)
            ).fetchone()[0]
        )
        aggregate_rows = connection.execute(
            """
            SELECT
                user_id,
                product_id,
                SUM(CASE event_type
                    WHEN 'view' THEN ?
                    WHEN 'click' THEN ?
                    WHEN 'add_to_cart' THEN ?
                    WHEN 'purchase' THEN ?
                END) AS interaction_strength
            FROM events
            WHERE event_timestamp < ?
            GROUP BY user_id, product_id
            """,
            (
                EVENT_WEIGHTS["view"],
                EVENT_WEIGHTS["click"],
                EVENT_WEIGHTS["add_to_cart"],
                EVENT_WEIGHTS["purchase"],
                inner_cutoff,
            ),
        ).fetchall()
        rows = np.fromiter((row[0] - 1 for row in aggregate_rows), dtype=np.int32)
        columns = np.fromiter((row[1] - 1 for row in aggregate_rows), dtype=np.int32)
        strengths = np.fromiter((row[2] for row in aggregate_rows), dtype=np.float64)
        interactions = csr_matrix(
            (strengths, (rows, columns)), shape=(n_users, n_products)
        )
        target_rows = connection.execute(
            """
            WITH inner_history AS (
                SELECT user_id, COUNT(DISTINCT product_id) AS history_items
                FROM events
                WHERE event_timestamp < :inner_cutoff
                GROUP BY user_id
            ),
            validation_positives AS (
                SELECT
                    e.user_id,
                    e.product_id,
                    e.event_type,
                    e.event_timestamp,
                    COALESCE(h.history_items, 0) AS history_items,
                    ROW_NUMBER() OVER (
                        PARTITION BY e.user_id
                        ORDER BY
                            CASE e.event_type
                                WHEN 'purchase' THEN 3
                                WHEN 'add_to_cart' THEN 2
                                ELSE 1
                            END DESC,
                            e.event_timestamp ASC,
                            e.product_id ASC
                    ) AS target_rank
                FROM events AS e
                LEFT JOIN inner_history AS h ON e.user_id = h.user_id
                WHERE e.event_timestamp >= :inner_cutoff
                  AND e.event_timestamp < :final_cutoff
                  AND e.event_type IN ('click', 'add_to_cart', 'purchase')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM events AS prior
                      WHERE prior.user_id = e.user_id
                        AND prior.product_id = e.product_id
                        AND prior.event_timestamp < :inner_cutoff
                  )
            )
            SELECT user_id, product_id, event_type, event_timestamp, history_items
            FROM validation_positives
            WHERE target_rank = 1 AND history_items >= :minimum_history
            ORDER BY user_id
            """,
            {
                "inner_cutoff": inner_cutoff,
                "final_cutoff": final_cutoff,
                "minimum_history": MIN_HISTORY_ITEMS,
            },
        ).fetchall()
    finally:
        connection.close()

    targets = [
        {
            "user_id": int(user_id),
            "target_product_id": int(product_id),
            "target_event_type": event_type,
            "target_timestamp": event_timestamp,
            "history_items": int(history_items),
        }
        for user_id, product_id, event_type, event_timestamp, history_items in target_rows
    ]
    assert targets, "No eligible inner-validation targets were found"
    with (DATA_PROCESSED / "hybrid_validation_holdout.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(targets[0]))
        writer.writeheader()
        writer.writerows(targets)
    return ValidationData(
        interactions=interactions,
        inner_cutoff=inner_cutoff,
        final_cutoff=final_cutoff,
        targets=targets,
        train_event_count=train_event_count,
    )


def popularity_scores(interactions: csr_matrix) -> np.ndarray:
    """Weighted global item popularity from pre-cutoff interactions only."""
    return np.asarray(interactions.sum(axis=0)).ravel()


def item_item_cosine(interactions: csr_matrix) -> Tuple[np.ndarray, csr_matrix]:
    """Cosine similarity between item columns after log-scaling user-item weights."""
    log_interactions = interactions.copy().astype(np.float64)
    log_interactions.data = np.log1p(log_interactions.data)
    gram = (log_interactions.T @ log_interactions).toarray()
    norms = np.sqrt(np.maximum(np.diag(gram), 1e-12))
    similarities = gram / np.outer(norms, norms)
    similarities[~np.isfinite(similarities)] = 0.0
    np.fill_diagonal(similarities, 0.0)
    return similarities, log_interactions
