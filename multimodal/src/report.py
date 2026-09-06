"""Generate/check documentation numbers directly from completed result artifacts."""
import argparse
import csv
import json
from pathlib import Path

from .config import ROOT
from .io_utils import atomic_write

START = "<!-- multimodal-results:start -->"
END = "<!-- multimodal-results:end -->"


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def render(prefix, resume=False):
    results = ROOT / "results/mvp"
    dataset = json.loads((results / "dataset_summary.json").read_text())
    config = json.loads((results / "benchmark_config.json").read_text())
    if config["status"] != "complete":
        raise ValueError("Cannot document an incomplete benchmark")
    image = next(r for r in read_rows(results / "image_retrieval.csv") if r["system"] == "faiss_flat")
    text = {r["system"]: r for r in read_rows(results / "text_retrieval.csv")}
    latency = json.loads((results / "latency.json").read_text())["measurements"]
    timing = {(r["task"], r["system"]): r for r in latency}
    complement = read_rows(results / "source_complementarity.csv")
    union_recall = sum(float(r["union_candidate_recall"]) for r in complement) / len(complement)
    model = config["encoder"]
    largest_category, largest_count = max(dataset["category_counts"].items(), key=lambda pair: pair[1])
    path = prefix + "results/mvp/"
    module = prefix + "README.md"
    lines = [START, "## Multimodal Product Retrieval", "",
        f"A separate measured MVP over **{dataset['products']:,} public Amazon Berkeley Objects (ABO) products**, "
        f"using pretrained `{model['model_name']}` with **{model['embedding_dimension']}-dimensional**, L2-normalized image/text embeddings. "
        f"No model was trained or fine-tuned. Inference used `{model['device']}`; model revision and preprocessing are recorded in "
        f"[benchmark_config.json]({path}benchmark_config.json).", "",
        f"The catalog retains {dataset['unique_images']:,} unique small images. Image evaluation uses **{dataset['image_queries']} distinct, unambiguous held-out catalog views** "
        f"against the full product index. {dataset['ambiguous_shared_view_queries_excluded']} alternate-view queries shared across multiple products were excluded, "
        "in addition to missing or unusable views. The query image cannot match any indexed image by image ID, bytes, or decoded pixels. "
        f"[Dataset and exclusions]({path}dataset_summary.json).", "",
        "| Image → product system | Queries | Recall@1 | Recall@5 | Recall@10 | MRR (full catalog) |",
        "|---|---:|---:|---:|---:|---:|",
        f"| SigLIP2 + FAISS IndexFlatIP | {image['queries']} | {float(image['recall@1']):.4f} | {float(image['recall@5']):.4f} | {float(image['recall@10']):.4f} | {float(image['mrr']):.4f} |", "",
        f"Source: [image_retrieval.csv]({path}image_retrieval.csv). NumPy exact cosine and FAISS have identical reported image metrics. "
        "IndexFlatIP is exact search, not ANN.", "",
        f"Text evaluation uses **{dataset['text_queries']} deterministic structured-attribute queries**, with 2–50 relevant products per query. "
        "Binary relevance means matching the query's product type and all supplied attributes. "
        "Queries contain no product IDs, model numbers, or copied complete titles. Recall measures the fraction of relevant products retrieved, not just any-hit success.", "",
        "| Text → product system | Recall@10 | NDCG@10 | MRR@50 |",
        "|---|---:|---:|---:|"]
    for name, label in (("lexical_bm25", "BM25 metadata"), ("faiss_flat", "SigLIP2 text → image vectors"), ("hybrid_rrf", "RRF hybrid")):
        row = text[name]
        lines.append(f"| {label} | {float(row['recall@10']):.4f} | {float(row['ndcg@10']):.4f} | {float(row['mrr']):.4f} |")
    lines += ["", f"Source: [text_retrieval.csv]({path}text_retrieval.csv). RRF fuses BM25 Top-{config['config']['retrieval']['depth']} "
              f"and FAISS Top-{config['config']['retrieval']['depth']} with rank constant {config['config']['retrieval']['rrf_k']}. "
              f"Their candidate union recall is {union_recall:.4f}. "
              f"[Per-query source complementarity]({path}source_complementarity.csv).", "",
              "**Observed result:** RRF improves over the vector-only baseline but underperforms BM25 on these exact-attribute labels. "
              "This benchmark favors lexical matching; it does not establish general semantic-search improvement.", "",
              "| Warm local latency scope | p50 (ms) | p95 (ms) | Timed samples |",
              "|---|---:|---:|---:|"]
    for key, label in ((('image', 'faiss_flat'), "FAISS image-vector retrieval only, K=10"),
                       (('image', 'encoder_plus_faiss_flat'), "Image decode + uncached encoder + IPC + FAISS"),
                       (('text', 'encoder_plus_faiss_flat'), "Text preprocessing + uncached encoder + IPC + FAISS"),
                       (('text', 'hybrid_rrf'), "BM25 + FAISS + RRF only, K=10")):
        row = timing[key]
        lines.append(f"| {label} | {row['p50_ms']:.4f} | {row['p95_ms']:.4f} | {row['samples']} |")
    lines += ["", f"Source: [latency.json]({path}latency.json), with raw samples in [latency_samples.csv]({path}latency_samples.csv). "
              "Retrieval-only timings use cached query vectors. Encoding-inclusive timings use the first 20 query IDs per modality, a warm model, "
              "single-query inference and local worker communication. Model loading, downloads, network serving, and concurrent load are excluded. "
              "These are local measurements, not production SLA or scale claims.", "",
              f"The serialized FAISS index is {config['indexes']['faiss_flat']['serialized_bytes']:,} bytes and its measured construction took "
              f"{config['indexes']['faiss_flat']['build_seconds']:.6f} seconds, excluding embedding generation. "
              f"[Index provenance]({path}benchmark_config.json).", "",
              "Defaults were fixed before scoring. This is an exploratory development benchmark with held-out image views; products remain in the index. "
              "There is no model training split, no hyperparameter search, and no claim of a frozen final test. "
              f"The largest catalog type is `{largest_category}` ({largest_count}/{dataset['products']} products). "
              "Category imbalance, related variants, near-duplicate imagery, metadata-derived labels, and possible pretrained-data overlap limit generalization. "
              "These ABO results are independent of the historical synthetic behavioral RecSys metrics.", ""]
    if resume:
        lines += ["### Supported resume wording", "",
            f"- Extended an e-commerce search/recommendation platform with pretrained SigLIP2 image/text embeddings and FAISS exact vector retrieval over {dataset['products']:,} public ABO listings; achieved {100 * float(image['recall@10']):.2f}% image-to-product Recall@10 on {dataset['image_queries']} distinct held-out views.",
            f"- Benchmarked BM25, vector retrieval, and Reciprocal Rank Fusion on {dataset['text_queries']} metadata-derived text queries; measured RRF Recall@10 of {float(text['hybrid_rrf']['recall@10']):.4f} versus {float(text['faiss_flat']['recall@10']):.4f} for vectors and {float(text['lexical_bm25']['recall@10']):.4f} for BM25.", "",
            "### Multimodal claims I should NOT make", "",
            "- Proprietary Amazon data, production-scale traffic, revenue impact, or online A/B improvement.",
            "- Training/fine-tuning SigLIP2, a learned reranker, agent, VLM, grounded RAG, Azure deployment, or distributed serving.",
            "- ANN or HNSW results: this MVP measures exact FAISS IndexFlatIP only.",
            "- Hybrid beats the strongest baseline, human-judged relevance, or independent unseen-product generalization.",
            "- Retrieval-only latency includes neural encoding, model startup, or network serving.", ""]
    lines += [f"See the [module documentation]({module}) for commands, ground-truth construction, and limitations.", END]
    return "\n".join(lines)


def update_document(path, block, check):
    text = path.read_text(encoding="utf-8")
    if START in text:
        before, remainder = text.split(START, 1)
        _, after = remainder.split(END, 1)
        expected = before + block + after
    else:
        expected = text.rstrip() + "\n\n" + block + "\n"
    if check and expected != text:
        raise ValueError(f"Multimodal documentation differs from artifacts: {path}")
    if not check:
        atomic_write(path, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    update_document(ROOT / "README.md", render(""), args.check)
    update_document(ROOT.parent / "README.md", render("multimodal/"), args.check)
    update_document(ROOT.parent / "RESUME_EVIDENCE.md", render("multimodal/", resume=True), args.check)
    print("Multimodal documentation consistency: OK")


if __name__ == "__main__":
    main()
