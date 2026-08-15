"""Generate a deterministic synthetic e-commerce event stream."""

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

from config import (
    DATA_RAW,
    N_CATEGORIES,
    N_PRODUCTS,
    N_USERS,
    OBSERVATION_DAYS,
    SEED,
    START_DATE,
    ensure_directories,
)


CATEGORY_NAMES = (
    "apparel",
    "beauty",
    "electronics",
    "home",
    "sports",
    "books",
    "toys",
    "grocery",
    "pet_supplies",
    "accessories",
)

SEGMENTS = ("casual", "browser", "shopper", "loyal")
SEGMENT_PROBABILITIES = np.array([0.32, 0.36, 0.23, 0.09])
EXTRA_SESSION_MEANS = np.array([1.0, 2.4, 4.5, 7.5])
DEPTH_MEANS = np.array([2.0, 2.7, 3.4, 4.2])
ENGAGEMENT_MULTIPLIERS = np.array([0.72, 0.95, 1.22, 1.45])

# These vocabularies produce synthetic listing-style metadata. Terms repeat
# across products and are correlated within category, but each field contains
# enough variation to avoid acting as a product identifier.
PRODUCT_METADATA = {
    "apparel": {
        "subcategories": ("activewear", "outerwear", "basics", "casual_wear"),
        "cores": ("shirt", "jacket", "pants", "hoodie"),
        "features": ("breathable", "stretch", "lightweight", "soft", "layered"),
        "uses": ("daily_wear", "commuting", "training", "weekend_travel"),
        "audiences": ("adults", "students", "travelers", "active_lifestyles"),
        "attributes": ("machine_washable", "relaxed_fit", "moisture_wicking", "reinforced_seams"),
    },
    "beauty": {
        "subcategories": ("skin_care", "hair_care", "body_care", "cosmetics"),
        "cores": ("serum", "cleanser", "cream", "treatment"),
        "features": ("hydrating", "gentle", "brightening", "smoothing", "fragrance_free"),
        "uses": ("daily_routine", "travel_care", "night_routine", "sensitive_skin"),
        "audiences": ("adults", "beginners", "beauty_enthusiasts", "sensitive_users"),
        "attributes": ("dermatologist_tested", "plant_based", "quick_absorbing", "non_greasy"),
    },
    "electronics": {
        "subcategories": ("audio", "mobile_accessories", "smart_home", "computer_accessories"),
        "cores": ("headphones", "charger", "speaker", "adapter"),
        "features": ("wireless", "compact", "fast_charging", "noise_reducing", "portable"),
        "uses": ("remote_work", "commuting", "gaming", "travel"),
        "audiences": ("professionals", "students", "gamers", "travelers"),
        "attributes": ("usb_c", "bluetooth", "long_battery", "multi_device"),
    },
    "home": {
        "subcategories": ("kitchen", "storage", "bedding", "home_decor"),
        "cores": ("organizer", "container", "lamp", "blanket"),
        "features": ("space_saving", "durable", "washable", "minimal", "adjustable"),
        "uses": ("small_spaces", "home_office", "meal_prep", "everyday_comfort"),
        "audiences": ("families", "renters", "homeowners", "students"),
        "attributes": ("easy_clean", "stackable", "non_slip", "tool_free_setup"),
    },
    "sports": {
        "subcategories": ("fitness", "outdoor", "team_sports", "recovery"),
        "cores": ("training_band", "bottle", "mat", "support"),
        "features": ("lightweight", "grip", "adjustable", "sweat_resistant", "portable"),
        "uses": ("home_workout", "gym_training", "hiking", "recovery"),
        "audiences": ("beginners", "athletes", "coaches", "outdoor_users"),
        "attributes": ("non_slip", "easy_carry", "multiple_resistance", "impact_resistant"),
    },
    "books": {
        "subcategories": ("fiction", "business", "self_development", "reference"),
        "cores": ("guide", "workbook", "novel", "handbook"),
        "features": ("practical", "illustrated", "step_by_step", "engaging", "concise"),
        "uses": ("skill_building", "study", "leisure_reading", "career_growth"),
        "audiences": ("students", "professionals", "beginners", "general_readers"),
        "attributes": ("paperback", "reference_tables", "practice_exercises", "expert_examples"),
    },
    "toys": {
        "subcategories": ("building", "creative_play", "puzzles", "outdoor_play"),
        "cores": ("activity_set", "building_set", "puzzle", "game"),
        "features": ("educational", "colorful", "interactive", "creative", "cooperative"),
        "uses": ("family_time", "learning", "travel_play", "indoor_play"),
        "audiences": ("young_children", "older_children", "families", "classrooms"),
        "attributes": ("easy_storage", "reusable", "large_pieces", "multiple_difficulty"),
    },
    "grocery": {
        "subcategories": ("snacks", "beverages", "pantry", "breakfast"),
        "cores": ("snack", "drink", "mix", "meal_base"),
        "features": ("savory", "lightly_sweet", "high_protein", "whole_grain", "convenient"),
        "uses": ("quick_meals", "work_snacks", "family_pantry", "outdoor_trips"),
        "audiences": ("families", "busy_professionals", "students", "active_lifestyles"),
        "attributes": ("resealable", "single_serve", "shelf_stable", "simple_ingredients"),
    },
    "pet_supplies": {
        "subcategories": ("feeding", "grooming", "toys", "travel_gear"),
        "cores": ("feeder", "brush", "toy", "carrier_accessory"),
        "features": ("durable", "easy_clean", "interactive", "gentle", "portable"),
        "uses": ("daily_care", "training", "travel", "indoor_play"),
        "audiences": ("dog_owners", "cat_owners", "new_pet_owners", "multi_pet_homes"),
        "attributes": ("non_slip", "washable", "chew_resistant", "adjustable"),
    },
    "accessories": {
        "subcategories": ("bags", "wallets", "jewelry", "travel_accessories"),
        "cores": ("pouch", "wallet", "bracelet", "travel_case"),
        "features": ("compact", "lightweight", "versatile", "minimal", "water_resistant"),
        "uses": ("daily_carry", "commuting", "travel", "gift_giving"),
        "audiences": ("professionals", "students", "travelers", "gift_shoppers"),
        "attributes": ("zip_closure", "adjustable", "multiple_pockets", "easy_clean"),
    },
}


def _write_csv(path: Path, rows: Iterable[Dict], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _iso(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _choice(rng: np.random.Generator, values: tuple) -> str:
    return values[int(rng.integers(0, len(values)))]


def _synthetic_product_metadata(
    rng: np.random.Generator, category: str, price: float
) -> Dict[str, str]:
    """Create deterministic, correlated listing features from an isolated RNG."""
    vocabulary = PRODUCT_METADATA[category]
    subcategory = _choice(rng, vocabulary["subcategories"])
    core = _choice(rng, vocabulary["cores"])
    feature = _choice(rng, vocabulary["features"])
    second_feature = _choice(rng, vocabulary["features"])
    use_case = _choice(rng, vocabulary["uses"])
    audience = _choice(rng, vocabulary["audiences"])
    attribute = _choice(rng, vocabulary["attributes"])
    second_attribute = _choice(rng, vocabulary["attributes"])
    if price < 25:
        price_bucket = "budget"
    elif price < 75:
        price_bucket = "mid_range"
    else:
        price_bucket = "premium"
    return {
        "category": category,
        "subcategory": subcategory,
        "title": f"{feature} {core} for {use_case}",
        "keywords": f"{core}|{feature} {core}|{core} for {audience}",
        "tags": f"{feature}|{second_feature}|{price_bucket}",
        "price_bucket": price_bucket,
        "use_case": use_case,
        "audience": audience,
        "attributes": f"{attribute}|{second_attribute}",
    }


def generate_dataset() -> Dict:
    """Create users, products, sessions, and events under data/raw."""
    ensure_directories()
    seed_sequence = np.random.SeedSequence(SEED)
    data_seed, experiment_seed = seed_sequence.spawn(2)
    rng = np.random.default_rng(data_seed)
    experiment_rng = np.random.default_rng(experiment_seed)
    # Product text must not perturb the established behavioral random stream.
    metadata_rng = np.random.default_rng(np.random.SeedSequence([SEED, 0xC07E]))
    start = datetime.fromisoformat(START_DATE)

    # Products are balanced across categories, with long-tailed popularity inside
    # each category and independent quality variation.
    product_rows: List[Dict] = []
    product_ids_by_category: List[np.ndarray] = []
    product_cdf_by_category: List[np.ndarray] = []
    product_quality = np.zeros(N_PRODUCTS + 1)
    product_price = np.zeros(N_PRODUCTS + 1)
    category_conversion = rng.uniform(0.82, 1.18, N_CATEGORIES)

    products_per_category = N_PRODUCTS // N_CATEGORIES
    for category_id in range(1, N_CATEGORIES + 1):
        first_id = (category_id - 1) * products_per_category + 1
        ids = np.arange(first_id, first_id + products_per_category)
        ranks = np.arange(1, len(ids) + 1)
        popularity = rng.lognormal(0.0, 0.25, len(ids)) / np.power(ranks + 3, 0.72)
        popularity = popularity / popularity.sum()
        cdf = np.cumsum(popularity)
        cdf[-1] = 1.0
        qualities = rng.beta(3.0, 2.5, len(ids))
        base_price = rng.uniform(16.0, 90.0)
        prices = np.clip(rng.lognormal(np.log(base_price), 0.55, len(ids)), 4.0, 600.0)
        product_ids_by_category.append(ids)
        product_cdf_by_category.append(cdf)
        for idx, product_id in enumerate(ids):
            product_quality[product_id] = qualities[idx]
            product_price[product_id] = prices[idx]
            category_name = CATEGORY_NAMES[category_id - 1]
            content_metadata = _synthetic_product_metadata(
                metadata_rng, category_name, float(prices[idx])
            )
            product_rows.append(
                {
                    "product_id": int(product_id),
                    "category_id": category_id,
                    "category_name": category_name,
                    "price": f"{prices[idx]:.2f}",
                    "popularity_score": f"{popularity[idx]:.8f}",
                    "quality_score": f"{qualities[idx]:.6f}",
                    "category_conversion_multiplier": f"{category_conversion[category_id - 1]:.6f}",
                    **content_metadata,
                }
            )

    segment_index = rng.choice(len(SEGMENTS), size=N_USERS, p=SEGMENT_PROBABILITIES)
    primary_categories = rng.integers(1, N_CATEGORIES + 1, size=N_USERS)
    secondary_categories = rng.integers(1, N_CATEGORIES + 1, size=N_USERS)
    duplicate = secondary_categories == primary_categories
    secondary_categories[duplicate] = (secondary_categories[duplicate] % N_CATEGORIES) + 1
    acquisition_days = rng.integers(0, 29, size=N_USERS)
    conversion_propensity = np.clip(rng.lognormal(0.0, 0.28, N_USERS), 0.48, 1.85)

    assignments = np.where(experiment_rng.random(N_USERS) < 0.5, "control", "treatment")
    # A direct reproducibility assertion uses a fresh RNG created from the same
    # spawned seed; experiment assignment is isolated from all behavioral draws.
    replay_rng = np.random.default_rng(experiment_seed)
    replay = np.where(replay_rng.random(N_USERS) < 0.5, "control", "treatment")
    assert np.array_equal(assignments, replay)
    control_share = float(np.mean(assignments == "control"))
    assert 0.48 <= control_share <= 0.52

    user_rows: List[Dict] = []
    for user_offset in range(N_USERS):
        user_rows.append(
            {
                "user_id": user_offset + 1,
                "segment": SEGMENTS[segment_index[user_offset]],
                "primary_category_id": int(primary_categories[user_offset]),
                "secondary_category_id": int(secondary_categories[user_offset]),
                "acquisition_date": (start + timedelta(days=int(acquisition_days[user_offset]))).date().isoformat(),
                "experiment_group": assignments[user_offset],
                "conversion_propensity": f"{conversion_propensity[user_offset]:.6f}",
            }
        )

    session_path = DATA_RAW / "sessions.csv"
    event_path = DATA_RAW / "events.csv"
    event_counts: Counter = Counter()
    session_count = 0
    event_count = 0
    event_id = 0
    max_timestamp = start
    min_timestamp = start + timedelta(days=OBSERVATION_DAYS)

    with session_path.open("w", newline="", encoding="utf-8") as session_handle, event_path.open(
        "w", newline="", encoding="utf-8"
    ) as event_handle:
        session_fields = ["session_id", "user_id", "session_start", "experiment_group"]
        event_fields = [
            "event_id",
            "user_id",
            "session_id",
            "product_id",
            "event_type",
            "event_timestamp",
            "experiment_group",
        ]
        session_writer = csv.DictWriter(session_handle, fieldnames=session_fields)
        event_writer = csv.DictWriter(event_handle, fieldnames=event_fields)
        session_writer.writeheader()
        event_writer.writeheader()

        for user_offset in range(N_USERS):
            user_id = user_offset + 1
            seg_idx = int(segment_index[user_offset])
            acquisition_day = int(acquisition_days[user_offset])
            first_offset = acquisition_day + rng.uniform(0.10, 0.90)
            extra_sessions = int(rng.poisson(EXTRA_SESSION_MEANS[seg_idx]))
            remaining = max(0.1, OBSERVATION_DAYS - 0.05 - first_offset)
            later_offsets = first_offset + rng.beta(0.82, 1.18, extra_sessions) * remaining
            session_offsets = np.sort(np.concatenate(([first_offset], later_offsets)))
            seen_products: List[int] = []

            for session_offset in session_offsets:
                session_count += 1
                session_id = session_count
                session_start = start + timedelta(days=float(session_offset))
                session_writer.writerow(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "session_start": _iso(session_start),
                        "experiment_group": assignments[user_offset],
                    }
                )
                depth = 1 + int(rng.poisson(DEPTH_MEANS[seg_idx]))
                primary_probability = 0.67 if assignments[user_offset] == "treatment" else 0.63
                secondary_probability = 0.20

                for position in range(depth):
                    category_draw = rng.random()
                    if category_draw < primary_probability:
                        category_id = int(primary_categories[user_offset])
                    elif category_draw < primary_probability + secondary_probability:
                        category_id = int(secondary_categories[user_offset])
                    else:
                        category_id = int(rng.integers(1, N_CATEGORIES + 1))

                    # A small repeat tendency creates realistic revisits without
                    # eliminating unseen products needed for temporal evaluation.
                    category_first = (category_id - 1) * products_per_category + 1
                    category_last = category_first + products_per_category
                    prior_in_category = [p for p in seen_products[-20:] if category_first <= p < category_last]
                    if prior_in_category and rng.random() < 0.10:
                        product_id = int(prior_in_category[int(rng.integers(0, len(prior_in_category)))])
                    else:
                        cdf = product_cdf_by_category[category_id - 1]
                        item_index = int(np.searchsorted(cdf, rng.random(), side="right"))
                        product_id = int(product_ids_by_category[category_id - 1][item_index])
                    seen_products.append(product_id)

                    view_time = session_start + timedelta(seconds=position * 150)
                    event_id += 1
                    event_writer.writerow(
                        {
                            "event_id": event_id,
                            "user_id": user_id,
                            "session_id": session_id,
                            "product_id": product_id,
                            "event_type": "view",
                            "event_timestamp": _iso(view_time),
                            "experiment_group": assignments[user_offset],
                        }
                    )
                    event_count += 1
                    event_counts["view"] += 1

                    affinity = 1.24 if category_id == primary_categories[user_offset] else (
                        1.08 if category_id == secondary_categories[user_offset] else 0.78
                    )
                    quality_factor = 0.70 + 0.62 * product_quality[product_id]
                    click_probability = (
                        0.165
                        * ENGAGEMENT_MULTIPLIERS[seg_idx]
                        * conversion_propensity[user_offset]
                        * affinity
                        * quality_factor
                    )
                    if assignments[user_offset] == "treatment":
                        click_probability *= 1.045
                    click_probability = min(0.58, click_probability)

                    if rng.random() < click_probability:
                        event_id += 1
                        click_time = view_time + timedelta(seconds=35)
                        event_writer.writerow(
                            {
                                "event_id": event_id,
                                "user_id": user_id,
                                "session_id": session_id,
                                "product_id": product_id,
                                "event_type": "click",
                                "event_timestamp": _iso(click_time),
                                "experiment_group": assignments[user_offset],
                            }
                        )
                        event_count += 1
                        event_counts["click"] += 1

                        cart_probability = min(
                            0.58,
                            0.255
                            * ENGAGEMENT_MULTIPLIERS[seg_idx]
                            * conversion_propensity[user_offset]
                            * (0.88 + 0.30 * product_quality[product_id]),
                        )
                        if rng.random() < cart_probability:
                            event_id += 1
                            cart_time = view_time + timedelta(seconds=75)
                            event_writer.writerow(
                                {
                                    "event_id": event_id,
                                    "user_id": user_id,
                                    "session_id": session_id,
                                    "product_id": product_id,
                                    "event_type": "add_to_cart",
                                    "event_timestamp": _iso(cart_time),
                                    "experiment_group": assignments[user_offset],
                                }
                            )
                            event_count += 1
                            event_counts["add_to_cart"] += 1

                            price_factor = np.clip(1.15 - 0.0014 * product_price[product_id], 0.62, 1.12)
                            purchase_probability = min(
                                0.72,
                                0.40
                                * conversion_propensity[user_offset]
                                * category_conversion[category_id - 1]
                                * price_factor,
                            )
                            if assignments[user_offset] == "treatment":
                                purchase_probability *= 1.055
                            if rng.random() < purchase_probability:
                                event_id += 1
                                purchase_time = view_time + timedelta(seconds=115)
                                event_writer.writerow(
                                    {
                                        "event_id": event_id,
                                        "user_id": user_id,
                                        "session_id": session_id,
                                        "product_id": product_id,
                                        "event_type": "purchase",
                                        "event_timestamp": _iso(purchase_time),
                                        "experiment_group": assignments[user_offset],
                                    }
                                )
                                event_count += 1
                                event_counts["purchase"] += 1
                                max_timestamp = max(max_timestamp, purchase_time)
                    min_timestamp = min(min_timestamp, view_time)
                    max_timestamp = max(max_timestamp, view_time)

    _write_csv(
        DATA_RAW / "users.csv",
        user_rows,
        [
            "user_id",
            "segment",
            "primary_category_id",
            "secondary_category_id",
            "acquisition_date",
            "experiment_group",
            "conversion_propensity",
        ],
    )
    _write_csv(
        DATA_RAW / "products.csv",
        product_rows,
        [
            "product_id",
            "category_id",
            "category_name",
            "price",
            "popularity_score",
            "quality_score",
            "category_conversion_multiplier",
            "category",
            "subcategory",
            "title",
            "keywords",
            "tags",
            "price_bucket",
            "use_case",
            "audience",
            "attributes",
        ],
    )

    assert len(user_rows) == N_USERS
    assert len(product_rows) == N_PRODUCTS
    assert event_count == sum(event_counts.values())
    assert event_counts["view"] >= 100_000
    assert event_counts["view"] >= event_counts["click"] >= event_counts["add_to_cart"] >= event_counts["purchase"]

    assignment_text = "|".join(assignments.tolist()).encode("utf-8")
    metadata = {
        "seed": SEED,
        "users": N_USERS,
        "products": N_PRODUCTS,
        "categories": N_CATEGORIES,
        "sessions": session_count,
        "total_events": event_count,
        "views": event_counts["view"],
        "clicks": event_counts["click"],
        "add_to_carts": event_counts["add_to_cart"],
        "purchases": event_counts["purchase"],
        "control_users": int(np.sum(assignments == "control")),
        "treatment_users": int(np.sum(assignments == "treatment")),
        "assignment_sha256": hashlib.sha256(assignment_text).hexdigest(),
        "observation_start": _iso(min_timestamp),
        "observation_end": _iso(max_timestamp),
    }
    (DATA_RAW / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


if __name__ == "__main__":
    generated = generate_dataset()
    print(json.dumps(generated, indent=2))
