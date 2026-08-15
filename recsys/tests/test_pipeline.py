import csv
import inspect
import json
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from content_based import (  # noqa: E402
    build_user_profiles,
    fit_product_tfidf,
    load_product_metadata,
    recommend_top_k,
    score_content_candidates,
)
from evaluate_recommender import _tune_hybrid, evaluate_recommenders  # noqa: E402
from experiment_audit import paired_bootstrap  # noqa: E402
from hybrid_ranker import minmax_normalize, retrieve_candidate_pools  # noqa: E402
from recommender import prepare_inner_validation, prepare_temporal_data  # noqa: E402


def read_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class PipelineValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = ROOT / "data" / "processed" / "ecommerce.sqlite"
        cls.connection = sqlite3.connect(cls.database)
        cls.metadata = json.loads(
            (ROOT / "data" / "raw" / "dataset_metadata.json").read_text(encoding="utf-8")
        )
        cls.diagnostics = {
            row["metric"]: row["value"]
            for row in read_rows(ROOT / "results" / "recommendation_diagnostics.csv")
        }

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def test_expected_outputs_exist_and_are_nonempty(self):
        expected = (
            "README.md",
            "RESUME_EVIDENCE.md",
            "data/raw/users.csv",
            "data/raw/products.csv",
            "data/raw/sessions.csv",
            "data/raw/events.csv",
            "data/raw/dataset_metadata.json",
            "data/processed/ecommerce.sqlite",
            "data/processed/recommendation_holdout.csv",
            "data/processed/hybrid_validation_holdout.csv",
            "results/funnel_metrics.csv",
            "results/retention_metrics.csv",
            "results/ab_test_results.csv",
            "results/recommendation_metrics.csv",
            "results/recommendation_segment_metrics.csv",
            "results/recommendation_diagnostics.csv",
            "results/model_comparison.csv",
            "results/content_history_metrics.csv",
            "results/hybrid_validation_grid.csv",
            "results/hybrid_config.json",
            "results/retrieval_diagnostics.csv",
            "results/hybrid_improvements.csv",
            "results/history_bucket_metrics.csv",
            "results/popularity_bias_diagnostics.csv",
            "results/evaluation_population_audit.json",
            "results/per_user_final_metrics.csv",
            "results/hybrid_bootstrap_ci.csv",
            "results/hybrid_significance_tests.json",
            "results/hybrid_win_loss_analysis.csv",
            "results/sparse_history_audit.csv",
            "results/category_metrics.csv",
            "results/retrieval_vs_ranking_analysis.csv",
            "results/component_contribution_audit.csv",
            "EXPERIMENT_AUDIT.md",
            "results/run_metadata.json",
        )
        for relative_path in expected:
            path = ROOT / relative_path
            with self.subTest(path=relative_path):
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)

    def test_dataset_scale_and_ids(self):
        self.assertEqual(self.metadata["seed"], 2027)
        self.assertGreaterEqual(self.metadata["users"], 10_000)
        self.assertGreaterEqual(self.metadata["products"], 300)
        self.assertGreaterEqual(self.metadata["total_events"], 100_000)
        self.assertEqual(
            self.metadata["total_events"],
            self.metadata["views"]
            + self.metadata["clicks"]
            + self.metadata["add_to_carts"]
            + self.metadata["purchases"],
        )
        invalid_ids = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM events e
            LEFT JOIN users u ON e.user_id = u.user_id
            LEFT JOIN products p ON e.product_id = p.product_id
            LEFT JOIN sessions s ON e.session_id = s.session_id
            WHERE u.user_id IS NULL OR p.product_id IS NULL OR s.session_id IS NULL
            """
        ).fetchone()[0]
        self.assertEqual(invalid_ids, 0)

    def test_event_sequence_and_session_time_are_valid(self):
        purchase_before_session = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM events e JOIN sessions s ON e.session_id = s.session_id
            WHERE e.event_type = 'purchase' AND e.event_timestamp < s.session_start
            """
        ).fetchone()[0]
        missing_predecessors = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM events e
            WHERE (e.event_type = 'click' AND NOT EXISTS (
                    SELECT 1 FROM events v
                    WHERE v.session_id=e.session_id AND v.product_id=e.product_id
                      AND v.event_type='view' AND v.event_timestamp < e.event_timestamp
                  ))
               OR (e.event_type = 'add_to_cart' AND NOT EXISTS (
                    SELECT 1 FROM events c
                    WHERE c.session_id=e.session_id AND c.product_id=e.product_id
                      AND c.event_type='click' AND c.event_timestamp < e.event_timestamp
                  ))
               OR (e.event_type = 'purchase' AND NOT EXISTS (
                    SELECT 1 FROM events a
                    WHERE a.session_id=e.session_id AND a.product_id=e.product_id
                      AND a.event_type='add_to_cart' AND a.event_timestamp < e.event_timestamp
                  ))
            """
        ).fetchone()[0]
        self.assertEqual(purchase_before_session, 0)
        self.assertEqual(missing_predecessors, 0)

    def test_experiment_assignment_is_consistent_and_balanced(self):
        invalid_groups = self.connection.execute(
            "SELECT COUNT(*) FROM users WHERE experiment_group NOT IN ('control', 'treatment')"
        ).fetchone()[0]
        event_mismatches = self.connection.execute(
            """
            SELECT COUNT(*) FROM events e JOIN users u ON e.user_id=u.user_id
            WHERE e.experiment_group <> u.experiment_group
            """
        ).fetchone()[0]
        control_users = self.connection.execute(
            "SELECT COUNT(*) FROM users WHERE experiment_group='control'"
        ).fetchone()[0]
        self.assertEqual(invalid_groups, 0)
        self.assertEqual(event_mismatches, 0)
        self.assertGreaterEqual(control_users / self.metadata["users"], 0.48)
        self.assertLessEqual(control_users / self.metadata["users"], 0.52)
        self.assertEqual(len(self.metadata["assignment_sha256"]), 64)

        product_columns = set(read_rows(ROOT / "data" / "raw" / "products.csv")[0])
        self.assertTrue(
            {
                "category",
                "subcategory",
                "title",
                "keywords",
                "tags",
                "price_bucket",
                "use_case",
                "audience",
                "attributes",
            }.issubset(product_columns)
        )

    def test_temporal_holdout_has_no_training_leakage(self):
        cutoff = self.diagnostics["temporal_cutoff"]
        holdouts = read_rows(ROOT / "data" / "processed" / "recommendation_holdout.csv")
        self.assertEqual(len(holdouts), int(self.diagnostics["heldout_interactions"]))
        self.assertTrue(all(row["target_timestamp"] >= cutoff for row in holdouts))
        self.assertTrue(all(int(row["history_items"]) >= 3 for row in holdouts))
        self.connection.execute("DROP TABLE IF EXISTS temp.holdout_targets")
        self.connection.execute(
            "CREATE TEMP TABLE holdout_targets (user_id INTEGER, product_id INTEGER)"
        )
        self.connection.executemany(
            "INSERT INTO holdout_targets VALUES (?, ?)",
            ((row["user_id"], row["target_product_id"]) for row in holdouts),
        )
        leakage_count = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM events e
            JOIN holdout_targets h ON e.user_id = h.user_id AND e.product_id = h.product_id
            WHERE e.event_timestamp < ?
            """,
            (cutoff,),
        ).fetchone()[0]
        self.assertEqual(leakage_count, 0)
        max_training_timestamp = self.connection.execute(
            "SELECT MAX(event_timestamp) FROM events WHERE event_timestamp < ?", (cutoff,)
        ).fetchone()[0]
        self.assertLess(max_training_timestamp, cutoff)

    def test_all_metrics_are_in_valid_ranges(self):
        funnel = read_rows(ROOT / "results" / "funnel_metrics.csv")
        for row in funnel:
            for column in (
                "view_to_click_rate",
                "click_to_cart_rate",
                "cart_to_purchase_rate",
                "view_to_purchase_rate",
            ):
                self.assertGreaterEqual(float(row[column]), 0.0)
                self.assertLessEqual(float(row[column]), 1.0)

        retention = read_rows(ROOT / "results" / "retention_metrics.csv")
        for row in retention:
            for column in ("week_1_retention", "week_2_retention"):
                if row[column]:
                    self.assertGreaterEqual(float(row[column]), 0.0)
                    self.assertLessEqual(float(row[column]), 1.0)

        ab = read_rows(ROOT / "results" / "ab_test_results.csv")[0]
        self.assertGreaterEqual(float(ab["p_value"]), 0.0)
        self.assertLessEqual(float(ab["p_value"]), 1.0)
        self.assertLessEqual(float(ab["ci_95_lower"]), float(ab["absolute_uplift"]))
        self.assertGreaterEqual(float(ab["ci_95_upper"]), float(ab["absolute_uplift"]))

        recommendation = read_rows(ROOT / "results" / "recommendation_metrics.csv")
        self.assertEqual(
            {row["model"] for row in recommendation},
            {"popularity", "item_item_cosine", "content", "hybrid"},
        )
        for row in recommendation:
            for column in (
                "recall@5",
                "precision@5",
                "ndcg@5",
                "recall@10",
                "precision@10",
                "ndcg@10",
                "catalog_coverage@10",
            ):
                self.assertGreaterEqual(float(row[column]), 0.0)
                self.assertLessEqual(float(row[column]), 1.0)
            self.assertLessEqual(float(row["recall@5"]), float(row["recall@10"]))

        comparison = read_rows(ROOT / "results" / "model_comparison.csv")
        self.assertEqual(
            [row["model"] for row in comparison],
            ["Popularity", "Collaborative", "Content", "Hybrid"],
        )

    def test_readme_uses_generated_values_and_forbidden_claim_is_absent(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"{self.metadata['total_events']:,}", readme)
        self.assertIn(f"{self.metadata['sessions']:,}", readme)
        recommendation = read_rows(ROOT / "results" / "recommendation_metrics.csv")
        for row in recommendation:
            self.assertIn(f"{float(row['recall@10']):.4f}", readme)

        text_extensions = {".py", ".sql", ".md", ".txt"}
        forbidden_brand = "tik" + "tok"
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix in text_extensions:
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertNotIn(forbidden_brand, path.read_text(encoding="utf-8").lower())

    def test_root_documentation_matches_generated_results(self):
        validator = ROOT.parent / "scripts" / "validate_project_docs.py"
        completed = subprocess.run(
            [sys.executable, str(validator)],
            cwd=ROOT.parent,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Documentation consistency: OK", completed.stdout)


class ContentRecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = prepare_temporal_data()
        cls.products = load_product_metadata()
        cls.product_vectors, cls.vocabulary = fit_product_tfidf(cls.products)
        cls.user_indices = np.array(
            [int(target["user_id"]) - 1 for target in cls.data.targets[:64]],
            dtype=np.int32,
        )

    def test_content_profiles_use_only_training_interactions(self):
        profiles = build_user_profiles(
            self.data.interactions, self.product_vectors, self.user_indices
        )
        expected = self.data.interactions[self.user_indices].dot(self.product_vectors).tocsr()
        norms = np.sqrt(np.asarray(expected.multiply(expected).sum(axis=1)).ravel())
        norms[norms == 0.0] = 1.0
        expected = expected.multiply((1.0 / norms)[:, None]).tocsr()
        np.testing.assert_allclose(profiles.toarray(), expected.toarray(), atol=1e-12)
        for target in self.data.targets[:64]:
            user_index = int(target["user_id"]) - 1
            target_index = int(target["target_product_id"]) - 1
            self.assertEqual(float(self.data.interactions[user_index, target_index]), 0.0)

        # Catalog TF-IDF has no target, user, or interaction input and excludes
        # singleton tokens that could make a synthetic listing an identifier.
        self.assertGreater(len(self.vocabulary), 0)
        self.assertTrue(all(not token.endswith("product_id") for token in self.vocabulary))

    def test_content_recommendations_exclude_seen_items(self):
        scores = score_content_candidates(
            self.data.interactions, self.product_vectors, self.user_indices
        )
        recommendations = recommend_top_k(
            scores, self.data.interactions, self.user_indices, 10
        )
        for user_index, recommended in zip(self.user_indices, recommendations):
            seen = set(self.data.interactions.getrow(int(user_index)).indices)
            self.assertTrue(seen.isdisjoint(recommended.tolist()))

    def test_content_metrics_are_deterministic(self):
        previous = {
            row["model"]: row for row in read_rows(ROOT / "results" / "recommendation_metrics.csv")
        }
        repeated_metrics, _ = evaluate_recommenders()
        repeated = {str(row["model"]): row for row in repeated_metrics}
        for model in ("content", "hybrid"):
            for metric in (
                "recall@5", "precision@5", "ndcg@5",
                "recall@10", "precision@10", "ndcg@10", "catalog_coverage@10",
            ):
                self.assertEqual(float(previous[model][metric]), float(repeated[model][metric]))


class HybridRecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.final = prepare_temporal_data()
        cls.validation = prepare_inner_validation(cls.final.cutoff)
        cls.config = json.loads(
            (ROOT / "results" / "hybrid_config.json").read_text(encoding="utf-8")
        )

    def test_inner_validation_is_strictly_before_final_test(self):
        self.assertTrue(
            all(target["target_timestamp"] < self.final.cutoff for target in self.validation.targets)
        )
        self.assertTrue(
            all(target["target_timestamp"] >= self.final.cutoff for target in self.final.targets)
        )
        validation_pairs = {
            (int(target["user_id"]), int(target["target_product_id"]))
            for target in self.validation.targets
        }
        final_pairs = {
            (int(target["user_id"]), int(target["target_product_id"]))
            for target in self.final.targets
        }
        self.assertTrue(validation_pairs.isdisjoint(final_pairs))
        for target in self.validation.targets:
            user_index = int(target["user_id"]) - 1
            product_index = int(target["target_product_id"]) - 1
            self.assertEqual(float(self.validation.interactions[user_index, product_index]), 0.0)

    def test_candidate_retrieval_excludes_seen_and_deduplicates(self):
        interactions = np.zeros((1, 8), dtype=np.float64)
        interactions[0, [0, 3]] = 1.0
        from scipy.sparse import csr_matrix

        collaborative = np.array([[8, 7, 6, 5, 4, 3, 2, 1]], dtype=np.float64)
        content = np.array([[1, 2, 8, 7, 6, 5, 4, 3]], dtype=np.float64)
        popularity = np.array([8, 7, 6, 5, 4, 3, 2, 1], dtype=np.float64)
        pools = retrieve_candidate_pools(
            collaborative, content, popularity, csr_matrix(interactions), [0], 3, 3, 2
        )
        pool = pools[0]
        self.assertEqual(len(pool.union), len(set(pool.union.tolist())))
        self.assertTrue({0, 3}.isdisjoint(pool.union.tolist()))
        self.assertNotIn("target", inspect.signature(retrieve_candidate_pools).parameters)

    def test_score_normalization_is_safe_and_deterministic(self):
        values = np.array([2.0, 4.0, np.nan, np.inf, 6.0])
        first = minmax_normalize(values)
        second = minmax_normalize(values)
        np.testing.assert_array_equal(first, second)
        self.assertTrue(np.all(np.isfinite(first)))
        np.testing.assert_array_equal(
            minmax_normalize(np.array([3.0, 3.0, 3.0])), np.zeros(3)
        )

    def test_selected_weights_originate_from_validation_grid(self):
        self.assertAlmostEqual(
            float(self.config["alpha"])
            + float(self.config["beta"])
            + float(self.config["gamma"]),
            1.0,
        )
        self.assertGreaterEqual(min(
            float(self.config["alpha"]),
            float(self.config["beta"]),
            float(self.config["gamma"]),
        ), 0.0)
        self.assertEqual(self.config["selection_source"], "inner_temporal_validation")
        self.assertFalse(self.config["final_test_metrics_used_for_selection"])
        self.assertNotIn("final_data", inspect.signature(_tune_hybrid).parameters)
        grid = read_rows(ROOT / "results" / "hybrid_validation_grid.csv")
        matches = [
            row for row in grid
            if float(row["alpha"]) == float(self.config["alpha"])
            and float(row["beta"]) == float(self.config["beta"])
            and float(row["gamma"]) == float(self.config["gamma"])
            and int(row["collaborative_m"]) == int(self.config["collaborative_m"])
            and int(row["content_m"]) == int(self.config["content_m"])
            and int(row["popularity_m"]) == int(self.config["popularity_m"])
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            float(matches[0]["ndcg@10"]), float(self.config["validation_ndcg@10"])
        )
        self.assertEqual(
            float(matches[0]["recall@10"]), float(self.config["validation_recall@10"])
        )


class Phase4ExperimentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.per_user = read_rows(ROOT / "results" / "per_user_final_metrics.csv")
        cls.population = json.loads(
            (ROOT / "results" / "evaluation_population_audit.json").read_text(
                encoding="utf-8"
            )
        )
        cls.significance = json.loads(
            (ROOT / "results" / "hybrid_significance_tests.json").read_text(
                encoding="utf-8"
            )
        )

    def test_all_models_share_the_identical_final_population(self):
        self.assertEqual(self.population["eligible_users"], 3954)
        self.assertEqual(self.population["target_count"], 3954)
        self.assertEqual(self.population["population_mismatch_count"], 0)
        self.assertEqual(
            set(self.population["per_model_evaluated_users"].values()), {3954}
        )
        self.assertEqual(
            set(self.population["per_model_target_sha256"].values()),
            {self.population["target_sha256"]},
        )

    def test_paired_bootstrap_is_deterministic(self):
        differences = np.array([0.0, 1.0, -1.0, 0.5, 0.25], dtype=np.float64)
        first = paired_bootstrap(differences, resamples=500, seed=8128)
        second = paired_bootstrap(differences, resamples=500, seed=8128)
        self.assertEqual(first, second)

    def test_mcnemar_cells_sum_to_final_population(self):
        for metric in ("Recall@5", "Recall@10"):
            result = self.significance[metric]
            total = sum(
                int(result[cell])
                for cell in ("both", "hybrid_only", "collaborative_only", "neither")
            )
            self.assertEqual(total, len(self.per_user))

    def test_per_user_metrics_reconstruct_published_metrics(self):
        published = {
            row["model"]: row
            for row in read_rows(ROOT / "results" / "recommendation_metrics.csv")
        }
        names = {
            "popularity": "popularity",
            "item_item_cosine": "collaborative",
            "content": "content",
            "hybrid": "hybrid",
        }
        for published_name, per_user_name in names.items():
            for k in (5, 10):
                recall = np.mean(
                    [float(row[f"{per_user_name}_hit{k}"]) for row in self.per_user]
                )
                ndcg = np.mean(
                    [float(row[f"{per_user_name}_ndcg{k}"]) for row in self.per_user]
                )
                self.assertAlmostEqual(
                    recall, float(published[published_name][f"recall@{k}"]), places=12
                )
                self.assertAlmostEqual(
                    ndcg, float(published[published_name][f"ndcg@{k}"]), places=12
                )

    def test_phase4_diagnostics_do_not_modify_hybrid_config(self):
        self.assertFalse(self.population["hybrid_config_modified_by_audit"])
        self.assertEqual(
            self.population["hybrid_config_sha256_before_audit"],
            self.population["hybrid_config_sha256_after_audit"],
        )


if __name__ == "__main__":
    unittest.main()
