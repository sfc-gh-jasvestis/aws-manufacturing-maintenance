-- ============================================================================
-- 06_INTELLIGENCE.SQL - search, anomaly detection, semantic view, agent,
-- live-telemetry alert and on-demand refresh DAG.
-- Run with snowflake/run_intelligence.py (substitutes validated __DEMO_DB__ /
-- __DEMO_WH__ / __ALERT_EMAIL__). Requires 00-05 and aws/setup_aws.py.
-- Alerts and tasks are created SUSPENDED; run them with EXECUTE ALERT / EXECUTE TASK.
-- ============================================================================
USE DATABASE __DEMO_DB__;
CREATE SCHEMA IF NOT EXISTS SEARCH;
CREATE SCHEMA IF NOT EXISTS APP;

-- ---------- Synthetic maintenance knowledge base (clearly synthetic SOPs) ----------
CREATE OR REPLACE TABLE SEARCH.MAINTENANCE_DOCS AS
WITH causes AS (
  SELECT DISTINCT r.ROOT_CAUSE, m.CATEGORY
  FROM RAW.SENSOR_READINGS r JOIN RAW.MACHINES m ON m.ID = r.ENTITY_ID
  WHERE r.ROOT_CAUSE IS NOT NULL AND r.FAILURE_COUNT > 0
)
SELECT
  'SOP-' || LPAD(ROW_NUMBER() OVER (ORDER BY CATEGORY, ROOT_CAUSE)::VARCHAR, 3, '0') AS DOC_ID,
  'SOP' AS DOC_TYPE,
  CATEGORY,
  ROOT_CAUSE,
  CATEGORY || ' - ' || ROOT_CAUSE || ' response procedure' AS TITLE,
  'Synthetic demo SOP. Equipment class: ' || CATEGORY || '. Failure mode: ' || ROOT_CAUSE || '. '
  || 'Step 1: apply lockout-tagout and confirm the stop code on the machine controller. '
  || 'Step 2: ' || CASE
       WHEN ROOT_CAUSE ILIKE '%spindle%' THEN 'measure spindle run-out and bearing temperature, check lubrication flow and replace the bearing kit if run-out exceeds tolerance.'
       WHEN ROOT_CAUSE ILIKE '%tool%' OR ROOT_CAUSE ILIKE '%coolant%' THEN 'inspect the tool holder and coolant delivery, verify coolant concentration and pump pressure, and re-zero tool offsets.'
       WHEN ROOT_CAUSE ILIKE '%heater%' OR ROOT_CAUSE ILIKE '%cooling%' OR ROOT_CAUSE ILIKE '%screw%' THEN 'verify barrel zone thermocouples against a reference probe, check heater band resistance and mold cooling flow, and inspect screw wear.'
       WHEN ROOT_CAUSE ILIKE '%hydraulic%' OR ROOT_CAUSE ILIKE '%die%' OR ROOT_CAUSE ILIKE '%clutch%' THEN 'check hydraulic pressure and seals for leaks, verify die alignment with the setup gauge and test clutch-brake stopping time.'
       WHEN ROOT_CAUSE ILIKE '%servo%' OR ROOT_CAUSE ILIKE '%gripper%' OR ROOT_CAUSE ILIKE '%cable%' THEN 'read the servo drive fault log, inspect the gripper and dress-pack cables for wear, and re-teach the home position.'
       WHEN ROOT_CAUSE ILIKE '%grid%' THEN 'confirm utility status with the plant electrical lead, check UPS logs and restart in the documented sequence.'
       ELSE 'inspect the affected assembly, record readings and escalate to the reliability engineer if readings are out of tolerance.'
     END
  || ' Step 3: if vibration exceeds 6 mm/s or temperature exceeds 75 C after restart, raise a work order and keep the machine on watch. '
  || 'Step 4: record root cause and parts used in the CMMS.' AS CONTENT
FROM causes;

CREATE OR REPLACE CORTEX SEARCH SERVICE SEARCH.MAINTENANCE_SOP_SEARCH
  ON CONTENT
  ATTRIBUTES CATEGORY, ROOT_CAUSE
  WAREHOUSE = __DEMO_WH__
  TARGET_LAG = '7 days'
AS (SELECT DOC_ID, TITLE, CATEGORY, ROOT_CAUSE, CONTENT FROM SEARCH.MAINTENANCE_DOCS);

-- ---------- Vibration anomaly detection (train first 75 days, detect last 15) ----------
CREATE OR REPLACE VIEW ML.VIBRATION_SERIES AS
SELECT ENTITY_ID, EVENT_DATE::TIMESTAMP_NTZ AS TS, VIBRATION_MM_S::FLOAT AS VIBRATION
FROM RAW.SENSOR_READINGS;
CREATE OR REPLACE VIEW ML.VIBRATION_TRAIN AS
SELECT * FROM ML.VIBRATION_SERIES WHERE TS < (SELECT DATEADD(day, -15, MAX(TS)) FROM ML.VIBRATION_SERIES);
CREATE OR REPLACE VIEW ML.VIBRATION_DETECT AS
SELECT * FROM ML.VIBRATION_SERIES WHERE TS >= (SELECT DATEADD(day, -15, MAX(TS)) FROM ML.VIBRATION_SERIES);

CREATE OR REPLACE SNOWFLAKE.ML.ANOMALY_DETECTION ML.VIBRATION_ANOMALY_MODEL(
  INPUT_DATA => SYSTEM$REFERENCE('VIEW', 'ML.VIBRATION_TRAIN'),
  SERIES_COLNAME => 'ENTITY_ID', TIMESTAMP_COLNAME => 'TS', TARGET_COLNAME => 'VIBRATION',
  LABEL_COLNAME => '');

CREATE OR REPLACE TABLE ML.VIBRATION_ANOMALIES AS
SELECT SERIES::VARCHAR AS ENTITY_ID, TS::DATE AS EVENT_DATE, Y AS VIBRATION, FORECAST AS EXPECTED,
       LOWER_BOUND, UPPER_BOUND, IS_ANOMALY, PERCENTILE
FROM TABLE(ML.VIBRATION_ANOMALY_MODEL!DETECT_ANOMALIES(
  INPUT_DATA => SYSTEM$REFERENCE('VIEW', 'ML.VIBRATION_DETECT'),
  SERIES_COLNAME => 'ENTITY_ID', TIMESTAMP_COLNAME => 'TS', TARGET_COLNAME => 'VIBRATION'));

-- ---------- Semantic view ----------
CREATE OR REPLACE SEMANTIC VIEW APP.MAINTENANCE_ANALYTICS
  TABLES (
    machines AS CURATED.PERFORMANCE_SUMMARY PRIMARY KEY (ENTITY_ID)
      COMMENT = 'One row per machine, 90-day totals',
    risk AS ML.FAILURE_RISK_SCORES PRIMARY KEY (ENTITY_ID)
      COMMENT = 'Latest next-7-day failure probability per machine',
    causes AS CURATED.DOWNTIME_CAUSES PRIMARY KEY (ROOT_CAUSE)
      COMMENT = 'Downtime by root cause, 90 days',
    daily AS CURATED.TREND_ANALYSIS PRIMARY KEY (METRIC_DATE)
      COMMENT = 'Fleet totals per day'
  )
  RELATIONSHIPS (risk_machine AS risk (ENTITY_ID) REFERENCES machines)
  FACTS (
    machines.downtime_hours_f AS DOWNTIME_HOURS,
    machines.operating_hours_f AS OPERATING_HOURS,
    machines.planned_hours_f AS PLANNED_HOURS,
    machines.failures_f AS ALERT_COUNT,
    risk.failure_prob_f AS FAILURE_PROB_7D,
    causes.cause_hours_f AS DOWNTIME_HOURS,
    causes.cause_failures_f AS FAILURE_COUNT,
    daily.day_operating_f AS OPERATING_HOURS,
    daily.day_planned_f AS PLANNED_HOURS,
    daily.day_failures_f AS FAILURE_COUNT
  )
  DIMENSIONS (
    machines.machine_id AS ENTITY_ID WITH SYNONYMS = ('machine', 'asset', 'entity', 'equipment id'),
    machines.machine_name AS ENTITY_NAME,
    machines.region AS REGION WITH SYNONYMS = ('planning area', 'plant location', 'site') COMMENT = 'Singapore planning area of the plant',
    machines.machine_type AS CATEGORY WITH SYNONYMS = ('equipment type', 'category'),
    risk.risk_band AS RISK_BAND COMMENT = 'High >= 0.5, Medium >= 0.25, else Low',
    risk.scored_as_of AS SCORED_AS_OF,
    causes.root_cause AS ROOT_CAUSE,
    daily.metric_date AS METRIC_DATE
  )
  METRICS (
    machines.machine_count AS COUNT(machines.machine_id) WITH SYNONYMS = ('number of machines', 'entities', 'asset count'),
    machines.total_downtime_hours AS SUM(machines.downtime_hours_f),
    machines.unplanned_stops AS SUM(machines.failures_f) WITH SYNONYMS = ('failures', 'breakdowns'),
    machines.uptime_pct AS 100 * SUM(machines.operating_hours_f) / NULLIF(SUM(machines.planned_hours_f), 0)
      COMMENT = 'Operating hours / planned hours',
    machines.mtbf_hours AS SUM(machines.operating_hours_f) / NULLIF(SUM(machines.failures_f), 0)
      COMMENT = 'Mean time between failures',
    risk.avg_failure_prob AS AVG(risk.failure_prob_f),
    causes.cause_downtime_hours AS SUM(causes.cause_hours_f),
    causes.cause_stops AS SUM(causes.cause_failures_f),
    daily.daily_uptime_pct AS 100 * SUM(daily.day_operating_f) / NULLIF(SUM(daily.day_planned_f), 0),
    daily.daily_stops AS SUM(daily.day_failures_f)
  )
  COMMENT = 'Synthetic Singapore discrete-manufacturing fleet predictive maintenance (demo)';

-- ---------- Cortex Agent ----------
CREATE OR REPLACE AGENT APP.MAINTENANCE_AGENT
  COMMENT = 'Predictive maintenance assistant over a synthetic Singapore discrete-manufacturing fleet'
  FROM SPECIFICATION
$$
models:
  orchestration: claude-sonnet-4-5
instructions:
  response: "Answer only from tool results. State that data is synthetic. Give machine IDs and numbers with units."
  orchestration: "Use maintenance_analyst for metrics, machines, risk and root causes. Use sop_search for maintenance procedures."
tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: maintenance_analyst
      description: "Machine downtime, uptime, MTBF, stops, root causes and failure-risk scores"
  - tool_spec:
      type: cortex_search
      name: sop_search
      description: "Synthetic maintenance SOPs by equipment class and failure mode"
tool_resources:
  maintenance_analyst:
    semantic_view: __DEMO_DB__.APP.MAINTENANCE_ANALYTICS
    execution_environment:
      type: warehouse
      warehouse: __DEMO_WH__
  sop_search:
    name: __DEMO_DB__.SEARCH.MAINTENANCE_SOP_SEARCH
    max_results: 3
    id_column: DOC_ID
    title_column: TITLE
$$;

-- ---------- Live-telemetry alert (IoT Core -> S3 -> Snowpipe) ----------
CREATE TABLE IF NOT EXISTS APP.ALERT_LOG (
  ALERTED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(), MACHINE_ID VARCHAR,
  EVENT_TS TIMESTAMP_NTZ, VIBRATION_MM_S FLOAT, TEMPERATURE_C FLOAT, SOP_HINT VARCHAR);

CREATE OR REPLACE NOTIFICATION INTEGRATION SG_MANUFACTURING_MAINTENANCE_EMAIL_INT
  TYPE = EMAIL ENABLED = TRUE ALLOWED_RECIPIENTS = ('__ALERT_EMAIL__');

CREATE OR REPLACE PROCEDURE APP.LOG_LIVE_ALARMS()
RETURNS NUMBER
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  n NUMBER;
BEGIN
  INSERT INTO APP.ALERT_LOG (MACHINE_ID, EVENT_TS, VIBRATION_MM_S, TEMPERATURE_C, SOP_HINT)
    SELECT t.MACHINE_ID, t.EVENT_TS, t.VIBRATION_MM_S, t.TEMPERATURE_C,
           'Check ' || m.CATEGORY || ' SOPs; current risk band ' || COALESCE(r.RISK_BAND, 'n/a')
    FROM RAW.LIVE_TELEMETRY t
    JOIN RAW.MACHINES m ON m.ID = t.MACHINE_ID
    LEFT JOIN ML.FAILURE_RISK_SCORES r ON r.ENTITY_ID = t.MACHINE_ID
    WHERE t.STATUS = 'ALARM'
      AND NOT EXISTS (SELECT 1 FROM APP.ALERT_LOG l WHERE l.MACHINE_ID = t.MACHINE_ID AND l.EVENT_TS = t.EVENT_TS);
  n := SQLROWCOUNT;
  IF (n > 0) THEN
    CALL SYSTEM$SEND_EMAIL('SG_MANUFACTURING_MAINTENANCE_EMAIL_INT', '__ALERT_EMAIL__',
      '[Demo] Singapore plant live alarm',
      'New live-telemetry alarms logged in APP.ALERT_LOG: ' || :n || '. Data is synthetic.');
  END IF;
  RETURN n;
END;
$$;

CREATE OR REPLACE ALERT APP.LIVE_ALARM_ALERT
  WAREHOUSE = __DEMO_WH__
  SCHEDULE = '5 MINUTE'
  IF (EXISTS (
    SELECT 1 FROM RAW.LIVE_TELEMETRY t
    WHERE t.STATUS = 'ALARM'
      AND NOT EXISTS (SELECT 1 FROM APP.ALERT_LOG l WHERE l.MACHINE_ID = t.MACHINE_ID AND l.EVENT_TS = t.EVENT_TS)))
  THEN CALL APP.LOG_LIVE_ALARMS();

-- ---------- On-demand refresh DAG (suspended; run with EXECUTE TASK APP.TASK_REFRESH_CURATED) ----------
CREATE OR REPLACE PROCEDURE APP.REFRESH_CURATED()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
BEGIN
  ALTER DYNAMIC TABLE CURATED.PERFORMANCE_SUMMARY REFRESH;
  ALTER DYNAMIC TABLE CURATED.TREND_ANALYSIS REFRESH;
  ALTER DYNAMIC TABLE CURATED.DOWNTIME_CAUSES REFRESH;
  ALTER DYNAMIC TABLE CURATED.KPI_SUMMARY REFRESH;
  RETURN 'refreshed';
END;
$$;

CREATE OR REPLACE TASK APP.TASK_REFRESH_CURATED
  WAREHOUSE = __DEMO_WH__
AS
  CALL APP.REFRESH_CURATED();

CREATE OR REPLACE TASK APP.TASK_RESCORE_RISK
  WAREHOUSE = __DEMO_WH__
  AFTER APP.TASK_REFRESH_CURATED
AS
  CREATE OR REPLACE TABLE ML.FAILURE_RISK_SCORES COPY GRANTS AS
  WITH latest AS (
    SELECT * FROM ML.FAILURE_FEATURES QUALIFY ROW_NUMBER() OVER (PARTITION BY ENTITY_ID ORDER BY EVENT_DATE DESC) = 1
  ), p AS (
    SELECT ENTITY_ID, EVENT_DATE,
           ML.FAILURE_RISK_MODEL!PREDICT(INPUT_DATA => OBJECT_CONSTRUCT(
             'CATEGORY', CATEGORY, 'AGE_YEARS', AGE_YEARS, 'VIBRATION_MM_S', VIBRATION_MM_S,
             'TEMPERATURE_C', TEMPERATURE_C, 'VIBRATION_7D', VIBRATION_7D, 'FAILURES_30D', FAILURES_30D)) AS PRED
    FROM latest
  )
  SELECT ENTITY_ID, EVENT_DATE AS SCORED_AS_OF, PRED:probability:FAIL::FLOAT AS FAILURE_PROB_7D,
         CASE WHEN PRED:probability:FAIL::FLOAT >= 0.5 THEN 'High'
              WHEN PRED:probability:FAIL::FLOAT >= 0.25 THEN 'Medium' ELSE 'Low' END AS RISK_BAND,
         CURRENT_TIMESTAMP() AS SCORED_AT
  FROM p;
