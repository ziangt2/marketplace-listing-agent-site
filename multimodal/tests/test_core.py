"""Unit fixtures are synthetic; published measurements use only the ABO manifests."""
import copy
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from multimodal.src.abo_dataset import candidate_list, inspect_image, normalize_listing, validate_catalog
from multimodal.src.build_embeddings import EmbeddingTable, encode_cached
from multimodal.src.embedding_model import normalize_vectors
from multimodal.src.exact_index import ExactIndex, FaissFlatIndex, Hit
from multimodal.src.hybrid_retrieval import reciprocal_rank_fusion, source_complementarity
from multimodal.src.latency import latency_summary
from multimodal.src.lexical_retrieval import LexicalIndex
from multimodal.src.metrics import retrieval_metrics
from multimodal.src.queries import build_image_queries, build_text_queries, validate_text_queries


def fixture_product(product_id, color="brown"):
    return {"product_id": product_id, "item_id": product_id, "title": "Test chair fixture", "product_type": "CHAIR",
            "material": "wood", "color": color, "style": "modern", "model_numbers": []}


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {"main": {"width": 256, "height": 256}, "alt": {"width": 128, "height": 128}}
        self.record = {"item_id": "id_one", "domain_name": "amazon.com", "item_name": [{"language_tag": "en_US", "value": "Actual field format"}],
                       "product_type": [{"value": "CHAIR"}], "main_image_id": "main", "other_image_id": ["alt"]}

    def test_deterministic_ids_and_listing_deduplication(self):
        second = {**self.record, "item_id": "id_two"}
        alternate_domain = {**self.record, "domain_name": "amazon.co.uk"}
        first, drops = candidate_list([self.record, second, alternate_domain], self.metadata, 2027)
        repeated, _ = candidate_list([alternate_domain, second, self.record], self.metadata, 2027)
        self.assertEqual(first, repeated)
        self.assertEqual(len({p["product_id"] for p in first}), 2)
        self.assertEqual(drops["duplicate_item_listing"], 1)
        self.assertEqual(next(p for p in first if p["product_id"] == "id_one")["domain_name"], "amazon.com")

    def test_missing_image_and_english_handling(self):
        self.assertEqual(normalize_listing(self.record, {})[1], "no_usable_image_metadata")
        self.assertEqual(normalize_listing({**self.record, "item_name": [{"language_tag": "de_DE", "value": "Stuhl"}]}, self.metadata)[1], "missing_english_title")

    def test_file_existence_checksum_and_global_query_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (64, 64), "red").save(root / "main.png")
            Image.new("RGB", (64, 64), "blue").save(root / "query.png")
            index = {"image_id": "main", "path": "main.png", **inspect_image(root / "main.png")}
            query = {"image_id": "query", "path": "query.png", **inspect_image(root / "query.png")}
            catalog = [{**fixture_product("one"), "index_image": index, "query_image": query}]
            validate_catalog(catalog, root)
            bad = copy.deepcopy(catalog)
            bad[0]["query_image"] = index
            with self.assertRaisesRegex(ValueError, "Query image"):
                validate_catalog(bad, root)
            (root / "query.png").unlink()
            with self.assertRaises(FileNotFoundError):
                validate_catalog(catalog, root)

    def test_pixel_duplicate_exclusion_across_products(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (64, 64), "red").save(root / "a.png", compress_level=0)
            Image.new("RGB", (64, 64), "red").save(root / "b.png", compress_level=9)
            a, b = inspect_image(root / "a.png"), inspect_image(root / "b.png")
            self.assertNotEqual(a["sha256"], b["sha256"])
            self.assertEqual(a["pixel_sha256"], b["pixel_sha256"])
            products = [{**fixture_product(i), "index_image": {"image_id": i, "path": i + ".png", **v}, "query_image": None} for i, v in (("a", a), ("b", b))]
            with self.assertRaisesRegex(ValueError, "Duplicate indexed"):
                validate_catalog(products, root)


class EmbeddingTests(unittest.TestCase):
    def test_norms_and_zero_nonfinite_rejection(self):
        result = normalize_vectors([[3, 4], [1, 0]])
        np.testing.assert_allclose(np.linalg.norm(result, axis=1), [1, 1])
        for bad in ([[0, 0]], [[np.nan, 1]], [[np.inf, 1]]):
            with self.assertRaises(ValueError):
                normalize_vectors(bad)

    def test_product_embedding_alignment(self):
        table = EmbeddingTable(["one", "two"], np.eye(2, dtype=np.float32))
        table.validate(["one", "two"])
        with self.assertRaisesRegex(ValueError, "order"):
            table.validate(["two", "one"])
        with self.assertRaisesRegex(ValueError, "misaligned"):
            EmbeddingTable(["one"], table.vectors).validate()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            EmbeddingTable(["one", "one"], table.vectors).validate()

    def test_cache_reuse_order_and_invalidation(self):
        class FixtureEncoder:
            metadata = {"model_name": "unit-test-fixture-only", "revision": "1"}
            embedding_dimension = 2
            batch_size = 2
            calls = 0

            def encode_text(self, values):
                self.calls += len(values)
                return normalize_vectors([[len(v), 1] for v in values])

        encoder = FixtureEncoder()
        with tempfile.TemporaryDirectory() as directory:
            first, _ = encode_cached(encoder, "text", ["a", "b"], ["oak", "steel"], ["hash-a", "hash-b"], directory)
            second, audit = encode_cached(encoder, "text", ["b", "a"], ["steel", "oak"], ["hash-b", "hash-a"], directory)
            np.testing.assert_array_equal(first.vectors[::-1], second.vectors)
            self.assertEqual(encoder.calls, 2)
            self.assertEqual(audit["cache_hits"], 2)
            encode_cached(encoder, "text", ["a"], ["new text"], ["changed-hash"], directory)
            self.assertEqual(encoder.calls, 3)
            encoder.metadata = {**encoder.metadata, "revision": "2"}
            encode_cached(encoder, "text", ["a"], ["oak"], ["hash-a"], directory)
            self.assertEqual(encoder.calls, 4)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.table = EmbeddingTable(["a", "b", "c"], normalize_vectors([[1, 0], [0, 1], [-1, 0]]))

    def test_exact_and_faiss_match_with_valid_output(self):
        query = normalize_vectors([[2, 1]])[0]
        for index in (ExactIndex(self.table), FaissFlatIndex(self.table)):
            first = index.search(query, 10)
            self.assertEqual([h.product_id for h in first], ["a", "b", "c"])
            self.assertEqual(first, index.search(query, 10))
            with self.assertRaises(ValueError):
                index.search([0, 0])
            with self.assertRaises(ValueError):
                index.search(query, 0)

    def test_exact_tie_break_uses_product_id(self):
        table = EmbeddingTable(["z", "a"], np.array([[1, 0], [1, 0]], dtype=np.float32))
        self.assertEqual([h.product_id for h in ExactIndex(table).search([1, 0], 1)], ["a"])

    def test_faiss_roundtrip(self):
        import faiss
        with tempfile.TemporaryDirectory() as directory:
            index = FaissFlatIndex(self.table)
            path = Path(directory) / "flat.faiss"
            index.save(path)
            loaded = faiss.read_index(str(path))
            _, positions = loaded.search(np.array([[1, 0]], dtype=np.float32), 1)
            self.assertEqual(self.table.ids[positions[0][0]], "a")

    def test_lexical_known_terms_and_unknown_empty(self):
        products = [fixture_product("a", "red"), fixture_product("b", "blue"), fixture_product("c", "green")]
        index = LexicalIndex(products)
        self.assertEqual(index.search("red")[0].product_id, "a")
        self.assertEqual(index.search("unknownunmatchedtoken"), [])

    def test_rrf_expected_scores_deduplication_and_complementarity(self):
        lexical = [Hit("a", 999, "lexical"), Hit("b", 100, "lexical")]
        vector = [Hit("b", 0.9, "vector"), Hit("c", 0.7, "vector")]
        hits = reciprocal_rank_fusion({"lexical": lexical, "vector": vector}, 3)
        self.assertEqual([h.product_id for h in hits], ["b", "a", "c"])
        self.assertAlmostEqual(hits[0].score, 1 / 61 + 1 / 62)
        self.assertEqual(hits, reciprocal_rank_fusion({"vector": vector, "lexical": lexical}, 3))
        duplicate = reciprocal_rank_fusion({"lexical": [lexical[0], lexical[0], lexical[1]]}, 2)
        self.assertAlmostEqual(duplicate[1].score, 1 / 62)
        complement = source_complementarity(lexical, vector, ["a", "b", "c", "d"])
        self.assertEqual(complement["union_candidate_recall"], 0.75)
        self.assertEqual(complement["lexical_only_relevant_hits"], 1)
        self.assertEqual(complement["vector_only_relevant_hits"], 1)


class EvaluationTests(unittest.TestCase):
    def test_shared_query_views_are_excluded_from_identity_task(self):
        catalog = [{**fixture_product(i), "query_image": {"pixel_sha256": pixels}} for i, pixels in (("a", "same"), ("b", "same"), ("c", "different"))]
        self.assertEqual([q["relevant_ids"] for q in build_image_queries(catalog)], [["c"]])

    def test_multi_positive_metrics(self):
        metrics = retrieval_metrics(["x", "b", "a"], ["a", "b", "c"])
        self.assertEqual(metrics["recall@1"], 0)
        self.assertAlmostEqual(metrics["recall@5"], 2 / 3)
        self.assertEqual(metrics["mrr"], 0.5)
        self.assertAlmostEqual(metrics["ndcg@5"], (1 / math.log2(3) + 0.5) / (1 + 1 / math.log2(3) + 0.5))
        self.assertEqual(retrieval_metrics([], ["a"])["mrr"], 0)
        with self.assertRaises(ValueError):
            retrieval_metrics(["a", "a"], ["a"])
        with self.assertRaises(ValueError):
            retrieval_metrics(["a"], [])

    def test_latency_percentiles(self):
        summary = latency_summary([1, 2, 3, 4, 5])
        self.assertEqual(summary["p50_ms"], 3)
        self.assertAlmostEqual(summary["p95_ms"], 4.8)

    def test_query_labels_determinism_and_no_singleton_ids(self):
        catalog = [fixture_product("fixture_" + str(i), "red" if i < 3 else "blue") for i in range(6)]
        settings = {"min_relevant": 2, "max_relevant": 4, "max_relevant_fraction": 1}
        queries, _ = build_text_queries(catalog, settings)
        repeated, _ = build_text_queries(list(reversed(catalog)), settings)
        self.assertEqual(queries, repeated)
        self.assertEqual(len(queries), 2)
        self.assertTrue(all(len(q["relevant_ids"]) == 3 for q in queries))
        self.assertTrue(all("fixture_" not in q["text"] for q in queries))
        broken = copy.deepcopy(queries)
        broken[0]["relevant_ids"] = ["wrong-id"]
        with self.assertRaises(ValueError):
            validate_text_queries(broken, catalog, settings)
        broken = copy.deepcopy(queries)
        broken[0]["text"] = "fixture_0"
        with self.assertRaises(ValueError):
            validate_text_queries(broken, catalog, settings)


if __name__ == "__main__":
    unittest.main()
