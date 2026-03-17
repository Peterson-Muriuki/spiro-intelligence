"""
pages/5_Reports.py
Automated country manager report export (CSV + digest).

Integration: reads all data from st.session_state.
"""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.kpis   import compute_station_kpis, country_summary, turnover_by_station
from models.churn_model import train_churn_model, score_customers
from models.ltv_model   import compute_ltv

if "stations" not in st.session_state:
    st.warning("Please open the app via **app.py** (`streamlit run app.py`).")
    st.stop()

stations  = st.session_state["stations"]
customers = st.session_state["customers"]
swaps     = st.session_state["swaps"]
revenue   = st.session_state["revenue"]
country   = st.session_state.get("selected_country", "All")

st.markdown("## 📄 Country Manager Reports")
st.caption(f"Market: **{country}** · Export data packs for weekly or monthly briefings.")

# ── Scored customers (cached) ──────────────────────────────────────────────
@st.cache_data(show_spinner="Preparing report data...")
def get_scored(df: pd.DataFrame):
    model, feat = train_churn_model(df)
    scored, _   = score_customers(df, model, feat)
    return compute_ltv(scored)

scored_all = get_scored(customers)

# Apply country filter
if country != "All":
    station_ids = stations[stations["country"] == country]["station_id"].tolist()
    stations_r  = stations[stations["country"] == country]
    customers_r = scored_all[scored_all["country"] == country]
    swaps_r     = swaps[swaps["station_id"].isin(station_ids)]
    revenue_r   = revenue[revenue["country"] == country]
else:
    stations_r  = stations
    customers_r = scored_all
    swaps_r     = swaps
    revenue_r   = revenue

kpis     = compute_station_kpis(stations_r, swaps_r, revenue_r)
turnover = turnover_by_station(swaps_r, stations_r)
at_risk  = customers_r[customers_r["churn_score"] >= 0.5].sort_values("churn_score", ascending=False)

# ── Executive summary ──────────────────────────────────────────────────────
st.markdown("### 📊 Executive Summary")

summary_data = pd.DataFrame({
    "Metric": [
        "Active Stations", "Total Stations", "Daily Turnover Rate",
        "Monthly Revenue ($)", "Revenue Growth (%)", "Swap Success Rate (%)",
        "Total Customers", "High-Risk Customers (churn >60%)",
        "At-Risk Monthly Revenue ($)", "Avg Customer LTV ($)",
    ],
    "Value": [
        kpis["active_stations"],
        kpis["total_stations"],
        f"{kpis['daily_turnover']}x",
        f"${kpis['monthly_revenue']:,.0f}",
        f"{kpis['revenue_growth_pct']:+.1f}%",
        f"{kpis['swap_success_rate']}%",
        len(customers_r),
        int((customers_r["churn_score"] >= 0.6).sum()),
        f"${at_risk['monthly_revenue'].sum():,.0f}",
        f"${customers_r['ltv'].mean():,.0f}",
    ],
})
st.dataframe(summary_data, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Export buttons ────────────────────────────────────────────────────────
st.markdown("### 📥 Export Data Packs")

col1, col2, col3 = st.columns(3)
slug = country.lower().replace(" ", "_")

with col1:
    st.markdown("**Station Turnover Report**")
    st.caption("Per-station utilisation, capacity, daily averages — last 30 days.")
    export_cols = [c for c in
                   ["station_id","city","country","status","capacity","daily_avg","utilisation_pct","zone_type"]
                   if c in turnover.columns]
    st.download_button(
        "⬇️ Station Report (CSV)",
        data=turnover[export_cols].to_csv(index=False).encode("utf-8"),
        file_name=f"spiro_station_report_{slug}.csv",
        mime="text/csv",
    )

with col2:
    st.markdown("**At-Risk Customers List**")
    st.caption("Customers with churn score ≥ 0.5 — prioritised for outreach.")
    risk_cols = [c for c in
                 ["customer_id","country","city","segment","churn_score","monthly_revenue","ltv","tenure_months","swap_freq_monthly"]
                 if c in at_risk.columns]
    st.download_button(
        "⬇️ At-Risk List (CSV)",
        data=at_risk[risk_cols].head(500).to_csv(index=False).encode("utf-8"),
        file_name=f"spiro_at_risk_{slug}.csv",
        mime="text/csv",
    )

with col3:
    st.markdown("**Revenue by Station & Month**")
    st.caption("Full revenue table for finance and planning teams.")
    st.download_button(
        "⬇️ Revenue Data (CSV)",
        data=revenue_r.to_csv(index=False).encode("utf-8"),
        file_name=f"spiro_revenue_{slug}.csv",
        mime="text/csv",
    )

# ── Country comparison ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🌍 Full Country Comparison")
ctry_summary = country_summary(stations, swaps, customers, revenue)
st.dataframe(
    ctry_summary.style.format({
        "Monthly Rev ($)": "${:,.0f}",
        "Avg Churn Risk":  "{:.1f}%",
    }).background_gradient(subset=["Monthly Rev ($)"], cmap="Greens"),
    use_container_width=True, hide_index=True,
)
st.download_button(
    "⬇️ Country Summary (CSV)",
    data=ctry_summary.to_csv(index=False).encode("utf-8"),
    file_name="spiro_country_summary.csv",
    mime="text/csv",
)

# ── Weekly digest ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📧 Weekly Digest Preview")

digest_text = f"""
SPIRO WEEKLY INTELLIGENCE DIGEST
{'='*50}
Market: {country} | Generated: {pd.Timestamp.now().strftime('%d %b %Y')}

OPERATIONS
  Active stations : {kpis['active_stations']} of {kpis['total_stations']} total
  Daily turnover  : {kpis['daily_turnover']}x swaps per station
  Swap success    : {kpis['swap_success_rate']}%

REVENUE
  Monthly revenue : ${kpis['monthly_revenue']:,.0f}
  Growth MoM      : {kpis['revenue_growth_pct']:+.1f}%

CUSTOMER HEALTH
  Total customers : {len(customers_r)}
  High churn risk : {int((customers_r['churn_score'] >= 0.6).sum())} customers
  At-risk revenue : ${at_risk['monthly_revenue'].sum():,.0f}/month
  Avg LTV         : ${customers_r['ltv'].mean():,.0f}

ACTION ITEMS
  1. Review {len(stations_r[stations_r['status']=='inactive'])} inactive stations for redeployment.
  2. Initiate retention campaign for {len(at_risk)} at-risk customers.
  3. Prioritise top-scored deployment sites from Deployment page.
{'='*50}
"""
st.code(digest_text, language=None)
st.download_button(
    "⬇️ Download Digest (.txt)",
    data=digest_text.encode("utf-8"),
    file_name=f"spiro_digest_{slug}.txt",
    mime="text/plain",
)