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

page = st.sidebar.radio("Navigation", ["Overview", "Equipment Health", "Anomaly Alerts", "ML Predictions (Snowflake ML)", "Maintenance Schedule", "Real-Time Ingestion (AWS IoT)", "AI Work Order (AWS Bedrock)", "Search Maintenance Docs", "Ask Maintenance"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.markdown("### Predictive Maintenance")
st.sidebar.caption("100 equipment / 200K sensor readings / 5K work orders (2.9K active) / ML RUL predictions")


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


@st.cache_data(ttl=60)
def load_rul():
    df = coerce_numeric(session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.ML.RUL_PREDICTIONS").to_pandas())
    for c in ["HEALTH_SCORE", "PREDICTED_DAYS_TO_FAILURE", "FAILURE_COUNT", "VIBRATION", "TEMPERATURE", "PRESSURE", "CURRENT_A"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=60)
def load_hierarchy():
    return session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.SITEWISE.VW_ASSET_HEALTH ORDER BY PLANT_NAME, PRODUCTION_LINE, EQUIPMENT_NAME").to_pandas()


@st.cache_data(ttl=60)
def load_realtime():
    return coerce_numeric(session.sql("SELECT * FROM MANUFACTURING_MAINTENANCE.RAW.SENSOR_READINGS_REALTIME ORDER BY INGESTED_AT DESC LIMIT 200").to_pandas())


if page == "Overview":
    st.title("Predictive Maintenance Dashboard")
    st.caption("Real-time equipment health monitoring and failure prediction")
    h = load_health()
    a = load_anomaly()
    s = load_schedule()

    breached_total = int((a["HOURS_TO_BREACH_ESTIMATE"] < 0).sum())
    breach_6h = int(((a["HOURS_TO_BREACH_ESTIMATE"] > 0) & (a["HOURS_TO_BREACH_ESTIMATE"] < 6) & (a["TREND_DIRECTION"] == "INCREASING")).sum())
    critical_assets = h[h["STATUS"].isin(["CRITICAL", "OFFLINE"])].nsmallest(1, "HEALTH_SCORE")
    if not critical_assets.empty:
        hero = critical_assets.iloc[0]
        hero_alerts = a[a["EQUIPMENT_NAME"] == hero["NAME"]].sort_values("HOURS_TO_BREACH_ESTIMATE")
        breached = hero_alerts[hero_alerts["HOURS_TO_BREACH_ESTIMATE"] < 0]
        if not breached.empty:
            worst = breached.iloc[0]
            sensor_label = worst['SENSOR_TYPE'].replace('_mm_s','').replace('_c','').replace('_bar','').replace('_a','').replace('_', ' ').title()
            st.error(f"🚨 CRITICAL FAILURE RISK: {hero['NAME']} at {int(hero['HEALTH_SCORE'])}% health — {sensor_label} EXCEEDED SAFE LIMIT ({worst['CURRENT_VALUE']:.1f} vs max {worst['THRESHOLD_HIGH']:.0f}) — {breached_total} sensors breached fleet-wide, {breach_6h} more within 6h — ${s['COST_USD'].sum()/1e6:.0f}M maintenance backlog at risk")
        elif not hero_alerts.empty:
            worst = hero_alerts.iloc[0]
            hrs = worst["HOURS_TO_BREACH_ESTIMATE"] if pd.notna(worst["HOURS_TO_BREACH_ESTIMATE"]) else 6
            sensor_label = worst['SENSOR_TYPE'].replace('_mm_s','').replace('_c','').replace('_bar','').replace('_a','').replace('_', ' ').title()
            st.error(f"🚨 CRITICAL FAILURE RISK: {hero['NAME']} at {int(hero['HEALTH_SCORE'])}% health — {sensor_label} approaching limit ({worst['CURRENT_VALUE']:.1f} / {worst['THRESHOLD_HIGH']:.0f}), breach in ~{hrs:.0f}h — {breach_6h} sensors fleet-wide within 6h — ${s['COST_USD'].sum()/1e6:.0f}M maintenance backlog at risk")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Equipment", len(h))
    c2.metric("🔴 Critical", int((h["STATUS"] == "CRITICAL").sum()), delta=f"{breached_total} breached", delta_color="inverse")
    c3.metric("⚠️ Warning", int((h["STATUS"] == "WARNING").sum()), delta=f"{breach_6h} <6h", delta_color="inverse")
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
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4, marker=dict(colors=colors), sort=False, textinfo="label+percent", textposition="inside")])
        fig.update_layout(title="Equipment Status Distribution", height=380, margin=dict(t=40, b=10, r=10), showlegend=False)
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
    st.dataframe(h[["EQUIPMENT_ID", "NAME", "EQUIPMENT_TYPE", "LOCATION", "STATUS", "CRITICALITY", "HEALTH_SCORE", "CRITICAL_SENSORS", "WARNING_SENSORS"]].sort_values("HEALTH_SCORE").reset_index(drop=True), use_container_width=True)

elif page == "Anomaly Alerts":
    st.title("Anomaly Alerts")
    st.caption("Sensor readings approaching or exceeding safe operating thresholds")
    a = load_anomaly()
    if a.empty:
        st.success("No active anomalies."); st.stop()

    inc = a[a["TREND_DIRECTION"] == "INCREASING"]
    already_breached = a[a["HOURS_TO_BREACH_ESTIMATE"] < 0]
    near = inc.dropna(subset=["HOURS_TO_BREACH_ESTIMATE"]).sort_values("HOURS_TO_BREACH_ESTIMATE").head(15)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Alerts", len(a))
    c2.metric("🔴 Already Breached", len(already_breached))
    c3.metric("⚠️ Increasing", len(inc))
    c4.metric("Breach <6h", int((inc.dropna(subset=['HOURS_TO_BREACH_ESTIMATE'])['HOURS_TO_BREACH_ESTIMATE'] < 6).sum()))

    if not near.empty:
        ns = near.sort_values("HOURS_TO_BREACH_ESTIMATE", ascending=False)
        x_vals = [float(v) for v in ns["HOURS_TO_BREACH_ESTIMATE"].tolist()]
        y_vals = [str(v) for v in ns["EQUIPMENT_NAME"].tolist()]
        cd = [[str(s), float(c) if c is not None else 0.0, float(t) if t is not None else 0.0] for s, c, t in zip(ns["SENSOR_TYPE"].tolist(), ns["CURRENT_VALUE"].tolist(), ns["THRESHOLD_HIGH"].tolist())]
        fig = go.Figure(data=[go.Bar(x=x_vals, y=y_vals, orientation="h", marker=dict(color=x_vals, colorscale="OrRd_r"), customdata=cd, hovertemplate="<b>%{y}</b><br>Hours to breach: %{x:.1f}<br>Sensor: %{customdata[0]}<br>Current: %{customdata[1]:.2f}<br>Threshold: %{customdata[2]:.2f}<extra></extra>")])
        fig.update_layout(title="Hours to Threshold Breach (lower = more urgent)", height=450, margin=dict(t=40, b=10, l=200), xaxis_title="Hours", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Alert Detail")
    st.dataframe(a[["EQUIPMENT_NAME", "EQUIPMENT_TYPE", "SENSOR_TYPE", "CURRENT_VALUE", "THRESHOLD_HIGH", "THRESHOLD_LOW", "TREND_DIRECTION", "HOURS_TO_BREACH_ESTIMATE", "PCT_TO_THRESHOLD"]].reset_index(drop=True), use_container_width=True)

elif page == "ML Predictions (Snowflake ML)":
    st.title("ML Predictions — Remaining Useful Life")
    st.caption("XGBoost model predicts days-to-failure per equipment (Snowflake Model Registry)")
    rul = load_rul()
    if rul.empty:
        st.info("No RUL predictions available."); st.stop()

    imminent = rul[rul["FAILURE_RISK"] == "IMMINENT"]
    soon = rul[rul["FAILURE_RISK"] == "SOON"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equipment", len(rul))
    c2.metric("🔴 Imminent (<7d)", len(imminent))
    c3.metric("⚠️ Soon (<30d)", len(soon))
    c4.metric("Avg Days to Failure", f"{rul['PREDICTED_DAYS_TO_FAILURE'].mean():.0f}d")

    RISK_COLORS = {"IMMINENT": "#E74C3C", "SOON": "#F39C12", "MONITOR": "#3498DB", "HEALTHY": "#2ECC71"}
    cc1, cc2 = st.columns(2)
    with cc1:
        x_vals = [float(v) for v in rul["HEALTH_SCORE"].tolist()]
        y_vals = [float(v) for v in rul["PREDICTED_DAYS_TO_FAILURE"].tolist()]
        colors = [RISK_COLORS.get(str(r), "#888") for r in rul["FAILURE_RISK"].tolist()]
        names = [str(v) for v in rul["EQUIPMENT_NAME"].tolist()]
        fig = go.Figure()
        for risk, color in RISK_COLORS.items():
            mask = rul["FAILURE_RISK"] == risk
            if mask.any():
                sub = rul[mask]
                fig.add_trace(go.Scatter(
                    x=[float(v) for v in sub["HEALTH_SCORE"].tolist()],
                    y=[float(v) for v in sub["PREDICTED_DAYS_TO_FAILURE"].tolist()],
                    mode="markers", name=risk, marker=dict(color=color, size=10),
                    text=[str(v) for v in sub["EQUIPMENT_NAME"].tolist()],
                    hovertemplate="<b>%{text}</b><br>Health: %{x:.0f}<br>Days to failure: %{y}<extra></extra>"
                ))
        fig.add_hline(y=7, line_dash="dash", line_color="red", annotation_text="Imminent (7d)")
        fig.add_hline(y=30, line_dash="dash", line_color="orange", annotation_text="Soon (30d)")
        fig.update_layout(title="Health Score vs Predicted Days to Failure", height=450, margin=dict(t=40, b=10), xaxis_title="Health Score", yaxis_title="Predicted Days to Failure")
        st.plotly_chart(fig, use_container_width=True)
    with cc2:
        rc = rul["FAILURE_RISK"].value_counts().reset_index()
        rc.columns = ["RISK", "COUNT"]
        labels = [str(v) for v in rc["RISK"].tolist()]
        values = [int(v) for v in rc["COUNT"].tolist()]
        pie_colors = [RISK_COLORS.get(l, "#888") for l in labels]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4, marker=dict(colors=pie_colors), sort=False, textinfo="label+percent", textposition="inside")])
        fig.update_layout(title="Failure Risk Distribution", height=450, margin=dict(t=40, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("All Predictions (sorted by urgency)")
    st.dataframe(rul[["EQUIPMENT_NAME", "EQUIPMENT_TYPE", "STATUS", "HEALTH_SCORE", "PREDICTED_DAYS_TO_FAILURE", "FAILURE_RISK", "FAILURE_COUNT"]].sort_values("PREDICTED_DAYS_TO_FAILURE").reset_index(drop=True), use_container_width=True)

elif page == "Maintenance Schedule":
    st.title("Maintenance Schedule")
    st.caption("Active work orders — preventive & corrective maintenance backlog")
    s = load_schedule()
    if s.empty:
        st.info("No work orders."); st.stop()

    overdue = s[s["DAYS_OVERDUE"] > 0]
    total_cost = s["COST_USD"].sum()
    pct_overdue = len(overdue) / len(s) * 100 if len(s) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Work Orders", f"{len(s):,}")
    c2.metric("🔴 Overdue", f"{len(overdue):,}", delta=f"{pct_overdue:.0f}% of total", delta_color="inverse")
    c3.metric("Avg Days Overdue", f"{overdue['DAYS_OVERDUE'].mean():.0f}d" if not overdue.empty else "0d", delta="6 months behind" if overdue["DAYS_OVERDUE"].mean() > 150 else None, delta_color="inverse")
    c4.metric("💰 Cost Exposure", f"${total_cost/1e6:.0f}M")

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
        st.dataframe(overdue.sort_values("DAYS_OVERDUE", ascending=False)[["WO_ID", "EQUIPMENT_NAME", "WO_TYPE", "PRIORITY", "DAYS_OVERDUE", "COST_USD", "DESCRIPTION"]].head(30).reset_index(drop=True), use_container_width=True)

elif page == "Real-Time Ingestion (AWS IoT)":
    st.title("Real-Time Ingestion — AWS IoT SiteWise")
    st.caption("Factory sensor data flows from IoT SiteWise -> S3 -> Snowpipe -> Snowflake in real-time")
    hier = load_hierarchy()
    rt = load_realtime()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plants", int(hier["PLANT_NAME"].nunique()) if not hier.empty else 0)
    c2.metric("Production Lines", int(hier["PRODUCTION_LINE"].nunique()) if not hier.empty else 0)
    c3.metric("Assets (SiteWise)", len(hier))
    c4.metric("Realtime Readings", f"{len(rt):,}")

    if not hier.empty:
        st.subheader("Plant Hierarchy — IoT SiteWise Asset Model")
        for plant in sorted(hier["PLANT_NAME"].unique()):
            with st.expander(f"🏭 {plant} ({len(hier[hier['PLANT_NAME']==plant])} assets)"):
                ph = hier[hier["PLANT_NAME"] == plant]
                for line in sorted(ph["PRODUCTION_LINE"].unique()):
                    pl = ph[ph["PRODUCTION_LINE"] == line]
                    st.markdown(f"**{line}** ({len(pl)} assets)")
                    st.dataframe(pl[["EQUIPMENT_NAME", "EQUIPMENT_TYPE", "STATUS", "HEALTH_SCORE", "CRITICAL_SENSORS", "WARNING_SENSORS"]].sort_values("HEALTH_SCORE").reset_index(drop=True), use_container_width=True, height=150)

    if not rt.empty:
        st.subheader("Latest Real-Time Sensor Readings (Snowpipe)")
        st.caption("Auto-ingested from S3 via Snowpipe AUTO_INGEST")
        st.dataframe(rt.head(50).reset_index(drop=True), use_container_width=True)
    else:
        st.info("No real-time sensor readings ingested yet. Run: python scripts/simulate_sensor_stream.py --upload")

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
            st.dataframe(eq.reset_index(drop=True), use_container_width=True)
    except Exception as e:
        st.error(f"Work order error: {e}")

elif page == "Search Maintenance Docs":
    st.title("Search Maintenance Documentation")
    st.caption("416 documents: OEM manuals, technician field notes, safety bulletins, spare parts catalog (Cortex Search)")

    sc1, sc2 = st.columns([3, 1])
    with sc1:
        query = st.text_input("Search documents", placeholder="e.g. vibration bearing compressor, lockout tagout crane, SKF-6208")
    with sc2:
        cat_filter = st.selectbox("Category", ["All", "Machine_Manual", "Field_Note", "Safety_Bulletin", "Spare_Parts"])

    if query:
        try:
            filter_obj = {}
            if cat_filter != "All":
                filter_obj = {"@eq": {"CATEGORY": cat_filter}}
            body = {
                "query": query,
                "columns": ["DOC_ID", "TITLE", "CATEGORY", "EQUIPMENT_TYPE", "EQUIPMENT_ID", "AUTHOR", "DOC_DATE", "CONTENT"],
                "filter": filter_obj,
                "limit": 10
            }
            resp = _snowflake.send_snow_api_request(
                "POST",
                "/api/v2/databases/MANUFACTURING_MAINTENANCE/schemas/SEARCH/cortex-search-services/MAINTENANCE_DOCS_SEARCH:query",
                {}, {}, body, None, 30000
            )
            parsed = json.loads(resp["content"])
            results = parsed.get("results", [])
            if results:
                st.markdown(f"**{len(results)} results**")
                for r in results:
                    cat = r.get("CATEGORY", "")
                    badge_colors = {"Machine_Manual": "blue", "Field_Note": "orange", "Safety_Bulletin": "red", "Spare_Parts": "green"}
                    badge = f":{'red' if cat == 'Safety_Bulletin' else 'blue'}[{cat.replace('_', ' ')}]"
                    title = r.get("TITLE", "Untitled")
                    with st.expander(f"{badge} **{title}** — {r.get('EQUIPMENT_TYPE', '')} | {r.get('AUTHOR', '')} | {r.get('DOC_DATE', '')}"):
                        content = r.get("CONTENT", "")
                        st.markdown(content[:2000])
                        if r.get("EQUIPMENT_ID"):
                            st.caption(f"Equipment: {r['EQUIPMENT_ID']}")
            else:
                st.info("No results found. Try a different query.")
        except Exception as e:
            st.error(f"Search error: {e}")

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
                                st.dataframe(session.sql(sql).to_pandas().reset_index(drop=True), use_container_width=True)
                            except Exception:
                                pass
                else:
                    st.error(parsed)
            except Exception as e:
                st.error(f"Error: {e}")

