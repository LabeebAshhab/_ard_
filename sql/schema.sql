-- Automated Report Delivery System - 6 table schema (REPORT removed).

DROP TABLE IF EXISTS execution_log CASCADE;
DROP TABLE IF EXISTS recipient    CASCADE;
DROP TABLE IF EXISTS email_config CASCADE;
DROP TABLE IF EXISTS schedule     CASCADE;
DROP TABLE IF EXISTS query        CASCADE;
DROP TABLE IF EXISTS task         CASCADE;

DROP TYPE IF EXISTS frequency_enum      CASCADE;
DROP TYPE IF EXISTS recipient_type_enum CASCADE;
DROP TYPE IF EXISTS run_status_enum     CASCADE;

CREATE TYPE frequency_enum      AS ENUM ('DAILY', 'WEEKLY', 'MONTHLY');
CREATE TYPE recipient_type_enum AS ENUM ('TO', 'CC', 'BCC');
-- RUNNING is an in-flight marker: the row is written the moment the program starts
-- the run, then moved to SUCCESS / FAILED / SENT as the run progresses.
CREATE TYPE run_status_enum     AS ENUM ('RUNNING', 'SUCCESS', 'FAILED', 'SENT');

CREATE TABLE task (
    task_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_name   VARCHAR(120) NOT NULL,
    description VARCHAR(255),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE query (
    query_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id     BIGINT       NOT NULL REFERENCES task(task_id) ON DELETE CASCADE,
    query_text  TEXT         NOT NULL,
    -- File-name prefix for this query's CSV. The run appends _<yyyymmdd>.csv, so
    -- the user gives only the prefix. Blank falls back to query_<query_id>.
    output_name VARCHAR(120),
    db_target   VARCHAR(120) NOT NULL,
    version_no  INT          NOT NULL DEFAULT 1,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE schedule (
    schedule_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id       BIGINT        NOT NULL REFERENCES task(task_id) ON DELETE CASCADE,
    schedule_time TIME          NOT NULL,
    frequency     frequency_enum NOT NULL,
    day_spec      VARCHAR(40),
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE
);

-- 1:1 with task, so task_id is unique.
CREATE TABLE email_config (
    config_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id   BIGINT       NOT NULL UNIQUE REFERENCES task(task_id) ON DELETE CASCADE,
    subject   VARCHAR(200) NOT NULL,
    body      TEXT,
    signature TEXT
);

CREATE TABLE recipient (
    recipient_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_id      BIGINT              NOT NULL REFERENCES email_config(config_id) ON DELETE CASCADE,
    email_address  VARCHAR(180)        NOT NULL,
    recipient_type recipient_type_enum NOT NULL DEFAULT 'TO',
    display_name   VARCHAR(120),
    is_active      BOOLEAN             NOT NULL DEFAULT TRUE
);

CREATE TABLE execution_log (
    log_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id        BIGINT NOT NULL REFERENCES task(task_id)     ON DELETE CASCADE,
    schedule_id    BIGINT NOT NULL REFERENCES schedule(schedule_id) ON DELETE CASCADE,
    run_started_at TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    csv_file_path  VARCHAR(255),
    row_count      INT,
    status         run_status_enum NOT NULL DEFAULT 'RUNNING',
    error_message  TEXT,
    delivered_at   TIMESTAMP
);

CREATE INDEX idx_query_task_active    ON query(task_id)    WHERE is_active;
CREATE INDEX idx_schedule_active      ON schedule(schedule_time) WHERE is_active;
CREATE INDEX idx_recipient_config     ON recipient(config_id) WHERE is_active;
-- The duplicate-run guard reads this: "did this schedule already fire today?"
CREATE INDEX idx_log_schedule_started ON execution_log(schedule_id, run_started_at DESC);
