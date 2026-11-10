"""Command-line entry point for HSK catalog releases.

    python -m scripts.import_hsk_release validate <dataset_dir> --report-dir <dir>
    python -m scripts.import_hsk_release import   <dataset_dir> --database-url <url> [--report-dir <dir>]
    python -m scripts.import_hsk_release publish  --track general-chinese --release <code> --database-url <url>

``validate`` never connects to a database. Commands that write require an
explicit ``--database-url``; the application's DATABASE_URL is deliberately
not used, so a run cannot reach the normal development or production database
by accident. Releases are imported as ``draft``; publishing is a separate,
gated step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _session(database_url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def main(argv: list[str] | None = None) -> int:
    from app.catalog import hsk_import

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate and report; no database access")
    validate.add_argument("dataset", type=Path)
    validate.add_argument("--report-dir", type=Path, required=True)
    validate.add_argument(
        "--counts-only",
        action="store_true",
        help="omit per-row identifiers from the JSON report (use for unapproved sources)",
    )

    load = commands.add_parser("import", help="validate and upsert a draft release")
    load.add_argument("dataset", type=Path)
    load.add_argument("--database-url", required=True)
    load.add_argument("--report-dir", type=Path)

    publish = commands.add_parser("publish", help="publish a draft release (gated)")
    publish.add_argument("--track", required=True, help="learning track code, e.g. general-chinese")
    publish.add_argument("--release", required=True)
    publish.add_argument("--database-url", required=True)
    publish.add_argument("--allow-awaiting-review", action="store_true")

    args = parser.parse_args(argv)

    if args.command in ("validate", "import"):
        dataset = hsk_import.load_dataset(args.dataset)
        result = hsk_import.validate_dataset(dataset)
        report_dir = getattr(args, "report_dir", None)
        if report_dir:
            path = hsk_import.write_report(
                result, report_dir, include_rows=not getattr(args, "counts_only", False)
            )
            print(f"report: {path}")
        else:
            print(json.dumps(hsk_import.finalize_report(result), ensure_ascii=False, indent=2))
        if args.command == "validate":
            return 0
        with _session(args.database_url) as db:
            applied = hsk_import.apply_release(db, result)
        print(json.dumps({"release_id": str(applied.release_id), **applied.counts}, indent=2))
        return 0

    from sqlalchemy import select

    from app.models.learning_track import LearningTrack

    with _session(args.database_url) as db:
        track = db.scalar(select(LearningTrack).where(LearningTrack.code == args.track))
        if track is None:
            print("track not found", file=sys.stderr)
            return 2
        hsk_import.publish_release(
            db,
            track_id=track.id,
            release_code=args.release,
            allow_awaiting_review=args.allow_awaiting_review,
        )
    print(f"published {args.release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
