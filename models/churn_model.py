"""
models/churn_model.py
Trains a Random Forest churn predictor and returns scored customer DataFrame.
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, roc_auc_score
import pickle
import os

FEATURES = [
    "swap_freq_monthly",
    "last_swap_days_ago",
    "tenure_months",
    "monthly_revenue",
]
SEGMENT_MAP = {"commuter": 0, "delivery": 1, "logistics": 2, "casual": 3}

def load_customers():
    return pd.read_csv("data/customers.csv", parse_dates=["join_date"])

def train_churn_model(df: pd.DataFrame):
    df = df.copy()
    df["segment_enc"] = df["segment"].map(SEGMENT_MAP).fillna(0)
    feature_cols = FEATURES + ["segment_enc"]
    X = df[feature_cols].fillna(0)
    y = df["churned"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    model = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    auc   = roc_auc_score(y_test, proba)
    print(f"Churn model AUC: {auc:.3f}")
    print(classification_report(y_test, preds))

    os.makedirs("models", exist_ok=True)
    with open("models/churn_model.pkl", "wb") as f:
        pickle.dump(model, f)

    return model, feature_cols

def score_customers(df: pd.DataFrame, model=None, feature_cols=None):
    if model is None:
        if os.path.exists("models/churn_model.pkl"):
            with open("models/churn_model.pkl", "rb") as f:
                model = pickle.load(f)
            feature_cols = FEATURES + ["segment_enc"]
        else:
            model, feature_cols = train_churn_model(df)

    df = df.copy()
    df["segment_enc"] = df["segment"].map(SEGMENT_MAP).fillna(0)
    X = df[feature_cols].fillna(0)
    df["churn_score"]  = model.predict_proba(X)[:, 1]
    df["churn_risk"]   = pd.cut(
        df["churn_score"],
        bins=[0, 0.30, 0.60, 1.01],
        labels=["Low", "Medium", "High"]
    )
    importances = dict(zip(feature_cols, model.feature_importances_))
    return df, importances

def get_at_risk_customers(df: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Return customers above churn threshold, sorted by score descending."""
    at_risk = df[df["churn_score"] >= threshold].copy()
    return at_risk.sort_values("churn_score", ascending=False)

if __name__ == "__main__":
    customers = load_customers()
    model, feat = train_churn_model(customers)
    scored, importances = score_customers(customers, model, feat)
    print("\nFeature importances:")
    for k, v in sorted(importances.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v:.3f}")
    print(f"\nAt-risk customers (score >= 0.5): {(scored['churn_score'] >= 0.5).sum()}")