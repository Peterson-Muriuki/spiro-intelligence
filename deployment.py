"""
pages/4_Deployment.py
Swap station deployment optimizer + demand forecasting.

Integration: reads stations and swaps from st.session_state.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.deployment_optimizer import (
    generate_candidate_grid, score_candidates, recommend_top_locations,
)
from models.demand_forecast import prepare_daily_demand, forecast_demand

if "stations" not in st.session_state:
    st.warning("Please open the app via **app.py** (`streamlit run app.py`).")
    st.stop()

stations = st.session_state["stations"]
swaps    = st.session_state["swaps"]
country  = st.session_state.get("selected_country", "All")

st.markdown("## 📍 Station Deployment Optimizer")
st.caption(f"Market: **{country}** · Score candidate locations, forecast demand, guide expansion.")

GEO_CENTERS = {
    "Nairobi":       (-1.286389, 36.817223),
    "Mombasa":       (-4.043477, 39.668206),
    "Kisumu":        (-0.091702, 34.767956),
    "Nakuru":        (-0.303099, 36.080026),
    "Lagos":         (6.524379,  3.379206),
    "Abuja":         (9.072264,  7.491302),
    "Kano":          (12.00012,  8.51672),
    "Port Harcourt": (4.815333,  7.049444),
    "Kigali":        (-1.944,   30.0587),
    "Butare":        (-2.5975,  29.7397),
    "Kampala":       (0.347596, 32.58252),
    "Entebbe":       (0.0634,   32.4638),
    "Jinja":         (0.4478,   33.2026),
}

# ── City selector ──────────────────────────────────────────────────────────
st.markdown("### 🏙️ Select City for Deployment Analysis")
city_options  = sorted(GEO_CENTERS.keys())
selected_city = st.selectbox("City", city_options, index=0)
n_candidates  = st.slider("Candidate locations to evaluate", 20, 80, 40)

city_center = GEO_CENTERS[selected_city]

# ── Score candidates ───────────────────────────────────────────────────────
@st.cache_data(show_spinner="Scoring candidate locations...")
def score_city(city_name, n, _stations_df):
    np.random.seed(42)
    cands  = generate_candidate_grid(GEO_CENTERS[city_name], n=n)
    scored = score_candidates(cands, _stations_df)
    return scored

scored = score_city(selected_city, n_candidates, stations)
top5   = recommend_top_locations(scored, top_n=5)

col1, col2, col3 = st.columns(3)
col1.metric("High Priority Sites",   (scored["priority"] == "High").sum())
col2.metric("Medium Priority Sites", (scored["priority"] == "Medium").sum())
col3.metric("Avg Coverage Gap (km)", f"{scored['nearest_station_km'].mean():.1f}")

st.markdown("---")

# ── Map ────────────────────────────────────────────────────────────────────
st.markdown("### 🗺️ Candidate Locations Map")
m = folium.Map(location=list(city_center), zoom_start=12, tiles="CartoDB positron")

for _, row in stations[stations["status"] == "active"].iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]], radius=8,
        color="blue", fill=True, fill_color="blue", fill_opacity=0.6,
        tooltip=f"Existing: {row['station_id']}",
    ).add_to(m)

PRIORITY_COLORS = {"High": "red", "Medium": "orange", "Low": "gray"}
for _, row in scored.iterrows():
    color  = PRIORITY_COLORS.get(str(row["priority"]), "gray")
    radius = 4 + row["deployment_score"] / 20
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=radius, color=color, fill=True, fill_color=color, fill_opacity=0.7,
        tooltip=f"{row['candidate_id']} — Score: {row['deployment_score']} ({row['priority']})",
    ).add_to(m)

legend_html = """
<div style='position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
            padding:10px 14px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.2);font-size:13px'>
<b>Deployment Priority</b><br>🔵 Existing · 🔴 High · 🟠 Medium · ⚪ Low
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))
st_folium(m, width=None, height=480, returned_objects=[])

# ── Top 5 ──────────────────────────────────────────────────────────────────
st.markdown("### 🥇 Top 5 Recommended Sites")
st.dataframe(
    top5.style.format({
        "deployment_score":   "{:.1f}",
        "nearest_station_km": "{:.2f}",
        "demand_density":     "{:.2f}",
        "coverage_gap":       "{:.2f}",
    }),
    use_container_width=True, hide_index=True,
)

st.markdown("### 📊 Score Breakdown")
fig_score = px.scatter(
    scored, x="nearest_station_km", y="deployment_score",
    color="priority", color_discrete_map=PRIORITY_COLORS,
    size="demand_density", template="plotly_white",
    labels={
        "nearest_station_km": "Distance to Nearest Station (km)",
        "deployment_score":   "Deployment Score",
    },
)
fig_score.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig_score, use_container_width=True)

# ── Demand forecast ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📈 Demand Forecast — Next 30 Days")

@st.cache_data(show_spinner="Running demand forecast...")
def run_forecast(_swaps_df):
    daily_demand = prepare_daily_demand(_swaps_df)
    return daily_demand, forecast_demand(daily_demand, periods=30)

daily_demand, fc = run_forecast(swaps)

hist_df = daily_demand.reset_index()
hist_df.columns = ["date", "swaps"]

fig_fc = go.Figure()
fig_fc.add_trace(go.Scatter(
    x=hist_df["date"], y=hist_df["swaps"],
    name="Historical", line=dict(color="#1D9E75", width=1.5),
))
fig_fc.add_trace(go.Scatter(
    x=fc["date"], y=fc["forecast"],
    name="Forecast", line=dict(color="#F97316", width=2, dash="dash"),
))
fig_fc.add_trace(go.Scatter(
    x=pd.concat([fc["date"], fc["date"][::-1]]),
    y=pd.concat([fc["upper"], fc["lower"][::-1]]),
    fill="toself", fillcolor="rgba(249,115,22,0.1)",
    line=dict(color="rgba(255,255,255,0)"),
    name="Confidence interval",
))
fig_fc.update_layout(
    template="plotly_white",
    xaxis_title="Date", yaxis_title="Daily Swaps",
    margin=dict(t=20, b=20),
    legend=dict(orientation="h"),
)
st.plotly_chart(fig_fc, use_container_width=True)

col_fc1, col_fc2, col_fc3 = st.columns(3)
col_fc1.metric("Avg Forecasted Swaps/Day", f"{fc['forecast'].mean():.0f}")
col_fc2.metric("Peak Forecasted Day",      f"{fc['forecast'].max():.0f}")
col_fc3.metric("30-Day Total Forecast",    f"{fc['forecast'].sum():.0f}")

# ── AI Deployment Recommendation ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 🤖 AI Deployment Recommendation")
if st.button("Get AI deployment recommendation", key="ai_deploy"):
    from utils.ai_engine import narrate_deployment
    with st.spinner("Generating AI deployment analysis..."):
        insight = narrate_deployment(scored, top5, selected_city)
    st.markdown(insight)
else:
    st.caption("Click above for an AI-generated deployment strategy for this city.")

# ── AI Deployment Recommendation ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 🤖 AI Deployment Recommendation")

from utils.ai_engine import ask_ai, ai_available, active_backend, prompt_deployment_recommendation

if not ai_available():
    st.info("AI insights unavailable. Add GROQ_API_KEY to Streamlit secrets or run Ollama locally.")
else:
    st.caption(f"Backend: {active_backend()}")
    if st.button("🏗️ Get AI Site Recommendation", key="ai_deployment"):
        top_sites_data = top5[["candidate_id","deployment_score","priority",
                                "nearest_station_km","demand_density","coverage_gap"]].to_dict("records")
        deployment_ctx = {
            "city":              selected_city,
            "top_sites":         top_sites_data,
            "total_candidates":  len(scored),
            "high_priority":     int((scored["priority"] == "High").sum()),
            "avg_coverage_gap":  round(float(scored["nearest_station_km"].mean()), 2),
            "demand_forecast_avg": round(float(fc["forecast"].mean()), 1),
        }
        with st.spinner(f"Generating deployment recommendation for {selected_city}..."):
            recommendation = ask_ai(
                prompt_deployment_recommendation(top_sites_data, selected_city),
                context=deployment_ctx,
            )
        st.markdown(recommendation)