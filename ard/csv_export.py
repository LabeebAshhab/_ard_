"""converting the query results to a csv file."""

import csv
import re
from datetime import datetime
from pathlib import Path

from .config import config


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "task"


def build_filename(output_prefix: str, query_id: int, when: datetime | None = None) -> str:
    """Named as <output_prefix>_<query_id>_<yyyy-mm-dd>.csv - the prefix and query
    id keep names apart, the date says which run it was."""
    when = when or datetime.now()
    return f"{_safe(output_prefix)}_{query_id}_{when:%Y-%m-%d}.csv"


def export_to_csv(result_sets: list[tuple[list[str], list[tuple]]], output_prefix: str,
                  query_id: int) -> tuple[Path, int]:
    """Write every result set of the query into one CSV and return (path, total_rows).

    A query field may hold several SELECTs; their results are stacked in the same
    file, each with its own header, separated by a blank line.
    """
    path = config.output_dir / build_filename(output_prefix, query_id)
    # Two runs on the same day would otherwise land on the same name.
    if path.exists():
        stem, suffix, n = path.stem, path.suffix, 2
        while path.exists():
            path = path.with_name(f"{stem}_{n}{suffix}")
            n += 1
    total = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        for index, (columns, rows) in enumerate(result_sets):
            if index > 0:
                writer.writerow([])  # blank line between stacked result sets
            writer.writerow(columns)
            writer.writerows(rows)
            total += len(rows)
    return path, total
