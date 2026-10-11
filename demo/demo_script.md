# Predictive Maintenance

**Singapore - Discrete Manufacturing**
Use case: Predictive Maintenance

> Predictive maintenance for Straits Precision Components, a fictional Singapore contract manufacturer of precision parts: 24 synthetic production assets (CNC machining centers, stamping presses, injection molding machines, industrial robots) at six plants in Tuas, Woodlands, Ang Mo Kio, Seletar, Jurong East and Tampines. Dynamic tables, a holdout-evaluated failure-risk classifier, a downtime forecast and grounded AI answers.

## Why Snowflake

- **Dynamic tables** reconcile asset KPIs from RAW sensor data, with checks in `run_core.py`
- **Failure-risk classification** gives a holdout-evaluated next-7-day unplanned-stop risk per asset
- **Downtime forecast** projects 14 days of fleet downtime with prediction intervals
- **Grounded AI**: the Cortex Agent (Analyst over a semantic view, plus Search over SOPs) shows its SQL and SOP citations. The memo is written by Cortex AI_COMPLETE (Snowflake build) or Amazon Bedrock (AWS build).
- **Live ingestion**: `APP.SIMULATE_TELEMETRY` in the Snowflake build, or IoT Core to S3 to Snowpipe auto-ingest in the AWS build, then an alert and email

## What is built

| | |
|---|---|
| Dimension table | `RAW.MACHINES` (24 rows) |
| Fact table | `RAW.SENSOR_READINGS` (2,160 asset-days, 90 days) |
| Curated layer | `CURATED.KPI_SUMMARY`, `PERFORMANCE_SUMMARY`, `DOWNTIME_CAUSES`, `TREND_ANALYSIS` |
| ML | `ML.FAILURE_RISK_SCORES`, `ML.FAILURE_RISK_HOLDOUT_METRICS`, `ML.DOWNTIME_FORECAST`, `ML.VIBRATION_ANOMALIES` |

Plants (Singapore planning areas): Tuas, Woodlands, Ang Mo Kio, Seletar, Jurong East, Tampines.
Equipment classes: CNC Machining Center, Stamping Press, Injection Molding Machine, Industrial Robot.

## KPI cards (live from `CURATED.KPI_SUMMARY`; no fallback values)

| Card | Value in a fresh build |
|---|---|
| Equipment Uptime | 98.9% |
| Unplanned Stops | 132 |
| MTBF (Avg) | 307.2 hrs |
| Equipment Managed | 24 |
| Parts on Order | 9 |
| Spare Coverage | 55.6% |

Values are synthetic. A rebuild reproduces them because the data is HASH-seeded.

## Demo flow

1. Executive Cockpit (Nurul Huda Rahim): KPIs, daily uptime and downtime by root cause; hydraulic leaks lead the hours lost
2. Predictive (Darren Koh): holdout metrics, risk bands, 14-day downtime forecast, vibration anomalies
3. PM Planning: spares coverage, PM compliance against yield, then Generate a memo written from Snowflake tables only
4. Live IoT: run `CALL APP.SIMULATE_TELEMETRY(20)` (Snowflake build) or `python aws/publish_telemetry.py --count 20` (AWS build; messages arrive about 20-60 s later through IoT Core, S3 and Snowpipe). Then run `EXECUTE ALERT APP.LIVE_ALARM_ALERT` and show the alert log and email.
5. Ask AI: the Cortex Agent answers metric questions through the semantic view and cites SOPs from Cortex Search. The SQL is shown.
6. QuickSight (AWS build only): the same Snowflake tables through DIRECT_QUERY; risk and IoT visuals
7. Architecture: both diagrams, the current build first

## Talking points

- Uptime ranges from 94.18% to 100% by asset, and Ang Mo Kio is the lowest plant at 97.31%. Downtime is concentrated in a few assets (EQP-0003 in Ang Mo Kio and EQP-0013 in Tampines).
- Stamping presses lose the most hours (158.1); hydraulic leaks and spindle bearing wear are the top two causes.
- The risk model is evaluated on a time-based holdout: precision 0.47 and recall 0.41 at 0.5, against a 0.24 base rate. Present it as triage, not a guarantee.
- Two estate-level power supply dips (Ang Mo Kio and Seletar), recorded as grid disturbances, are excluded from failure labels.

## Business impact

Use only the sourced references in `README.md` (Business Impact).

---
Hand-maintained.
