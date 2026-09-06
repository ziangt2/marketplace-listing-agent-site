"""Frozen 36-query development evaluation; raw drafts, full traces, honest denominators."""
import argparse
import csv
import io
import json
import platform
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import ROOT, manifest_path
from .grounding import validate_output
from .io_utils import atomic_write, file_sha256, read_jsonl, write_json, write_jsonl
from .llm_provider import OpenAIProvider
from .product_agent import PLAN_VERSION, PROMPT_VERSION, ProductSearchAgent

QUERIES = ROOT / "data/manifests/agent_queries_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "results/agent_v1"


def rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def oracle_satisfies(product, constraints):
    """Independent evaluation against original catalog fields, not planner or filter outputs."""
    factors = {"inches": 1, "in": 1, "inch": 1, "centimeters": 1 / 2.54, "cm": 1 / 2.54,
               "millimeters": 1 / 25.4, "mm": 1 / 25.4}
    for c in constraints:
        field, target, op = c["field"], c["value"], c["operator"]
        if field in ("width", "height", "depth"):
            d = product.get("dimensions", {}).get("length" if field == "depth" else field, {})
            if "value" not in d or d.get("unit") not in factors:
                return False
            actual = d["value"] * factors[d["unit"]]
            match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(in|cm|mm)", target)
            target = float(match[1]) * factors[match[2]]
            if not {"lt": actual < target, "lte": actual <= target, "gt": actual > target,
                    "gte": actual >= target, "eq": abs(actual - target) < 1e-6}[op]:
                return False
        else:
            actual = " ".join(re.findall(r"[a-z0-9]+", product.get(field, "").lower()))
            target = " ".join(re.findall(r"[a-z0-9]+", target.lower()))
            if not actual:
                return False
            if field == "material" and target == "wood":
                if not set(actual.split()) & {"wood", "ash", "pine", "solidpine", "bamboo", "mdf", "hardwood"}:
                    return False
            elif not (actual == target if op == "eq" else target in actual):
                return False
    return True


def score_query(query, run, products):
    trace, recs = run["tool_trace"], run["recommendations"]
    evidence = {e["product_id"]: e for e in run["evidence"]}
    delivered = validate_output({"recommendations": [{"product_id": r["product_id"], "evidence": r["evidence"]}
                                                    for r in recs]}, evidence, set(products))
    selected = [r["product_id"] for r in recs]
    constraints = query["expected_constraints"]
    constraint_valid = sum(oracle_satisfies(products[i], constraints) for i in selected) if constraints else 0
    first_ok = bool(trace) and trace[0]["tool"] in query["expected_first_tools"]
    names = [t["tool"] for t in trace if t["success"]]
    multi_ok = first_ok and (not constraints or "filter_products" in names)
    if query["expect_comparison_when_answered"] and selected:
        multi_ok = multi_ok and "compare_products" in names
    unsupported = query["expected_unsupported"]
    limitation_text = " ".join(run["limitations"])
    return {"query_id": query["query_id"], "category": query["category"], "status": run["status"],
            "routing_success": first_ok, "expected_sequence_success": multi_ok,
            "tool_calls": len(trace), "successful_tools": sum(t["success"] for t in trace),
            "invalid_tools": sum(t["invalid_call"] for t in trace), "recommendations": len(recs),
            "raw_fully_grounded": run["grounding"]["fully_grounded"],
            "raw_validation_errors": len(run["grounding"]["errors"]),
            "delivered_fully_grounded": delivered["fully_grounded"],
            "constraint_query": bool(constraints), "constrained_recommendations": len(recs) if constraints else 0,
            "constraint_valid_recommendations": constraint_valid,
            "constraint_query_answered_correctly": bool(recs) and bool(constraints) and constraint_valid == len(recs),
            "unsupported_query": bool(unsupported),
            "unsupported_acknowledged": bool(unsupported) and all(u in limitation_text for u in unsupported),
            "api_calls": sum(not c["cache_hit"] for c in run["llm_calls"]),
            "cache_hits": sum(c["cache_hit"] for c in run["llm_calls"]), **run["latency"]}


def aggregate(rows, runs):
    n = len(rows)
    total = lambda field: sum(row[field] for row in rows)
    counts = Counter()
    for run in runs:
        counts.update(run["grounding"]["counts"])
    metrics = {"evaluation_scope": "36 authored development queries; no held-out agent quality claim or LLM judge",
        "query_count": n, "status_counts": dict(Counter(r["status"] for r in rows)),
        "categories": dict(Counter(r["category"] for r in rows)),
        "routing_success": rate(total("routing_success"), n),
        "expected_tool_sequence_success": rate(total("expected_sequence_success"), n),
        "successful_tool_execution": rate(total("successful_tools"), total("tool_calls")),
        "invalid_tool_calls": rate(total("invalid_tools"), total("tool_calls")),
        "average_tool_calls": total("tool_calls") / n,
        "raw": {"counts": dict(counts),
            "product_id_validity": rate(counts["catalog_valid"], counts["recommendations"]),
            "candidate_coverage": rate(counts["candidate_valid"], counts["recommendations"]),
            "evidence_field_validity": rate(counts["field_valid"], counts["evidence_items"]),
            "evidence_value_validity": rate(counts["value_valid"], counts["evidence_items"]),
            "unsupported_attribute_claims": rate(counts["unsupported_attributes"], counts["evidence_items"]),
            "fully_grounded_nonempty_responses": rate(total("raw_fully_grounded"), n),
            "responses_with_validation_errors": sum(r["raw_validation_errors"] > 0 for r in rows)},
        "delivered": {"fully_grounded_nonempty_responses": rate(total("delivered_fully_grounded"), n),
            "grounded_among_answered": rate(total("delivered_fully_grounded"), sum(r["status"] == "answered" for r in rows)),
            "recommendation_count": total("recommendations")},
        "constraint_satisfaction": rate(total("constraint_valid_recommendations"), total("constrained_recommendations")),
        "constraint_queries_answered_correctly": rate(total("constraint_query_answered_correctly"), total("constraint_query")),
        "unsupported_requests_acknowledged": rate(total("unsupported_acknowledged"), total("unsupported_query")),
        "live_api_calls": total("api_calls"), "cache_hits": total("cache_hits"),
        "limitations": ["Grounding checks structured citations, not semantic relevance or real-world metadata accuracy.",
            "All product-specific prose is rendered deterministically from validated fields, not unconstrained LLM prose.",
            "Empty recommendations count as abstentions, never fully grounded answers; constraints also report nonempty coverage.",
            "Agent fixtures are authored development cases, with reused held-out image views from the historical image benchmark.",
            "Temperature zero does not promise cross-call determinism; exact-request cached replay is separately verified."]}
    latency = {"unit": "ms", "samples": n, "startup_excluded": True,
               "method": "Sequential warm agent requests. Retrieval includes encoding IPC; LLM wall includes API or cache lookup. API latency excludes cache replay. Total includes planning, tools, validation, generation; local model/index startup is separately recorded."}
    for field in ("retrieval_ms", "all_tools_ms", "llm_wall_ms", "llm_api_ms", "total_ms"):
        values = [row[field] for row in rows]
        latency[field] = {"p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95))}
    metrics["by_category"] = {}
    for category in sorted({r["category"] for r in rows}):
        subset = [r for r in rows if r["category"] == category]
        metrics["by_category"][category] = {"queries": len(subset), "answered": sum(r["status"] == "answered" for r in subset),
            "routing_successes": sum(r["routing_success"] for r in subset),
            "fully_grounded_nonempty": sum(r["delivered_fully_grounded"] for r in subset)}
    return metrics, latency


def stable_result(run):
    """Only nondeterministic telemetry is omitted from replay identity."""
    return {k: run[k] for k in ("query", "plan", "raw_output", "grounding", "answer", "recommendations",
                                "comparison", "limitations", "status", "evidence", "error")} | {
        "tools": [{k: v for k, v in t.items() if k != "latency_ms"} for t in run["tool_trace"]]}


def run_benchmark(output, cache_only=False, replay_of=None):
    output = Path(output)
    if (output / "agent_runs.jsonl").exists():
        raise ValueError("Refusing to overwrite an existing evaluation; choose a new output directory")
    queries = read_jsonl(QUERIES)
    provider = OpenAIProvider(cache_only=cache_only)
    agent = ProductSearchAgent(provider=provider)
    started = time.perf_counter()
    agent.tools.warmup()
    startup_ms = (time.perf_counter() - started) * 1000
    sources = [QUERIES, manifest_path("mvp"), ROOT / "config/default.json", *sorted((ROOT / "src").glob("*.py"))]
    config = {"timestamp": datetime.now(timezone.utc).isoformat(), "provider": "openai", "model": provider.model,
        "temperature": 0, "prompt_versions": [PLAN_VERSION, PROMPT_VERSION], "cache_only": cache_only,
        "query_split": "authored development", "query_count": len(queries), "top_k": 50,
        "broad_lexical_retry_k": 100, "evidence_window": 8, "max_recommendations": 3, "tool_budget": 8,
        "startup_ms": startup_ms, "python": platform.python_version(), "platform": platform.platform(),
        "encoder": agent.tools.encoder.metadata,
        "source_sha256": {str(p.relative_to(ROOT)): file_sha256(p) for p in sources}}
    write_json(output / "agent_benchmark_config.json", config)
    write_jsonl(output / "agent_queries.jsonl", queries)
    rows, runs = [], []
    try:
        for query in queries:
            image_path = ROOT / query["image"]["path"] if "image" in query else None
            if image_path and file_sha256(image_path) != query["image"]["sha256"]:
                raise ValueError("Frozen evaluation image checksum mismatch")
            result = agent.run(query["query"], image_path)
            result["query_id"] = query["query_id"]
            runs.append(result)
            rows.append(score_query(query, result, agent.tools.products))
            write_jsonl(output / "agent_runs.jsonl", runs)
            print(f"{query['query_id']} {query['category']}: {result['status']}; {len(result['tool_trace'])} tools; {result['latency']['total_ms']:.0f} ms", flush=True)
    finally:
        agent.tools.close()
    metrics, latency = aggregate(rows, runs)
    latency["startup_ms"] = startup_ms
    write_json(output / "rag_grounding_metrics.json", metrics)
    write_json(output / "agent_latency.json", latency)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(output / "agent_evaluation.csv", buffer.getvalue().encode())
    if replay_of:
        previous = read_jsonl(Path(replay_of) / "agent_runs.jsonl")
        same = len(previous) == len(runs) and all(stable_result(a) == stable_result(b) for a, b in zip(previous, runs))
        write_json(output / "replay_validation.json", {"matches": same, "compared_queries": len(runs),
            "source_runs_sha256": file_sha256(Path(replay_of) / "agent_runs.jsonl"),
            "live_api_calls": metrics["live_api_calls"], "ignored_fields": ["latency telemetry", "cache/API telemetry"]})
        if not same or metrics["live_api_calls"]:
            raise ValueError("Cache replay did not reproduce the saved evaluation")
    print(json.dumps({"metrics": metrics, "latency": latency}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--replay-of")
    args = parser.parse_args()
    run_benchmark(args.output, args.cache_only, args.replay_of)


if __name__ == "__main__":
    main()
