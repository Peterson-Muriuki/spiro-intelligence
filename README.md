# ⚡ Spiro Swap Station Intelligence Dashboard

[![CI](https://github.com/Peterson-Muriuki/spiro-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Peterson-Muriuki/spiro-intelligence/actions/workflows/ci.yml)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://peterson-muriuki-spiro-intelligence.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**A Country Manager Decision-Support System for EV Battery Swap Operations**

Built as a portfolio project demonstrating end-to-end analytics engineering for Spiro's
swap station network across Africa.

---

## What This Solves

| Country Manager Need | Solution |
|---|---|
| Clear, actionable insights | KPI overview + live alert digest |
| Optimize station deployment | Multi-criteria scoring optimizer + map |
| Track turnover metrics | Per-station utilisation + daily averages |
| Identify churning customers | GBM churn prediction model (AUC ~0.82) |
| Customer lifetime value | LTV model with Bronze/Silver/Gold tiers |
| Insights accessible anytime | Streamlit web app, deployable to cloud |
| Weekly briefings | Auto-generated digest + CSV exports |

---

## Project Structure

```
spiro-intelligence/
├── app.py                    # Main entry point
├── requirements.txt
├── README.md
├── data/
│   ├── generate_data.py      # Synthetic data generator
│   ├── stations.csv          # Generated
│   ├── customers.csv         # Generated
│   ├── swap_events.csv       # Generated
│   └── revenue.csv           # Generated
├── models/
│   ├── churn_model.py        # GBM churn prediction
│   ├── ltv_model.py          # Customer LTV computation
│   ├── deployment_optimizer.py  # Station placement scoring
│   └── demand_forecast.py    # Time-series forecasting
├── utils/
│   ├── kpis.py               # Core KPI functions
│   └── alerts.py             # Alert engine
└── pages/
    ├── 1_Overview.py         # KPIs, revenue, turnover
    ├── 2_Station_Map.py      # Geospatial station map
    ├── 3_Churn_LTV.py        # Churn prediction + LTV
    ├── 4_Deployment.py       # Deployment optimizer + forecast
    └── 5_Reports.py          # Export + weekly digest
```

---

## Setup & Run (Windows CMD)

```cmd
cd C:\Projects\spiro-intelligence
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python data/generate_data.py
streamlit run app.py
```

---

## Deploy to Streamlit Cloud

## Analytics Modules

### Churn Model
- Algorithm: Gradient Boosting Machine (sklearn)
- Features: swap frequency, days since last swap, tenure, revenue, segment
- Output: churn score 0-1 per customer, risk tier (Low/Medium/High)

### LTV Model
- Method: Discounted survival-adjusted revenue projection
- Horizon: 36 months, 10% annual discount rate, 62% gross margin
- Output: $ LTV per customer, Bronze/Silver/Gold segments

### Deployment Optimizer
- Scores candidate locations on 4 criteria: demand density, coverage gap, revenue potential, underserved score
- Outputs ranked deployment priority map

### Demand Forecast
- Holt-Winters Exponential Smoothing (additive trend + seasonality)
- 30-day ahead forecast with confidence intervals

---

## Tech Stack

| Layer | Tools |
|---|---|
| Language | Python 3.10+ |
| Dashboard | Streamlit |
| ML Models | scikit-learn (GBM, K-Means) |
| Forecasting | statsmodels (ETS) |
| Visualization | Plotly, Folium |
| Data | pandas, numpy |

---

*Built by Peterson Muriuki — Data Analyst | Financial Engineer*
*[pitmuriuki@gmail.com](mailto:pitmuriuki@gmail.com) | [GitHub](https://github.com) | [LinkedIn](https://www.linkedin.com/in/peterson-muriuki-5857aaa9/)*
