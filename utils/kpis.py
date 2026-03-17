
"""
utils/kpis.py
Core KPI calculations used across all dashboard pages.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def compute_station_kpis(stations_df, swap_events_df, revenue_df):
    """Returns a dict of top-line KPIs for the overview page."""
    active_stations = (stations_df["status"] == "active").sum()
    total_stations  = len(stations_df)

    # Turnover rate = avg daily swaps per active station (last 30 days)
    cutoff = pd.to_datetime(swap_events_df["date"]).max() - timedelta(days=30)
    recent = swap_events_df[pd.to_datetime(swap_events_df["date"]) >= cutoff]
    daily_swaps_per_station = (
        len(recent) / 30 / max(active_stations, 1)
    )

    # Revenue
    latest_month = revenue_df["month"].max()
    latest_rev   = revenue_df[revenue_df["month"] == latest_month]["revenue_usd"].sum()
    prev_month   = revenue_df["month"].unique()
    prev_month   = sorted(prev_month)[-2] if len(prev_month) >= 2 else latest_month
    prev_rev     = revenue_df[revenue_df["month"] == prev_month]["revenue_usd"].sum()
    rev_growth   = ((latest_rev - prev_rev) / max(prev_rev, 1)) * 100

    # Success rate
    success_rate = swap_events_df["swap_successful"].mean() * 100

    # Avg idle time proxy (hours between swaps per station)
    station_events = swap_events_df.groupby("station_id").size()
    avg_events     = station_events.mean()
    idle_hours_proxy = max(0, 24 - (avg_events / 30))

    return {
        "active_stations":   int(active_stations),
        "total_stations":    int(total_stations),
        "daily_turnover":    round(daily_swaps_per_station, 1),
        "monthly_revenue":   round(latest_rev, 0),
        "revenue_growth_pct":round(rev_growth, 1),
        "swap_success_rate": round(success_rate, 1),
        "idle_hours_daily":  round(idle_hours_proxy, 1),
    }

def turnover_by_station(swap_events_df, stations_df, days=30):
    """Returns per-station turnover metrics."""
    cutoff = pd.to_datetime(swap_events_df["date"]).max() - timedelta(days=days)
    recent = swap_events_df[pd.to_datetime(swap_events_df["date"]) >= cutoff]
    counts = recent.groupby("station_id").size().reset_index(name="total_swaps")
    counts["daily_avg"] = (counts["total_swaps"] / days).round(1)
    merged = stations_df.merge(counts, on="station_id", how="left").fillna({"total_swaps": 0, "daily_avg": 0})
    merged["utilisation_pct"] = (
        merged["daily_avg"] / (merged["capacity"] * 0.8) * 100
    ).clip(0, 150).round(1)
    return merged

def revenue_trend(revenue_df, country=None):
    """Monthly revenue trend, optionally filtered by country."""
    df = revenue_df.copy()
    if country and country != "All":
        df = df[df["country"] == country]
    trend = df.groupby("month")["revenue_usd"].sum().reset_index()
    trend["month_dt"] = pd.to_datetime(trend["month"])
    return trend.sort_values("month_dt")

def country_summary(stations_df, swap_events_df, customers_df, revenue_df):
    """One-row-per-country summary for the overview table."""
    rows = []
    for country in stations_df["country"].unique():
        s   = stations_df[stations_df["country"] == country]
        c   = customers_df[customers_df["country"] == country]
        r   = revenue_df[revenue_df["country"] == country]
        rev = r[r["month"] == r["month"].max()]["revenue_usd"].sum()
        rows.append({
            "Country":          country,
            "Active Stations":  int((s["status"] == "active").sum()),
            "Total Stations":   len(s),
            "Customers":        len(c),
            "Monthly Rev ($)":  round(rev, 0),
            "Avg Churn Risk":   round(c["churn_probability"].mean() * 100, 1),
        })
    return pd.DataFrame(rows).sort_values("Monthly Rev ($)", ascending=False)