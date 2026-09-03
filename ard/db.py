"""Database conn."""

import calendar
import contextlib
from datetime import date, datetime, time
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .config import config


@contextlib.contextmanager
def connect(dsn: str | None = None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn or config.app_dsn, row_factory=dict_row) as conn:
        
        conn.execute(f"SET TIME ZONE '{config.timezone}'")
        yield conn


def fetch_all(conn: psycopg.Connection, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(conn: psycopg.Connection, sql: str, params: tuple = ()) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


# ------------------------------------------------------------------ read side

def due_schedules(conn: psycopg.Connection, window_start: time, window_end: time,
                  today: date) -> list[dict]:
    """Active scheduler"""
    if window_start <= window_end:
        time_clause = "s.schedule_time >= %s AND s.schedule_time <= %s"
    else:
        time_clause = "(s.schedule_time >= %s OR s.schedule_time <= %s)"
    params: tuple[Any, ...] = (window_start, window_end)

    sql = f"""
        SELECT s.schedule_id, s.task_id, s.schedule_time, s.frequency, s.day_spec,
               t.task_name, t.output_prefix
        FROM schedule s
        JOIN task t ON t.task_id = s.task_id
        WHERE s.is_active AND t.is_active AND {time_clause}
        ORDER BY s.schedule_time
    """
    return [r for r in fetch_all(conn, sql, params) if matches_day(r, today)]


def matches_day(schedule: dict, today: date) -> bool:
    """For Day Matching"""
    frequency = schedule["frequency"]
    day_spec = (schedule["day_spec"] or "").strip().upper()

    if frequency == "DAILY":
        return True
    if frequency == "WEEKLY":
        return day_spec == today.strftime("%A").upper()
    if frequency == "MONTHLY":
        if day_spec == "LAST":
            return today.day == calendar.monthrange(today.year, today.month)[1]
        return day_spec.isdigit() and int(day_spec) == today.day
    return False


def already_ran(conn: psycopg.Connection, schedule_id: int, occurrence: datetime) -> bool:
    """Stopping duplicate runs"""
    row = fetch_one(
        conn,
        """
        SELECT 1 FROM execution_log
        WHERE schedule_id = %s AND run_started_at >= %s
        LIMIT 1
        """,
        (schedule_id, occurrence),
    )
    return row is not None


def active_queries(conn: psycopg.Connection, task_id: int) -> list[dict]:
    """All the queries a task can"""
    return fetch_all(
        conn,
        """
        SELECT query_id, task_id, query_text, db_target, version_no
        FROM query
        WHERE task_id = %s AND is_active
        ORDER BY query_id
        """,
        (task_id,),
    )


def task_by_id(conn: psycopg.Connection, task_id: int) -> dict | None:
    return fetch_one(
        conn,
        "SELECT task_id, task_name, description, output_prefix, is_active "
        "FROM task WHERE task_id = %s",
        (task_id,),
    )


def first_schedule_for_task(conn: psycopg.Connection, task_id: int) -> dict | None:
    """For the manual trigger"""
    return fetch_one(
        conn,
        "SELECT schedule_id FROM schedule WHERE task_id = %s "
        "ORDER BY is_active DESC, schedule_id LIMIT 1",
        (task_id,),
    )


def email_config(conn: psycopg.Connection, task_id: int) -> dict | None:
    return fetch_one(
        conn,
        "SELECT config_id, task_id, subject, body, signature "
        "FROM email_config WHERE task_id = %s",
        (task_id,),
    )


def active_recipients(conn: psycopg.Connection, config_id: int) -> list[dict]:
    return fetch_all(
        conn,
        """
        SELECT recipient_id, email_address, recipient_type, display_name
        FROM recipient
        WHERE config_id = %s AND is_active
        ORDER BY recipient_id
        """,
        (config_id,),
    )


def run_source_query(dsn: str, query_text: str) -> tuple[list[str], list[tuple]]:
    """A task's SQL on its target database which return (columns, rows)."""
    with psycopg.connect(dsn) as conn:
        conn.execute(f"SET TIME ZONE '{config.timezone}'")
        with conn.cursor() as cur:
            cur.execute(query_text)
            columns = [c.name for c in (cur.description or [])]
            rows = cur.fetchall() if cur.description else []
    return columns, rows


# writing the log into exe_table


def log_run_started(conn: psycopg.Connection, task_id: int, schedule_id: int) -> int:
    row = fetch_one(
        conn,
        """
        INSERT INTO execution_log (task_id, schedule_id, run_started_at, status)
        VALUES (%s, %s, CURRENT_TIMESTAMP, 'RUNNING')
        RETURNING log_id
        """,
        (task_id, schedule_id),
    )
    conn.commit()
    return row["log_id"]


def log_export_success(conn: psycopg.Connection, log_id: int, csv_path: str,
                       row_count: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE execution_log SET csv_file_path = %s, row_count = %s, "
            "status = 'SUCCESS' WHERE log_id = %s",
            (csv_path, row_count, log_id),
        )
    conn.commit()


def log_failure(conn: psycopg.Connection, log_id: int, error_message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE execution_log SET status = 'FAILED', error_message = %s "
            "WHERE log_id = %s",
            (error_message[:4000], log_id),
        )
    conn.commit()


def log_delivered(conn: psycopg.Connection, log_ids: list[int]) -> None:
    """Stamp delivered_at with the time the mail was accepted by the SMTP server."""
    if not log_ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE execution_log SET status = 'SENT', "
            "delivered_at = CURRENT_TIMESTAMP WHERE log_id = ANY(%s)",
            (log_ids,),
        )
    conn.commit()
