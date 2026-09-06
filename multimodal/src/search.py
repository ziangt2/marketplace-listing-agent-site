"""Minimal working search interface: python -m multimodal.src.search --text 'wooden chair'."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

from .abo_dataset import prepare_catalog
from .build_embeddings import catalog_embeddings
from .config import load_config
from .encoder_worker import EncoderWorker
from .exact_index import FaissFlatIndex
from .hybrid_retrieval import reciprocal_rank_fusion
from .lexical_retrieval import LexicalIndex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("dev", "mvp", "standard"), default="mvp")
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--text")
    query.add_argument("--image", type=Path)
    parser.add_argument("--mode", choices=("vector", "lexical", "hybrid"), default="vector")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if args.k < 1 or args.k > 100:
        parser.error("k must be between 1 and 100")
    if args.image and args.mode != "vector":
        parser.error("Image search uses vector mode")
    config = load_config()
    catalog, _ = prepare_catalog(args.profile, config)
    by_id = {p["product_id"]: p for p in catalog}
    lexical = LexicalIndex(catalog, config["retrieval"]["bm25_k1"], config["retrieval"]["bm25_b"])
    if args.mode != "lexical":
        encoder = EncoderWorker(config["encoder"])
        table, _ = catalog_embeddings(catalog, encoder)
        index = FaissFlatIndex(table)
    started = perf_counter()
    if args.mode == "lexical":
        hits = lexical.search(args.text, args.k)
    else:
        vector = encoder.encode_image(args.image) if args.image else encoder.encode_text([args.text])[0]
        if args.mode == "vector":
            hits = index.search(vector, args.k)
        else:
            depth = max(args.k, config["retrieval"]["depth"])
            hits = reciprocal_rank_fusion({"lexical_bm25": lexical.search(args.text, depth),
                                           "faiss_flat": index.search(vector, depth)}, args.k, config["retrieval"]["rrf_k"])
    elapsed = (perf_counter() - started) * 1000
    print(json.dumps({"mode": args.mode, "query_latency_ms": elapsed,
                      "latency_scope": "query encoding and retrieval; excludes model/catalog loading",
                      "products": [{**asdict(hit), "rank": rank,
                                    "metadata": {key: by_id[hit.product_id][key] for key in ("title", "product_type", "material", "color", "style", "brand", "dimensions", "index_image")}}
                                   for rank, hit in enumerate(hits, 1)]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
