"""
utils/alerts.py
Generates actionable alerts for the country manager.
These surface as a sidebar digest and can be exported.
"""
import pandas as pd
from datetime import datetime, timedelta

def generate_alerts(stations_df, customers_df, swap_events_df, kpis: dict) -> list[dict]:
    """Returns a list of alert dicts with level, title, message."""
    alerts = []

    # 1. Inactive stations
    inactive = stations_df[stations_df["status"] == "inactive"]
    if len(inactive) > 0:
        alerts.append({
            "level": "warning",
            "icon":  "⚠️",
            "title": f"{len(inactive)} stations offline",
            "message": f"Stations {', '.join(inactive['station_id'].head(3).tolist())} are inactive. Review for redeployment.",
        })

    # 2. High churn risk cluster
    churn_col = "churn_probability" if "churn_probability" in customers_df.columns else "churn_score"
    if churn_col in customers_df.columns:
        high_risk = (customers_df[churn_col] >= 0.6).sum()
        if high_risk > 0:
            pct = round(high_risk / len(customers_df) * 100, 1)
            alerts.append({
                "level": "danger",
                "icon":  "🔴",
                "title": f"{high_risk} high-risk customers ({pct}%)",
                "message": "Customers with >60% churn probability. Consider retention outreach.",
            })

    # 3. Revenue growth
    if kpis.get("revenue_growth_pct", 0) < 0:
        alerts.append({
            "level": "danger",
            "icon":  "📉",
            "title": f"Revenue declined {abs(kpis['revenue_growth_pct'])}% MoM",
            "message": "Monthly revenue is below prior period. Investigate underperforming markets.",
        })
    elif kpis.get("revenue_growth_pct", 0) > 10:
        alerts.append({
            "level": "success",
            "icon":  "📈",
            "title": f"Revenue up {kpis['revenue_growth_pct']}% MoM",
            "message": "Strong growth. Consider accelerating deployment in top-performing markets.",
        })

    # 4. Low utilisation stations
    cutoff = pd.to_datetime(swap_events_df["date"]).max() - timedelta(days=7)
    recent = swap_events_df[pd.to_datetime(swap_events_df["date"]) >= cutoff]
    station_counts = recent.groupby("station_id").size()
    active_ids = stations_df[stations_df["status"] == "active"]["station_id"]
    low_util = active_ids[~active_ids.isin(station_counts.index) |
                          active_ids.isin(station_counts[station_counts < 5].index)]
    if len(low_util) > 0:
        alerts.append({
            "level": "warning",
            "icon":  "🟡",
            "title": f"{len(low_util)} low-utilisation stations (7 days)",
            "message": f"Fewer than 5 swaps/week. Consider relocating or running local campaigns.",
        })

    # 5. Maintenance stations
    maint = stations_df[stations_df["status"] == "maintenance"]
    if len(maint) > 0:
        alerts.append({
            "level": "info",
            "icon":  "🔧",
            "title": f"{len(maint)} stations under maintenance",
            "message": f"Ensure SLA timelines are met to restore capacity.",
        })

    return alerts

def format_alert_html(alert: dict) -> str:
    colors = {
        "danger":  ("#fee2e2", "#b91c1c"),
        "warning": ("#fef9c3", "#92400e"),
        "success": ("#dcfce7", "#166534"),
        "info":    ("#e0f2fe", "#075985"),
    }
    bg, fg = colors.get(alert["level"], ("#f3f4f6", "#374151"))
    return f"""
    <div style='background:{bg};border-left:4px solid {fg};padding:10px 14px;
                border-radius:6px;margin-bottom:8px;'>
      <strong style='color:{fg}'>{alert["icon"]} {alert["title"]}</strong><br>
      <span style='color:{fg};font-size:0.85em'>{alert["message"]}</span>
    </div>
    """
