"""Download only public listing metadata and selected ABO small catalog images."""
import csv
import gzip
import hashlib
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageOps

from .config import ROOT, manifest_path
from .io_utils import atomic_write, digest, file_sha256, read_jsonl, write_json, write_jsonl

SOURCE = "https://amazon-berkeley-objects.s3.amazonaws.com"
SELECTION_VERSION = "english-multiview-hash-v1"


def download(url, path, expected_sha256=None):
    """Reuse verified local bytes; retry transient errors, never select around them."""
    path = Path(path)
    if path.is_file():
        if expected_sha256 and file_sha256(path) != expected_sha256:
            raise ValueError(f"Checksum mismatch: {path}; remove this corrupt cache file and retry")
        return path
    for attempt in range(3):
        try:
            with requests.get(url, timeout=(10, 60)) as response:
                if response.status_code == 404:
                    raise FileNotFoundError(url)
                response.raise_for_status()
                data = response.content
            if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
                raise ValueError(f"Source changed: {url}")
            atomic_write(path, data)
            return path
        except (requests.RequestException, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def english_value(value, allow_untagged=False):
    if isinstance(value, str):
        return value.strip() if allow_untagged else ""
    rows = value if isinstance(value, list) else []
    eligible = [row for row in rows if isinstance(row, dict) and (
        str(row.get("language_tag", "")).lower().startswith("en")
        or (allow_untagged and not row.get("language_tag"))
    )]
    eligible.sort(key=lambda row: (row.get("language_tag") != "en_US", str(row.get("language_tag", "")), str(row.get("value", ""))))
    return str(eligible[0].get("value", "")).strip() if eligible else ""


def normalize_listing(row, image_metadata):
    item_id = row.get("item_id")
    title = english_value(row.get("item_name"))
    category = english_value(row.get("product_type"), allow_untagged=True)
    if not item_id:
        return None, "missing_item_id"
    if not title:
        return None, "missing_english_title"
    if not category:
        return None, "missing_product_type"
    images = list(dict.fromkeys([row.get("main_image_id")] + row.get("other_image_id", [])))
    images = [i for i in images if i in image_metadata
              and min(int(image_metadata[i]["width"]), int(image_metadata[i]["height"])) >= 64]
    if not images:
        return None, "no_usable_image_metadata"
    return {
        "product_id": str(item_id), "item_id": str(item_id),
        "domain_name": row.get("domain_name", ""), "title": title,
        "product_type": category,
        **{field: english_value(row.get(field)) for field in ("material", "color", "style", "brand", "pattern", "finish_type")},
        "dimensions": row.get("item_dimensions", {}),
        "model_numbers": sorted({str(x.get("value")) for x in row.get("model_number", []) if x.get("value")}),
        "image_ids": images,
    }, None


def candidate_list(rows, image_metadata, seed):
    dropped = Counter()
    by_id = {}
    for row in rows:
        product, reason = normalize_listing(row, image_metadata)
        if reason:
            dropped[reason] += 1
            continue
        product_id = product["product_id"]
        # ABO listing keys are (item_id, domain_name). Choose one listing per item.
        preference = lambda p: (p["domain_name"] != "amazon.com", p["domain_name"], digest(p))
        if product_id in by_id:
            dropped["duplicate_item_listing"] += 1
            if preference(product) >= preference(by_id[product_id]):
                continue
        by_id[product_id] = product
    products = sorted(by_id.values(), key=lambda p: (
        len(p["image_ids"]) < 2, digest([seed, p["product_id"]]), p["product_id"]
    ))
    return products, dropped


def inspect_image(path):
    with Image.open(path) as original:
        rgb = ImageOps.exif_transpose(original).convert("RGB")
        rgb.load()
        if min(rgb.size) < 32:
            raise ValueError("image_too_small")
        pixels = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
        return {"sha256": file_sha256(path), "pixel_sha256": pixels,
                "width": rgb.width, "height": rgb.height}


def fetch_image(image_id, image_metadata):
    source_path = image_metadata[image_id]["path"]
    if not re.fullmatch(r"[0-9a-f]{2}/[0-9a-f]+\.(jpg|png)", source_path):
        raise ValueError("Unexpected ABO image path")
    relative = f"data/raw/images/{source_path}"
    url = f"{SOURCE}/images/small/{source_path}"
    path = download(url, ROOT / relative)
    return {"image_id": image_id, "path": relative, "source_url": url, **inspect_image(path)}


def validate_catalog(catalog, root=ROOT, check_files=True):
    ids = [p["product_id"] for p in catalog]
    if not ids or ids != sorted(set(ids)):
        raise ValueError("Catalog IDs must be nonempty, unique, and sorted")
    index_hashes = {p["index_image"]["sha256"] for p in catalog}
    index_pixels = {p["index_image"]["pixel_sha256"] for p in catalog}
    index_ids = {p["index_image"]["image_id"] for p in catalog}
    if len(index_hashes) != len(catalog) or len(index_pixels) != len(catalog):
        raise ValueError("Duplicate indexed image contents")
    for product in catalog:
        if product["item_id"] != product["product_id"]:
            raise ValueError("Original item identity lost")
        query = product.get("query_image")
        if query and (query["image_id"] in index_ids or query["sha256"] in index_hashes or query["pixel_sha256"] in index_pixels):
            raise ValueError("Query image occurs in indexed catalog")
        if check_files:
            for entry in (product["index_image"], query):
                if entry:
                    path = (root / entry["path"]).resolve()
                    if not path.is_relative_to(root.resolve()):
                        raise ValueError("Image outside dataset directory")
                    actual = inspect_image(path)
                    if any(actual[k] != entry[k] for k in actual):
                        raise ValueError(f"Image checksum/shape changed for {product['product_id']}")


def prepare_catalog(profile, config):
    manifest = manifest_path(profile)
    summary_path = manifest.with_suffix(".summary.json")
    count = config["sizes"][profile]
    selection = {"version": SELECTION_VERSION, "seed": config["seed"], "requested_products": count}
    if manifest.exists():
        summary = json.loads(summary_path.read_text())
        if summary["selection"] != selection or file_sha256(manifest) != summary["catalog_sha256"]:
            raise ValueError("Frozen manifest differs from configuration or checksum; use a separate profile")
        catalog = read_jsonl(manifest)
        entries = {e["path"]: e for p in catalog for e in (p["index_image"], p.get("query_image")) if e}
        def restore(entry):
            if not entry["source_url"].startswith(SOURCE + "/images/small/") or not re.fullmatch(r"data/raw/images/[0-9a-f]{2}/[0-9a-f]+\.(jpg|png)", entry["path"]):
                raise ValueError("Invalid image source in manifest")
            download(entry["source_url"], ROOT / entry["path"], entry["sha256"])
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(restore, entries.values()))
        validate_catalog(catalog)
        return catalog, summary

    print("Downloading ABO listing and image metadata (no image archive)", flush=True)
    keys = [f"listings/metadata/listings_{i:x}.json.gz" for i in range(16)] + ["images/metadata/images.csv.gz"]
    def fetch_metadata(key):
        path = download(f"{SOURCE}/{key}", ROOT / "data" / "raw" / key)
        return {"key": key, "url": f"{SOURCE}/{key}", "sha256": file_sha256(path), "bytes": path.stat().st_size}
    with ThreadPoolExecutor(max_workers=8) as pool:
        sources = list(pool.map(fetch_metadata, keys))
    with gzip.open(ROOT / "data/raw/images/metadata/images.csv.gz", "rt") as handle:
        image_metadata = {row["image_id"]: row for row in csv.DictReader(handle)}
    read_count = 0
    def listings():
        nonlocal read_count
        for key in keys[:-1]:
            with gzip.open(ROOT / "data/raw" / key, "rt", encoding="utf-8") as handle:
                for line in handle:
                    read_count += 1
                    yield json.loads(line)
    candidates, dropped = candidate_list(listings(), image_metadata, config["seed"])
    print(f"{len(candidates)} eligible unique items; fetching views for {count} products", flush=True)
    catalog, seen_hashes, seen_pixels = [], set(), set()
    image_failures = Counter()
    def materialize(product):
        result = dict(product)
        views, failures = [], Counter()
        # At most two downloads per candidate: index + one preferred held-out view.
        for image_id in product["image_ids"][:2]:
            try:
                view = fetch_image(image_id, image_metadata)
                views.append(view)
            except FileNotFoundError:
                failures["image_http_404"] += 1
            except requests.RequestException:
                raise  # Transport failure must not silently change the subset.
            except (OSError, ValueError):
                failures["invalid_image"] += 1
        result.pop("image_ids")
        if not views:
            return None, failures
        result["index_image"] = views[0]
        result["query_image"] = views[1] if len(views) > 1 else None
        return result, failures
    with ThreadPoolExecutor(max_workers=8) as pool:
        start = 0
        while start < len(candidates):
            batch = candidates[start:start + min(100, count - len(catalog))]
            start += len(batch)
            for product, failures in pool.map(materialize, batch):
                image_failures.update(failures)
                if product is None:
                    dropped["no_valid_downloaded_image"] += 1
                    continue
                view = product["index_image"]
                if view["sha256"] in seen_hashes or view["pixel_sha256"] in seen_pixels:
                    dropped["duplicate_index_image"] += 1
                    continue
                seen_hashes.add(view["sha256"])
                seen_pixels.add(view["pixel_sha256"])
                catalog.append(product)
            print(f"Prepared {len(catalog)}/{count} products", flush=True)
            if len(catalog) == count:
                break
    if len(catalog) < count:
        raise ValueError(f"Only {len(catalog)} usable products; requested {count}")
    excluded_queries = Counter()
    index_ids = {p["index_image"]["image_id"] for p in catalog}
    for product in catalog:
        query = product["query_image"]
        if not query:
            excluded_queries["no_second_valid_view"] += 1
        elif query["sha256"] in seen_hashes or query["pixel_sha256"] in seen_pixels or query["image_id"] in index_ids:
            product["query_image"] = None
            excluded_queries["view_identical_to_any_indexed_image"] += 1
    catalog.sort(key=lambda p: p["product_id"])
    validate_catalog(catalog)
    write_jsonl(manifest, catalog)
    entries = {e["sha256"]: e for p in catalog for e in (p["index_image"], p["query_image"]) if e}
    summary = {
        "dataset": "public Amazon Berkeley Objects research dataset",
        "source": SOURCE + "/index.html", "license": "CC BY 4.0",
        "attribution": "Amazon.com; ABO dataset creators (see multimodal/data/README.md)",
        "selection": selection,
        "subset_rule": "English title + product type + image metadata; one listing per item (amazon.com preferred); multiview first, then SHA256(seed,item_id); exclude duplicate indexed image bytes/pixels; product-id order",
        "listing_records_scanned": read_count, "eligible_unique_items": len(candidates),
        "products": len(catalog), "unique_images": len(entries),
        "image_queries": sum(bool(p["query_image"]) for p in catalog),
        "dropped_records": dict(dropped), "image_failures": dict(image_failures),
        "excluded_image_queries": dict(excluded_queries),
        "not_selected_eligible_items": len(candidates) - len(catalog) - dropped["no_valid_downloaded_image"] - dropped["duplicate_index_image"],
        "category_counts": dict(Counter(p["product_type"] for p in catalog)),
        "catalog_sha256": file_sha256(manifest), "source_metadata": sources,
        "selected_image_bytes": sum((ROOT / e["path"]).stat().st_size for e in entries.values()),
    }
    write_json(summary_path, summary)
    return catalog, summary
