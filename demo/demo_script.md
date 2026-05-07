# Demo Script: Industrial AI Maintenance Co-pilot
## ~70-second walkthrough — Snowflake + AWS IoT SiteWise + AWS Bedrock + QuickSight

---

## The Story
Hydraulic Pump 63 vibration trending toward 6.0 mm/s — failure threshold. SiteWise sees the sensors; Snowflake catches the anomaly; Bedrock writes the work order with parts, skills, ETA — before the failure window closes.

---

## Personas

| Persona | Tool | What they care about |
|---|---|---|
| Maintenance Technician | Streamlit AI Work Order page | Click-to-dispatch with parts list and safety notes |
| Plant Manager | Amazon QuickSight + Amazon Q | Asset health portfolio, MTBF, $ saved |

---

## Script

### [0:00–0:10] HOOK
> "Pump 63 vibration at 5.59 mm/s, failure at 6.0. AWS IoT SiteWise saw it; Snowflake fired the anomaly; Bedrock writes the work order — parts, skills, ETA."

### [0:10–0:25] STREAMLIT — Equipment Health + Anomaly Alerts
> Open `MANUFACTURING_MAINTENANCE.APP.PREDICTIVE_MAINTENANCE_APP`.
> "Equipment Health: 100 assets ranked by health score; Pump 63 in the red. Anomaly Alerts: vibration trending up, hours-to-breach < 24."

### [0:25–0:50] AI WORK ORDER (AWS Bedrock) — the AWS hero
> Open page **AI Work Order (AWS Bedrock)**.
> "Pick Pump 63, click Generate. The stored proc bundles the SiteWise asset context with the Snowflake anomaly fields and asks Bedrock Claude for a structured work order: Summary, Recommended Action, Parts List, Required Skills, ETA, Safety Notes. The technician dispatches in one click."

### [0:50–1:05] QUICKSIGHT + AMAZON Q
> "QuickSight `mfg-maintenance-dashboard` rolls health and MTBF for the manager. Amazon Q topic `mfg-maintenance-q`: 'Which assets are at critical health?' answers from the field."

### [1:05–1:10] CLOSE
> "SiteWise watches; Snowflake decides; Bedrock writes; QuickSight reports. Four AWS-native pillars, one prevented failure."

---

## Pre-Recording Checklist
- [ ] `SELECT COUNT(*) FROM MANUFACTURING_MAINTENANCE.SITEWISE.ASSET_MODEL` returns 100
- [ ] Run `CALL AI.SP_GENERATE_WORK_ORDER('PUMP-063')` — returns full markdown
- [ ] AI Work Order page renders the work order under 30 seconds
- [ ] Open https://app.snowflake.com/SFSEAPAC/sg_demo43/#/streamlit-apps/MANUFACTURING_MAINTENANCE.APP.PREDICTIVE_MAINTENANCE_APP
- [ ] Open https://us-west-2.quicksight.aws.amazon.com/sn/dashboards/mfg-maintenance-dashboard
