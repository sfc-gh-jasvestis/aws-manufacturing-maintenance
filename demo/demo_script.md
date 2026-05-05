# Demo Script: Predictive Maintenance
## ~70-second walkthrough — AWS + Snowflake

---

## The Story
Gantry Crane 7 vibration is at 5.6 mm/s — threshold is 6.0. Trending up. Twelve hours to failure if we do nothing. Catching this saves $2.3M.

---

## Personas

| Persona | Tool | What they care about |
|---|---|---|
| Reliability Engineer | Streamlit on Snowflake | Real-time sensor anomalies, equipment health, work orders |
| Plant Manager | Amazon QuickSight + Amazon Q | Asset health by line, downtime cost, schedule compliance |

---

## Script

### [0:00–0:10] HOOK
> "Gantry Crane 7 vibration is at 5.6 mm/s — threshold is 6.0. Trending up. Twelve hours to failure. Catching this saves $2.3M."

### [0:10–0:35] SNOWFLAKE — STREAMLIT
> Open `MANUFACTURING_MAINTENANCE.APP.PREDICTIVE_MAINTENANCE_APP`.
> "Overview banner names Crane 7. Equipment Health page sorts by score — Critical and Offline equipment surface at the bottom, Operational at the top. Anomaly Alerts page lists every sensor approaching threshold ranked by hours-to-breach. 200,000 sensor readings flow through a Dynamic Table that recomputes every five minutes."

### [0:35–0:50] CORTEX AI
> "Ask the Data: 'Which equipment is most critical?' Cortex Analyst over `MAINTENANCE_ANALYTICS_VIEW` returns the answer. Snowflake ML.ANOMALY_DETECTION on the same sensor stream identifies drift before any threshold-based alert fires."

### [0:50–1:05] AWS
> "Sensor archives land in S3 at `s3://sg-manufacturing-demos-2026/maintenance/`. QuickSight `mfg-maintenance-dashboard`: KPIs for total equipment, critical, warning, average health, plus status donut and health-score-by-type with threshold reference lines. Amazon Q topic `mfg-maintenance-q` lets the plant manager ask 'How many work orders are overdue?' from a phone."

### [1:05–1:10] CLOSE
> "Snowflake catches it. AWS surfaces it to leadership. $2.3M saved before the failure."

---

## Pre-Recording Checklist
- [ ] Verify Crane 7 vibration 5.6 mm/s in `ANOMALY_ALERTS`
- [ ] Verify health score monotonic with status (OPERATIONAL > WARNING > CRITICAL > OFFLINE)
- [ ] Open https://app.snowflake.com/SFSEAPAC/sg_demo43/#/streamlit-apps/MANUFACTURING_MAINTENANCE.APP.PREDICTIVE_MAINTENANCE_APP
- [ ] Open https://us-west-2.quicksight.aws.amazon.com/sn/dashboards/mfg-maintenance-dashboard
