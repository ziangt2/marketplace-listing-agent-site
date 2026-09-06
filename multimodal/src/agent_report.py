"""Reconstruct agent metrics and render documentation from saved measured artifacts."""
import argparse
import csv
import io
import json
from pathlib import Path

from .agent_benchmark import DEFAULT_OUTPUT, QUERIES, aggregate, score_query
from .config import ROOT, manifest_path
from .grounding import validate_output
from .io_utils import file_sha256, read_jsonl
from .product_evidence import evidence_for

START, END = "<!-- agent-results:start -->", "<!-- agent-results:end -->"
DOCS = [ROOT.parent / "README.md", ROOT.parent / "RESUME_EVIDENCE.md", ROOT / "README.md"]


def verified_results():
    load = lambda name: json.loads((DEFAULT_OUTPUT / name).read_text())
    queries, runs = read_jsonl(DEFAULT_OUTPUT / "agent_queries.jsonl"), read_jsonl(DEFAULT_OUTPUT / "agent_runs.jsonl")
    config = load("agent_benchmark_config.json")
    if queries != read_jsonl(QUERIES) or len(queries) != 36 or len(runs) != 36:
        raise ValueError("Frozen agent fixture or run count mismatch")
    for path, expected in config["source_sha256"].items():
        if file_sha256(ROOT / path) != expected:
            raise ValueError("Evaluated source differs: " + path)
    products = {p["product_id"]: p for p in read_jsonl(manifest_path("mvp"))}
    rows = []
    for query, run in zip(queries, runs):
        if query["query_id"] != run["query_id"] or query["query"] != run["query"]:
            raise ValueError("Query/run identity mismatch")
        evidence = {p["product_id"]: p for p in run["evidence"]}
        for pid, item in evidence.items():
            source = evidence_for(products[pid])
            if item["fields"] != source["fields"] or item["dimension_sources"] != source["dimension_sources"]:
                raise ValueError("Evidence differs from original ABO metadata")
        if validate_output(run["raw_output"], evidence, set(products)) != run["grounding"]:
            raise ValueError("Raw grounding metrics do not reconstruct")
        rows.append(score_query(query, run, products))
    metrics, latency = aggregate(rows, runs)
    latency["startup_ms"] = config["startup_ms"]
    if metrics != load("rag_grounding_metrics.json") or latency != load("agent_latency.json"):
        raise ValueError("Saved metrics/latency do not reconstruct from query runs")
    buffer = io.StringIO(newline="")
    saved_csv = DEFAULT_OUTPUT / "agent_evaluation.csv"
    columns = next(csv.reader(io.StringIO(saved_csv.read_text())))
    if set(columns) != set(rows[0]):
        raise ValueError("Evaluation CSV columns differ")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    if buffer.getvalue().replace("\r\n", "\n") != (DEFAULT_OUTPUT / "agent_evaluation.csv").read_text():
        raise ValueError("Evaluation CSV does not reconstruct")
    return metrics, latency, config


def block(doc, metrics, latency, config):
    base = "results/agent_v2" if doc.parent == ROOT else "multimodal/results/agent_v2"
    initial = "results/agent_v1" if doc.parent == ROOT else "multimodal/results/agent_v1"
    fmt = lambda r: f"{r['numerator']}/{r['denominator']} ({r['rate']:.2%})" if r["rate"] is not None else "not applicable"
    raw, delivered = metrics["raw"], metrics["delivered"]
    statuses = metrics["status_counts"]
    lines = [START, "## Agentic Multimodal Product Search", "",
        f"One bounded tool-using agent and grounded RAG layer now extend the same 1,000-product ABO retrieval system. "
        f"A completed **{metrics['query_count']}-query development evaluation** uses `{config['model']}`, temperature 0, "
        f"with six cases in each of six categories. The LLM plans constraints and selects cited evidence; "
        "product-specific prose is rendered from validated fields. No training or fine-tuning.", "",
        "Explicit lexical/category requests prefer BM25 because the historical structured-text benchmark favors it. "
        "Attached images use SigLIP2 + FAISS; mixed requests execute metadata filters. Ambiguous descriptions "
        "use RRF by default or the planner's vector route. This policy does not establish semantic relevance superiority.", "",
        f"Source: [frozen queries]({base}/agent_queries.jsonl), [per-query evaluation]({base}/agent_evaluation.csv), "
        f"[full raw drafts, evidence and executed traces]({base}/agent_runs.jsonl), [configuration/source hashes]({base}/agent_benchmark_config.json).", "",
        "| Deterministic measure | Measured result |", "|---|---:|",
        f"| Expected first tool | {fmt(metrics['routing_success'])} |",
        f"| Expected conditional tool sequence | {fmt(metrics['expected_tool_sequence_success'])} |",
        f"| Successful tool execution | {fmt(metrics['successful_tool_execution'])} |",
        f"| Invalid tool calls | {fmt(metrics['invalid_tool_calls'])} |",
        f"| Mean tool calls per query | {metrics['average_tool_calls']:.2f} |",
        f"| Raw recommendation ID validity / candidate coverage | {fmt(raw['candidate_coverage'])} |",
        f"| Raw evidence field validity | {fmt(raw['evidence_field_validity'])} |",
        f"| Raw evidence value validity | {fmt(raw['evidence_value_validity'])} |",
        f"| Raw unsupported structured attributes | {fmt(raw['unsupported_attribute_claims'])} |",
        f"| Raw fully grounded, nonempty responses / all queries | {fmt(raw['fully_grounded_nonempty_responses'])} |",
        f"| Delivered grounded, nonempty responses / all queries | {fmt(delivered['fully_grounded_nonempty_responses'])} |",
        f"| Delivered grounding among answered queries | {fmt(delivered['grounded_among_answered'])} |",
        f"| Constraint satisfaction among emitted constrained recommendations | {fmt(metrics['constraint_satisfaction'])} |",
        f"| Constraint queries answered with satisfying recommendations | {fmt(metrics['constraint_queries_answered_correctly'])} |",
        f"| Unsupported requests explicitly acknowledged | {fmt(metrics['unsupported_requests_acknowledged'])} |", "",
        f"Source: [rag_grounding_metrics.json]({base}/rag_grounding_metrics.json). "
        f"Outcomes: **{statuses.get('answered', 0)} answered, {statuses.get('abstained', 0)} abstained, {statuses.get('error', 0)} errors**. "
        "Empty responses never earn grounding or constraint-coverage credit. These checks establish metadata fidelity "
        "on structured claims; answer relevance, real-world catalog accuracy and apartment suitability are not measured.", "",
        "| Warm latency scope, 36 sequential queries | p50 (ms) | p95 (ms) |", "|---|---:|---:|",
        *[f"| {label} | {latency[key]['p50']:.2f} | {latency[key]['p95']:.2f} |" for key, label in [
            ("retrieval_ms", "Local retrieval, including query encoding/IPC when used"),
            ("llm_api_ms", "Hosted LLM calls per query, excluding cached requests"),
            ("llm_wall_ms", "LLM boundary including cache lookup"), ("total_ms", "Total agent request")]], "",
        f"Source: [agent_latency.json]({base}/agent_latency.json). {metrics['live_api_calls']} live API calls and "
        f"{metrics['cache_hits']} exact-request cache hits; shared image-only planning requests may hit the cache. "
        f"Startup/model/index preparation ({latency['startup_ms']:.2f} ms) is excluded. Local timings and API/network "
        "timings are separate; the historical 9.47 ms image-only p95 is unchanged and is not total agent latency.", "",
        f"The same authored fixtures were used to diagnose and repair an initial run, retained in "
        f"[agent_v1]({initial}/rag_grounding_metrics.json), then evaluated as v2. This is development evaluation, "
        "not an independent held-out agent test. Image inputs reuse held-out views of indexed products. "
        "No online business impact, production-scale serving, model training, Azure, multi-agent autonomy, "
        "RRF superiority over BM25, or general elimination of hallucinations is claimed."]
    if doc.name == "RESUME_EVIDENCE.md":
        lines += ["", "### Supported agent resume wording", "",
            f"- Extended pretrained multimodal product retrieval with a bounded tool-using agent, structured LLM evidence "
            f"selection and deterministic grounding checks; executed {metrics['query_count']} development queries with "
            f"{metrics['routing_success']['rate']:.0%} expected-tool routing and "
            f"{delivered['fully_grounded_nonempty_responses']['numerator']}/{metrics['query_count']} nonempty grounded responses.",
            f"- Validated {raw['counts']['evidence_items']} structured evidence claims against retrieved ABO metadata; "
            f"measured {metrics['constraint_satisfaction']['numerator']}/{metrics['constraint_satisfaction']['denominator']} "
            "constraint-satisfying emitted recommendations, with abstentions and coverage reported separately."]
    return "\n".join(lines + [END])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    metrics, latency, config = verified_results()
    for doc in DOCS:
        text = doc.read_text()
        generated = block(doc, metrics, latency, config)
        if START in text:
            current = text[text.index(START):text.index(END) + len(END)]
            if args.check and current != generated:
                raise ValueError("Agent documentation is stale: " + str(doc))
            text = text.replace(current, generated)
        elif args.check:
            raise ValueError("Agent documentation block missing: " + str(doc))
        else:
            text = text.rstrip() + "\n\n" + generated + "\n"
        if not args.check:
            doc.write_text(text)
    print("Agent artifacts reconstruct and documentation matches measured results.")


if __name__ == "__main__":
    main()
