import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multimodal.src.agent_tools import SearchTools
from multimodal.src.grounding import validate_output, render_answer
from multimodal.src.llm_provider import OpenAIProvider, ProviderError
from multimodal.src.product_agent import ProductSearchAgent, obvious_route, unavailable_in
from multimodal.src.product_evidence import evidence_for, inches, satisfies, validate_constraints


def product(pid="A", **overrides):
    return dict(product_id=pid, title="Wood chair", product_type="CHAIR", material="Ash", color="Brown", style="",
                dimensions={"width": {"value": 50.8, "unit": "centimeters"}}, **overrides)


def claim(pid="A", field="material", value="Ash"):
    return {"recommendations": [{"product_id": pid, "evidence": [{"field": field, "value": value}]}]}


def plan(**updates):
    return dict(route="search_text", search_query="chair", broad_query="chair", constraints=[],
                unsupported=[], compare=False) | updates


class FakeProvider:
    def __init__(self, *outputs):
        self.outputs, self.calls = iter(outputs), []

    def generate_structured(self, **kwargs):
        result = next(self.outputs)
        if isinstance(result, Exception):
            raise result
        return result


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {"A": evidence_for(product())}

    def test_missing_fields_are_absent(self):
        self.assertNotIn("style", self.evidence["A"]["fields"])
        self.assertNotIn("price", self.evidence["A"]["fields"])

    def test_unit_conversion_preserves_source(self):
        self.assertEqual(self.evidence["A"]["fields"]["width"], "20 in")
        self.assertEqual(self.evidence["A"]["dimension_sources"]["width"]["value"], 50.8)
        self.assertEqual(inches("508 mm"), 20)

    def test_unknown_product_rejected(self):
        self.assertFalse(validate_output(claim("FAKE"), self.evidence, {"A"})["accepted"])

    def test_catalog_product_outside_candidates_rejected(self):
        result = validate_output(claim("B"), self.evidence, {"A", "B"})
        self.assertIn("product_outside_candidates", result["errors"])

    def test_invalid_field_and_value_rejected(self):
        for field, value in [("price", "$10"), ("style", "Modern"), ("material", "Solid wood")]:
            with self.subTest(field=field):
                self.assertFalse(validate_output(claim(field=field, value=value), self.evidence, {"A"})["accepted"])

    def test_free_form_prose_cannot_bypass_validation(self):
        raw = claim()
        raw["answer"] = "This costs $10"
        self.assertFalse(validate_output(raw, self.evidence, {"A"})["accepted"])
        raw = claim()
        raw["recommendations"][0]["reason"] = "Waterproof"
        self.assertFalse(validate_output(raw, self.evidence, {"A"})["accepted"])

    def test_duplicate_recommendation_rejected(self):
        raw = claim()
        raw["recommendations"] *= 2
        self.assertIn("duplicate_product_id", validate_output(raw, self.evidence, {"A"})["errors"])

    def test_valid_output_deterministic_and_rendered(self):
        first = validate_output(claim(), self.evidence, {"A"})
        self.assertEqual(first, validate_output(claim(), self.evidence, {"A"}))
        self.assertTrue(first["fully_grounded"])
        result = render_answer(first, self.evidence, [], [])
        self.assertEqual(result["recommendations"][0]["reason"], "ABO reports material: Ash.")

    def test_empty_output_is_not_a_grounded_answer(self):
        result = validate_output({"recommendations": []}, {}, {"A"})
        self.assertFalse(result["fully_grounded"])
        self.assertFalse(result["errors"])

    def test_equivalent_dimension_is_canonicalized(self):
        result = validate_output(claim(field="width", value="50.8 cm"), self.evidence, {"A"})
        self.assertTrue(result["fully_grounded"])
        self.assertEqual(result["accepted"][0]["evidence"][0]["value"], "20 in")
        self.assertFalse(validate_output(claim(field="width", value="51 cm"), self.evidence, {"A"})["accepted"])

    def test_filter_numeric_and_material_family(self):
        constraints = [{"field": "material", "operator": "eq", "value": "wood"},
                       {"field": "width", "operator": "lt", "value": "25 in"}]
        self.assertTrue(satisfies(self.evidence["A"], constraints))
        self.assertEqual(satisfies(self.evidence["A"], constraints), satisfies(self.evidence["A"], constraints))

    def test_no_material_inference_from_title(self):
        p = product()
        p["material"] = ""
        self.assertFalse(satisfies(evidence_for(p), [{"field": "material", "operator": "eq", "value": "wood"}]))

    def test_missing_dimensions_fail_closed(self):
        self.assertFalse(satisfies(self.evidence["A"], [{"field": "height", "operator": "lt", "value": "25 in"}]))

    def test_unsupported_filter_and_units_rejected(self):
        for field, value in [("price", "10"), ("width", "25"), ("width", "NaN in"), ("width", "20 feet")]:
            with self.assertRaises(ValueError):
                validate_constraints([{"field": field, "operator": "lt", "value": value}])


class ToolAndAgentTests(unittest.TestCase):
    def setUp(self):
        self.tools = SearchTools(catalog=[product()])

    def test_invalid_tool_schemas_recorded(self):
        for tool, args in [("delete_products", {}), ("search_text", {"query": "chair", "top_k": True}),
                           ("search_text", {"query": "chair", "top_k": 0}),
                           ("search_image", {"image": "/etc/passwd", "top_k": 10})]:
            result = self.tools.invoke(tool, args)
            self.assertFalse(result["success"])
            self.assertTrue(result["invalid_call"])

    def test_followup_ids_scoped_to_current_retrieval(self):
        self.assertFalse(self.tools.invoke("get_product", {"product_id": "A"})["success"])
        self.tools.candidates["A"] = evidence_for(product())
        self.assertTrue(self.tools.invoke("get_product", {"product_id": "A"})["success"])
        self.tools.reset()
        self.assertFalse(self.tools.invoke("get_product", {"product_id": "A"})["success"])

    def test_real_filter_and_comparison(self):
        self.tools.candidates["A"] = evidence_for(product())
        result = self.tools.invoke("filter_products", {"product_ids": ["A"], "constraints": [
            {"field": "width", "operator": "lt", "value": "25 in"}]})
        self.assertEqual(result["result"]["products"][0]["product_id"], "A")
        result = self.tools.invoke("compare_products", {"product_ids": ["A"]})
        self.assertEqual(result["result"]["narrowest_width"], "20 in")

    def test_routing_obvious_queries(self):
        self.assertEqual(obvious_route("black office chair", False), "search_text")
        self.assertEqual(obvious_route("wooden and narrower", True), "search_image")
        self.assertIsNone(obvious_route("cozy reading corner", False))

    def test_unsupported_request_detected(self):
        self.assertEqual(unavailable_in("chair under $100 in stock"), ["price", "availability"])

    def test_failed_tool_handled_without_recommendation(self):
        agent = ProductSearchAgent(self.tools, FakeProvider(plan()))
        with patch.object(self.tools.lexical, "search", side_effect=RuntimeError("private failure")):
            result = agent.run("Find a chair")
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["recommendations"])
        self.assertFalse(result["tool_trace"][0]["success"])
        self.assertNotIn("private failure", json.dumps(result))

    def test_bad_plan_cannot_make_up_filter(self):
        agent = ProductSearchAgent(self.tools, FakeProvider(plan(constraints=[{"field": "price", "operator": "lt", "value": "100"}])))
        result = agent.run("chair under $100")
        self.assertEqual(result["status"], "error")
        self.assertFalse(result["tool_trace"])

    def test_bad_llm_output_withheld(self):
        # Exercise the whole agent with deterministic fixture retrieval, without a model download.
        from multimodal.src.exact_index import Hit
        agent = ProductSearchAgent(self.tools, FakeProvider(plan(), claim("MADE_UP")))
        with patch.object(self.tools.lexical, "search", return_value=[Hit("A", 1.0, "lexical_bm25")]):
            result = agent.run("Find a chair")
        self.assertFalse(result["recommendations"])
        self.assertIn("unknown_product_id", result["grounding"]["errors"])

    def test_image_plan_does_not_require_unused_fallback_text(self):
        agent = ProductSearchAgent(self.tools, FakeProvider(plan(broad_query="", search_query="")))
        with patch.object(self.tools, "invoke", return_value={"success": True, "result": {"products": []}}) as invoke:
            result = agent.run("Find visually similar products", image_path="fixture.jpg")
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(invoke.call_args.args[0], "search_image")

    def test_ambiguous_query_uses_semantic_tool(self):
        agent = ProductSearchAgent(self.tools, FakeProvider(plan()))
        with patch.object(self.tools, "invoke", return_value={"success": True, "result": {"products": []}}) as invoke:
            agent.run("something for a cozy reading corner")
        self.assertEqual(invoke.call_args.args[0], "search_hybrid")

    def test_successful_agent_invokes_actual_tools(self):
        from multimodal.src.exact_index import Hit
        agent = ProductSearchAgent(self.tools, FakeProvider(plan(compare=True), claim()))
        with patch.object(self.tools.lexical, "search", return_value=[Hit("A", 1.0, "lexical_bm25")]):
            result = agent.run("Compare chairs")
        self.assertEqual([s["tool"] for s in result["tool_trace"]], ["search_text", "get_product", "compare_products"])
        self.assertEqual(result["status"], "answered")


class CacheTests(unittest.TestCase):
    def test_exact_request_replay_and_no_credentials_in_cache(self):
        class Response:
            status_code = 200
            def json(self):
                return {"id": "fixture", "status": "completed", "model": "test-model", "usage": {},
                        "output": [{"content": [{"type": "output_text", "text": '{"recommendations": []}'}]}]}
        with tempfile.TemporaryDirectory() as folder, patch.dict("os.environ", {"OPENAI_API_KEY": "secret-test-token"}):
            kwargs = dict(system="test", payload={"query": "test"}, schema={}, prompt_version="test_v1")
            provider = OpenAIProvider(model="test-model", cache_root=folder)
            with patch("multimodal.src.llm_provider.requests.post", return_value=Response()) as post:
                first = provider.generate_structured(**kwargs)
                second = provider.generate_structured(**kwargs)
                self.assertEqual(post.call_count, 1)
            self.assertEqual(first, second)
            self.assertTrue(provider.calls[-1]["cache_hit"])
            self.assertEqual(provider.calls[-1]["api_ms"], 0)
            self.assertNotIn("secret-test-token", next(Path(folder).glob("*.json")).read_text())
            offline = OpenAIProvider(model="test-model", cache_root=folder, cache_only=True)
            self.assertEqual(offline.generate_structured(**kwargs), first)
            with self.assertRaises(ProviderError):
                offline.generate_structured(**(kwargs | {"payload": {"query": "changed"}}))


if __name__ == "__main__":
    unittest.main()
