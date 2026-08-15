from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
RESULTS = PROJECT_ROOT / "results"
DATABASE_PATH = DATA_PROCESSED / "ecommerce.sqlite"

SEED = 2027
N_USERS = 15_000
N_PRODUCTS = 600
N_CATEGORIES = 10
START_DATE = "2026-01-05"
OBSERVATION_DAYS = 56

EVENT_WEIGHTS = {
    "view": 1.0,
    "click": 2.0,
    "add_to_cart": 4.0,
    "purchase": 6.0,
}
HOLDOUT_DAYS = 14
MIN_HISTORY_ITEMS = 3
TOP_K_VALUES = (5, 10)


def ensure_directories() -> None:
    for path in (DATA_RAW, DATA_PROCESSED, RESULTS, RESULTS / "figures"):
        path.mkdir(parents=True, exist_ok=True)
