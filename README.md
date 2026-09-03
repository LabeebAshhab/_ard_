# Automated Report Delivery — with GUI

The same pipeline as the folder above, plus a Tkinter desktop window for the setup
step the notes describe ("GUI initial process — put data into tables") and for
watching the automation run.

Everything the CLI version does still works here; the GUI is an extra front end over
the same `ard` package.

## Setup

```bash
pip install -r requirements.txt
```

Tkinter ships with the standard Windows Python installer — no extra package.

Postgres (skip if the `ard-postgres` container from the other folder is already up —
both folders talk to the same database):

```bash
docker compose up -d
```

```bash
python -m ard --init-db --seed
```

## Open the window

```bash
python gui.py
```

`python -m ard --gui` does the same thing.

## The tabs

| Tab | What you do there |
| --- | --- |
| 1. Task | Add a task, name it, set the CSV output prefix, switch it on or off. |
| 2. Query | Write the SQL for a task. A task can hold several — each one becomes its own CSV. |
| 3. Schedule | Time of day plus DAILY / WEEKLY / MONTHLY and the day rule. |
| 4. Email config | Subject, body and signature for the task's e-mail. |
| 5. Recipient | To / Cc / Bcc addresses; `Active` off keeps the row for history but skips it. |
| 6. Run and log | Start/stop the scheduler, run one task now, watch the live output and `EXECUTION_LOG`. |

Every tab is a grid on top and a form below: click a row to load it, **New** clears the
form, **Save** inserts or updates, **Delete** removes it (and its dependent rows).

`day_spec` is ignored for DAILY, holds a weekday name (`MONDAY`) for WEEKLY, and a
day-of-month number or `LAST` for MONTHLY.

## The run tab

- **Start scheduler** runs the 30-minute poller in a background thread, so the window
  stays usable; **Stop scheduler** interrupts it immediately.
- **Check now (one tick)** forces a single poll.
- **Run task** executes one task right away, ignoring its schedule time — the quickest
  way to test a new query and e-mail.
- The execution log refreshes itself after every run.

## How a run works

Same as the CLI version:

1. The poller reads `SCHEDULE` for active rows whose `schedule_time` falls in
   `[now - interval, now]` and whose frequency/day rule matches today; a schedule that
   already ran today is skipped.
2. Every active `QUERY` of the due task runs on the database named by `db_target`.
3. Each result set is written to `output/<output_prefix>_q<query_id>_<timestamp>.csv`.
4. The CSVs are attached to one e-mail built from `EMAIL_CONFIG` and the active
   `RECIPIENT` rows (Bcc stays out of the headers).
5. `EXECUTION_LOG` gets a row per query: `RUNNING` at the start, `SUCCESS` with the file
   path and row count (or `FAILED` with the error), and `SENT` with `delivered_at` once
   the mail has actually gone out.

A failing query is logged and skipped; the other files of the task still go out.

## E-mail

`SMTP_DRY_RUN=true` in `.env` (the default) writes the message to `logs/*.eml` instead
of sending, so the whole thing can be demonstrated without an SMTP account.

## Files

```
gui.py                shortcut: python gui.py
ard/gui/app.py        window, tabs, DPI/scaling handling
ard/gui/spec.py       the field list for each editable table
ard/gui/crud_tab.py   the generic grid + form tab
ard/gui/run_tab.py    scheduler controls, live log, EXECUTION_LOG viewer
ard/crud.py           insert / update / delete for the five setup tables
ard/…                 the pipeline itself (config, db, csv_export, mailer, runner, scheduler)
sql/                  schema.sql and seed_data.sql
```
