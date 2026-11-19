from __future__ import annotations

import argparse
import json
from pathlib import Path

from heirs_navigator.config import Settings
from heirs_navigator.ingest.corpus import fetch_sources, load_sources
from heirs_navigator.ingest.index import build_index


def main() -> None:
    parser = argparse.ArgumentParser(prog="heirs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch")
    sub.add_parser("index")
    sub.add_parser("report")
    evaluation = sub.add_parser("eval")
    evaluation.add_argument("--split", choices=["dev", "test"], default="dev")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "fetch":
        missing = fetch_sources(
            load_sources(Path("data/sources.yaml")), Path("data/raw"), Path("data/manifest.csv")
        )
        print(json.dumps({"missing": missing}))
    elif args.command == "index":
        print(
            json.dumps(
                {"chunks_indexed": build_index(Path("data/manifest.csv"), settings.index_dir)}
            )
        )
    elif args.command == "eval":
        from heirs_navigator.evaluation import evaluate

        print(json.dumps(evaluate(args.split), indent=2))
    elif args.command == "report":
        from heirs_navigator.evaluation import generate_ablation_report

        print(generate_ablation_report(Path("eval/results"), Path("eval/ablation.md")))


if __name__ == "__main__":
    main()
