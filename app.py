# app.py  ·  Spiro Swap Station Intelligence Dashboard
# Entry point — run with: streamlit run app.py

import streamlit as st
import pandas as pd
import os, sys, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Page config (MUST be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Spiro Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auto-generate data if CSVs are missing ─────────────────────────────────
DATA_FILES = [
    "data/stations.csv",
    "data/customers.csv",
    "data/swap_events.csv",
    "data/revenue.csv",
]

def data_exists() -> bool:
    return all(os.path.exists(f) for f in DATA_FILES)

if not data_exists():
    with st.spinner("First run detected — generating synthetic data (takes ~20s)..."):
        result = subprocess.run(
            [sys.executable, "data/generate_data.py"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            st.error(f"Data generation failed:\n{result.stderr}")
            st.stop()
    st.success("Data generated. Loading dashboard...")
    st.rerun()

# ── Data loader (cached for 1 hour) ───────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Loading data...")
def load_all_data():
    stations  = pd.read_csv("data/stations.csv")
    customers = pd.read_csv("data/customers.csv", parse_dates=["join_date"])
    swaps     = pd.read_csv(
        "data/swap_events.csv",
        parse_dates=["timestamp", "date"],
        dtype={"swap_id": str, "station_id": str, "customer_id": str},
    )
    revenue   = pd.read_csv("data/revenue.csv")
    return stations, customers, swaps, revenue

stations, customers, swaps, revenue = load_all_data()

# ── Push to session_state so every page can read without re-loading ────────
st.session_state["stations"]  = stations
st.session_state["customers"] = customers
st.session_state["swaps"]     = swaps
st.session_state["revenue"]   = revenue

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    try:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Ev_logo.svg/120px-Ev_logo.svg.png",
            width=55,
        )
    except Exception:
        pass

    st.markdown("## ⚡ Spiro Intelligence")
    st.caption("Country Manager Decision Support")
    st.markdown("---")

    # Country filter
    country_options  = ["All"] + sorted(stations["country"].unique().tolist())
    selected_country = st.selectbox("🌍 Country", country_options, key="country_selector")
    st.session_state["selected_country"] = selected_country

    st.markdown("---")

    # Live alerts
    from utils.kpis import compute_station_kpis
    from utils.alerts import generate_alerts, format_alert_html

    kpis   = compute_station_kpis(stations, swaps, revenue)
    alerts = generate_alerts(stations, customers, swaps, kpis)

    st.markdown("### 🔔 Live Alerts")
    if alerts:
        for alert in alerts[:4]:
            st.markdown(format_alert_html(alert), unsafe_allow_html=True)
    else:
        st.caption("No active alerts.")

    st.markdown("---")

    # ✅ FIXED BLOCK (no indentation issues)
    st.markdown(
"""**Pages**
1. 📊 Overview
2. 🗺️ Station Map
3. 🔮 Churn & LTV
4. 📍 Deployment
5. 📄 Reports
6. 💹 Financial Model
""",
    unsafe_allow_html=False,
    )

    st.markdown("---")
    st.caption(f"Refreshed: {pd.Timestamp.now().strftime('%d %b %Y %H:%M')}")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# ── Home / Landing page ────────────────────────────────────────────────────
st.markdown("## ⚡ Spiro Swap Station Intelligence")
st.markdown("*Country Manager Decision Support System — Analytics, Operations & Finance*")
st.markdown("---")

# KPIs
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    "Active Stations",
    kpis["active_stations"],
    f"of {kpis['total_stations']} total",
)

col2.metric(
    "Daily Turnover",
    f"{kpis['daily_turnover']}x",
    "swaps / station / day",
)

col3.metric(
    "Monthly Revenue",
    f"${kpis['monthly_revenue']:,.0f}",
    f"{kpis['revenue_growth_pct']:+.1f}% MoM",
)

col4.metric(
    "Swap Success Rate",
    f"{kpis['swap_success_rate']}%",
)

col5.metric(
    "Idle Hours / Day",
    f"{kpis['idle_hours_daily']}h",
    "per station",
)

st.markdown("---")

st.info(
    "👈 Use the sidebar to navigate pages and filter by country. "
    "Start with **1 Overview** for a full market snapshot, "
    "or jump to **6 Financial Model** for station economics and DCF analysis."
)

# Country summary
from utils.kpis import country_summary

summary = country_summary(stations, swaps, customers, revenue)

st.markdown("### 🌍 Country Snapshot")
st.dataframe(
    summary.style.format({
        "Monthly Rev ($)": "${:,.0f}",
        "Avg Churn Risk": "{:.1f}%",
    }),
    use_container_width=True,
    hide_index=True,
)

# Financial preview
st.markdown("---")
st.markdown("### 💹 Financial Model Quick View")

from models.financial_model import unit_economics, breakeven_analysis

ue = unit_economics({})
be = breakeven_analysis({})

fc1, fc2, fc3, fc4 = st.columns(4)

fc1.metric("Revenue / Station / Month", f"${ue['gross_revenue']:,.0f}")
fc2.metric(
    "EBITDA / Station / Month",
    f"${ue['ebitda']:,.0f}",
    f"{ue['ebitda_margin_pct']:.1f}% margin",
)
fc3.metric("Breakeven Swaps / Day", f"{be['breakeven_swaps_per_day']}")
fc4.metric("Margin of Safety", f"{be['margin_of_safety_pct']:.1f}%")

st.caption("👆 Default assumptions. Open **6 Financial Model** to adjust all parameters interactively.")