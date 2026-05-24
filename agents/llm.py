from __future__ import annotations

import argparse
from datetime import date

from agents.project_brief_graph import run_project_brief


def main() -> None:
    parser = argparse.ArgumentParser(description="Run project brief agent.")
    parser.add_argument("project_id", nargs="?", default="P001")
    parser.add_argument("--as-of", dest="as_of", default=None, help="Date in YYYY-MM-DD format")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    brief = run_project_brief(project_id=args.project_id, as_of=as_of)
    print(brief.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
