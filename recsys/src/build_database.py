"""Load generated CSV files into SQLite and execute SQL analytics."""

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from config import DATABASE_PATH, DATA_RAW, RESULTS, ensure_directories


def _read_values(path: Path, columns: Sequence[str]) -> Iterable[tuple]:
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            yield tuple(row[column] for column in columns)


def build_database() -> Path:
    ensure_directories()
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;

            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                segment TEXT NOT NULL,
                primary_category_id INTEGER NOT NULL,
                secondary_category_id INTEGER NOT NULL,
                acquisition_date TEXT NOT NULL,
                experiment_group TEXT NOT NULL CHECK (experiment_group IN ('control', 'treatment')),
                conversion_propensity REAL NOT NULL
            );

            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL,
                category_name TEXT NOT NULL,
                price REAL NOT NULL CHECK (price > 0),
                popularity_score REAL NOT NULL,
                quality_score REAL NOT NULL,
                category_conversion_multiplier REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT NOT NULL,
                title TEXT NOT NULL,
                keywords TEXT NOT NULL,
                tags TEXT NOT NULL,
                price_bucket TEXT NOT NULL,
                use_case TEXT NOT NULL,
                audience TEXT NOT NULL,
                attributes TEXT NOT NULL
            );

            CREATE TABLE sessions (
                session_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                session_start TEXT NOT NULL,
                experiment_group TEXT NOT NULL CHECK (experiment_group IN ('control', 'treatment'))
            );

            CREATE TABLE events (
                event_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                session_id INTEGER NOT NULL REFERENCES sessions(session_id),
                product_id INTEGER NOT NULL REFERENCES products(product_id),
                event_type TEXT NOT NULL CHECK (event_type IN ('view', 'click', 'add_to_cart', 'purchase')),
                event_timestamp TEXT NOT NULL,
                experiment_group TEXT NOT NULL CHECK (experiment_group IN ('control', 'treatment'))
            );
            """
        )

        table_columns = {
            "users": (
                "user_id",
                "segment",
                "primary_category_id",
                "secondary_category_id",
                "acquisition_date",
                "experiment_group",
                "conversion_propensity",
            ),
            "products": (
                "product_id",
                "category_id",
                "category_name",
                "price",
                "popularity_score",
                "quality_score",
                "category_conversion_multiplier",
                "category",
                "subcategory",
                "title",
                "keywords",
                "tags",
                "price_bucket",
                "use_case",
                "audience",
                "attributes",
            ),
            "sessions": ("session_id", "user_id", "session_start", "experiment_group"),
            "events": (
                "event_id",
                "user_id",
                "session_id",
                "product_id",
                "event_type",
                "event_timestamp",
                "experiment_group",
            ),
        }
        for table, columns in table_columns.items():
            source = DATA_RAW / f"{table}.csv"
            placeholders = ",".join("?" for _ in columns)
            connection.executemany(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                _read_values(source, columns),
            )
            connection.commit()

        connection.executescript(
            """
            CREATE INDEX idx_events_timestamp ON events(event_timestamp);
            CREATE INDEX idx_events_user_time ON events(user_id, event_timestamp);
            CREATE INDEX idx_events_product ON events(product_id);
            CREATE INDEX idx_events_session_product_time ON events(session_id, product_id, event_timestamp);
            CREATE INDEX idx_events_type ON events(event_type);
            CREATE INDEX idx_sessions_user ON sessions(user_id);
            """
        )
        orphan_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM events e
            LEFT JOIN users u ON e.user_id = u.user_id
            LEFT JOIN products p ON e.product_id = p.product_id
            LEFT JOIN sessions s ON e.session_id = s.session_id
            WHERE u.user_id IS NULL OR p.product_id IS NULL OR s.session_id IS NULL
            """
        ).fetchone()[0]
        inconsistent_groups = connection.execute(
            """
            SELECT COUNT(*)
            FROM events e JOIN users u ON e.user_id = u.user_id
            WHERE e.experiment_group <> u.experiment_group
            """
        ).fetchone()[0]
        purchase_before_session = connection.execute(
            """
            SELECT COUNT(*)
            FROM events e JOIN sessions s ON e.session_id = s.session_id
            WHERE e.event_type = 'purchase' AND e.event_timestamp < s.session_start
            """
        ).fetchone()[0]
        assert orphan_count == 0
        assert inconsistent_groups == 0
        assert purchase_before_session == 0
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode = DELETE")
    finally:
        connection.close()
    for suffix in ("-shm", "-wal"):
        sidecar = DATABASE_PATH.with_name(DATABASE_PATH.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
    return DATABASE_PATH


def _query_to_csv(connection: sqlite3.Connection, sql_path: Path, output_path: Path) -> None:
    cursor = connection.execute(sql_path.read_text(encoding="utf-8"))
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def run_sql_analyses() -> None:
    source_dir = Path(__file__).resolve().parent
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        _query_to_csv(connection, source_dir / "funnel_analysis.sql", RESULTS / "funnel_metrics.csv")
        _query_to_csv(connection, source_dir / "retention_analysis.sql", RESULTS / "retention_metrics.csv")
    finally:
        connection.close()


if __name__ == "__main__":
    path = build_database()
    run_sql_analyses()
    print(f"Built {path}")
