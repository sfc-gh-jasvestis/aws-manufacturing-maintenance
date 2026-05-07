# Demo Script: Industrial AI Maintenance Co-pilot
## ~3-Minute Recorded Walkthrough
**Format**: Screen recording with voiceover
**Target**: Customer meeting / booth loop / social share
**Pre-requisites**: Data loaded, Streamlit deployed, QuickSight dashboard published, SiteWise asset model populated, Bedrock Lambda `mfg-maint-workorder-bedrock` deployed (or Cortex Complete fallback in this demo account)

---

## Two Personas

| Persona | Role | Tool | What they care about |
|---|---|---|---|
| **Maintenance Technician** | Dispatch + diagnostics | Streamlit (AI Work Order page) | Click-to-dispatch with parts list, required skills, ETA, safety notes |
| **Plant Manager** | Asset portfolio + budget | Amazon QuickSight + Amazon Q | MTBF, $ saved by predictive intervention, asset health by location |

---

## What's Built

| Layer | Component | Detail |
|---|---|---|
| **Sensors (AWS)** | AWS IoT SiteWise | Asset model `mfg-maintenance/cranes` — 100 industrial assets with vibration, temp, pressure properties |
| **Hot tier** | S3 | `s3://sg-manufacturing-demos-2026/maintenance/sitewise/` — SiteWise hot-tier export |
| **RAW** | 3 tables | EQUIPMENT (100), SENSORS (24K), MAINTENANCE_HISTORY (5K) |
| **CURATED** | 3 Dynamic Tables | EQUIPMENT_HEALTH, ANOMALY_ALERTS (123), MAINTENANCE_SCHEDULE (1.4K) |
| **AI** | Semantic View + Cortex anomaly + work-order LLM | MAINTENANCE_ANALYTICS_VIEW, `SP_GENERATE_WORK_ORDER` (Bedrock-shaped) |
| **AWS Hero** | IoT SiteWise + Bedrock | Asset model + Lambda `mfg-maint-workorder-bedrock` calling Bedrock Claude |
| **Consumption** | Streamlit | 7-page Predictive Maintenance App |
| | QuickSight | `mfg-maintenance-dashboard` + Amazon Q topic `mfg-maintenance-q` |

---

## Pre-Recording Checklist

- [ ] `SELECT COUNT(*) FROM MANUFACTURING_MAINTENANCE.SITEWISE.ASSET_MODEL` returns 100
- [ ] PUMP-063 vibration ~5.59 mm/s in `ANOMALY_ALERTS`
- [ ] CRANE-007 in CRITICAL status (or comparable hero asset)
- [ ] `CALL MANUFACTURING_MAINTENANCE.AI.SP_GENERATE_WORK_ORDER('PUMP-063')` returns full markdown work order in < 30s
- [ ] Open Streamlit: https://app.snowflake.com/SFSEAPAC/sg_demo43/#/streamlit-apps/MANUFACTURING_MAINTENANCE.APP.PREDICTIVE_MAINTENANCE_APP
- [ ] Open QuickSight: https://us-west-2.quicksight.aws.amazon.com/sn/dashboards/mfg-maintenance-dashboard
- [ ] Pre-open AWS tabs:
  - SiteWise: `https://us-west-2.console.aws.amazon.com/iotsitewise/home?region=us-west-2#/asset-models`
  - Lambda: `https://us-west-2.console.aws.amazon.com/lambda/home?region=us-west-2#/functions/mfg-maint-workorder-bedrock`
  - Bedrock: `https://us-west-2.console.aws.amazon.com/bedrock/home?region=us-west-2#/foundation-models`
- [ ] Audio: quiet room, external mic
- [ ] Resolution: 1920x1080

---

## Script

### [0:00–0:20] THE PROBLEM & ARCHITECTURE

**Show**: Streamlit Overview + critical asset banner

> "Hydraulic Pump 63, Warehouse B. Vibration trending at 5.59 millimeters per second — failure threshold 6.0. Twenty-four hours to catastrophic failure. The maintenance crew is busy on three other assets. Who writes the work order — and how long does it take? We're going to do it in one click. **AWS IoT SiteWise** watches the sensors. **Snowflake** catches the anomaly. **AWS Bedrock** writes a structured work order — parts, skills, ETA, safety. The technician dispatches before the failure window closes."

### [0:20–0:45] PAGE 1: EQUIPMENT HEALTH

**Show**: Equipment health ranked by score, Pump 63 in red

**Tech**: Dynamic Tables + Cortex anomaly detection

> "One hundred assets ranked by health score. Pump 63 sits at the bottom — 23 out of 100. Two critical sensors, four warnings. The Dynamic Table `EQUIPMENT_HEALTH` rolls every sensor reading into one number every five minutes. The asset model behind it — that's **AWS IoT SiteWise** — `mfg-maintenance/cranes` — pumping properties into S3 every minute, ingested by Snowflake."

### [0:45–1:10] PAGE 2: ANOMALY ALERTS

**Show**: Anomaly table with hours-to-breach < 24

**Tech**: ML.ANOMALY_DETECTION + threshold tracking

> "Cortex anomaly detection on the vibration time-series. Pump 63 hours-to-breach: under 24. Trend direction: increasing. Sensor value 5.59, threshold 6.0. Without this we'd find out when the bearing seizes. With this we have a day to act."

### [1:10–1:55] PAGE 3: AI WORK ORDER — Bedrock

**Show**: Click `AI Work Order (AWS Bedrock)` page, select PUMP-063

**Tech**: Lambda + Bedrock Claude (or Cortex Complete fallback in this demo account)

> "Here's the AWS hero. Pick Pump 63. Click Generate. Snowflake's stored proc bundles the SiteWise asset context — health score, critical sensors, warning sensors, last maintenance — with the live anomaly fields and ships it to **AWS Lambda** `mfg-maint-workorder-bedrock`. The Lambda calls **Bedrock Claude**. In about twenty seconds the technician gets a structured work order: Summary, Recommended Action, Parts List with quantities, Required Skills, Estimated Time, Safety Notes."

**Action**: Wait for the markdown to render; scroll through.

> "Look at the parts list — pump coupling, mounting bolts, seals kit, hydraulic fluid, vibration dampeners. Required skills — hydraulic systems technician with vibration certification. Estimated time — four to six hours. Safety — lockout/tagout required. That's a real dispatchable work order — not a chatbot reply."

**Action**: Switch to **AWS Bedrock console** → show foundation-model `anthropic.claude-sonnet-4` available; switch to Lambda → show the function and recent invocations.

> "There's Bedrock with Claude approved on the AWS side. There's the Lambda — sub-30-second p99. The customer keeps the foundation-model relationship in their AWS account; Snowflake just orchestrates."

### [1:55–2:20] PAGE 4: ASK MAINTENANCE

**Show**: Type "Which assets are at critical health?" — confirm answer

**Tech**: Cortex Analyst + Semantic View

> "Natural language. **Cortex Analyst** over `MAINTENANCE_ANALYTICS_VIEW` answers — three assets in CRITICAL, eleven in WARNING, six maintenance windows due this week. The technician asks; the planner asks; the manager asks. Same semantic layer."

### [2:20–2:50] QUICKSIGHT + AMAZON Q — the manager lens

**Show**: Switch to QuickSight dashboard `mfg-maintenance-dashboard`

**Tech**: QuickSight Snowflake direct query + Amazon Q topic

> "Manager view. **QuickSight** dashboard `mfg-maintenance-dashboard` rolls health, MTBF, dollars saved by predictive intervention. **Amazon Q topic** `mfg-maintenance-q`: 'Which assets are most likely to fail this week?' — three of them, with locations. From a phone in the plant manager's office."

### [2:50–3:10] CLOSE

> "Recap. Industrial sensors publish to **AWS IoT SiteWise**. SiteWise lands hot-tier data in **S3**; Snowflake ingests via external table and **Dynamic Tables** roll it up into health scores. **Cortex anomaly detection** flags Pump 63 with twenty-four hours to spare. One click bundles the SiteWise context with the anomaly fields, ships it to **AWS Bedrock** via Lambda, and returns a dispatchable work order — parts, skills, ETA, safety. **QuickSight** and **Amazon Q** keep the manager informed. Two AWS services on the operational path, two on the AI path, four Snowflake capabilities — one prevented failure. That's $2.3 million saved on a single asset. That's **Predictive Maintenance** on Snowflake and AWS."

---

## Key Demo Differentiators (vs other AWS demos)

1. **AWS IoT SiteWise + Snowflake** — most demos start at S3; this one starts at the actual asset model.
2. **Bedrock for structured output** — work-order Markdown is dispatchable, not a chat transcript.
3. **Customer keeps Bedrock contract** — Lambda makes the foundation-model invocation; Snowflake never touches the AWS bill.
4. **Quantified outcome** — $2.3M saved per prevented failure is the hook for the manager.
5. **Q topic answers** to try: "Which assets are at critical health?" / "When is the next maintenance window?" / "How much have we saved this quarter?"
