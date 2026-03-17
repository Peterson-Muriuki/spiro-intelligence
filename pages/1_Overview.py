"""
pages/1_Overview.py
Operational overview: KPI cards, revenue trend, peak hours, station turnover.

Integration: reads all data from st.session_state (set by app.py).
             Never calls st.set_page_config — that lives in app.py only.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.kpis import compute_station_kpis, turnover_by_station

# ── Guard: ensure data is loaded ──────────────────────────────────────────
if "stations" not in st.session_state:
    st.warning("Please open the app via **app.py** (`streamlit run app.py`).")
    st.stop()

stations  = st.session_state["stations"]
customers = st.session_state["customers"]
swaps     = st.session_state["swaps"]
revenue   = st.session_state["revenue"]
country   = st.session_state.get("selected_country", "All")

# ── Country filter ─────────────────────────────────────────────────────────
if country != "All":
    station_ids = stations[stations["country"] == country]["station_id"].tolist()
    stations_f  = stations[stations["country"] == country]
    customers_f = customers[customers["country"] == country]
    swaps_f     = swaps[swaps["station_id"].isin(station_ids)]
    revenue_f   = revenue[revenue["country"] == country]
else:
    stations_f, customers_f, swaps_f, revenue_f = stations, customers, swaps, revenue

kpis = compute_station_kpis(stations_f, swaps_f, revenue_f)

# ── Header ─────────────────────────────────────────────────────────────────
st.markdown("## 📊 Operational Overview")
st.caption(f"Market: **{country}** · KPIs, revenue trends, turnover, and demand patterns.")

# ── KPI cards ──────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Active Stations",    kpis["active_stations"],    f"of {kpis['total_stations']}")
c2.metric("Daily Turnover",     f"{kpis['daily_turnover']}x")
c3.metric("Monthly Revenue",    f"${kpis['monthly_revenue']:,.0f}", f"{kpis['revenue_growth_pct']:+.1f}%")
c4.metric("Swap Success Rate",  f"{kpis['swap_success_rate']}%")
c5.metric("Idle Hours/Day",     f"{kpis['idle_hours_daily']}h")

st.markdown("---")

# ── Revenue trend ──────────────────────────────────────────────────────────
st.markdown("### 📈 Monthly Revenue Trend")

if country == "All":
    rev_by_country = revenue.groupby(["month", "country"])["revenue_usd"].sum().reset_index()
    rev_by_country["month_dt"] = pd.to_datetime(rev_by_country["month"])
    fig_rev = px.area(
        rev_by_country.sort_values("month_dt"),
        x="month_dt", y="revenue_usd", color="country",
        template="plotly_white",
        labels={"month_dt": "Month", "revenue_usd": "Revenue (USD)", "country": "Country"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
else:
    rev_trend = revenue_f.groupby("month")["revenue_usd"].sum().reset_index()
    rev_trend["month_dt"] = pd.to_datetime(rev_trend["month"])
    fig_rev = px.area(
        rev_trend.sort_values("month_dt"),
        x="month_dt", y="revenue_usd",
        template="plotly_white",
        labels={"month_dt": "Month", "revenue_usd": "Revenue (USD)"},
        color_discrete_sequence=["#1D9E75"],
    )
fig_rev.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig_rev, use_container_width=True)

col_l, col_r = st.columns(2)

# ── Peak hours ─────────────────────────────────────────────────────────────
with col_l:
    st.markdown("### ⏱ Peak Swap Hours")
    hourly = swaps_f.groupby("hour").size().reset_index(name="swaps")
    fig_h = px.bar(
        hourly, x="hour", y="swaps",
        template="plotly_white",
        labels={"hour": "Hour of Day", "swaps": "Swaps"},
        color="swaps", color_continuous_scale="Teal",
    )
    fig_h.update_layout(margin=dict(t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig_h, use_container_width=True)

# ── Day of week ────────────────────────────────────────────────────────────
with col_r:
    st.markdown("### 📅 Swaps by Day of Week")
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    daily = swaps_f.groupby("day_of_week").size().reset_index(name="swaps")
    daily["day_of_week"] = pd.Categorical(daily["day_of_week"], categories=day_order, ordered=True)
    daily = daily.sort_values("day_of_week")
    fig_d = px.bar(
        daily, x="day_of_week", y="swaps",
        template="plotly_white",
        color="swaps", color_continuous_scale="Purpor",
        labels={"day_of_week": "", "swaps": "Swaps"},
    )
    fig_d.update_layout(margin=dict(t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig_d, use_container_width=True)

# ── Turnover table ─────────────────────────────────────────────────────────
st.markdown("### 🔄 Station Turnover (Last 30 Days)")
turnover = turnover_by_station(swaps_f, stations_f)
top_cols = [c for c in
            ["station_id","city","country","status","capacity","daily_avg","utilisation_pct"]
            if c in turnover.columns]
st.dataframe(
    turnover[top_cols].sort_values("daily_avg", ascending=False).head(20)
    .style.format({"daily_avg": "{:.1f}", "utilisation_pct": "{:.0f}%"}),
    use_container_width=True, hide_index=True,
)

# ── Customer segment ───────────────────────────────────────────────────────
st.markdown("### 👤 Customer Segment Distribution")
seg = customers_f.groupby("segment").size().reset_index(name="count")
fig_pie = px.pie(seg, names="segment", values="count",
                 hole=0.4, template="plotly_white",
                 color_discrete_sequence=px.colors.qualitative.Set3)
fig_pie.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig_pie, use_container_width=True)