# Predictive Maintenance — Demo Script

## Story

You're Tom Anderson, Plant Manager at a major port facility. An AI alert fires: Crane 7 vibration is climbing toward the danger zone. Within 3.5 minutes, you'll see the anomaly trend, understand you have 26 hours before predicted failure, recall that crane failures average $2.3M in damage and downtime, schedule preventive maintenance, and discover a second asset (Reefer 12) starting to drift.

## Personas

| Persona | Title | Goal |
|---------|-------|------|
| **Tom Anderson** | Plant Manager | Zero unplanned downtime, protect asset life |
| **Lisa Chang** | VP Operations | Reduce maintenance cost, improve uptime KPIs |

## What's Built

| Layer | Object | Purpose |
|-------|--------|---------|
| Data | 100 assets, 200K sensor readings, 5K work orders, 500 failures | Complete maintenance model |
| Dynamic Tables | EQUIPMENT_HEALTH, ANOMALY_ALERTS, MAINTENANCE_SCHEDULE | Real-time health scoring |
| ML | Sensor Anomaly Detection (unsupervised) | Detects drift before threshold breach |
| Search | MAINTENANCE_DOCS_SEARCH (100 docs) | Procedure & manual retrieval |
| Semantic View | MAINTENANCE_ANALYTICS_VIEW | Natural language analytics |
| Agent | MAINTENANCE_AGENT | Conversational maintenance assistant |
| Streamlit | PREDICTIVE_MAINTENANCE_APP | Plant operations dashboard |

## Narrative Arc

```
ALERT → INVESTIGATE → QUANTIFY RISK → PREVENT → DISCOVER MORE
  │          │              │              │            │
  ▼          ▼              ▼              ▼            ▼
Crane 7    5.6mm/s       $2.3M avg     Schedule     Reefer 12
vibration  trending UP   crane failure  PM work     also drifting
                         26h to breach  order
```

## Timed Script (3.5 minutes)

### Opening — Plant Health Dashboard (0:00–0:20)
- Open Streamlit app — PREDICTIVE_MAINTENANCE_APP
- "I'm Tom Anderson, managing 100 critical assets at this facility"
- KPI cards: 100 assets | 2 active alerts | 12 overdue PMs | 93% fleet health
- **Key visual:** Equipment health heatmap with Crane 7 in orange/red

### Beat 1 — The AI Alert (0:20–0:50)
- Click on Anomaly Alerts panel
- "Crane 7 — vibration reading at 5.6 mm/s. Threshold is 6.0"
- "The AI detected this as anomalous 2 days ago based on the rate of increase"
- Show sensor trend chart: clear upward trajectory
- **Number:** 5.6 mm/s current, 6.0 threshold, INCREASING trend

### Beat 2 — Time to Failure (0:50–1:20)
- Show predictive window
- "Based on the rate of increase, we have approximately 26 hours before breach"
- "Without intervention, historical data shows crane failure within 48-72 hours after threshold"
- "That's our window — 26 hours to act"
- **Number:** ~26 hours to threshold breach

### Beat 3 — Quantify the Risk (1:20–1:50)
- Switch to Failure History tab
- Filter: EQUIPMENT_TYPE = 'CRANE'
- "Average crane failure costs $2.3M — that's parts, labor, and lost throughput"
- "Last failure was 8 months ago — 3 days of downtime"
- "We've had 3 emergency work orders on Crane 7 in the last month alone"
- **Number:** $2.3M avg cost, 3 days downtime, 3 emergency WOs in 30 days

### Beat 4 — Ask AI for Action Plan (1:50–2:30)
- Open AI Assistant
- Type: "What maintenance should we perform on Crane 7 given the vibration trend?"
- Agent responds: bearing inspection, alignment check, lubrication procedure
- Cortex Search retrieves specific maintenance procedures from manuals
- "The agent pulled the exact procedure from our maintenance manual"
- **Key moment:** AI gives specific, actionable maintenance steps

### Beat 5 — Discover Secondary Risk (2:30–3:10)
- Type: "Are any other assets showing early warning signs?"
- Agent identifies: Reefer 12 — temperature at -15.8°C, threshold -15°C, INCREASING
- "Reefer 12 is also drifting — 57 hours to threshold but worth watching"
- "Proactive detection caught two issues before they became emergencies"
- **Number:** Reefer 12: -15.8°C current, -15°C threshold, ~57h window

### Closing — Preventive Action (3:10–3:30)
- Return to dashboard
- "Immediate work order for Crane 7 — bearing inspection tomorrow morning"
- "Reefer 12 goes on the watch list for end of week"
- "Two prevented failures: $2.3M in avoided crane damage, zero unplanned downtime"
- **Tagline:** "Catch the drift before it becomes a disaster"

## Pre-Recording Checklist

- [ ] Streamlit app loaded with equipment health view
- [ ] Crane 7 showing 5.6 mm/s vibration, threshold 6.0
- [ ] Anomaly alert active and visible
- [ ] Failure history showing $2.3M average crane cost
- [ ] 3 emergency work orders visible for Crane 7
- [ ] Agent responding with maintenance recommendation
- [ ] Reefer 12 showing as secondary alert
- [ ] Search returning maintenance procedures
- [ ] Warehouse CORTEX is STARTED

## Key Questions to Anticipate

1. **"How early can it detect?"** — Anomaly detection catches drift 2-5 days before threshold breach depending on rate of change
2. **"What sensors are used?"** — Vibration (mm/s), temperature (°C), pressure (bar), current (A) — configurable per asset type
3. **"False positive rate?"** — Model tuned for <5% false positive; confirmed by 3 emergency WOs pattern on Crane 7
4. **"Integration with CMMS?"** — Work order export via API or S3; can integrate with SAP PM, Maximo, or any CMMS
5. **"ROI calculation?"** — $2.3M avg failure × prevented incidents vs. $15K preventive maintenance cost = 150x ROI per catch
