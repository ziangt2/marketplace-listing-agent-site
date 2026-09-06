"""Metadata-derived queries and exact-match qrels, never title/ID queries."""
import itertools
import re
from collections import Counter

from .io_utils import digest

ATTRIBUTES = ("material", "color", "style")


def normalized(value):
    return " ".join(str(value).lower().split())


def safe_attribute(value):
    # Conservative exclusion of codes, digits, long descriptions and punctuation.
    return bool(re.fullmatch(r"[a-zA-Z]+(?:[ -][a-zA-Z]+){0,5}", str(value)))


def query_text(constraints):
    text = constraints["product_type"].replace("_", " ").lower()
    if "color" in constraints:
        text = f"{constraints['color']} {text}"
    if "material" in constraints:
        text += f" made of {constraints['material']}"
    if "style" in constraints:
        text += f" in {constraints['style']} style"
    return text


def validate_text_queries(queries, catalog, settings):
    ids = [q["query_id"] for q in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate query IDs")
    maximum = min(settings["max_relevant"], int(len(catalog) * settings["max_relevant_fraction"]))
    forbidden = {normalized(p["product_id"]) for p in catalog}
    forbidden.update(normalized(m) for p in catalog for m in p.get("model_numbers", []) if m)
    for query in queries:
        if not set(query["constraints"]).issubset({"product_type", *ATTRIBUTES}) or len(query["constraints"]) < 2:
            raise ValueError("Text queries require type and at least one structured attribute")
        if query["text"] != query_text(query["constraints"]):
            raise ValueError("Query text differs from documented template")
        if any(len(code) >= 3 and re.search(r"(?<!\w)" + re.escape(code) + r"(?!\w)", query["text"], re.I) for code in forbidden):
            raise ValueError("Product/model identifier leakage")
        relevant = sorted(p["product_id"] for p in catalog if all(normalized(p[field]) == value for field, value in query["constraints"].items()))
        if query["relevant_ids"] != relevant or not settings["min_relevant"] <= len(relevant) <= maximum:
            raise ValueError("Invalid relevance population")
        if any(normalized(p["title"]) == query["text"] for p in catalog):
            raise ValueError("Copied complete title")


def build_text_queries(catalog, settings):
    # Enumerate structured groups; keep the most specific valid group per product.
    groups = {}
    for product in catalog:
        available = [field for field in ATTRIBUTES if safe_attribute(product[field])]
        for size in range(1, len(available) + 1):
            for fields in itertools.combinations(available, size):
                constraints = {field: normalized(product[field]) for field in ("product_type", *fields)}
                key = tuple(sorted(constraints.items()))
                groups.setdefault(key, []).append(product["product_id"])
    maximum = min(settings["max_relevant"], int(len(catalog) * settings["max_relevant_fraction"]))
    valid = {key: sorted(ids) for key, ids in groups.items() if settings["min_relevant"] <= len(ids) <= maximum}
    candidates = {}
    for key, ids in valid.items():
        for product_id in ids:
            if product_id not in candidates or (-len(key), key) < (-len(candidates[product_id]), candidates[product_id]):
                candidates[product_id] = key
    queries, rejected = [], Counter()
    for key in sorted(set(candidates.values())):
        constraints = dict(key)
        query = {"query_id": "text_" + digest(constraints)[:16], "task": "text",
                 "text": query_text(constraints), "constraints": constraints,
                 "product_type": constraints["product_type"], "relevant_ids": valid[key]}
        try:
            validate_text_queries([query], catalog, settings)
        except ValueError as error:
            rejected[str(error)] += 1
            continue
        queries.append(query)
    queries.sort(key=lambda q: q["query_id"])
    if not queries:
        raise ValueError("No defensible text queries; expand the subset instead of relaxing labels silently")
    validate_text_queries(queries, catalog, settings)
    return queries, {"candidate_attribute_groups": len(groups), "valid_attribute_groups": len(valid),
                     "retained_queries": len(queries), "rejected_queries": dict(rejected),
                     "min_relevant": settings["min_relevant"], "max_relevant": maximum,
                     "labels": "binary exact conjunction of product_type and supplied English attributes",
                     "rule": "most specific valid attribute group per product, lexicographic ties; deduplicate identical queries"}


def build_image_queries(catalog):
    counts = Counter(p["query_image"]["pixel_sha256"] for p in catalog if p.get("query_image"))
    return [{"query_id": "image_" + p["product_id"], "task": "image",
             "image": p["query_image"], "product_type": p["product_type"].lower(),
             "relevant_ids": [p["product_id"]]} for p in catalog if p.get("query_image") and counts[p["query_image"]["pixel_sha256"]] == 1]
