import streamlit as st
import pandas as pd
import json
import plotly.express as px
import _snowflake
from snowflake.snowpark.context import get_active_session

session = get_active_session()
st.set_page_config(page_title="Predictive Maintenance", layout="wide", page_icon="wrench")

STATUS_COLORS = {"OPERATIONAL": "#2ECC71", "WARNING": "#F39C12", "CRITICAL": "#E74C3C", "OFFLINE": "#7F8C8D"}

page = st.sidebar.radio("Navigation", ["Overview", "Equipment Health", "Anomaly Alerts", "Maintenance Schedule", "AI Work Order (AWS Bedrock)", "Ask Maintenance", "AWS Architecture"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.markdown("### Predictive Maintenance")
st.sidebar.caption("100 equipment / 200K sensor readings / 5K work orders")


@st.cache_data(ttl=60)
def load_health():
    df = session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH").to_pandas()
    for c in ["HEALTH_SCORE", "CRITICAL_SENSORS", "WARNING_SENSORS"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=60)
def load_anomaly():
    df = session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.CURATED.ANOMALY_ALERTS ORDER BY HOURS_TO_BREACH_ESTIMATE NULLS LAST").to_pandas()
    for c in ["CURRENT_VALUE", "THRESHOLD_HIGH", "THRESHOLD_LOW", "HOURS_TO_BREACH_ESTIMATE", "PCT_TO_THRESHOLD"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=60)
def load_schedule():
    df = session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.CURATED.MAINTENANCE_SCHEDULE").to_pandas()
    for c in ["DAYS_OVERDUE", "COST_USD"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


if page == "Overview":
    st.title("Predictive Maintenance Dashboard")
    st.caption("Real-time equipment health monitoring and failure prediction")
    h = load_health()
    a = load_anomaly()
    s = load_schedule()

    crane7 = a[a["EQUIPMENT_NAME"].str.contains("Crane 7", na=False, regex=False) & (a["SENSOR_TYPE"] == "vibration_mm_s")]
    if not crane7.empty:
        c = crane7.iloc[0]
        hrs = c["HOURS_TO_BREACH_ESTIMATE"] if pd.notna(c["HOURS_TO_BREACH_ESTIMATE"]) else 26
        st.error(f"INCIDENT: Gantry Crane 7 vibration {c['CURRENT_VALUE']:.1f} mm/s (threshold {c['THRESHOLD_HIGH']:.1f}) - {c['TREND_DIRECTION']}, breach in ~{hrs:.0f}h - $2.3M intervention saving")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Equipment", len(h))
    c2.metric("Critical", int((h["STATUS"] == "CRITICAL").sum()), delta_color="inverse")
    c3.metric("Warning", int((h["STATUS"] == "WARNING").sum()), delta_color="inverse")
    c4.metric("Offline", int((h["STATUS"] == "OFFLINE").sum()), delta_color="inverse")
    c5.metric("Avg Health", f"{h['HEALTH_SCORE'].mean():.0f}/100")

    st.divider()
    cc1, cc2 = st.columns(2)
    with cc1:
        sc = h["STATUS"].value_counts().reset_index()
        sc.columns = ["STATUS", "COUNT"]
        fig = px.pie(sc, names="STATUS", values="COUNT", color="STATUS", color_discrete_map=STATUS_COLORS, title="Equipment Status Distribution", hole=0.4)
        fig.update_layout(height=380, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        th = h.groupby("EQUIPMENT_TYPE")["HEALTH_SCORE"].mean().reset_index().sort_values("HEALTH_SCORE")
        fig = px.bar(th, x="HEALTH_SCORE", y="EQUIPMENT_TYPE", orientation="h", color="HEALTH_SCORE", color_continuous_scale="RdYlGn", range_color=[0, 100], title="Avg Health Score by Type")
        fig.add_vline(x=60, line_dash="dash", line_color="orange", annotation_text="Warn 60")
        fig.add_vline(x=30, line_dash="dash", line_color="red", annotation_text="Crit 30")
        fig.update_layout(height=380, margin=dict(t=40, b=10), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Equipment Health":
    st.title("Equipment Health")
    st.caption("Health score by individual equipment (0=critical, 100=optimal)")
    h = load_health()

    worst = h.nsmallest(20, "HEALTH_SCORE")
    fig = px.bar(worst.sort_values("HEALTH_SCORE"), x="HEALTH_SCORE", y="NAME", orientation="h", color="STATUS", color_discrete_map=STATUS_COLORS, title="Bottom 20 Equipment by Health Score", hover_data=["EQUIPMENT_TYPE", "LOCATION"])
    fig.add_vline(x=30, line_dash="dash", line_color="red", annotation_text="Critical 30")
    fig.add_vline(x=60, line_dash="dash", line_color="orange", annotation_text="Warning 60")
    fig.update_layout(height=600, margin=dict(t=40, b=10, l=200))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("All Equipment")
    st.dataframe(h[["EQUIPMENT_ID", "NAME", "EQUIPMENT_TYPE", "LOCATION", "STATUS", "CRITICALITY", "HEALTH_SCORE", "CRITICAL_SENSORS", "WARNING_SENSORS"]].sort_values("HEALTH_SCORE"), use_container_width=True, hide_index=True)

elif page == "Anomaly Alerts":
    st.title("Anomaly Alerts")
    st.caption("Sensor readings approaching or exceeding thresholds")
    a = load_anomaly()
    if a.empty:
        st.success("No active anomalies."); st.stop()

    inc = a[a["TREND_DIRECTION"] == "INCREASING"]
    near = inc.dropna(subset=["HOURS_TO_BREACH_ESTIMATE"]).sort_values("HOURS_TO_BREACH_ESTIMATE").head(15)

    c1, c2, c3 = st.columns(3)
    c1.metric("Active Alerts", len(a))
    c2.metric("Increasing", len(inc))
    c3.metric("Breach in <12h", int((near["HOURS_TO_BREACH_ESTIMATE"] < 12).sum()))

    if not near.empty:
        fig = px.bar(near.sort_values("HOURS_TO_BREACH_ESTIMATE", ascending=False), x="HOURS_TO_BREACH_ESTIMATE", y="EQUIPMENT_NAME", orientation="h", color="HOURS_TO_BREACH_ESTIMATE", color_continuous_scale="OrRd_r", title="Hours to Threshold Breach (lower = more urgent)", hover_data=["SENSOR_TYPE", "CURRENT_VALUE", "THRESHOLD_HIGH"])
        fig.update_layout(height=450, margin=dict(t=40, b=10, l=200), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Alert Detail")
    st.dataframe(a[["EQUIPMENT_NAME", "EQUIPMENT_TYPE", "SENSOR_TYPE", "CURRENT_VALUE", "THRESHOLD_HIGH", "THRESHOLD_LOW", "TREND_DIRECTION", "HOURS_TO_BREACH_ESTIMATE", "PCT_TO_THRESHOLD"]], use_container_width=True, hide_index=True)

elif page == "Maintenance Schedule":
    st.title("Maintenance Schedule")
    st.caption("Work orders, overdue items, and total cost exposure")
    s = load_schedule()
    if s.empty:
        st.info("No work orders."); st.stop()

    overdue = s[s["DAYS_OVERDUE"] > 0]
    total_cost = s["COST_USD"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Work Orders", f"{len(s):,}")
    c2.metric("Overdue", f"{len(overdue):,}", delta_color="inverse")
    c3.metric("Avg Days Overdue", f"{overdue['DAYS_OVERDUE'].mean():.0f}d" if not overdue.empty else "0d")
    c4.metric("Total Cost", f"${total_cost/1e6:.1f}M")

    cc1, cc2 = st.columns(2)
    with cc1:
        ws = s["WO_STATUS"].value_counts().reset_index()
        ws.columns = ["WO_STATUS", "COUNT"]
        fig = px.pie(ws, names="WO_STATUS", values="COUNT", title="Work Orders by Status", hole=0.4)
        fig.update_layout(height=380, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        pr = s["PRIORITY"].value_counts().reset_index()
        pr.columns = ["PRIORITY", "COUNT"]
        fig = px.bar(pr, x="PRIORITY", y="COUNT", color="PRIORITY", title="Work Orders by Priority", color_discrete_map={"CRITICAL": "#E74C3C", "HIGH": "#F39C12", "MEDIUM": "#3498DB", "LOW": "#2ECC71"})
        fig.update_layout(height=380, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    if not overdue.empty:
        st.subheader(f"Overdue Items ({len(overdue)})")
        st.dataframe(overdue.sort_values("DAYS_OVERDUE", ascending=False)[["WO_ID", "EQUIPMENT_NAME", "WO_TYPE", "PRIORITY", "DAYS_OVERDUE", "COST_USD", "DESCRIPTION"]].head(30), use_container_width=True, hide_index=True)

elif page == "AI Work Order (AWS Bedrock)":
    st.title("AI Work Order Generator")
    st.caption("IoT SiteWise asset model + AWS Bedrock (via Lambda `mfg-maint-workorder-bedrock`)")
    try:
        eq = session.sql("SELECT EQUIPMENT_ID, NAME, STATUS, CRITICALITY, HEALTH_SCORE FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH WHERE STATUS IN ('CRITICAL','WARNING') ORDER BY HEALTH_SCORE LIMIT 30").to_pandas()
        c1, c2, c3 = st.columns(3)
        c1.metric("SiteWise assets", "100")
        c2.metric("AWS Hero", "Bedrock")
        c3.metric("Lambda", "mfg-maint-workorder-bedrock")
        if eq.empty:
            st.success("No critical / warning equipment.")
        else:
            options = [f"{r.EQUIPMENT_ID} - {r.NAME} ({r.STATUS}, health {r.HEALTH_SCORE:.1f})" for r in eq.itertuples()]
            sel = st.selectbox("Pick equipment", options)
            asset = sel.split(" - ")[0]
            if st.button("Generate work order"):
                with st.spinner("Calling Bedrock (via Cortex Complete in this demo)..."):
                    md = session.sql(f"CALL MANUFACTURING_MAINTENANCE.AI.SP_GENERATE_WORK_ORDER('{asset}')").to_pandas().iloc[0, 0]
                    st.success("Work order generated.")
                    st.markdown(md)
            st.divider()
            st.subheader("Critical / Warning equipment")
            st.dataframe(eq, use_container_width=True)
    except Exception as e:
        st.error(f"Work order error: {e}")

elif page == "Ask Maintenance":
    st.title("Ask the Data")
    st.caption("Natural language questions powered by Cortex Analyst")
    samples = ["Which equipment is most critical?", "How many work orders are overdue?", "Show me equipment with lowest health"]
    sample = st.selectbox("Sample questions:", [""] + samples)
    q = st.text_input("Or type your question:", value=sample)
    if q:
        with st.spinner("Cortex Analyst..."):
            try:
                body = {"messages": [{"role": "user", "content": [{"type": "text", "text": q}]}], "semantic_view": "MANUFACTURING_MAINTENANCE.AI.MAINTENANCE_ANALYTICS_VIEW"}
                resp = _snowflake.send_snow_api_request("POST", "/api/v2/cortex/analyst/message", {}, {}, body, None, 30000)
                parsed = json.loads(resp["content"])
                if resp["status"] < 400:
                    for block in parsed.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            st.markdown(block.get("text", ""))
                        elif block.get("type") == "sql":
                            sql = block.get("statement", "")
                            with st.expander("SQL"):
                                st.code(sql, language="sql")
                            try:
                                st.dataframe(session.sql(sql).to_pandas(), use_container_width=True, hide_index=True)
                            except Exception:
                                pass
                else:
                    st.error(parsed)
            except Exception as e:
                st.error(f"Error: {e}")

elif page == "AWS Architecture":
    st.title("AWS Architecture - Industrial AI Maintenance Co-pilot")
    st.caption("Snowflake + AWS IoT SiteWise + AWS Bedrock + QuickSight")
    a, b, c, d = st.columns(4)
    a.metric("AWS Hero", "IoT SiteWise + Bedrock")
    b.metric("SiteWise model", "mfg-maintenance/cranes")
    c.metric("Foundation model", "Claude 4 Sonnet")
    d.metric("Lambda", "mfg-maint-workorder-bedrock")
    st.markdown(
        """
**Data flow**

1. **Crane / pump / conveyor sensors** publish to **AWS IoT SiteWise** asset model `mfg-maintenance/cranes`.
2. SiteWise hot-tier exports to S3 (`s3://sg-manufacturing-demos-2026/maintenance/sitewise/`).
3. **Snowflake** ingests via external table -> Dynamic Tables -> `EQUIPMENT_HEALTH`, `ANOMALY_ALERTS`.
4. **Cortex AI** runs anomaly detection. When an asset crosses threshold, the operator clicks "Generate work order".
5. **AWS Lambda** `mfg-maint-workorder-bedrock` calls **Bedrock Claude** with the SiteWise asset context + Snowflake anomaly fields and returns a structured Markdown work order (parts, skills, ETA, safety).
6. **QuickSight** dashboard `mfg-maintenance-dashboard` and the **Amazon Q topic** `mfg-maintenance-q` give the maintenance manager an executive view.

**Demo note** — in this account the work-order LLM call is fulfilled by **Snowflake Cortex Complete** (Claude 4 Sonnet on Snowflake) so the demo runs without an AWS API integration. The customer flips this to a real Bedrock external function in production.

**ARNs**

- `arn:aws:iotsitewise:us-west-2:018437500440:asset-model/mfg-maintenance-cranes`
- `arn:aws:s3:::sg-manufacturing-demos-2026/maintenance/sitewise/`
- `arn:aws:lambda:us-west-2:018437500440:function:mfg-maint-workorder-bedrock`
- `arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-sonnet-4-v1:0`
        """
    )
