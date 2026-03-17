"""
models/demand_forecast.py
Time-series demand forecasting using ARIMA (statsmodels).
Falls back to simple exponential smoothing if prophet is unavailable.
"""
import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
import warnings
warnings.filterwarnings("ignore")

def prepare_daily_demand(swap_events_df: pd.DataFrame, station_id: str = None) -> pd.Series:
    df = swap_events_df.copy()
    if station_id:
        df = df[df["station_id"] == station_id]
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date").size().rename("swaps")
    daily = daily.asfreq("D", fill_value=0)
    return daily

def prepare_monthly_demand(swap_events_df: pd.DataFrame, country: str = None) -> pd.Series:
    df = swap_events_df.copy()
    if country:
        stations = pd.read_csv("data/stations.csv")
        country_stations = stations[stations["country"] == country]["station_id"].tolist()
        df = df[df["station_id"].isin(country_stations)]
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    monthly = df.groupby("month").size().rename("swaps")
    monthly.index = monthly.index.to_timestamp()
    return monthly

def forecast_demand(series: pd.Series, periods: int = 30, freq: str = "D") -> pd.DataFrame:
    """Forecast `periods` steps ahead. Returns df with date, forecast, lower, upper."""
    try:
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal="add" if len(series) >= 14 else None,
            seasonal_periods=7 if freq == "D" else 12,
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True)
        forecast = fit.forecast(periods)
        # Simple confidence interval: ±1.5 std of residuals
        resid_std = fit.resid.std()
        future_index = pd.date_range(series.index[-1] + pd.Timedelta("1D"), periods=periods, freq=freq)
        result = pd.DataFrame({
            "date":     future_index,
            "forecast": forecast.values.clip(0),
            "lower":    (forecast.values - 1.5 * resid_std).clip(0),
            "upper":    (forecast.values + 1.5 * resid_std).clip(0),
        })
        return result
    except Exception as e:
        print(f"Forecast warning: {e} — using naive fallback.")
        last_val = series.iloc[-7:].mean()
        future_index = pd.date_range(series.index[-1] + pd.Timedelta("1D"), periods=periods, freq=freq)
        return pd.DataFrame({
            "date":     future_index,
            "forecast": [last_val] * periods,
            "lower":    [last_val * 0.8] * periods,
            "upper":    [last_val * 1.2] * periods,
        })

def peak_hours_analysis(swap_events_df: pd.DataFrame) -> pd.DataFrame:
    df = swap_events_df.copy()
    df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
    hourly = df.groupby("hour").size().reset_index(name="swaps")
    hourly["pct"] = (hourly["swaps"] / hourly["swaps"].sum() * 100).round(1)
    return hourly

if __name__ == "__main__":
    swaps = pd.read_csv("data/swap_events.csv", parse_dates=["timestamp", "date"])
    daily = prepare_daily_demand(swaps)
    print(f"Daily demand series: {len(daily)} days")
    fc = forecast_demand(daily, periods=14)
    print(fc.head())