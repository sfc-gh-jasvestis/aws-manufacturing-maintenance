import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
import _snowflake
from snowflake.snowpark.context import get_active_session

session = get_active_session()

def coerce_numeric(df, cols=None):
    """Force Decimal/object cols to float64 so plotly renders them numerically (not as categorical)."""
    if df is None or len(df) == 0:
        return df
    target = cols or [c for c in df.columns if df[c].dtype == "object"]
    for c in target:
        try:
            df[c] = pd.Series([float(x) if x is not None else None for x in df[c]], index=df.index, dtype="float64")
        except (TypeError, ValueError):
            pass
    return df
st.set_page_config(page_title="Predictive Maintenance", layout="wide", page_icon="wrench")

STATUS_COLORS = {"OPERATIONAL": "#2ECC71", "WARNING": "#F39C12", "CRITICAL": "#E74C3C", "OFFLINE": "#7F8C8D"}

page = st.sidebar.radio("Navigation", ["Overview", "Equipment Health", "Anomaly Alerts", "Maintenance Schedule", "AI Work Order (AWS Bedrock)", "Ask Maintenance", "AWS Architecture"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.markdown("### Predictive Maintenance")
st.sidebar.caption("100 equipment / 200K sensor readings / 5K work orders")


@st.cache_data(ttl=60)
def load_health():
    df = coerce_numeric(session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH").to_pandas())
    for c in ["HEALTH_SCORE", "CRITICAL_SENSORS", "WARNING_SENSORS"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=60)
def load_anomaly():
    df = coerce_numeric(session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.CURATED.ANOMALY_ALERTS ORDER BY HOURS_TO_BREACH_ESTIMATE NULLS LAST").to_pandas())
    for c in ["CURRENT_VALUE", "THRESHOLD_HIGH", "THRESHOLD_LOW", "HOURS_TO_BREACH_ESTIMATE", "PCT_TO_THRESHOLD"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=60)
def load_schedule():
    df = coerce_numeric(session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.CURATED.MAINTENANCE_SCHEDULE").to_pandas())
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
        labels = [str(v) for v in sc["STATUS"].tolist()]
        values = [int(v) for v in sc["COUNT"].tolist()]
        colors = [STATUS_COLORS.get(l, "#888") for l in labels]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4, marker=dict(colors=colors), sort=False, textinfo="label+percent")])
        fig.update_layout(title="Equipment Status Distribution", height=380, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        th = h.groupby("EQUIPMENT_TYPE")["HEALTH_SCORE"].mean().reset_index().sort_values("HEALTH_SCORE")
        x_vals = [float(v) for v in th["HEALTH_SCORE"].tolist()]
        y_vals = [str(v) for v in th["EQUIPMENT_TYPE"].tolist()]
        fig = go.Figure(data=[go.Bar(x=x_vals, y=y_vals, orientation="h", marker=dict(color=x_vals, colorscale="RdYlGn", cmin=0, cmax=100), hovertemplate="<b>%{y}</b><br>Health: %{x:.1f}<extra></extra>")])
        fig.add_vline(x=60, line_dash="dash", line_color="orange", annotation_text="Warn 60")
        fig.add_vline(x=30, line_dash="dash", line_color="red", annotation_text="Crit 30")
        fig.update_layout(title="Avg Health Score by Type", height=380, margin=dict(t=40, b=10), xaxis_title="Health Score", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

elif page == "Equipment Health":
    st.title("Equipment Health")
    st.caption("Health score by individual equipment (0=critical, 100=optimal)")
    h = load_health()

    worst = h.nsmallest(20, "HEALTH_SCORE").sort_values("HEALTH_SCORE")
    x_vals = [float(v) for v in worst["HEALTH_SCORE"].tolist()]
    y_vals = [str(v) for v in worst["NAME"].tolist()]
    statuses = [str(v) for v in worst["STATUS"].tolist()]
    bar_colors = [STATUS_COLORS.get(s, "#888") for s in statuses]
    cd = [[str(t), str(l)] for t, l in zip(worst["EQUIPMENT_TYPE"].tolist(), worst["LOCATION"].tolist())]
    fig = go.Figure(data=[go.Bar(x=x_vals, y=y_vals, orientation="h", marker_color=bar_colors, customdata=cd, hovertemplate="<b>%{y}</b><br>Health: %{x:.1f}<br>Type: %{customdata[0]}<br>Location: %{customdata[1]}<extra></extra>")])
    fig.add_vline(x=30, line_dash="dash", line_color="red", annotation_text="Critical 30")
    fig.add_vline(x=60, line_dash="dash", line_color="orange", annotation_text="Warning 60")
    fig.update_layout(title="Bottom 20 Equipment by Health Score", height=600, margin=dict(t=40, b=10, l=200), xaxis_title="Health Score", yaxis_title="")
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
        ns = near.sort_values("HOURS_TO_BREACH_ESTIMATE", ascending=False)
        x_vals = [float(v) for v in ns["HOURS_TO_BREACH_ESTIMATE"].tolist()]
        y_vals = [str(v) for v in ns["EQUIPMENT_NAME"].tolist()]
        cd = [[str(s), float(c) if c is not None else 0.0, float(t) if t is not None else 0.0] for s, c, t in zip(ns["SENSOR_TYPE"].tolist(), ns["CURRENT_VALUE"].tolist(), ns["THRESHOLD_HIGH"].tolist())]
        fig = go.Figure(data=[go.Bar(x=x_vals, y=y_vals, orientation="h", marker=dict(color=x_vals, colorscale="OrRd_r"), customdata=cd, hovertemplate="<b>%{y}</b><br>Hours to breach: %{x:.1f}<br>Sensor: %{customdata[0]}<br>Current: %{customdata[1]:.2f}<br>Threshold: %{customdata[2]:.2f}<extra></extra>")])
        fig.update_layout(title="Hours to Threshold Breach (lower = more urgent)", height=450, margin=dict(t=40, b=10, l=200), xaxis_title="Hours", yaxis_title="")
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
        labels = [str(v) for v in ws["WO_STATUS"].tolist()]
        values = [int(v) for v in ws["COUNT"].tolist()]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4, sort=False, textinfo="label+percent")])
        fig.update_layout(title="Work Orders by Status", height=380, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        pr = s["PRIORITY"].value_counts().reset_index()
        pr.columns = ["PRIORITY", "COUNT"]
        x_vals = [str(v) for v in pr["PRIORITY"].tolist()]
        y_vals = [int(v) for v in pr["COUNT"].tolist()]
        prio_colors = {"CRITICAL": "#E74C3C", "HIGH": "#F39C12", "MEDIUM": "#3498DB", "LOW": "#2ECC71"}
        bar_colors = [prio_colors.get(p, "#888") for p in x_vals]
        fig = go.Figure(data=[go.Bar(x=x_vals, y=y_vals, marker_color=bar_colors, text=y_vals, textposition="auto", hovertemplate="<b>%{x}</b><br>Count: %{y}<extra></extra>")])
        fig.update_layout(title="Work Orders by Priority", height=380, margin=dict(t=40, b=10), yaxis_title="Count", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    if not overdue.empty:
        st.subheader(f"Overdue Items ({len(overdue)})")
        st.dataframe(overdue.sort_values("DAYS_OVERDUE", ascending=False)[["WO_ID", "EQUIPMENT_NAME", "WO_TYPE", "PRIORITY", "DAYS_OVERDUE", "COST_USD", "DESCRIPTION"]].head(30), use_container_width=True, hide_index=True)

elif page == "AI Work Order (AWS Bedrock)":
    st.title("AI Work Order Generator")
    st.caption("IoT SiteWise asset model + AWS Bedrock (via Lambda `mfg-maint-workorder-bedrock`)")
    try:
        eq = coerce_numeric(session.sql("SELECT EQUIPMENT_ID, NAME, STATUS, CRITICALITY, HEALTH_SCORE FROM MANUFACTURING_MAINTENANCE.CURATED.EQUIPMENT_HEALTH WHERE STATUS IN ('CRITICAL','WARNING') ORDER BY HEALTH_SCORE LIMIT 30").to_pandas())
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
