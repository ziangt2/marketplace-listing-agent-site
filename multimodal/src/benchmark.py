"""Actual ABO measurements; no training, no performance-based configuration selection."""
import argparse
import csv
import io
import json
import os
import platform
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from .abo_dataset import prepare_catalog
from .build_embeddings import catalog_embeddings, encode_cached
from .config import DEFAULT_CONFIG, ROOT, load_config, manifest_path, queries_path
from .encoder_worker import EncoderWorker
from .exact_index import ExactIndex, FaissFlatIndex
from .hybrid_retrieval import reciprocal_rank_fusion, source_complementarity
from .io_utils import atomic_write, digest, file_sha256, write_json, write_jsonl
from .latency import measure
from .lexical_retrieval import LexicalIndex
from .metrics import aggregate, retrieval_metrics
from .queries import build_image_queries, build_text_queries


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path}")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path, output.getvalue())


def evaluate_queries(queries, vectors, systems, depth, task):
    rows, runs = [], []
    for i, query in enumerate(queries):
        for name, retrieve in systems.items():
            hits = retrieve(query, vectors[i], depth)
            ranked = [hit.product_id for hit in hits]
            metrics = retrieval_metrics(ranked, query["relevant_ids"])
            rows.append({"task": task, "system": name, "query_id": query["query_id"],
                         "product_type": query["product_type"], "relevant_count": len(query["relevant_ids"]),
                         "ranking_depth": depth, **metrics})
            runs.append({"query_id": query["query_id"], "system": name,
                         "top10": ranked[:10], "first_relevant_rank": metrics["first_relevant_rank"]})
    return rows, runs


def aggregate_systems(rows, task, depth):
    groups = defaultdict(list)
    for row in rows:
        groups[row["system"]].append(row)
    return [{"task": task, "system": name, "mrr_cutoff": depth, **aggregate(group)} for name, group in groups.items()]


def run(profile, config_path, output=None):
    config = load_config(config_path)
    destination = Path(output) if output else ROOT / "results" / profile
    if destination.exists() and any(destination.iterdir()):
        if output:
            raise FileExistsError(f"Preserving existing results at {destination}; choose a fresh --output directory")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%f")
        destination = ROOT / "results" / f"local-{profile}-{stamp}"
        print(f"Preserving published results; rerun outputs: {destination}", flush=True)
    started = time.perf_counter()
    catalog, dataset_summary = prepare_catalog(profile, config)
    text_queries, query_summary = build_text_queries(catalog, config["evaluation"])
    image_queries = build_image_queries(catalog)
    if not image_queries:
        raise ValueError("No valid held-out image queries")
    query_manifest = queries_path(profile)
    queries = image_queries + text_queries
    # Query definitions are immutable for a given profile once published.
    if query_manifest.exists():
        from .io_utils import read_jsonl
        if read_jsonl(query_manifest) != queries:
            raise ValueError("Frozen query definitions changed; use a separate experiment profile")
    else:
        write_jsonl(query_manifest, queries)
    print(f"Benchmark population: {len(catalog)} products; {len(image_queries)} image, {len(text_queries)} text queries", flush=True)
    encoder = EncoderWorker(config["encoder"])
    indexed, catalog_cache = catalog_embeddings(catalog, encoder)
    image_vectors, image_cache = encode_cached(encoder, "image", [q["query_id"] for q in image_queries],
        [ROOT / q["image"]["path"] for q in image_queries], [q["image"]["sha256"] for q in image_queries])
    text_vectors, text_cache = encode_cached(encoder, "text", [q["query_id"] for q in text_queries],
        [q["text"] for q in text_queries], [digest(q["text"]) for q in text_queries])
    index_started = time.perf_counter()
    exact = ExactIndex(indexed)
    exact_build = time.perf_counter() - index_started
    index_started = time.perf_counter()
    flat = FaissFlatIndex(indexed)
    flat_build = time.perf_counter() - index_started
    index_folder = ROOT / "data/processed" / digest([dataset_summary["catalog_sha256"], encoder.metadata])
    index_folder.mkdir(parents=True, exist_ok=True)
    index_path = index_folder / "catalog.faiss"
    flat.save(index_path)
    write_json(index_folder / "catalog.json", {"product_ids": indexed.ids, "encoder": encoder.metadata,
                                               "catalog_sha256": dataset_summary["catalog_sha256"]})
    lexical = LexicalIndex(catalog, config["retrieval"]["bm25_k1"], config["retrieval"]["bm25_b"])
    depth = config["retrieval"]["depth"]
    def hybrid(query, vector, k):
        return reciprocal_rank_fusion({"lexical_bm25": lexical.search(query["text"], depth),
                                       "faiss_flat": flat.search(vector, depth)}, k, config["retrieval"]["rrf_k"])
    image_systems = {"numpy_exact": lambda q, v, k: exact.search(v, k),
                     "faiss_flat": lambda q, v, k: flat.search(v, k)}
    text_systems = {"lexical_bm25": lambda q, v, k: lexical.search(q["text"], k), **image_systems,
                    "hybrid_rrf": hybrid}
    print("Evaluating image retrieval, then text/lexical/RRF on identical populations", flush=True)
    image_rows, image_runs = evaluate_queries(image_queries, image_vectors.vectors, image_systems, len(catalog), "image")
    text_rows, text_runs = evaluate_queries(text_queries, text_vectors.vectors, text_systems, depth, "text")
    image_metrics = aggregate_systems(image_rows, "image", len(catalog))
    text_metrics = aggregate_systems(text_rows, "text", depth)
    complements = [{"query_id": q["query_id"], **source_complementarity(lexical.search(q["text"], depth), flat.search(v, depth), q["relevant_ids"])}
                   for q, v in zip(text_queries, text_vectors.vectors)]
    groups = defaultdict(list)
    for row in image_rows + text_rows:
        groups[(row["task"], row["system"], row["product_type"])].append(row)
    segments = [{"task": task, "system": name, "product_type": category, **aggregate(rows)}
                for (task, name, category), rows in sorted(groups.items()) if len(rows) >= config["evaluation"]["min_segment_queries"]]

    print("Measuring warm retrieval and separate uncached query-encoding latency", flush=True)
    settings = config["evaluation"]
    timings, latency_samples = [], []
    for task, query_set, vectors, systems in (("image", image_queries, image_vectors.vectors, image_systems),
                                             ("text", text_queries, text_vectors.vectors, text_systems)):
        inputs = list(zip(query_set, vectors))
        for name, retrieve in systems.items():
            timing, samples = measure(lambda pair: retrieve(pair[0], pair[1], 10), inputs,
                                      settings["latency_repeats"], settings["latency_warmups"])
            timings.append({"task": task, "system": name, "k": 10, "scope": "warm retrieval only; query embeddings already computed", **timing})
            latency_samples.extend({"task": task, "system": name, "sample": i, "ms": ms} for i, ms in enumerate(samples))
        sample_queries = query_set[:settings["encoder_latency_samples"]]
        def end_to_end(query):
            v = encoder.encode_image(ROOT / query["image"]["path"]) if task == "image" else encoder.encode_text([query["text"]])[0]
            return flat.search(v, 10)
        timing, samples = measure(end_to_end, sample_queries, 1, 2)
        timings.append({"task": task, "system": "encoder_plus_faiss_flat", "k": 10,
                        "scope": "warm local encoder worker; image decode/text preprocessing + uncached single-query inference + CPU transfer + pipe IPC + retrieval; no model load/network",
                        "query_ids": [q["query_id"] for q in sample_queries], **timing})
        latency_samples.extend({"task": task, "system": "encoder_plus_faiss_flat", "sample": i, "ms": ms} for i, ms in enumerate(samples))

    all_rows = image_rows + text_rows
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    recorded = {
        "status": "complete", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile": profile, "config": config, "config_sha256": file_sha256(config_path),
        "catalog_sha256": dataset_summary["catalog_sha256"], "queries_sha256": file_sha256(query_manifest),
        "encoder": encoder.metadata, "cache": {"catalog": catalog_cache, "image_queries": image_cache, "text_queries": text_cache},
        "protocol": {"training": "none", "configuration_selection": "fixed defaults before measurements; no performance tuning",
                     "population": "exploratory development benchmark; not a frozen final test",
                     "image_holdout": "different catalog view; byte and decoded-pixel exclusion against every indexed image; also exclude query pixels shared by multiple catalog products; product identities remain in catalog",
                     "text_ground_truth": query_summary, "text_mrr_cutoff": depth, "image_mrr_cutoff": len(catalog),
                     "vector_representation": "one normalized pretrained image embedding per product; text queries search that image index",
                     "latency": "local warm serial requests; retrieval-only and encoding-inclusive reported separately; no network or production load",
                     "ties": "NumPy score then product_id; FAISS returned scores then product_id (boundary ties use FAISS membership)"},
        "indexes": {"numpy_exact": {"build_seconds": exact_build, "vector_bytes": indexed.vectors.nbytes},
                    "faiss_flat": {"type": "IndexFlatIP", "approximate": False, "build_seconds": flat_build,
                                   "serialized_bytes": index_path.stat().st_size, "sha256": file_sha256(index_path)}},
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor(),
                        "faiss": faiss.__version__, "numpy": np.__version__, "faiss_threads": faiss.omp_get_max_threads(),
                        "thread_environment": {key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}},
        "base_git_commit": head,
        "implementation_sha256": {str(p.relative_to(ROOT)): file_sha256(p) for p in sorted((ROOT / "src").glob("*.py"))},
        "total_run_seconds": time.perf_counter() - started,
    }
    # Publish only after the entire measured run succeeds. The config is the completion marker.
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "dataset_summary.json", {**dataset_summary, "image_queries": len(image_queries),
               "image_views_available": dataset_summary["image_queries"],
               "ambiguous_shared_view_queries_excluded": dataset_summary["image_queries"] - len(image_queries),
               "text_queries": len(text_queries), "text_query_construction": query_summary})
    write_csv(destination / "image_retrieval.csv", image_metrics)
    write_csv(destination / "text_retrieval.csv", text_metrics)
    write_csv(destination / "hybrid_retrieval.csv", [r for r in text_metrics if r["system"] in ("lexical_bm25", "faiss_flat", "hybrid_rrf")])
    write_csv(destination / "source_complementarity.csv", complements)
    write_csv(destination / "query_segment_metrics.csv", segments)
    write_csv(destination / "per_query_metrics.csv", all_rows)
    write_jsonl(destination / "retrieval_runs.jsonl", image_runs + text_runs)
    write_json(destination / "latency.json", {"measurements": timings})
    write_csv(destination / "latency_samples.csv", latency_samples)
    write_json(destination / "benchmark_config.json", recorded)
    encoder.close()
    print(json.dumps({"results": str(destination), "image": image_metrics, "text": text_metrics}, indent=2), flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("dev", "mvp", "standard"), default="mvp")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run(args.profile, args.config, args.output)


if __name__ == "__main__":
    main()
