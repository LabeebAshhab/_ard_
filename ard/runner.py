"""One run of one task: query -> CSV -> e-mail -> execution log."""

import logging
from pathlib import Path

import psycopg

from . import db
from .config import config
from .csv_export import export_to_csv
from .mailer import send

log = logging.getLogger(__name__)


def run_task(conn: psycopg.Connection, task: dict, schedule_id: int) -> dict:
    """Execute every active query of the task, mail the CSVs, and record the run.

    A log row is written per query the moment it starts (status RUNNING), moves to
    SUCCESS once its CSV exists or FAILED with the error, and finally to SENT with
    delivered_at once the mail has actually gone out.
    """
    task_id = task["task_id"]
    queries = db.active_queries(conn, task_id)
    if not queries:
        log.warning("task %s (%s) has no active query - skipped", task_id, task["task_name"])
        return {"task_id": task_id, "files": [], "sent": False}

    attachments: list[Path] = []
    exported_log_ids: list[int] = []

    for query in queries:
        log_id = db.log_run_started(conn, task_id, schedule_id)
        try:
            result_sets = db.run_source_query(
                config.dsn_for_target(query["db_target"]), query["query_text"]
            )
            csv_path, row_count = export_to_csv(
                result_sets, task["output_prefix"], query["query_id"]
            )
            db.log_export_success(conn, log_id, str(csv_path), row_count)
            attachments.append(csv_path)
            exported_log_ids.append(log_id)
            log.info("query %s -> %s (%s rows)", query["query_id"], csv_path.name, row_count)
        except Exception as exc:
            # One bad query must not stop the other files of the same task.
            db.log_failure(conn, log_id, f"{type(exc).__name__}: {exc}")
            log.exception("query %s failed for task %s", query["query_id"], task_id)

    if not attachments:
        return {"task_id": task_id, "files": [], "sent": False}

    email_cfg = db.email_config(conn, task_id)
    if email_cfg is None:
        for log_id in exported_log_ids:
            db.log_failure(conn, log_id, "no EMAIL_CONFIG for this task")
        return {"task_id": task_id, "files": attachments, "sent": False}

    recipients = db.active_recipients(conn, email_cfg["config_id"])
    try:
        send(email_cfg, recipients, attachments)
        db.log_delivered(conn, exported_log_ids)
        log.info("task %s delivered to %s recipient(s)", task_id, len(recipients))
        sent = True
        # After Delivery the CSV files are deleted. 
        
        _cleanup_files(attachments)
    except Exception as exc:
        for log_id in exported_log_ids:
            db.log_failure(conn, log_id, f"delivery failed - {type(exc).__name__}: {exc}")
        log.exception("delivery failed for task %s", task_id)
        sent = False

    return {"task_id": task_id, "files": attachments, "sent": sent}


def _cleanup_files(paths: list[Path]) -> None:
    """Delete the local CSV files."""
    for path in paths:
        try:
            path.unlink(missing_ok=True)
            log.info("deleted local CSV after SENT: %s", path.name)
        except OSError as exc:
            log.warning("could not delete %s: %s", path, exc)


def run_task_by_id(conn: psycopg.Connection, task_id: int) -> dict:
    """Manual trigger, ignoring the schedule time - used by `--run-task`."""
    task = db.task_by_id(conn, task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found")
    schedule = db.first_schedule_for_task(conn, task_id)
    if schedule is None:
        raise ValueError(f"task {task_id} has no schedule row to log against")
    return run_task(conn, task, schedule["schedule_id"])
