"""
models/ltv_model.py
Computes Customer Lifetime Value using a BG/NBD-inspired simplified approach.
LTV = (Monthly Revenue) × (Expected Remaining Months) × (1 - Churn Probability)
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

AVG_GROSS_MARGIN = 0.62      # 62% margin assumption for EV swap biz
DISCOUNT_RATE    = 0.10 / 12  # 10% annual, monthly
MAX_HORIZON      = 36         # months to project

def compute_ltv(customers_df: pd.DataFrame) -> pd.DataFrame:
    df = customers_df.copy()

    # Expected remaining lifetime in months (simple survival estimate)
    churn_col = "churn_probability" if "churn_probability" in df.columns else "churn_score"
    if churn_col not in df.columns:
        df[churn_col] = 0.15  # fallback

    df["monthly_survival"]  = 1 - df[churn_col].clip(0.01, 0.99)
    df["expected_lifetime"] = df["monthly_survival"] / (1 - df["monthly_survival"])
    df["expected_lifetime"] = df["expected_lifetime"].clip(1, MAX_HORIZON)

    # Discounted LTV
    df["ltv"] = (
        df["monthly_revenue"]
        * AVG_GROSS_MARGIN
        * df["expected_lifetime"]
        * (1 / (1 + DISCOUNT_RATE)) ** (df["tenure_months"].clip(0, MAX_HORIZON))
    )
    df["ltv"] = df["ltv"].round(2)

    # LTV segments
    ltv_q = df["ltv"].quantile([0.33, 0.66])
    df["ltv_segment"] = pd.cut(
        df["ltv"],
        bins=[-np.inf, ltv_q[0.33], ltv_q[0.66], np.inf],
        labels=["Bronze", "Silver", "Gold"]
    )

    return df

def ltv_summary_by_segment(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["country", "segment", "ltv_segment", "ltv", "monthly_revenue", "tenure_months"]
    available = [c for c in cols if c in df.columns]
    summary = df.groupby(["country", "segment"]).agg(
        avg_ltv     = ("ltv", "mean"),
        total_ltv   = ("ltv", "sum"),
        avg_revenue = ("monthly_revenue", "mean"),
        count       = ("customer_id", "count"),
    ).reset_index().round(2)
    return summary

def ltv_country_heatmap(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("country").agg(
        avg_ltv   = ("ltv", "mean"),
        total_ltv = ("ltv", "sum"),
        n_gold    = ("ltv_segment", lambda x: (x == "Gold").sum()),
    ).reset_index().round(2)

if __name__ == "__main__":
    customers = pd.read_csv("data/customers.csv", parse_dates=["join_date"])
    customers_ltv = compute_ltv(customers)
    print(customers_ltv[["customer_id", "monthly_revenue", "churn_probability", "ltv", "ltv_segment"]].head(10))
    print("\nLTV by country:")
    print(ltv_country_heatmap(customers_ltv))