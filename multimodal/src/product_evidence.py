"""Allowlisted ABO evidence and explicit, fail-closed metadata constraints."""
import math
import re

TEXT_FIELDS = ("title", "product_type", "material", "color", "style", "brand", "pattern", "finish_type")
DIMENSIONS = ("width", "height", "depth")
FILTER_FIELDS = ("product_type", "material", "color", "style", *DIMENSIONS)
UNITS = {"in": 1, "inch": 1, "inches": 1, "cm": 1 / 2.54, "centimeters": 1 / 2.54,
         "mm": 1 / 25.4, "millimeters": 1 / 25.4}


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def number_text(value):
    return format(float(value), ".6f").rstrip("0").rstrip(".")


def evidence_for(product, hit=None, rank=None):
    fields = {f: product[f] for f in TEXT_FIELDS if product.get(f)}
    sources = {}
    for field in DIMENSIONS:
        axis = "length" if field == "depth" else field
        source = product.get("dimensions", {}).get(axis, {})
        unit = str(source.get("unit", "")).lower()
        value = source.get("value")
        if unit in UNITS and type(value) in (int, float) and math.isfinite(value) and value > 0:
            fields[field] = number_text(value * UNITS[unit]) + " in"
            sources[field] = {"source_field": "dimensions." + axis, "value": value, "unit": unit}
    result = {"product_id": product["product_id"], "fields": fields, "dimension_sources": sources}
    if hit is not None:
        result["retrieval"] = {"source": hit.source, "rank": rank, "score": hit.score, "ranks": hit.ranks}
    return result


def inches(value):
    if not isinstance(value, str):
        raise ValueError("Dimensions require a numeric string with an explicit unit")
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(inches|inch|in|cm|mm|centimeters|millimeters)\s*", value.lower())
    if not match:
        raise ValueError("Unsupported dimension value/unit")
    result = float(match[1]) * UNITS[match[2]]
    if not math.isfinite(result) or result <= 0 or result > 100000:
        raise ValueError("Dimension outside supported range")
    return result


def validate_constraints(constraints):
    if not isinstance(constraints, list) or len(constraints) > 12:
        raise ValueError("Expected at most 12 constraints")
    for constraint in constraints:
        if not isinstance(constraint, dict) or set(constraint) != {"field", "operator", "value"}:
            raise ValueError("Invalid constraint schema")
        field, operator, value = (constraint[k] for k in ("field", "operator", "value"))
        if field not in FILTER_FIELDS or not isinstance(value, str) or not value.strip() or len(value) > 150:
            raise ValueError("Unsupported constraint field/value")
        if field in DIMENSIONS:
            if operator not in ("eq", "lt", "lte", "gt", "gte"):
                raise ValueError("Invalid numeric operator")
            inches(value)
        elif operator not in ("eq", "contains"):
            raise ValueError("Invalid text operator")
    return constraints


def matches(evidence, constraint):
    """Missing data never satisfies a requested constraint; no title inference."""
    field, op, value = (constraint[k] for k in ("field", "operator", "value"))
    actual = evidence["fields"].get(field)
    if actual is None:
        return False
    if field in DIMENSIONS:
        actual, target = inches(actual), inches(value)
        return {"eq": abs(actual - target) < 1e-6, "lt": actual < target,
                "lte": actual <= target, "gt": actual > target, "gte": actual >= target}[op]
    actual, value = normalized(actual), normalized(value)
    # This is a documented material-family filter, not an assertion of solid-wood construction.
    if field == "material" and value in ("wood", "wooden"):
        return any(token in actual.split() for token in ("wood", "ash", "pine", "solidpine", "bamboo", "mdf", "hardwood"))
    return actual == value if op == "eq" else value in actual


def satisfies(evidence, constraints):
    validate_constraints(constraints)
    return all(matches(evidence, c) for c in constraints)
