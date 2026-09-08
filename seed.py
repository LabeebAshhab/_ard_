"""Standalone dummy-data loader - NOT part of the operational app.

Run it by hand to reset the database to a known demo state:

    python seed.py

It applies, in order:
  1. sql/schema.sql    - drops and recreates the 6 ARD tables (this DELETES all
                         existing data).
  2. sql/seed_data.sql - the demo source table and sample rows.

Loading test data is deliberately kept out of the `ard` package so the app code
holds only real operations. Never run this against a database with real reports -
it wipes everything first.
"""

from ard import db
from ard.config import BASE_DIR

SQL_FILES = [
    BASE_DIR / "sql" / "schema.sql",     # drops + recreates the tables (wipes data)
    BASE_DIR / "sql" / "seed_data.sql",  # demo source table + dummy rows
]


def load_dummy_data() -> None:
    with db.connect() as conn:
        for path in SQL_FILES:
            conn.execute(path.read_text(encoding="utf-8"))
            conn.commit()
            print(f"applied {path.name}")
    print("dummy data loaded.")


if __name__ == "__main__":
    load_dummy_data()
