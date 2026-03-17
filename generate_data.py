"""
generate_data.py
Generates synthetic but realistic data for the Spiro Swap Station Intelligence dashboard.
Run once: python data/generate_data.py
"""
import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import os

fake = Faker()
np.random.seed(42)
random.seed(42)

COUNTRIES = ["Kenya", "Nigeria", "Rwanda", "Uganda"]
CITIES = {
    "Kenya":   ["Nairobi", "Mombasa", "Kisumu", "Nakuru"],
    "Nigeria": ["Lagos", "Abuja", "Kano", "Port Harcourt"],
    "Rwanda":  ["Kigali", "Butare", "Gisenyi"],
    "Uganda":  ["Kampala", "Entebbe", "Jinja"],
}
GEO_CENTERS = {
    "Nairobi":       (-1.286389, 36.817223),
    "Mombasa":       (-4.043477, 39.668206),
    "Kisumu":        (-0.091702, 34.767956),
    "Nakuru":        (-0.303099, 36.080026),
    "Lagos":         (6.524379, 3.379206),
    "Abuja":         (9.072264, 7.491302),
    "Kano":          (12.00012, 8.51672),
    "Port Harcourt": (4.815333, 7.049444),
    "Kigali":        (-1.944, 30.0587),
    "Butare":        (-2.5975, 29.7397),
    "Gisenyi":       (-1.7004, 29.2577),
    "Kampala":       (0.347596, 32.58252),
    "Entebbe":       (0.0634, 32.4638),
    "Jinja":         (0.4478, 33.2026),
}

# ── 1. STATIONS ──────────────────────────────────────────────────────────────
def generate_stations(n=80):
    rows = []
    sid = 1
    for country in COUNTRIES:
        for city in CITIES[country]:
            lat0, lon0 = GEO_CENTERS[city]
            n_city = random.randint(4, 8)
            for _ in range(n_city):
                capacity   = random.choice([10, 20, 30, 40])
                deployed   = random.choice([2020, 2021, 2022, 2023, 2024])
                rows.append({
                    "station_id":    f"ST{sid:04d}",
                    "country":       country,
                    "city":          city,
                    "lat":           round(lat0 + np.random.normal(0, 0.03), 6),
                    "lon":           round(lon0 + np.random.normal(0, 0.03), 6),
                    "capacity":      capacity,
                    "status":        random.choices(["active", "inactive", "maintenance"], weights=[80, 10, 10])[0],
                    "year_deployed": deployed,
                    "zone_type":     random.choice(["commercial", "residential", "transit hub", "industrial"]),
                })
                sid += 1
    return pd.DataFrame(rows)

# ── 2. CUSTOMERS ─────────────────────────────────────────────────────────────
def generate_customers(n=1500):
    rows = []
    for i in range(n):
        country = random.choices(COUNTRIES, weights=[40, 30, 15, 15])[0]
        city    = random.choice(CITIES[country])
        join    = fake.date_between(start_date="-3y", end_date="today")
        monthly = round(random.gauss(45, 18), 2)
        monthly = max(5, monthly)
        tenure  = (datetime.today().date() - join).days / 30
        # Churn signal: lower frequency + shorter tenure = higher risk
        swap_freq     = max(0, round(random.gauss(18, 7)))
        last_swap_days= int(np.random.exponential(12))
        churn_prob    = max(0, min(1,
            0.05
            + (1 / (swap_freq + 1)) * 0.4
            + (last_swap_days / 60) * 0.3
            - (tenure / 36) * 0.1
            + random.gauss(0, 0.05)
        ))
        churned       = random.random() < churn_prob
        rows.append({
            "customer_id":       f"C{i+1:05d}",
            "country":           country,
            "city":              city,
            "join_date":         join,
            "monthly_revenue":   monthly,
            "swap_freq_monthly": swap_freq,
            "last_swap_days_ago":last_swap_days,
            "tenure_months":     round(tenure, 1),
            "segment":           random.choice(["commuter", "delivery", "logistics", "casual"]),
            "churned":           int(churned),
            "churn_probability": round(churn_prob, 4),
        })
    return pd.DataFrame(rows)

# ── 3. SWAP EVENTS (last 12 months) ──────────────────────────────────────────
def generate_swap_events(stations_df, customers_df, n=25000):
    rows = []
    active_stations = stations_df[stations_df["status"] == "active"]["station_id"].tolist()
    customer_ids    = customers_df["customer_id"].tolist()
    base_date       = datetime.today() - timedelta(days=365)
    for _ in range(n):
        dt    = base_date + timedelta(
            days   = random.randint(0, 365),
            hours  = random.randint(5, 23),
            minutes= random.randint(0, 59),
        )
        duration = max(2, int(random.gauss(8, 3)))
        rows.append({
            "swap_id":     fake.uuid4()[:8].upper(),
            "station_id":  random.choice(active_stations),
            "customer_id": random.choice(customer_ids),
            "timestamp":   dt,
            "date":        dt.date(),
            "hour":        dt.hour,
            "day_of_week": dt.strftime("%A"),
            "duration_min":duration,
            "battery_health_pct": random.randint(60, 100),
            "swap_successful": random.choices([1, 0], weights=[95, 5])[0],
        })
    return pd.DataFrame(rows)

# ── 4. REVENUE (monthly, per station) ────────────────────────────────────────
def generate_revenue(stations_df):
    rows = []
    for _, st in stations_df.iterrows():
        for m in range(12):
            month     = (datetime.today().replace(day=1) - pd.DateOffset(months=11-m))
            base_rev  = st["capacity"] * random.uniform(8, 20)
            if st["status"] != "active":
                base_rev *= 0.1
            rows.append({
                "station_id": st["station_id"],
                "country":    st["country"],
                "city":       st["city"],
                "month":      month.strftime("%Y-%m"),
                "revenue_usd":round(base_rev + random.gauss(0, base_rev * 0.1), 2),
            })
    return pd.DataFrame(rows)

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)

    print("Generating stations...")
    stations = generate_stations()
    stations.to_csv("data/stations.csv", index=False)
    print(f"  {len(stations)} stations saved.")

    print("Generating customers...")
    customers = generate_customers(1500)
    customers.to_csv("data/customers.csv", index=False)
    print(f"  {len(customers)} customers saved.")

    print("Generating swap events...")
    swaps = generate_swap_events(stations, customers, 25000)
    swaps.to_csv("data/swap_events.csv", index=False)
    print(f"  {len(swaps)} swap events saved.")

    print("Generating revenue...")
    revenue = generate_revenue(stations)
    revenue.to_csv("data/revenue.csv", index=False)
    print(f"  {len(revenue)} revenue rows saved.")

    print("\nAll data generated successfully.")