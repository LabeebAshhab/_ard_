"""Generic insert / update / delete for the five configuration tables."""

import psycopg

from . import db

# Tables the GUI is allowed to write, with their primary key.
EDITABLE = {
    "task": "task_id",
    "query": "query_id",
    "schedule": "schedule_id",
    "email_config": "config_id",
    "recipient": "recipient_id",
}


def _check(table: str) -> str:
    if table not in EDITABLE:
        raise ValueError(f"table {table!r} is not editable from the GUI")
    return EDITABLE[table]


def list_rows(conn: psycopg.Connection, table: str, columns: list[str],
              order_by: str | None = None) -> list[dict]:
    pk = _check(table)
    cols = ", ".join(columns)
    return db.fetch_all(conn, f"SELECT {cols} FROM {table} ORDER BY {order_by or pk}")


def insert_row(conn: psycopg.Connection, table: str, values: dict) -> int:
    pk = _check(table)
    cols = list(values)
    placeholders = ", ".join(["%s"] * len(cols))
    row = db.fetch_one(
        conn,
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING {pk}",
        tuple(values[c] for c in cols),
    )
    conn.commit()
    return row[pk]


def update_row(conn: psycopg.Connection, table: str, pk_value: int, values: dict) -> None:
    pk = _check(table)
    assignments = ", ".join(f"{c} = %s" for c in values)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {table} SET {assignments} WHERE {pk} = %s",
            (*values.values(), pk_value),
        )
    conn.commit()


def delete_row(conn: psycopg.Connection, table: str, pk_value: int) -> None:
    pk = _check(table)
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {pk} = %s", (pk_value,))
    conn.commit()


def options_for(conn: psycopg.Connection, table: str) -> list[tuple[int, str]]:
    """(id, label) pairs used to fill the foreign-key dropdowns."""
    if table == "task":
        rows = db.fetch_all(conn, "SELECT task_id AS id, task_name AS label FROM task ORDER BY task_id")
    elif table == "email_config":
        rows = db.fetch_all(
            conn,
            "SELECT c.config_id AS id, t.task_name AS label FROM email_config c "
            "JOIN task t ON t.task_id = c.task_id ORDER BY c.config_id",
        )
    else:
        raise ValueError(f"no lookup defined for {table!r}")
    return [(r["id"], f"{r['id']} - {r['label']}") for r in rows]
