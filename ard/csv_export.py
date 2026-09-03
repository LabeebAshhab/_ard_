"""converting the query results to a csv file."""

import csv
import re
from datetime import datetime
from pathlib import Path

from .config import config


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "task"


def build_filename(output_prefix: str, query_id: int, when: datetime | None = None) -> str:
    """each file is named from the task's output_prefix along the query id which keeps the names different."""
    when = when or datetime.now()
    return f"{_safe(output_prefix)}_q{query_id}_{when:%d_%B_%Y}.csv"


def export_to_csv(columns: list[str], rows: list[tuple], output_prefix: str,
                  query_id: int) -> tuple[Path, int]:
    """Write the result set and return (path, row_count)."""
    path = config.output_dir / build_filename(output_prefix, query_id)
    # Two runs inside the same second would otherwise land on the same name.
    if path.exists():
        stem, suffix, n = path.stem, path.suffix, 2
        while path.exists():
            path = path.with_name(f"{stem}_{n}{suffix}")
            n += 1
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        writer.writerows(rows)
    return path, len(rows)
