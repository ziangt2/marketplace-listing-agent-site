"""Prepare or restore the frozen catalog: python -m multimodal.src.build_catalog."""
import argparse

from .abo_dataset import prepare_catalog
from .config import DEFAULT_CONFIG, load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("dev", "mvp", "standard"), default="dev")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    _, summary = prepare_catalog(args.profile, load_config(args.config))
    print(f"Catalog ready: {summary['products']} products, {summary['image_queries']} distinct-view image queries")


if __name__ == "__main__":
    main()
