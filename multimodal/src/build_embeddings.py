"""Content-addressed caches preserve product/vector identity across runs."""
import argparse
import io
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .abo_dataset import validate_catalog
from .config import DEFAULT_CONFIG, ROOT, load_config, manifest_path
from .embedding_model import SiglipEncoder
from .io_utils import atomic_write, digest, read_jsonl, write_json


@dataclass
class EmbeddingTable:
    ids: list
    vectors: np.ndarray

    def validate(self, expected_ids=None):
        if len(self.ids) != len(set(self.ids)):
            raise ValueError("Duplicate embedding identities")
        if self.vectors.ndim != 2 or len(self.ids) != len(self.vectors):
            raise ValueError("Embedding rows and identities are misaligned")
        if not np.isfinite(self.vectors).all() or not np.allclose(np.linalg.norm(self.vectors, axis=1), 1, atol=1e-5):
            raise ValueError("Embeddings must be finite and L2 normalized")
        if expected_ids is not None and self.ids != list(expected_ids):
            raise ValueError("Embedding/product order differs")
        return self


def encode_cached(encoder, modality, ids, values, checksums, cache_root=ROOT / "data/cache/embeddings"):
    if len(ids) != len(values) or len(ids) != len(checksums):
        raise ValueError("Cache input alignment mismatch")
    fingerprint = digest(encoder.metadata)
    folder = Path(cache_root) / fingerprint / modality
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder.parent / "encoder.json", encoder.metadata)
    keys = [digest([modality, checksum]) for checksum in checksums]
    vectors = [None] * len(ids)
    missing = []
    for i, key in enumerate(keys):
        path = folder / (key + ".npy")
        if path.is_file():
            value = np.load(path, allow_pickle=False)
            if value.shape != (encoder.embedding_dimension,) or not np.isfinite(value).all() or not np.isclose(np.linalg.norm(value), 1, atol=1e-5):
                raise ValueError(f"Corrupt embedding cache: {path}")
            vectors[i] = value
        else:
            missing.append(i)
    for start in range(0, len(missing), encoder.batch_size):
        positions = missing[start:start + encoder.batch_size]
        batch = [values[i] for i in positions]
        encoded = encoder.encode_text(batch) if modality == "text" else encoder.encode_images(batch)
        if encoded.shape != (len(positions), encoder.embedding_dimension):
            raise ValueError("Encoder returned a misaligned batch")
        EmbeddingTable([ids[i] for i in positions], encoded).validate()
        for i, value in zip(positions, encoded):
            buffer = io.BytesIO()
            np.save(buffer, value, allow_pickle=False)
            atomic_write(folder / (keys[i] + ".npy"), buffer.getvalue())
            vectors[i] = value
        if start % (encoder.batch_size * 10) == 0:
            print(f"Encoded {modality}: {min(start + len(positions), len(missing))}/{len(missing)} uncached inputs", flush=True)
    matrix = np.stack(vectors) if vectors else np.empty((0, encoder.embedding_dimension), dtype=np.float32)
    table = EmbeddingTable(list(ids), matrix).validate(ids)
    return table, {"encoder_fingerprint": fingerprint, "ids": list(ids), "source_checksums": list(checksums),
                   "cache_keys": keys, "cache_hits": len(ids) - len(missing), "encoded": len(missing)}


def catalog_embeddings(catalog, encoder):
    products = [p["product_id"] for p in catalog]
    images = [p["index_image"] for p in catalog]
    return encode_cached(encoder, "image", products, [ROOT / v["path"] for v in images], [v["sha256"] for v in images])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("dev", "mvp", "standard"), default="mvp")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    catalog = read_jsonl(manifest_path(args.profile))
    validate_catalog(catalog)
    encoder = SiglipEncoder(load_config(args.config)["encoder"])
    table, _ = catalog_embeddings(catalog, encoder)
    queries = [p for p in catalog if p.get("query_image")]
    encode_cached(encoder, "image", [p["product_id"] for p in queries],
                  [ROOT / p["query_image"]["path"] for p in queries],
                  [p["query_image"]["sha256"] for p in queries])
    print(json.dumps({"products": len(table.ids), **encoder.metadata}, indent=2))


if __name__ == "__main__":
    main()
