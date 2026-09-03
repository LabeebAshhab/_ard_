-- Dummy data for testing: a demo source table + rows in all 6 ARD tables.

-- ---------------------------------------------------------------- source data
-- Stands in for the real reporting source the QUERY rows select from.
DROP TABLE IF EXISTS total_transaction;
CREATE TABLE total_transaction (
    txn_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    txn_date    DATE           NOT NULL,
    customer    VARCHAR(80)    NOT NULL,
    channel     VARCHAR(30)    NOT NULL,
    amount      NUMERIC(12, 2) NOT NULL,
    status      VARCHAR(20)    NOT NULL
);

INSERT INTO total_transaction (txn_date, customer, channel, amount, status) VALUES
  ('2026-04-02', 'Rahim Traders',    'APP',    12500.00, 'SUCCESS'),
  ('2026-04-05', 'Karim Store',      'USSD',    3400.50, 'SUCCESS'),
  ('2026-04-09', 'Nagad Merchant 7', 'APP',    88000.00, 'SUCCESS'),
  ('2026-04-11', 'Shopno Mart',      'WEB',     6750.25, 'FAILED'),
  ('2026-04-15', 'Rahim Traders',    'APP',    22100.00, 'SUCCESS'),
  ('2026-04-18', 'City Pharma',      'AGENT',  15900.75, 'SUCCESS'),
  ('2026-04-21', 'Karim Store',      'APP',      980.00, 'PENDING'),
  ('2026-04-25', 'Bengal Foods',     'WEB',    47300.00, 'SUCCESS'),
  ('2026-04-28', 'City Pharma',      'USSD',    2200.00, 'FAILED'),
  ('2026-04-30', 'Nagad Merchant 7', 'AGENT', 130450.90, 'SUCCESS');

-- ---------------------------------------------------------------------- task
INSERT INTO task (task_name, description, output_prefix, is_active) VALUES
  ('Daily Transactions',    'Daily transaction dump for the ops team',    'daily_txn',      TRUE),
  ('Weekly Channel Summary','Channel-wise weekly totals for management',  'weekly_channel', TRUE),
  ('Monthly Failed Report', 'All failed transactions of the month',       'monthly_failed', TRUE),
  ('Retired Legacy Report', 'Kept for history, no longer scheduled',      'legacy',         FALSE);

-- --------------------------------------------------------------------- query
-- Task 1 carries three active queries on purpose: one task produces several CSV
-- files in a single run, each named from the task's output_prefix.
INSERT INTO query (task_id, query_text, db_target, version_no, is_active) VALUES
  (1, 'SELECT txn_id, txn_date, customer, channel, amount, status FROM total_transaction ORDER BY txn_date', 'core_db', 2, TRUE),
  (1, 'SELECT channel, COUNT(*) AS txn_count, SUM(amount) AS total_amount FROM total_transaction GROUP BY channel ORDER BY channel', 'core_db', 1, TRUE),
  (1, 'SELECT customer, SUM(amount) AS total_amount FROM total_transaction WHERE status = ''SUCCESS'' GROUP BY customer ORDER BY total_amount DESC', 'reporting_db', 1, TRUE),
  (1, 'SELECT * FROM total_transaction', 'core_db', 1, FALSE),
  (2, 'SELECT channel, COUNT(*) AS txn_count, SUM(amount) AS total_amount FROM total_transaction WHERE txn_date >= CURRENT_DATE - 7 GROUP BY channel', 'reporting_db', 1, TRUE),
  (3, 'SELECT txn_id, txn_date, customer, amount FROM total_transaction WHERE status = ''FAILED'' ORDER BY txn_date', 'core_db', 1, TRUE),
  (4, 'SELECT 1', 'core_db', 1, FALSE);

-- ------------------------------------------------------------------ schedule
-- day_spec: unused for DAILY, weekday name for WEEKLY, day-of-month for MONTHLY.
INSERT INTO schedule (task_id, schedule_time, frequency, day_spec, is_active) VALUES
  (1, '07:30', 'DAILY',   NULL,     TRUE),
  (1, '18:00', 'DAILY',   NULL,     TRUE),
  (2, '09:00', 'WEEKLY',  'MONDAY', TRUE),
  (3, '06:00', 'MONTHLY', '1',      TRUE),
  (4, '10:00', 'DAILY',   NULL,     FALSE);

-- -------------------------------------------------------------- email_config
INSERT INTO email_config (task_id, subject, body, signature) VALUES
  (1, 'Daily Transactions Report',     'Please find attached the daily transaction report.', E'Regards,\nARD Automation'),
  (2, 'Weekly Channel Summary',        'Weekly channel-wise summary is attached.',           E'Regards,\nARD Automation'),
  (3, 'Monthly Failed Transactions',   'Monthly failed transaction report is attached.',     E'Regards,\nARD Automation'),
  (4, 'Legacy Report',                 'Legacy report.',                                     E'Regards,\nARD Automation');

-- ----------------------------------------------------------------- recipient
INSERT INTO recipient (config_id, email_address, recipient_type, display_name, is_active) VALUES
  (1, 'ops.lead@example.com',      'TO',  'Ops Lead',        TRUE),
  (1, 'ops.team@example.com',      'CC',  'Ops Team',        TRUE),
  (1, 'audit@example.com',         'BCC', 'Audit',           TRUE),
  (1, 'left.employee@example.com', 'TO',  'Former Employee', FALSE),
  (2, 'management@example.com',    'TO',  'Management',      TRUE),
  (2, 'finance@example.com',       'CC',  'Finance',         TRUE),
  (3, 'risk@example.com',          'TO',  'Risk Team',       TRUE),
  (4, 'nobody@example.com',        'TO',  'Nobody',          FALSE);

-- ------------------------------------------------------------- execution_log
-- Sample history: a delivered run, a query-level failure, and a run still going.
INSERT INTO execution_log (task_id, schedule_id, run_started_at, csv_file_path, row_count, status, error_message, delivered_at) VALUES
  (1, 1, '2026-08-30 07:30:04', 'output/daily_txn_q1_20260830_073004.csv',      10, 'SENT',    NULL,                                    '2026-08-30 07:30:19'),
  (1, 1, '2026-08-30 07:30:04', 'output/daily_txn_q2_20260830_073005.csv',       5, 'SENT',    NULL,                                    '2026-08-30 07:30:19'),
  (2, 3, '2026-08-24 09:00:02', 'output/weekly_channel_q5_20260824_090002.csv',  4, 'SENT',    NULL,                                    '2026-08-24 09:00:11'),
  (3, 4, '2026-08-01 06:00:01', NULL,                                          NULL, 'FAILED',  'relation "total_transaction" does not exist', NULL),
  (1, 2, '2026-08-30 18:00:03', 'output/daily_txn_q1_20260830_180003.csv',      10, 'SUCCESS', NULL,                                    NULL);
