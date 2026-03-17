"""
models/financial_model.py
Core financial modelling engine for Spiro swap station operations.

Modules:
  - unit_economics      : revenue & cost structure per station
  - pl_projection       : monthly P&L for the full network
  - cash_flow_model     : operating + capex cash flows
  - breakeven_analysis  : swaps-to-profitability analysis
  - dcf_valuation       : NPV / IRR per market
  - monte_carlo_simulation : risk distribution on key assumptions
  - run_all_scenarios   : Base / Bull / Bear comparison table
"""

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT ASSUMPTIONS
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    "swap_price_usd":           2.50,
    "swaps_per_station_day":    18.0,
    "active_days_per_month":    28,
    "battery_cost_usd":         800.0,
    "station_capex_usd":        5000.0,
    "capex_lifetime_years":     5,
    "opex_per_station_month":   220.0,
    "staff_cost_per_station":   80.0,
    "logistics_cost_pct":       0.08,
    "n_stations":               20,
    "station_growth_monthly":   0.03,
    "churn_rate_monthly":       0.04,
    "gross_margin_pct":         0.62,
    "discount_rate_annual":     0.12,
    "tax_rate":                 0.25,
    "projection_months":        36,
    "batteries_per_station":    20,
}

SCENARIOS = {
    "Base": {
        "swap_price_usd":         2.50,
        "swaps_per_station_day":  18.0,
        "opex_per_station_month": 220.0,
        "station_growth_monthly": 0.03,
        "churn_rate_monthly":     0.04,
    },
    "Bull": {
        "swap_price_usd":         3.20,
        "swaps_per_station_day":  25.0,
        "opex_per_station_month": 200.0,
        "station_growth_monthly": 0.06,
        "churn_rate_monthly":     0.02,
    },
    "Bear": {
        "swap_price_usd":         1.80,
        "swaps_per_station_day":  10.0,
        "opex_per_station_month": 260.0,
        "station_growth_monthly": 0.01,
        "churn_rate_monthly":     0.07,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. UNIT ECONOMICS
# ─────────────────────────────────────────────────────────────────────────────

def unit_economics(params: dict) -> dict:
    p = {**DEFAULTS, **params}

    monthly_swaps  = p["swaps_per_station_day"] * p["active_days_per_month"]
    gross_revenue  = monthly_swaps * p["swap_price_usd"]

    capex_monthly  = (p["station_capex_usd"] + p["batteries_per_station"] * p["battery_cost_usd"]) \
                     / (p["capex_lifetime_years"] * 12)
    logistics_cost = gross_revenue * p["logistics_cost_pct"]
    total_opex     = p["opex_per_station_month"] + p["staff_cost_per_station"] + logistics_cost
    total_cost     = total_opex + capex_monthly

    gross_profit   = gross_revenue * p["gross_margin_pct"]
    ebitda         = gross_profit - p["opex_per_station_month"] - p["staff_cost_per_station"] - logistics_cost
    ebit           = ebitda - capex_monthly
    nopat          = ebit * (1 - p["tax_rate"])

    var_cost_per_swap         = p["swap_price_usd"] * (1 - p["gross_margin_pct"]) \
                                + p["swap_price_usd"] * p["logistics_cost_pct"]
    contribution_per_swap     = p["swap_price_usd"] - var_cost_per_swap
    contribution_margin_pct   = (contribution_per_swap / p["swap_price_usd"] * 100) if p["swap_price_usd"] else 0

    return {
        "monthly_swaps":                round(monthly_swaps, 0),
        "gross_revenue":                round(gross_revenue, 2),
        "capex_monthly_amortised":      round(capex_monthly, 2),
        "logistics_cost":               round(logistics_cost, 2),
        "total_opex":                   round(total_opex, 2),
        "total_cost":                   round(total_cost, 2),
        "gross_profit":                 round(gross_profit, 2),
        "ebitda":                       round(ebitda, 2),
        "ebit":                         round(ebit, 2),
        "nopat":                        round(nopat, 2),
        "ebitda_margin_pct":            round(ebitda / gross_revenue * 100, 1) if gross_revenue else 0,
        "contribution_per_swap":        round(contribution_per_swap, 4),
        "contribution_margin_pct":      round(contribution_margin_pct, 1),
        "revenue_per_battery_day":      round(gross_revenue / p["batteries_per_station"] / p["active_days_per_month"], 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. P&L PROJECTION
# ─────────────────────────────────────────────────────────────────────────────

def pl_projection(params: dict) -> pd.DataFrame:
    p = {**DEFAULTS, **params}
    rows = []
    n0   = p["n_stations"]

    for m in range(1, p["projection_months"] + 1):
        n_stn  = n0 * ((1 + p["station_growth_monthly"]) ** m)
        ue     = unit_economics(p)

        revenue      = ue["gross_revenue"] * n_stn
        cogs         = revenue * (1 - p["gross_margin_pct"])
        gross_profit = revenue - cogs
        opex_total   = (p["opex_per_station_month"] + p["staff_cost_per_station"]) * n_stn
        logistics    = revenue * p["logistics_cost_pct"]
        ebitda       = gross_profit - opex_total - logistics
        depreciation = ue["capex_monthly_amortised"] * n_stn
        ebit         = ebitda - depreciation
        tax          = max(0, ebit * p["tax_rate"])
        net_income   = ebit - tax

        rows.append({
            "month":         m,
            "n_stations":    round(n_stn, 1),
            "revenue":       round(revenue, 0),
            "cogs":          round(cogs, 0),
            "gross_profit":  round(gross_profit, 0),
            "opex":          round(opex_total + logistics, 0),
            "ebitda":        round(ebitda, 0),
            "depreciation":  round(depreciation, 0),
            "ebit":          round(ebit, 0),
            "tax":           round(tax, 0),
            "net_income":    round(net_income, 0),
            "ebitda_margin": round(ebitda / revenue * 100, 1) if revenue else 0,
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 3. CASH FLOW MODEL
# ─────────────────────────────────────────────────────────────────────────────

def cash_flow_model(params: dict) -> pd.DataFrame:
    p  = {**DEFAULTS, **params}
    pl = pl_projection(params)

    initial_capex = (p["station_capex_usd"] + p["batteries_per_station"] * p["battery_cost_usd"]) \
                    * p["n_stations"]
    cum_cash = -initial_capex
    rows     = []

    station_per_unit = p["station_capex_usd"] + p["batteries_per_station"] * p["battery_cost_usd"]

    for i, row in pl.iterrows():
        prev_n = pl.loc[i - 1, "n_stations"] if i > 0 else p["n_stations"]
        new_stations = max(0, row["n_stations"] - prev_n)
        capex    = new_stations * station_per_unit
        ocf      = row["net_income"] + row["depreciation"]
        fcf      = ocf - capex
        cum_cash += fcf

        rows.append({
            "month":           row["month"],
            "operating_cf":    round(ocf, 0),
            "capex":           round(-capex, 0),
            "free_cash_flow":  round(fcf, 0),
            "cumulative_cash": round(cum_cash, 0),
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 4. BREAKEVEN ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def breakeven_analysis(params: dict) -> dict:
    p = {**DEFAULTS, **params}

    capex_monthly  = (p["station_capex_usd"] + p["batteries_per_station"] * p["battery_cost_usd"]) \
                     / (p["capex_lifetime_years"] * 12)
    fixed_costs    = p["opex_per_station_month"] + p["staff_cost_per_station"] + capex_monthly

    var_cost_per_swap      = p["swap_price_usd"] * (1 - p["gross_margin_pct"]) \
                             + p["swap_price_usd"] * p["logistics_cost_pct"]
    contribution_per_swap  = p["swap_price_usd"] - var_cost_per_swap

    if contribution_per_swap <= 0:
        be_swaps_month = float("inf")
    else:
        be_swaps_month = fixed_costs / contribution_per_swap

    be_swaps_day = be_swaps_month / p["active_days_per_month"]

    cf = cash_flow_model(params)
    pos = cf[cf["cumulative_cash"] >= 0]
    payback_months = int(pos["month"].min()) if len(pos) > 0 else None

    current_swaps_month = p["swaps_per_station_day"] * p["active_days_per_month"]
    mos = ((current_swaps_month - be_swaps_month) / current_swaps_month * 100) \
          if current_swaps_month else 0

    return {
        "breakeven_swaps_per_day":   round(be_swaps_day, 1),
        "breakeven_swaps_per_month": round(be_swaps_month, 0),
        "contribution_per_swap":     round(contribution_per_swap, 4),
        "fixed_costs_monthly":       round(fixed_costs, 2),
        "payback_months":            payback_months if payback_months else ">36",
        "margin_of_safety_pct":      round(mos, 1),
        "current_swaps_month":       round(current_swaps_month, 0),
        "variable_cost_per_swap":    round(var_cost_per_swap, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. DCF VALUATION
# ─────────────────────────────────────────────────────────────────────────────

def _irr(cashflows, max_iter=1000, tol=1e-6):
    rate = 0.01
    for _ in range(max_iter):
        npv  = sum(c / (1 + rate) ** t for t, c in enumerate(cashflows))
        dnpv = sum(-t * c / (1 + rate) ** (t + 1) for t, c in enumerate(cashflows))
        if abs(dnpv) < 1e-12:
            break
        new_rate = rate - npv / dnpv
        if abs(new_rate - rate) < tol:
            return new_rate
        rate = new_rate
    return rate


def dcf_valuation(params: dict) -> dict:
    p   = {**DEFAULTS, **params}
    pl  = pl_projection(params)
    cf  = cash_flow_model(params)

    r_monthly = (1 + p["discount_rate_annual"]) ** (1/12) - 1

    initial_investment = (p["station_capex_usd"] + p["batteries_per_station"] * p["battery_cost_usd"]) \
                         * p["n_stations"]

    cash_flows = [-initial_investment] + cf["free_cash_flow"].tolist()
    discounted = [c / (1 + r_monthly) ** t for t, c in enumerate(cash_flows)]
    npv        = sum(discounted)

    g_monthly = (1 + 0.02) ** (1/12) - 1
    last_fcf  = cf["free_cash_flow"].iloc[-1]
    if r_monthly > g_monthly and last_fcf > 0:
        terminal_v  = last_fcf * (1 + g_monthly) / (r_monthly - g_monthly)
        terminal_pv = terminal_v / (1 + r_monthly) ** len(cash_flows)
    else:
        terminal_pv = 0

    npv_with_tv = npv + terminal_pv

    try:
        irr_monthly = _irr(cash_flows)
        irr_annual  = (1 + irr_monthly) ** 12 - 1
        if irr_annual > 5 or irr_annual < -1:
            irr_annual = None
    except Exception:
        irr_annual = None

    total_profit = pl["net_income"].sum()
    roi = total_profit / initial_investment * 100 if initial_investment else 0

    return {
        "initial_investment":   round(initial_investment, 0),
        "npv":                  round(npv, 0),
        "npv_with_terminal":    round(npv_with_tv, 0),
        "terminal_value":       round(terminal_pv, 0),
        "irr_annual_pct":       round(irr_annual * 100, 1) if irr_annual else None,
        "roi_pct":              round(roi, 1),
        "total_revenue_36m":    round(pl["revenue"].sum(), 0),
        "total_net_income_36m": round(pl["net_income"].sum(), 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. MONTE CARLO
# ─────────────────────────────────────────────────────────────────────────────

def monte_carlo_simulation(params: dict, n_sims: int = 2000) -> dict:
    p = {**DEFAULTS, **params}
    np.random.seed(42)

    npvs, revenues, irrs = [], [], []

    for _ in range(n_sims):
        sim = {
            **p,
            "swap_price_usd":         max(0.5, np.random.normal(p["swap_price_usd"],         p["swap_price_usd"] * 0.15)),
            "swaps_per_station_day":  max(1.0, np.random.normal(p["swaps_per_station_day"],  p["swaps_per_station_day"] * 0.20)),
            "opex_per_station_month": max(50,  np.random.normal(p["opex_per_station_month"], p["opex_per_station_month"] * 0.12)),
            "churn_rate_monthly":     max(0.005, np.random.beta(2, 20)),
            "discount_rate_annual":   max(0.05, np.random.normal(p["discount_rate_annual"], 0.02)),
        }
        try:
            dcf = dcf_valuation(sim)
            pl_ = pl_projection(sim)
            npvs.append(dcf["npv"])
            revenues.append(pl_["revenue"].sum())
            if dcf["irr_annual_pct"] is not None:
                irrs.append(dcf["irr_annual_pct"])
        except Exception:
            continue

    npvs_arr = np.array(npvs)
    rev_arr  = np.array(revenues)
    irr_arr  = np.array(irrs)

    return {
        "npv_simulations":     npvs_arr,
        "revenue_simulations": rev_arr,
        "irr_simulations":     irr_arr,
        "npv_p10":   round(np.percentile(npvs_arr, 10), 0),
        "npv_p50":   round(np.percentile(npvs_arr, 50), 0),
        "npv_p90":   round(np.percentile(npvs_arr, 90), 0),
        "npv_mean":  round(npvs_arr.mean(), 0),
        "prob_positive_npv": round((npvs_arr > 0).mean() * 100, 1),
        "var_95":    round(np.percentile(npvs_arr, 5), 0),
        "rev_p50":   round(np.percentile(rev_arr, 50), 0),
        "rev_p10":   round(np.percentile(rev_arr, 10), 0),
        "rev_p90":   round(np.percentile(rev_arr, 90), 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. SCENARIO COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def run_all_scenarios(base_params: dict) -> pd.DataFrame:
    rows = []
    for name, overrides in SCENARIOS.items():
        p   = {**DEFAULTS, **base_params, **overrides}
        ue  = unit_economics(p)
        dcf = dcf_valuation(p)
        be  = breakeven_analysis(p)
        pl  = pl_projection(p)
        rows.append({
            "Scenario":               name,
            "Swap Price ($)":         overrides["swap_price_usd"],
            "Swaps/Day":              overrides["swaps_per_station_day"],
            "Monthly Rev/Stn ($)":    ue["gross_revenue"],
            "EBITDA/Stn ($)":         ue["ebitda"],
            "EBITDA Margin (%)":      ue["ebitda_margin_pct"],
            "Breakeven Swaps/Day":    be["breakeven_swaps_per_day"],
            "Payback (months)":       be["payback_months"],
            "NPV ($)":                dcf["npv"],
            "IRR (%)":                dcf["irr_annual_pct"],
            "36M Net Income ($)":     pl["net_income"].sum(),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# CLI TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== UNIT ECONOMICS ===")
    ue = unit_economics({})
    for k, v in ue.items():
        print(f"  {k}: {v}")

    print("\n=== BREAKEVEN ===")
    be = breakeven_analysis({})
    for k, v in be.items():
        print(f"  {k}: {v}")

    print("\n=== DCF VALUATION ===")
    dcf = dcf_valuation({})
    for k, v in dcf.items():
        print(f"  {k}: {v}")

    print("\n=== SCENARIOS ===")
    sc = run_all_scenarios({})
    print(sc.to_string())

    print("\n=== MONTE CARLO ===")
    mc = monte_carlo_simulation({}, n_sims=500)
    print(f"  NPV P10/P50/P90: {mc['npv_p10']:,.0f} / {mc['npv_p50']:,.0f} / {mc['npv_p90']:,.0f}")
    print(f"  Prob positive NPV: {mc['prob_positive_npv']}%")
    print(f"  VaR 95%: {mc['var_95']:,.0f}")