# Demo Script: Industrial AI Maintenance Co-pilot
## ~4:15-Minute Recorded Walkthrough
**Format**: Screen recording with voiceover
**Target**: Customer meeting / booth loop / social share
**Pre-requisites**: Data loaded, Streamlit deployed, QuickSight dashboard published, SiteWise assets populated (100), Snowpipe running, SNS topic active, Bedrock Lambda deployed

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
| **Digital Twin (AWS)** | AWS IoT SiteWise | 100 assets across 3 plants, 8 production lines — vibration, temp, pressure properties |
| **Ingestion** | S3 + Snowpipe | `s3://sg-manufacturing-demos-2026/maintenance/realtime/` -> AUTO_INGEST pipe |
| **RAW** | 4 tables | EQUIPMENT (100), SENSOR_READINGS (200K), WORK_ORDERS (5K), FAILURE_HISTORY (500), SENSOR_READINGS_REALTIME (Snowpipe) |
| **CURATED** | 3 Dynamic Tables | EQUIPMENT_HEALTH (100), ANOMALY_ALERTS (161), MAINTENANCE_SCHEDULE (2.9K active) |
| **ML** | Snowflake ML | XGBoost RUL model in Model Registry + RUL_PREDICTIONS DT (days-to-failure per asset) |
| **Search** | Cortex Search | MAINTENANCE_DOCS_SEARCH — 416 docs (manuals, field notes, safety, parts) |
| **AI** | Semantic View + Cortex + Agent | MAINTENANCE_ANALYTICS_VIEW, SP_GENERATE_WORK_ORDER (Bedrock-shaped) |
| **Alerting** | Snowflake Alert + SNS | CRITICAL_EQUIPMENT_ALERT fires every 5 min -> SNS -> technician email/SMS |
| **Consumption** | Streamlit (9 pages) | Overview, Equipment Health, Anomaly Alerts, ML Predictions, Maintenance Schedule, IoT SiteWise, AI Work Order, Search Docs, Ask Maintenance |
| | QuickSight | `mfg-maintenance-dashboard` + `mfg-maintenance-rul-dashboard` + Amazon Q |

---

## Pre-Recording Checklist

- [ ] `SELECT STATUS, COUNT(*) FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH GROUP BY STATUS` -> 10 CRITICAL, 17 WARNING, 65 OPERATIONAL, 8 OFFLINE
- [ ] Air Compressor 21 (COMP-021) health score = 10 with 4 critical sensors (OFFLINE)
- [ ] Air Compressor 33 (COMP-033) health score = 18 with 4 critical sensors (CRITICAL)
- [ ] 161 active anomaly alerts across the fleet; 13 already breached
- [ ] RUL predictions: 12 IMMINENT (<7d), 3 SOON (<30d), 13 MONITOR (<90d)
- [ ] Snowpipe running: `SELECT SYSTEM$PIPE_STATUS('MANUFACTURING_MAINTENANCE.RAW.SENSOR_REALTIME_PIPE')` -> executionState: RUNNING
- [ ] Run `python scripts/simulate_sensor_stream.py --batches 3 --upload` 5 min before recording (fresh S3 data)
- [ ] `CALL MANUFACTURING_MAINTENANCE.AI.SP_GENERATE_WORK_ORDER('COMP-021')` returns work order in < 30s
- [ ] Open Streamlit: https://app.snowflake.com/SFSEAPAC/sg_demo43/#/streamlit-apps/MANUFACTURING_MAINTENANCE.APP.PREDICTIVE_MAINTENANCE_APP
- [ ] Open QuickSight: https://us-west-2.quicksight.aws.amazon.com/sn/dashboards/mfg-maintenance-dashboard
- [ ] Pre-open AWS tabs:
  - SiteWise: `https://us-west-2.console.aws.amazon.com/iotsitewise/home?region=us-west-2#/assets`
  - S3: `https://us-west-2.console.aws.amazon.com/s3/buckets/sg-manufacturing-demos-2026?prefix=maintenance/realtime/`
  - SNS: `https://us-west-2.console.aws.amazon.com/sns/v3/home?region=us-west-2#/topic/arn:aws:sns:us-west-2:018437500440:mfg-maintenance-critical-alerts`
  - Lambda: `https://us-west-2.console.aws.amazon.com/lambda/home?region=us-west-2#/functions/mfg-maint-workorder-bedrock`
  - Bedrock: `https://us-west-2.console.aws.amazon.com/bedrock/home?region=us-west-2#/foundation-models`
- [ ] Audio: quiet room, external mic
- [ ] Resolution: 1920x1080

---

## Script

### [0:00-0:20] THE PROBLEM

**Show**: Streamlit Overview — critical asset banner

> "Air Compressor 21. Health score: ten out of a hundred. Four sensors critical. Status: OFFLINE. This asset is the worst in a fleet of one hundred — and it's not alone. Ten equipment in CRITICAL state, seventeen in WARNING, eight OFFLINE. The maintenance crew is managing 161 active anomaly alerts with $36 million in maintenance backlog. In the next four minutes, I'll show you how we go from sensor to dispatch — using five AWS services and Snowflake AI — in a single pipeline."

### [0:20-0:45] AWS IoT SITEWISE — the digital twin

**Action**: Tab to AWS IoT SiteWise console -> show asset list (100 assets)

> "This is where the data starts. **AWS IoT SiteWise** — the digital twin of the factory floor. Three plants: Singapore Jurong, Singapore Tuas, Batam. Eight production lines. One hundred industrial assets — compressors, cranes, conveyors, pumps, generators. Each one publishing vibration, temperature, and pressure every minute. SiteWise models the hierarchy: plant to line to asset to sensor. Click into any compressor — you see the live property values. This is the source of truth for the physical world."

**Action**: Click into a failing compressor asset to show properties

### [0:45-1:05] S3 + SNOWPIPE — real-time ingestion

**Action**: Tab to S3 console -> show `maintenance/realtime/` prefix with recent CSV files

> "SiteWise exports to **Amazon S3** every minute. Here are the sensor CSVs landing in real-time — timestamped, one per batch. On the Snowflake side, **Snowpipe** with AUTO_INGEST watches this S3 prefix. No ETL code. No orchestration. Files land, SQS fires a notification, Snowpipe loads them into the `SENSOR_READINGS_REALTIME` table automatically. Zero-latency ingestion."

**Action**: Switch to Streamlit -> Real-Time Ingestion page -> show latest readings

### [1:05-1:30] ML PREDICTIONS — Snowflake ML

**Show**: Streamlit ML Predictions page — scatter plot, predictions table

**Tech**: Snowflake Model Registry + XGBoost + Dynamic Table

> "**Snowflake ML** — machine learning built into the data platform. We trained an **XGBoost model** on 200,000 sensor readings and 500 historical failures — and registered it in the **Snowflake Model Registry**. The model predicts Remaining Useful Life — how many days until each asset fails. Twelve equipment at IMMINENT risk — less than seven days. Air Compressor 21: five days to predicted failure. The scatter plot tells the story: bottom-left quadrant is the danger zone — low health, few days left. The Dynamic Table `RUL_PREDICTIONS` re-runs inference every five minutes. No external ML infrastructure. No data movement. Training, registry, and inference — all in Snowflake."

### [1:30-1:50] ANOMALY ALERTS — 161 active threats

**Show**: Streamlit Anomaly Alerts page — breach chart, alert table

**Tech**: ML.ANOMALY_DETECTION + threshold tracking

> "One hundred and sixty-one active anomaly alerts. Thirteen already breached — negative hours-to-breach means they're *past* the safe limit right now. Fifty-five more will breach within six hours. Air Compressor 21 — four sensors critical, all trending INCREASING. Without predictive maintenance, we find out when the bearing seizes. With this, we see it coming days ahead."

### [1:50-2:15] SNS ALERTS — technician notification

**Action**: Tab to AWS SNS console -> show topic `mfg-maintenance-critical-alerts`

> "When any equipment drops below 20% health, a **Snowflake Alert** fires — every five minutes. The alert pushes to **Amazon SNS**, which fans out to email, SMS, or a Lambda for PagerDuty integration. The on-call technician gets notified in under sixty seconds. Air Compressor 21 at ten percent health — that notification already fired. The technician is already looking at their phone."

**Action**: Show SNS subscription list / recent delivery

### [2:15-2:45] AI WORK ORDER — Bedrock

**Show**: Streamlit AI Work Order page -> select COMP-021 -> Generate

**Tech**: Lambda + Bedrock Claude

> "Now the AWS hero moment. Pick Air Compressor 21. Click Generate. Snowflake bundles the SiteWise asset context — health score ten, four critical sensors, OFFLINE status — with the live anomaly readings. Ships it to **AWS Lambda** `mfg-maint-workorder-bedrock`. Lambda calls **Bedrock Claude**. In twenty seconds: a structured, dispatchable work order."

**Action**: Wait for markdown to render; scroll through

> "Summary. Recommended Action. Parts List — compressor bearings, pressure relief valve, gaskets, vibration dampeners. Required Skills — compressed-air technician with vibration analysis certification. Estimated Time — four to six hours. Safety Notes — lockout/tagout, residual pressure bleed. That's not a chatbot reply — that's a *dispatchable work order*."

**Action**: Tab to Bedrock console -> show `claude-sonnet-4-6`; Lambda -> show recent invocations

### [2:45-3:15] SEARCH DOCS — Cortex Search

**Show**: Streamlit Search Maintenance Docs page

**Tech**: Cortex Search + 416 documents (OEM manuals, technician field notes, safety bulletins, spare parts)

> "The work order says replace the bearings. But which bearings? What did the last technician find? Search 'vibration bearing compressor'. **Cortex Search** across 416 documents — OEM machine manuals, technician field notes, safety bulletins, spare parts catalogs. First result: a technician field note from two weeks ago — 'COMP-021: found bearing race pitting on drive end, replaced SKF 6208-2RS, vibration dropped from 5.2 to 1.8 mm/s.' That's institutional knowledge that normally lives in someone's head — or a crumpled notebook. Now it's searchable."

**Action**: Type "lockout tagout compressor" -> show safety bulletin result

> "Before they start the job: 'lockout tagout compressor'. Safety bulletin — OSHA 29 CFR 1910.147, required PPE, step-by-step lockout procedure, residual pressure bleed. The technician gets the work order, the repair history, the parts list, *and* the safety procedure — all from one search."

**Action**: Type "SKF bearing compressor" -> show spare parts result with part numbers and costs

### [3:15-3:35] QUICKSIGHT — the executive lens

**Show**: Switch to QuickSight dashboard

**Tech**: QuickSight Snowflake direct query + Amazon Q

> "Plant manager view. **QuickSight** connects directly to Snowflake — equipment status distribution, average health by type, and now the RUL predictions dashboard: failure risk distribution, average days to failure by equipment type. **Amazon Q**: 'Which equipment is at imminent failure risk?' — twelve assets. 'What's the average health score?' — sixty-six. From the plant manager's phone."

### [3:35-3:55] ASK THE DATA — Cortex Analyst

**Show**: Streamlit Ask Maintenance page -> "Which equipment has the lowest health score?"

**Tech**: Cortex Analyst + Semantic View

> "Natural language over the same data. **Cortex Analyst** and the `MAINTENANCE_ANALYTICS_VIEW`. 'Which equipment has the lowest health?' — Air Compressor 21, health ten. Same semantic layer for the technician, the planner, the plant manager, and the AI agent."

### [3:55-4:10] CLOSE

> "One pipeline. Sensor to dispatch. **IoT SiteWise** sees the vibration spike. **Snowpipe** lands the data in seconds. **Snowflake ML** predicts the failure days before it happens. **SNS** wakes up the technician. **Bedrock** writes the work order. **Cortex Search** hands them the manual, the repair history, and the safety procedure. One hundred assets. Twelve about to fail. Zero surprises. That's predictive maintenance — and *that's* what happens when Snowflake and AWS work together."

---

## Key Demo Differentiators

1. **Closed-loop pipeline** — most demos show one or two services. This one shows five AWS services + Snowflake AI in one continuous flow: sensor -> ingest -> predict -> alert -> dispatch -> report.
2. **Real-time ingestion** — Snowpipe AUTO_INGEST from S3 with SQS notifications. Not batch. Not scheduled. Files land, data loads.
3. **Snowflake ML replaces SageMaker** — XGBoost model trained, registered, and serving inference entirely inside Snowflake. No external ML infrastructure.
4. **IoT SiteWise asset hierarchy** — 3 plants, 8 production lines, 100 assets. The digital twin mirrors the physical factory.
5. **Proactive alerting** — Snowflake Alert + SNS means the technician knows before the machine breaks.
6. **Bedrock structured output** — work-order Markdown is dispatchable, not a chat transcript.
7. **161 active alerts + 12 IMMINENT predictions** — fleet under real stress, not a toy with one alert.
8. **$36M maintenance backlog** — the business case writes itself.
9. **Cortex Search on 416 documents** — OEM manuals, handwritten technician notes, safety bulletins, spare parts. Institutional knowledge made searchable — not trapped in binders or someone's head.

---

## AWS Tab-Switch Quick Reference

| When | Service | URL |
|------|---------|-----|
| 0:20 | IoT SiteWise | `us-west-2.console.aws.amazon.com/iotsitewise/home?region=us-west-2#/assets` |
| 0:45 | S3 | `s3/buckets/sg-manufacturing-demos-2026?prefix=maintenance/realtime/` |
| 1:50 | SNS | `sns/v3/home?region=us-west-2#/topic/arn:aws:sns:us-west-2:018437500440:mfg-maintenance-critical-alerts` |
| 2:35 | Lambda | `lambda/home?region=us-west-2#/functions/mfg-maint-workorder-bedrock` |
| 2:40 | Bedrock | `bedrock/home?region=us-west-2#/foundation-models` |
| 2:45 | QuickSight | `quicksight.aws.amazon.com/sn/dashboards/mfg-maintenance-dashboard` |
