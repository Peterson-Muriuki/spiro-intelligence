"""
models/deployment_optimizer.py
Scores and ranks candidate locations for new swap station deployment.
Uses a weighted multi-criteria scoring model.
"""
import pandas as pd
import numpy as np
from scipy.spatial.distance import cdist

# Scoring weights (tunable)
WEIGHTS = {
    "demand_density":     0.30,
    "coverage_gap":       0.25,
    "revenue_potential":  0.25,
    "underserved_score":  0.20,
}

def compute_coverage_gap(stations_df: pd.DataFrame, grid_df: pd.DataFrame, radius_km: float = 2.0) -> pd.DataFrame:
    """For each grid point, compute distance to nearest active station."""
    active = stations_df[stations_df["status"] == "active"][["lat", "lon"]].values
    grid_coords = grid_df[["lat", "lon"]].values

    if len(active) == 0:
        grid_df["nearest_station_km"] = 999.0
        return grid_df

    # Approximate km distance using degree offsets
    dists = cdist(
        np.radians(grid_coords),
        np.radians(active),
        metric=lambda u, v: 6371 * np.sqrt(
            ((u[0] - v[0])) ** 2 + ((u[1] - v[1]) * np.cos((u[0] + v[0]) / 2)) ** 2
        )
    )
    grid_df["nearest_station_km"] = dists.min(axis=1)
    return grid_df

def generate_candidate_grid(city_center: tuple, n: int = 30, spread: float = 0.08) -> pd.DataFrame:
    lat0, lon0 = city_center
    lats = lat0 + np.random.uniform(-spread, spread, n)
    lons = lon0 + np.random.uniform(-spread, spread, n)
    pop_density   = np.random.uniform(500, 8000, n)
    commuter_index= np.random.uniform(0.2, 1.0, n)
    income_index  = np.random.uniform(0.3, 0.9, n)
    return pd.DataFrame({
        "candidate_id":   [f"CND{i+1:03d}" for i in range(n)],
        "lat": lats, "lon": lons,
        "pop_density":    pop_density,
        "commuter_index": commuter_index,
        "income_index":   income_index,
    })

def score_candidates(
    candidates_df: pd.DataFrame,
    stations_df:   pd.DataFrame,
    swap_events_df: pd.DataFrame = None,
) -> pd.DataFrame:
    df = candidates_df.copy()
    df = compute_coverage_gap(stations_df, df)

    # Normalise features to 0-1
    def minmax(s):
        rng = s.max() - s.min()
        return (s - s.min()) / rng if rng > 0 else s * 0 + 0.5

    df["demand_density"]    = minmax(df["pop_density"] * df["commuter_index"])
    df["coverage_gap"]      = minmax(df["nearest_station_km"])
    df["revenue_potential"] = minmax(df["income_index"] * df["pop_density"])
    df["underserved_score"] = minmax(df["nearest_station_km"] / (df["pop_density"] + 1) * 1000)

    df["deployment_score"] = (
        WEIGHTS["demand_density"]    * df["demand_density"]
        + WEIGHTS["coverage_gap"]   * df["coverage_gap"]
        + WEIGHTS["revenue_potential"] * df["revenue_potential"]
        + WEIGHTS["underserved_score"] * df["underserved_score"]
    )
    df["deployment_score"] = (df["deployment_score"] * 100).round(1)
    df["priority"] = pd.cut(
        df["deployment_score"],
        bins=[0, 40, 65, 101],
        labels=["Low", "Medium", "High"]
    )
    return df.sort_values("deployment_score", ascending=False)

def recommend_top_locations(scored_df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    return scored_df.head(top_n)[
        ["candidate_id", "lat", "lon", "deployment_score", "priority",
         "nearest_station_km", "demand_density", "coverage_gap"]
    ].reset_index(drop=True)

if __name__ == "__main__":
    stations = pd.read_csv("data/stations.csv")
    nairobi_center = (-1.286389, 36.817223)
    candidates = generate_candidate_grid(nairobi_center, n=40)
    scored     = score_candidates(candidates, stations)
    print("Top 5 deployment recommendations for Nairobi:")
    print(recommend_top_locations(scored))