"""Audit shipped real-data evidence without downloading images or model weights."""
import csv
import json
import unittest
from collections import defaultdict

import numpy as np

from multimodal.src.abo_dataset import validate_catalog
from multimodal.src.config import ROOT, load_config, manifest_path, queries_path
from multimodal.src.io_utils import file_sha256, read_jsonl
from multimodal.src.latency import latency_summary
from multimodal.src.metrics import aggregate, retrieval_metrics
from multimodal.src.queries import build_image_queries, build_text_queries, validate_text_queries


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class PublishedArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = ROOT / "results/mvp"
        cls.config = json.loads((cls.results / "benchmark_config.json").read_text())
        cls.catalog = read_jsonl(manifest_path("mvp"))
        cls.queries = read_jsonl(queries_path("mvp"))
        cls.rows = csv_rows(cls.results / "per_query_metrics.csv")

    def test_manifest_checksums_population_and_leakage(self):
        validate_catalog(self.catalog, check_files=False)
        self.assertEqual(file_sha256(manifest_path("mvp")), self.config["catalog_sha256"])
        self.assertEqual(file_sha256(queries_path("mvp")), self.config["queries_sha256"])
        text_queries = [q for q in self.queries if q["task"] == "text"]
        settings = self.config["config"]["evaluation"]
        validate_text_queries(text_queries, self.catalog, settings)
        generated, _ = build_text_queries(self.catalog, settings)
        self.assertEqual(text_queries, generated)
        self.assertEqual([q for q in self.queries if q["task"] == "image"], build_image_queries(self.catalog))
        dataset = json.loads((self.results / "dataset_summary.json").read_text())
        self.assertEqual(dataset["products"], len(self.catalog))
        self.assertEqual(dataset["text_queries"], len(text_queries))
        self.assertEqual(dataset["image_queries"], len(self.queries) - len(text_queries))
        self.assertEqual(dataset["image_queries"] + dataset["ambiguous_shared_view_queries_excluded"], dataset["image_views_available"])

    def test_cached_embedding_alignment_matches_catalog_and_queries(self):
        cache = self.config["cache"]
        self.assertEqual(cache["catalog"]["ids"], [p["product_id"] for p in self.catalog])
        self.assertEqual(cache["catalog"]["source_checksums"], [p["index_image"]["sha256"] for p in self.catalog])
        for task in ("text", "image"):
            self.assertEqual(cache[task + "_queries"]["ids"], [q["query_id"] for q in self.queries if q["task"] == task])

    def test_metrics_reconstruct_and_system_populations_match(self):
        groups = defaultdict(list)
        for row in self.rows:
            groups[(row["task"], row["system"])].append(row)
        for task in ("text", "image"):
            expected_ids = {q["query_id"] for q in self.queries if q["task"] == task}
            for published in csv_rows(self.results / f"{task}_retrieval.csv"):
                rows = groups[(task, published["system"])]
                self.assertEqual({r["query_id"] for r in rows}, expected_ids)
                self.assertEqual(len(rows), len(expected_ids))
                reconstructed = aggregate([{k: float(v) for k, v in r.items() if k == "mrr" or k.startswith(("recall@", "ndcg@", "hit@"))} for r in rows])
                for key, value in reconstructed.items():
                    self.assertAlmostEqual(float(published[key]), value, places=12)
            exact = {r["query_id"]: r for r in groups[(task, "numpy_exact")]}
            for row in groups[(task, "faiss_flat")]:
                for key in ("recall@1", "recall@5", "recall@10", "mrr"):
                    self.assertEqual(row[key], exact[row["query_id"]][key])

    def test_saved_top10_prove_reported_recall_and_ndcg(self):
        relevant = {q["query_id"]: q["relevant_ids"] for q in self.queries}
        known = {p["product_id"] for p in self.catalog}
        rows = {(r["query_id"], r["system"]): r for r in self.rows}
        runs = read_jsonl(self.results / "retrieval_runs.jsonl")
        self.assertEqual(len(runs), len(rows))
        for run in runs:
            self.assertTrue(set(run["top10"]).issubset(known))
            result = retrieval_metrics(run["top10"], relevant[run["query_id"]])
            saved = rows[(run["query_id"], run["system"])]
            for key in ("recall@1", "recall@5", "recall@10", "ndcg@10"):
                self.assertAlmostEqual(result[key], float(saved[key]), places=12)
            rank = run["first_relevant_rank"]
            self.assertAlmostEqual(1 / rank if rank else 0, float(saved["mrr"]), places=12)

    def test_latency_percentiles_reconstruct(self):
        groups = defaultdict(list)
        for row in csv_rows(self.results / "latency_samples.csv"):
            groups[(row["task"], row["system"])].append(float(row["ms"]))
        for published in json.loads((self.results / "latency.json").read_text())["measurements"]:
            reconstructed = latency_summary(groups[(published["task"], published["system"])])
            for key, value in reconstructed.items():
                self.assertAlmostEqual(value, published[key], places=12)

    def test_source_complementarity_counts(self):
        for row in csv_rows(self.results / "source_complementarity.csv"):
            self.assertEqual(int(row["union_relevant_hits"]), sum(int(row[key]) for key in ("lexical_only_relevant_hits", "vector_only_relevant_hits", "overlap_relevant_hits")))
            self.assertGreaterEqual(float(row["union_candidate_recall"]), 0)
            self.assertLessEqual(float(row["union_candidate_recall"]), 1)


if __name__ == "__main__":
    unittest.main()
