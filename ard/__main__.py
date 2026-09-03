"""CLI entry point: python -m ard [--gui | --init-db | --poll-once | --run-task N | --status]"""

import argparse
import logging
import sys
from pathlib import Path

from . import db
from .config import BASE_DIR, config
from .runner import run_task_by_id
from .scheduler import poll_once, run_forever


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.log_dir / "ard.log", encoding="utf-8"),
        ],
    )


def init_db(with_seed: bool) -> None:
    """Created the schema and loaded the dummy test data."""
    files = [BASE_DIR / "sql" / "schema.sql"]
    if with_seed:
        files.append(BASE_DIR / "sql" / "seed_data.sql")
    with db.connect() as conn:
        for path in files:
            conn.execute(Path(path).read_text(encoding="utf-8"))
            conn.commit()
            print(f"applied {path.name}")


def show_status() -> None:
    with db.connect() as conn:
        rows = db.fetch_all(
            conn,
            """
            SELECT l.log_id, t.task_name, l.run_started_at, l.status,
                   l.row_count, l.csv_file_path, l.delivered_at, l.error_message
            FROM execution_log l
            JOIN task t ON t.task_id = l.task_id
            ORDER BY l.log_id DESC
            LIMIT 20
            """,
        )
    for r in rows:
        print(f"[{r['log_id']:>4}] {r['run_started_at']:%Y-%m-%d %H:%M:%S} "
              f"{r['status']:<8} {r['task_name']:<24} rows={r['row_count']} "
              f"file={r['csv_file_path'] or '-'} delivered={r['delivered_at'] or '-'}"
              + (f" err={r['error_message']}" if r["error_message"] else ""))


def main() -> int:
    parser = argparse.ArgumentParser(prog="ard", description="Automated Report Delivery")
    parser.add_argument("--init-db", action="store_true", help="create the 6 tables")
    parser.add_argument("--seed", action="store_true", help="load dummy data (with --init-db)")
    parser.add_argument("--poll-once", action="store_true", help="run one scheduler tick")
    parser.add_argument("--run-task", type=int, metavar="ID",
                        help="run one task now, ignoring its schedule time")
    parser.add_argument("--status", action="store_true", help="show recent execution_log rows")
    parser.add_argument("--gui", action="store_true", help="open the desktop window")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.gui:
        from .gui import main as gui_main
        return gui_main()
    if args.init_db:
        init_db(args.seed)
        return 0
    if args.status:
        show_status()
        return 0
    if args.run_task is not None:
        with db.connect() as conn:
            result = run_task_by_id(conn, args.run_task)
        print(f"task {result['task_id']}: {len(result['files'])} file(s), sent={result['sent']}")
        return 0
    if args.poll_once:
        print(f"{poll_once()} task(s) run")
        return 0

    run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
