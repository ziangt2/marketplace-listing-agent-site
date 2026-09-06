import json
import unittest

from multimodal.src.agent_benchmark import DEFAULT_OUTPUT, QUERIES, oracle_satisfies, stable_result
from multimodal.src.agent_report import verified_results
from multimodal.src.config import ROOT, manifest_path
from multimodal.src.io_utils import file_sha256, read_jsonl


class SavedEvaluationTests(unittest.TestCase):
    def test_measured_artifacts_reconstruct(self):
        metrics, _, _ = verified_results()
        self.assertEqual(metrics["query_count"], 36)
        self.assertEqual(sum(metrics["status_counts"].values()), 36)

    def test_historical_files_preserved(self):
        audit = json.loads((DEFAULT_OUTPUT / "historical_preservation.json").read_text())
        publication = json.loads((ROOT / "results/publication_preservation.json").read_text())
        self.assertTrue(audit["unchanged"])
        for path, checksum in audit["sha256"].items():
            # The development audit includes three pre-existing user edits. Publishing
            # this feature preserves their committed baseline and leaves those edits local.
            allowed = {checksum}
            for category in ("preexisting_uncommitted_files", "git_text_normalization"):
                if path in publication[category]:
                    recorded = publication[category][path]
                    self.assertEqual(recorded["local_baseline_sha256"], checksum)
                    allowed.add(recorded["published_baseline_sha256"])
            self.assertIn(file_sha256(ROOT.parent / path), allowed, path)

    def test_fixture_images_use_existing_held_out_views(self):
        old = {q["image"]["image_id"]: q["image"] for q in read_jsonl(ROOT / "data/manifests/queries_mvp_v2.jsonl") if q["task"] == "image"}
        queries = read_jsonl(QUERIES)
        self.assertEqual(len(queries), 36)
        self.assertEqual(len({q["query_id"] for q in queries}), 36)
        self.assertEqual(len({q["category"] for q in queries}), 6)
        for query in queries:
            if "image" in query:
                self.assertEqual(query["image"], old[query["image"]["image_id"]])

    def test_replay_semantics_and_no_new_api_calls(self):
        replay = ROOT / "results/agent_v2_replay"
        original, repeated = read_jsonl(DEFAULT_OUTPUT / "agent_runs.jsonl"), read_jsonl(replay / "agent_runs.jsonl")
        self.assertEqual([stable_result(r) for r in original], [stable_result(r) for r in repeated])
        self.assertTrue(all(c["cache_hit"] for r in repeated for c in r["llm_calls"]))

    def test_constraint_oracle_uses_source_metadata(self):
        products = {p["product_id"]: p for p in read_jsonl(manifest_path("mvp"))}
        self.assertTrue(oracle_satisfies(products["B07GFRCZWY"], [{"field": "width", "operator": "lt", "value": "115 cm"}]))
        self.assertFalse(oracle_satisfies(products["B07GFRCZWY"], [{"field": "width", "operator": "lt", "value": "100 cm"}]))

    def test_bad_drafts_remain_visible_and_are_withheld(self):
        runs = read_jsonl(DEFAULT_OUTPUT / "agent_runs.jsonl")
        rejected = [r for r in runs if r["grounding"]["errors"]]
        self.assertTrue(rejected)
        for run in rejected:
            self.assertTrue(run["raw_output"]["recommendations"])
            self.assertFalse(run["recommendations"])
            self.assertEqual(run["status"], "error")


if __name__ == "__main__":
    unittest.main()
