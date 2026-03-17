"""
pages/2_Station_Map.py
Interactive geospatial map of swap stations.

Integration: reads from st.session_state only.
"""
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.kpis import turnover_by_station

if "stations" not in st.session_state:
    st.warning("Please open the app via **app.py** (`streamlit run app.py`).")
    st.stop()

stations = st.session_state["stations"]
swaps    = st.session_state["swaps"]
country  = st.session_state.get("selected_country", "All")

turnover_df = turnover_by_station(swaps, stations)
if country != "All":
    turnover_df = turnover_df[turnover_df["country"] == country]

st.markdown("## 🗺️ Swap Station Map")
st.caption(f"Market: **{country}** · Geographic distribution, utilisation, and status.")

# ── Filters ────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
status_filter = col_f1.multiselect(
    "Status", ["active", "inactive", "maintenance"],
    default=["active", "maintenance"],
)
city_options = ["All"] + sorted(turnover_df["city"].unique().tolist())
city_filter  = col_f2.selectbox("City", city_options)
util_min     = col_f3.slider("Min Utilisation %", 0, 150, 0)

filtered = turnover_df[turnover_df["status"].isin(status_filter)]
if city_filter != "All":
    filtered = filtered[filtered["city"] == city_filter]
filtered = filtered[filtered["utilisation_pct"] >= util_min]

st.caption(f"Showing **{len(filtered)}** stations")

# ── Folium map ─────────────────────────────────────────────────────────────
center_lat = filtered["lat"].mean() if len(filtered) > 0 else -1.28
center_lon = filtered["lon"].mean() if len(filtered) > 0 else 36.82

m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="CartoDB positron")

STATUS_COLORS = {"active": "green", "inactive": "red", "maintenance": "orange"}

for _, row in filtered.iterrows():
    color  = STATUS_COLORS.get(row["status"], "blue")
    radius = max(5, min(20, row["utilisation_pct"] / 10))
    popup_html = (
        f"<b>{row['station_id']}</b><br>"
        f"City: {row['city']}, {row['country']}<br>"
        f"Status: <b>{row['status']}</b><br>"
        f"Capacity: {row['capacity']} batteries<br>"
        f"Daily avg swaps: {row['daily_avg']}<br>"
        f"Utilisation: {row['utilisation_pct']:.0f}%<br>"
        f"Zone: {row.get('zone_type', 'N/A')}"
    )
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=radius,
        color=color, fill=True, fill_color=color, fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=f"{row['station_id']} — {row['utilisation_pct']:.0f}% util",
    ).add_to(m)

legend_html = """
<div style='position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
            padding:10px 14px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.2);font-size:13px'>
<b>Station Status</b><br>
🟢 Active &nbsp; 🔴 Inactive &nbsp; 🟠 Maintenance<br>
<i>Circle size = utilisation %</i>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))

col_map, col_stats = st.columns([2, 1])
with col_map:
    st_folium(m, width=None, height=520, returned_objects=[])

with col_stats:
    st.markdown("### 📊 Station Stats")
    st.metric("Displayed",       len(filtered))
    st.metric("Active",          (filtered["status"] == "active").sum())
    st.metric("Avg Utilisation", f"{filtered['utilisation_pct'].mean():.1f}%")
    st.metric("Avg Daily Swaps", f"{filtered['daily_avg'].mean():.1f}")

    st.markdown("---")
    status_counts = filtered["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    fig_s = px.bar(
        status_counts, x="Status", y="Count",
        color="Status", color_discrete_map=STATUS_COLORS,
        template="plotly_white",
    )
    fig_s.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_s, use_container_width=True)

st.markdown("### 📉 Utilisation Distribution")
fig_u = px.histogram(
    filtered, x="utilisation_pct", nbins=25,
    color="status", color_discrete_map=STATUS_COLORS,
    template="plotly_white",
    labels={"utilisation_pct": "Utilisation %"},
)
fig_u.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig_u, use_container_width=True)

with st.expander("📋 Full Station Table"):
    show_cols = [c for c in
                 ["station_id","city","country","status","capacity","daily_avg","utilisation_pct","zone_type"]
                 if c in filtered.columns]
    st.dataframe(
        filtered[show_cols].sort_values("utilisation_pct", ascending=False),
        use_container_width=True, hide_index=True,
    )