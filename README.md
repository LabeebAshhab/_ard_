# Automated Report Delivery (ARD)

ARD runs saved SQL queries on a schedule, exports each result set to a CSV file, and
e-mails those files to a configured list of recipients. Everything a report needs —
the queries, the schedule, the e-mail text, and the recipient list — lives in a
PostgreSQL database, so reports are configured as data rather than code.

The project ships two front ends over the same `ard` package:

- a **command-line interface** (`python -m ard …`) for initialising the database and
  running the scheduler, and
- a **Tkinter desktop GUI** (`python gui.py`) for editing every setup table and
  watching the automation run.

## How it works

1. A poller checks the `SCHEDULE` table every `POLL_INTERVAL_MINUTES` (30 by default).
2. For each active schedule whose `schedule_time` falls in the current window and whose
   DAILY / WEEKLY / MONTHLY rule matches today, ARD runs every active `QUERY` of that
   task against the database named by the query's `db_target`.
3. Each query is written to its own `output/<output_name>_<yyyymmdd>.csv`, where
   `output_name` is the file-name prefix set on that query (a query left blank
   falls back to `query_<query_id>`).
4. All of a task's CSVs are attached to a single e-mail built from its `EMAIL_CONFIG`
   and active `RECIPIENT` rows.
5. `EXECUTION_LOG` records each query's progress: `RUNNING` at the start, then `SUCCESS`
   (with file path and row count) or `FAILED` (with the error), and finally `SENT` with
   `delivered_at` once the mail has gone out.

A schedule that already ran today is skipped, and a failing query is logged and skipped
without blocking the rest of the task.

## Requirements

- **Python 3.10+** (Tkinter is included with the standard Windows/macOS Python installer)
- **Docker Desktop** (for the bundled PostgreSQL, or bring your own Postgres)

## Setup from scratch

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

Using a virtual environment is recommended:

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

(On macOS/Linux: `source .venv/bin/activate`.)

### 2. Start the database with Docker

The included `docker-compose.yml` starts PostgreSQL 16 and [DBGate](https://dbgate.org/)
(a web database browser):

```bash
docker compose up -d
```

This gives you:

| Service  | Address           | Credentials                          |
| -------- | ----------------- | ------------------------------------ |
| Postgres | `localhost:5432`  | db `ard`, user `ard`, pass `ard_pass` |
| DBGate   | http://localhost:5000 | connect to the Postgres service above |

Data persists in the `ard_pgdata` Docker volume between restarts. To stop the stack:

```bash
docker compose down
```

### 3. Create the `.env` file

Copy the example and adjust it if needed:

```bash
cp .env.example .env
```

The defaults match the Docker database and enable SMTP dry-run mode. Key settings:

| Variable                | Purpose                                                                 |
| ----------------------- | ----------------------------------------------------------------------- |
| `ARD_DB_*`              | Connection to the application database (the 6 ARD tables).              |
| `POLL_INTERVAL_MINUTES` | How often the scheduler checks for due tasks (default 30).              |
| `APP_TIMEZONE`          | Timezone for schedule matching and log timestamps (default `Asia/Dhaka`). |
| `SOURCE_DB_TARGETS`     | Named DSNs that queries can run against, as `name=dsn,name=dsn`. An unknown `db_target` falls back to the application DB. |
| `SMTP_DRY_RUN`          | `true` writes the e-mail to `logs/*.eml` instead of sending — use for testing. |
| `SMTP_*`                | SMTP host, port, credentials and `From` address for real delivery.      |

### 4. Build the database schema

Create the six (empty) tables:

```bash
python -m ard --init-db
```

For a quick demo, load the bundled dummy data instead. `seed.py` is a standalone
script (kept out of the app code) that **wipes every table** and reloads the demo
dataset — schema plus sample rows in one step:

```bash
python seed.py
```

## Using the GUI

Open the desktop window:

```bash
python gui.py
```

(`python -m ard --gui` does the same thing.)

Each tab is a grid on top and a form below: click a row to load it, **New** clears the
form, **Save** inserts or updates, and **Delete** removes the row and its dependents.

| Tab             | What you do there                                                                 |
| --------------- | --------------------------------------------------------------------------------- |
| 1. Task         | Add a task, name it, switch it on or off.                                         |
| 2. Query        | Write the SQL for a task and give it an **Output name** (the CSV file-name prefix; `_<yyyymmdd>.csv` is added automatically). One task can hold several queries — each becomes its own named CSV. |
| 3. Schedule     | Set a time of day plus DAILY / WEEKLY / MONTHLY and the day rule.                  |
| 4. Email config | Subject, body and signature for the task's e-mail.                                 |
| 5. Recipient    | TO / CC / BCC addresses; unchecking `Active` keeps a row for history but skips it. |
| 6. Run and log  | Start/stop the scheduler, run one task now, and watch the live output and `EXECUTION_LOG`. |

The `day_spec` field is ignored for DAILY, holds a weekday name (e.g. `MONDAY`) for
WEEKLY, and a day-of-month number or `LAST` for MONTHLY.

**Run and log tab:**

- **Start scheduler** runs the poller in a background thread so the window stays usable;
  **Stop scheduler** interrupts it immediately.
- **Check now (one tick)** forces a single poll.
- **Run task** executes one task right away, ignoring its schedule time — the quickest
  way to test a new query and e-mail.
- The execution log refreshes after every run.

## Using the CLI

| Command                          | What it does                                              |
| -------------------------------- | -------------------------------------------------------- |
| `python -m ard --init-db`        | Create the six (empty) tables.                           |
| `python seed.py`                 | Wipe every table and reload the bundled dummy data.      |
| `python -m ard`                  | Run the scheduler continuously (poll forever).           |
| `python -m ard --poll-once`      | Run a single scheduler tick and exit.                    |
| `python -m ard --run-task N`     | Run task `N` now, ignoring its schedule time.            |
| `python -m ard --status`         | Print the 20 most recent `execution_log` rows.           |
| `python -m ard --gui`            | Open the desktop window.                                 |
| `-v` / `--verbose`               | Enable debug logging (added to any command above).       |

## E-mail

With `SMTP_DRY_RUN=true` (the default) each message is written to `logs/*.eml` instead
of being sent, so the whole pipeline can be demonstrated without an SMTP account. Set it
to `false` and fill in the `SMTP_*` values to deliver for real (Bcc recipients stay out
of the visible headers).

## Database tables

| Table           | Holds                                                                       |
| --------------- | --------------------------------------------------------------------------- |
| `task`          | One report definition: name, description, active flag.                      |
| `query`         | The SQL for a task, its CSV `output_name` prefix, and the `db_target` it runs against (many per task). |
| `schedule`      | Time of day, frequency (DAILY/WEEKLY/MONTHLY) and day rule for a task.       |
| `email_config`  | Subject, body and signature — one row per task.                             |
| `recipient`     | TO / CC / BCC addresses linked to a task's `email_config`.                  |
| `execution_log` | One row per query run, tracking `RUNNING → SUCCESS/FAILED → SENT`.           |

## Project layout

```
gui.py                shortcut launcher: python gui.py
seed.py               standalone dummy-data loader (wipe + reload demo data)
docker-compose.yml    Postgres 16 + DBGate
.env.example          template for your local .env
requirements.txt      Python dependencies
ard/
  __main__.py         the CLI (python -m ard …)
  config.py           runtime configuration loaded from .env
  db.py               database connection helpers
  crud.py             insert / update / delete for the five setup tables
  csv_export.py       result set → CSV file
  mailer.py           builds and sends (or dry-runs) the e-mail
  runner.py           runs one task: queries → CSVs → e-mail → log
  scheduler.py        the polling loop and per-tick due-task logic
  gui/
    app.py            window, tabs, DPI/scaling handling
    spec.py           the field list for each editable table
    crud_tab.py       the generic grid + form tab
    run_tab.py        scheduler controls, live log, EXECUTION_LOG viewer
sql/
  schema.sql          the 6-table schema
  seed_data.sql       dummy data loaded by seed.py
output/               generated CSV files
logs/                 ard.log and dry-run .eml files
```

See `ARD_Setup_Guide.pdf` for a step-by-step walkthrough with screenshots.

## License

Released under the [MIT License](LICENSE).
