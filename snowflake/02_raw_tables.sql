-- Synthetic machine-day observations for a fictional Singapore discrete-manufacturing
-- fleet; no seeded predictions or invented asset counts.
-- Randomness is HASH-seeded so every rebuild is reproducible yet varied:
-- per-machine reliability/age, shift patterns, wear between PM visits, missed PM,
-- variable restoration times, category-weighted root causes, plant-wide outages.
USE DATABASE IDENTIFIER($DEMO_DB);
USE SCHEMA RAW;
USE WAREHOUSE IDENTIFIER($DEMO_WH);

CREATE TABLE RAW.MACHINES AS
WITH equipment AS (
  SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS MACHINE_INDEX
  FROM TABLE(GENERATOR(ROWCOUNT => 24))
), draws AS (
  SELECT MACHINE_INDEX,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-site')), 1000000) / 1e6 AS U_REGION,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-eqclass')), 1000000) / 1e6 AS U_CATEGORY,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-age')), 1000000) / 1e6 AS U_AGE,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-rate')), 1000000) / 1e6 AS U_RATE,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-shift')), 1000000) / 1e6 AS U_SHIFT,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-pm')), 1000000) / 1e6 AS U_PM,
         MOD(ABS(HASH(MACHINE_INDEX, 'sg-mfg-discipline')), 1000000) / 1e6 AS U_DISCIPLINE
  FROM equipment
)
SELECT 'EQP-' || LPAD(MACHINE_INDEX::VARCHAR, 4, '0') AS ID,
       'Synthetic asset ' || LPAD(MACHINE_INDEX::VARCHAR, 4, '0') AS NAME,
       CASE WHEN U_REGION < 0.22 THEN 'Tuas' WHEN U_REGION < 0.40 THEN 'Woodlands'
            WHEN U_REGION < 0.58 THEN 'Ang Mo Kio' WHEN U_REGION < 0.75 THEN 'Seletar'
            WHEN U_REGION < 0.90 THEN 'Jurong East' ELSE 'Tampines' END AS REGION,
       CASE WHEN U_CATEGORY < 0.30 THEN 'CNC Machining Center' WHEN U_CATEGORY < 0.55 THEN 'Stamping Press'
            WHEN U_CATEGORY < 0.80 THEN 'Injection Molding Machine' ELSE 'Industrial Robot' END AS CATEGORY,
       MACHINE_INDEX,
       ROUND(1 + U_AGE * 14, 1) AS AGE_YEARS,
       -- Base daily failure probability 0.4%-3.6%; ~12% of machines are "bad actors" (x3).
       (0.004 + U_RATE * 0.032) * IFF(U_RATE > 0.88, 3, 1) AS BASE_FAILURE_RATE,
       IFF(U_SHIFT < 0.55, 24, 16) AS SHIFT_HOURS,
       7 * (1 + FLOOR(U_PM * 3)) AS PM_INTERVAL_DAYS,
       0.50 + U_DISCIPLINE * 0.48 AS PM_COMPLETION_PROB,
       'Active' AS STATUS
FROM draws;

CREATE TABLE RAW.SENSOR_READINGS AS
WITH days AS (
  SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS DAY_INDEX
  FROM TABLE(GENERATOR(ROWCOUNT => 90))
), outages AS (
  -- Two estate-level power supply dips in the window.
  SELECT * FROM VALUES (19, 'Ang Mo Kio', 3.5), (57, 'Seletar', 2.0) AS o(DAY_INDEX, REGION, HOURS)
), base AS (
  SELECT m.ID AS ENTITY_ID, m.MACHINE_INDEX, m.CATEGORY, m.REGION, m.AGE_YEARS,
         m.BASE_FAILURE_RATE, m.PM_INTERVAL_DAYS, m.PM_COMPLETION_PROB, d.DAY_INDEX,
         DATEADD('day', d.DAY_INDEX - 89, CURRENT_DATE()) AS EVENT_DATE,
         -- Every seventh day of the window runs a short 8-hour shift.
         IFF(MOD(d.DAY_INDEX, 7) = 6, 8.0, m.SHIFT_HOURS) AS PLANNED_HOURS,
         MOD(d.DAY_INDEX + m.MACHINE_INDEX * 3, m.PM_INTERVAL_DAYS) AS DAYS_SINCE_PM,
         MOD(ABS(HASH(m.ID, d.DAY_INDEX, 'sg-mfg-fail')), 1000000) / 1e6 AS U_FAIL,
         MOD(ABS(HASH(m.ID, d.DAY_INDEX, 'sg-mfg-restore')), 1000000) / 1e6 + 1e-6 AS U_RESTORE,
         MOD(ABS(HASH(m.ID, d.DAY_INDEX, 'sg-mfg-cause')), 1000000) / 1e6 AS U_CAUSE,
         MOD(ABS(HASH(m.ID, d.DAY_INDEX, 'sg-mfg-pmdone')), 1000000) / 1e6 AS U_PMDONE,
         MOD(ABS(HASH(m.ID, d.DAY_INDEX, 'sg-mfg-units')), 1000000) / 1e6 AS U_UNITS,
         MOD(ABS(HASH(m.ID, d.DAY_INDEX, 'sg-mfg-noise')), 1000000) / 1e6 AS U_NOISE,
         o.HOURS AS OUTAGE_HOURS
  FROM RAW.MACHINES m CROSS JOIN days d
  LEFT JOIN outages o ON o.DAY_INDEX = d.DAY_INDEX AND o.REGION = m.REGION
), pm AS (
  SELECT *,
         IFF(DAYS_SINCE_PM = 0, 1, 0) AS PM_DUE,
         IFF(DAYS_SINCE_PM = 0 AND U_PMDONE < PM_COMPLETION_PROB, 1, 0) AS PM_COMPLETED,
         -- Wear rises between visits; unreliable PM discipline adds carried-over wear.
         DAYS_SINCE_PM / PM_INTERVAL_DAYS + (1 - PM_COMPLETION_PROB) AS WEAR,
         -- Inter-monsoon heat stress (days 30-74 of the window) on injection molding barrels and hydraulics.
         IFF(CATEGORY = 'Injection Molding Machine' AND DAY_INDEX BETWEEN 30 AND 74, 1.35, 1.0) AS HEAT_FACTOR
  FROM base
), failures AS (
  SELECT *,
         LEAST(0.6, BASE_FAILURE_RATE * (0.4 + 1.6 * WEAR) * (1 + AGE_YEARS / 25) * HEAT_FACTOR) AS P_FAIL
  FROM pm
), events AS (
  SELECT *,
         CASE WHEN OUTAGE_HOURS IS NOT NULL THEN 1
              WHEN U_FAIL < P_FAIL / 4 THEN 2
              WHEN U_FAIL < P_FAIL THEN 1 ELSE 0 END AS FAILURE_COUNT
  FROM failures
), timed AS (
  SELECT *,
         -- Exponential restoration durations; mean depends on category.
         CASE WHEN FAILURE_COUNT = 0 THEN 0.0
              WHEN OUTAGE_HOURS IS NOT NULL THEN OUTAGE_HOURS
              ELSE LEAST(PLANNED_HOURS - 0.5, ROUND(FAILURE_COUNT * (0.5 - LN(U_RESTORE) *
                     CASE CATEGORY WHEN 'Stamping Press' THEN 4.0 WHEN 'CNC Machining Center' THEN 3.0
                                   WHEN 'Injection Molding Machine' THEN 3.5 ELSE 1.5 END), 1)) END AS DOWNTIME_HOURS
  FROM events
)
SELECT ENTITY_ID || '-' || TO_CHAR(EVENT_DATE, 'YYYYMMDD') AS EVENT_ID,
       ENTITY_ID, EVENT_DATE, PLANNED_HOURS, DOWNTIME_HOURS,
       PLANNED_HOURS - DOWNTIME_HOURS AS OPERATING_HOURS,
       FAILURE_COUNT,
       CASE WHEN FAILURE_COUNT = 0 THEN 'None'
            WHEN OUTAGE_HOURS IS NOT NULL THEN 'Grid disturbance'
            WHEN CATEGORY = 'CNC Machining Center' THEN IFF(U_CAUSE < 0.45, 'Spindle bearing wear', IFF(U_CAUSE < 0.8, 'Tool breakage', 'Coolant pump fault'))
            WHEN CATEGORY = 'Stamping Press' THEN IFF(U_CAUSE < 0.5, 'Hydraulic leak', IFF(U_CAUSE < 0.8, 'Die misalignment', 'Clutch brake wear'))
            WHEN CATEGORY = 'Injection Molding Machine' THEN IFF(U_CAUSE < 0.55, 'Barrel heater fault', IFF(U_CAUSE < 0.85, 'Screw and barrel wear', 'Mold cooling fault'))
            ELSE IFF(U_CAUSE < 0.5, 'Servo drive fault', IFF(U_CAUSE < 0.8, 'Gripper fault', 'Cable harness wear')) END AS ROOT_CAUSE,
       PM_DUE, PM_COMPLETED,
       ROUND(OPERATING_HOURS * (30 + U_UNITS * 30)) AS TOTAL_UNITS,
       FLOOR(ROUND(OPERATING_HOURS * (30 + U_UNITS * 30)) *
             LEAST(0.995, GREATEST(0.82, 0.988 - 0.035 * WEAR - 0.03 * FAILURE_COUNT - 0.012 * U_NOISE))) AS GOOD_UNITS,
       100.0 * (PLANNED_HOURS - DOWNTIME_HOURS) / PLANNED_HOURS AS KPI_EQUIPMENT_UPTIME,
       ROUND(2.1 + 3.2 * WEAR + 1.6 * FAILURE_COUNT + U_NOISE * 0.9, 2) AS VIBRATION_MM_S,
       ROUND(48 + 7 * WEAR + IFF(HEAT_FACTOR > 1, 8, 0) + U_NOISE * 3, 1) AS TEMPERATURE_C,
       CURRENT_TIMESTAMP() AS LOADED_AT
FROM timed;

CREATE TABLE RAW.SPARE_PARTS AS
SELECT ID AS ENTITY_ID,
       CASE CATEGORY WHEN 'CNC Machining Center' THEN 'Spindle bearing kit' WHEN 'Stamping Press' THEN 'Hydraulic seal kit'
                     WHEN 'Injection Molding Machine' THEN 'Heater band set' ELSE 'Servo drive module' END AS PART_TYPE,
       1 + MOD(ABS(HASH(ID, 'sg-mfg-req')), 4) AS REQUIRED_QTY,
       MOD(ABS(HASH(ID, 'sg-mfg-hand')), 5) AS ON_HAND_QTY,
       IFF(MOD(ABS(HASH(ID, 'sg-mfg-hand')), 5) < 1 + MOD(ABS(HASH(ID, 'sg-mfg-req')), 4),
           MOD(ABS(HASH(ID, 'sg-mfg-order')), 3), 0) AS ON_ORDER_QTY,
       CURRENT_DATE() AS SNAPSHOT_DATE
FROM RAW.MACHINES;
