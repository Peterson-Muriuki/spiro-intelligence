"""
pages/6_Financial_Model.py
Interactive financial modelling dashboard.

Sections:
  1. Assumption sliders (sidebar)
  2. Unit economics waterfall
  3. 36-month P&L projection
  4. Cash flow & payback
  5. Breakeven sensitivity
  6. DCF valuation
  7. Scenario comparison (Base / Bull / Bear)
  8. Monte Carlo simulation + tornado

Integration: standalone — does NOT need session_state data.
             Does NOT call st.set_page_config.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.financial_model import (
    DEFAULTS, SCENARIOS,
    unit_economics, pl_projection, cash_flow_model,
    breakeven_analysis, dcf_valuation,
    monte_carlo_simulation, run_all_scenarios,
)

st.markdown("## 💹 Financial Model & Station Economics")
st.caption("Interactive unit economics, P&L, DCF valuation, scenario analysis, and Monte Carlo simulation.")

# ── SIDEBAR: assumption sliders ────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Model Assumptions")
    st.caption("Adjust parameters — all charts update live.")

    st.markdown("#### 💰 Revenue")
    swap_price   = st.slider("Swap price ($/swap)",         0.50, 6.00, DEFAULTS["swap_price_usd"],           0.10)
    swaps_day    = st.slider("Swaps/station/day",            2,   50,   int(DEFAULTS["swaps_per_station_day"]),  1)
    active_days  = st.slider("Active days/month",           20,   31,   DEFAULTS["active_days_per_month"],       1)

    st.markdown("#### 🏗️ Costs")
    station_capex = st.slider("Station capex ($)",        1000, 15000, int(DEFAULTS["station_capex_usd"]),     500)
    battery_cost  = st.slider("Battery cost/slot ($)",     200,  2000, int(DEFAULTS["battery_cost_usd"]),      50)
    batteries     = st.slider("Batteries/station",           5,    50, int(DEFAULTS["batteries_per_station"]),  5)
    opex_monthly  = st.slider("OpEx/station/month ($)",     50,   600, int(DEFAULTS["opex_per_station_month"]), 10)
    staff_cost    = st.slider("Staff cost/station ($)",     20,   300, int(DEFAULTS["staff_cost_per_station"]), 10)
    logistics_pct = st.slider("Logistics cost (% rev)",     0,    20,  int(DEFAULTS["logistics_cost_pct"] * 100), 1) / 100

    st.markdown("#### 📈 Growth & Market")
    n_stations    = st.slider("Starting stations",           1,   100, int(DEFAULTS["n_stations"]),  1)
    growth_mo     = st.slider("Station growth (%/month)",    0,    15, int(DEFAULTS["station_growth_monthly"] * 100), 1) / 100
    gross_margin  = st.slider("Gross margin (%)",           30,    85, int(DEFAULTS["gross_margin_pct"] * 100), 1) / 100

    st.markdown("#### 🏦 Finance")
    discount_rate = st.slider("Discount rate (% annual)",    5,    30, int(DEFAULTS["discount_rate_annual"] * 100), 1) / 100
    tax_rate      = st.slider("Tax rate (%)",                0,    40, int(DEFAULTS["tax_rate"] * 100), 1) / 100
    capex_life    = st.slider("Capex lifetime (years)",      3,    10, DEFAULTS["capex_lifetime_years"], 1)

params = {
    "swap_price_usd":           swap_price,
    "swaps_per_station_day":    swaps_day,
    "active_days_per_month":    active_days,
    "station_capex_usd":        station_capex,
    "battery_cost_usd":         battery_cost,
    "batteries_per_station":    batteries,
    "opex_per_station_month":   opex_monthly,
    "staff_cost_per_station":   staff_cost,
    "logistics_cost_pct":       logistics_pct,
    "n_stations":               n_stations,
    "station_growth_monthly":   growth_mo,
    "gross_margin_pct":         gross_margin,
    "discount_rate_annual":     discount_rate,
    "tax_rate":                 tax_rate,
    "capex_lifetime_years":     capex_life,
    "projection_months":        36,
}

# ── Compute all outputs ────────────────────────────────────────────────────
ue  = unit_economics(params)
be  = breakeven_analysis(params)
dcf = dcf_valuation(params)
pl  = pl_projection(params)
cf  = cash_flow_model(params)

# ── SECTION 1: KPI summary ─────────────────────────────────────────────────
st.markdown("### 📊 Station Economics Summary")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenue/Station/Month",  f"${ue['gross_revenue']:,.0f}")
c2.metric("EBITDA/Station/Month",   f"${ue['ebitda']:,.0f}",
          f"{ue['ebitda_margin_pct']:.1f}% margin",
          delta_color="normal" if ue["ebitda"] >= 0 else "inverse")
c3.metric("Contribution/Swap",      f"${ue['contribution_per_swap']:.3f}")
c4.metric("Breakeven Swaps/Day",    f"{be['breakeven_swaps_per_day']}")
c5.metric("Payback Period",         f"{be['payback_months']} months")
c6.metric("NPV (36M)",              f"${dcf['npv']:,.0f}",
          delta_color="normal" if dcf["npv"] >= 0 else "inverse")

st.markdown("---")

# ── SECTION 2: Waterfall + detail ─────────────────────────────────────────
col_wf, col_ue = st.columns([3, 2])

with col_wf:
    st.markdown("### 💧 Unit Economics Waterfall (per station/month)")
    cogs_val  = ue["gross_revenue"] * (1 - gross_margin)
    opex_val  = opex_monthly + staff_cost

    fig_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute","relative","relative","relative","total",
                 "relative","total","relative","total"],
        x=["Gross Revenue","COGS","Logistics","OpEx & Staff",
           "Gross Profit","Depreciation","EBIT","Tax","NOPAT"],
        y=[ue["gross_revenue"], -cogs_val, -ue["logistics_cost"],
           -opex_val, ue["gross_profit"], -ue["capex_monthly_amortised"],
           ue["ebit"], -max(0, ue["ebit"] * tax_rate), ue["nopat"]],
        connector=dict(line=dict(color="#d1d5db", width=1)),
        increasing=dict(marker_color="#1D9E75"),
        decreasing=dict(marker_color="#ef4444"),
        totals=dict(marker_color="#0F6E56"),
        text=[f"${abs(v):,.0f}" for v in
              [ue["gross_revenue"], cogs_val, ue["logistics_cost"],
               opex_val, ue["gross_profit"], ue["capex_monthly_amortised"],
               ue["ebit"], max(0, ue["ebit"] * tax_rate), ue["nopat"]]],
        textposition="outside",
    ))
    fig_wf.update_layout(
        template="plotly_white", margin=dict(t=30, b=20),
        yaxis_title="USD ($)", height=400, showlegend=False,
    )
    st.plotly_chart(fig_wf, use_container_width=True)

with col_ue:
    st.markdown("### 📋 Unit Economics Detail")
    ue_rows = [
        ("Monthly Swaps",            f"{ue['monthly_swaps']:,.0f}"),
        ("Gross Revenue",            f"${ue['gross_revenue']:,.2f}"),
        ("Gross Profit",             f"${ue['gross_profit']:,.2f}"),
        ("Logistics Cost",           f"${ue['logistics_cost']:,.2f}"),
        ("Total OpEx",               f"${ue['total_opex']:,.2f}"),
        ("Capex (amortised/month)",  f"${ue['capex_monthly_amortised']:,.2f}"),
        ("EBITDA",                   f"${ue['ebitda']:,.2f}"),
        ("EBITDA Margin",            f"{ue['ebitda_margin_pct']:.1f}%"),
        ("EBIT",                     f"${ue['ebit']:,.2f}"),
        ("NOPAT",                    f"${ue['nopat']:,.2f}"),
        ("Contribution / Swap",      f"${ue['contribution_per_swap']:.4f}"),
        ("Contribution Margin",      f"{ue['contribution_margin_pct']:.1f}%"),
        ("Revenue / Battery / Day",  f"${ue['revenue_per_battery_day']:.3f}"),
    ]
    st.dataframe(
        pd.DataFrame(ue_rows, columns=["Line Item", "Value"]),
        use_container_width=True, hide_index=True, height=460,
    )

st.markdown("---")

# ── SECTION 3: P&L projection ──────────────────────────────────────────────
st.markdown("### 📈 36-Month P&L Projection (Full Network)")

col_pl1, col_pl2 = st.columns([3, 2])
with col_pl1:
    fig_pl = go.Figure()
    fig_pl.add_trace(go.Scatter(x=pl["month"], y=pl["revenue"],   name="Revenue",
                                line=dict(color="#1D9E75", width=2),
                                fill="tozeroy", fillcolor="rgba(29,158,117,0.07)"))
    fig_pl.add_trace(go.Scatter(x=pl["month"], y=pl["ebitda"],    name="EBITDA",
                                line=dict(color="#3B8BD4", width=2)))
    fig_pl.add_trace(go.Scatter(x=pl["month"], y=pl["net_income"],name="Net Income",
                                line=dict(color="#F97316", width=2)))
    fig_pl.add_hline(y=0, line_dash="dash", line_color="#9ca3af", line_width=1)
    fig_pl.update_layout(template="plotly_white", height=340,
                         xaxis_title="Month", yaxis_title="USD ($)",
                         margin=dict(t=20, b=20),
                         legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig_pl, use_container_width=True)

with col_pl2:
    st.markdown("**EBITDA Margin (%)**")
    fig_m = px.area(pl, x="month", y="ebitda_margin", template="plotly_white",
                    height=160, color_discrete_sequence=["#1D9E75"],
                    labels={"month": "Month", "ebitda_margin": "EBITDA %"})
    fig_m.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_m, use_container_width=True)

    st.markdown("**Station Count Growth**")
    fig_stn = px.area(pl, x="month", y="n_stations", template="plotly_white",
                      height=140, color_discrete_sequence=["#7F77DD"],
                      labels={"month": "Month", "n_stations": "Stations"})
    fig_stn.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_stn, use_container_width=True)

with st.expander("📋 Full P&L Table"):
    fmt = {"revenue":"${:,.0f}","cogs":"${:,.0f}","gross_profit":"${:,.0f}",
           "opex":"${:,.0f}","ebitda":"${:,.0f}","ebit":"${:,.0f}",
           "net_income":"${:,.0f}","ebitda_margin":"{:.1f}%"}
    st.dataframe(pl.style.format(fmt), use_container_width=True, hide_index=True)

st.markdown("---")

# ── SECTION 4: Cash flow & payback ────────────────────────────────────────
st.markdown("### 💵 Cash Flow & Payback Period")

col_cf1, col_cf2 = st.columns([3, 2])
with col_cf1:
    fig_cf = go.Figure()
    fig_cf.add_trace(go.Bar(
        x=cf["month"], y=cf["free_cash_flow"], name="Free Cash Flow",
        marker_color=["#1D9E75" if v >= 0 else "#ef4444" for v in cf["free_cash_flow"]],
    ))
    fig_cf.add_trace(go.Scatter(
        x=cf["month"], y=cf["cumulative_cash"], name="Cumulative Cash",
        line=dict(color="#F97316", width=2.5), yaxis="y2",
    ))
    fig_cf.add_hline(y=0, line_dash="dash", line_color="#9ca3af", line_width=1)
    fig_cf.update_layout(
        template="plotly_white", height=340,
        xaxis_title="Month",
        yaxis=dict(title="Free Cash Flow ($)"),
        yaxis2=dict(title="Cumulative Cash ($)", overlaying="y", side="right"),
        margin=dict(t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_cf, use_container_width=True)

with col_cf2:
    m1, m2 = st.columns(2)
    payback = be["payback_months"]
    m1.metric("Payback Period",    f"{payback} mo" if isinstance(payback, int) else str(payback))
    m2.metric("Initial Capex",     f"${dcf['initial_investment']:,.0f}")
    m1.metric("Margin of Safety",  f"{be['margin_of_safety_pct']:.1f}%")
    m2.metric("Fixed Costs/Mo",    f"${be['fixed_costs_monthly']:,.0f}")

    be_bar_df = pd.DataFrame({
        "Category": ["Breakeven swaps/day", "Current swaps/day"],
        "Value":    [be["breakeven_swaps_per_day"], swaps_day],
    })
    fig_bebar = px.bar(be_bar_df, x="Category", y="Value",
                       color="Category",
                       color_discrete_map={"Breakeven swaps/day": "#ef4444",
                                           "Current swaps/day":   "#1D9E75"},
                       template="plotly_white", height=230, text_auto=".1f")
    fig_bebar.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_bebar, use_container_width=True)

st.markdown("---")

# ── SECTION 5: Breakeven sensitivity ──────────────────────────────────────
st.markdown("### 🎯 Breakeven Sensitivity")

col_s1, col_s2 = st.columns(2)

with col_s1:
    prices  = np.arange(0.5, 6.1, 0.25)
    be_vals = [breakeven_analysis({**params, "swap_price_usd": p})["breakeven_swaps_per_day"]
               for p in prices]
    fig_sp = go.Figure()
    fig_sp.add_trace(go.Scatter(x=prices, y=be_vals, mode="lines",
                                line=dict(color="#3B8BD4", width=2)))
    fig_sp.add_hline(y=swaps_day,  line_dash="dash", line_color="#1D9E75",
                     annotation_text=f"Current: {swaps_day}/day")
    fig_sp.add_vline(x=swap_price, line_dash="dot",  line_color="#F97316",
                     annotation_text=f"${swap_price:.2f}")
    fig_sp.update_layout(template="plotly_white", height=290,
                         title="Breakeven swaps/day vs swap price",
                         xaxis_title="Swap Price ($)",
                         yaxis_title="Breakeven Swaps/Day",
                         margin=dict(t=40, b=20))
    st.plotly_chart(fig_sp, use_container_width=True)

with col_s2:
    volumes = range(2, 51, 2)
    ebitdas = [unit_economics({**params, "swaps_per_station_day": v})["ebitda"] for v in volumes]
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(x=list(volumes), y=ebitdas,
                                  mode="lines+markers",
                                  line=dict(color="#F97316", width=2),
                                  marker=dict(size=5)))
    fig_vol.add_hline(y=0, line_dash="dash", line_color="#9ca3af")
    fig_vol.add_vline(x=swaps_day, line_dash="dot", line_color="#1D9E75",
                      annotation_text=f"Current: {swaps_day}/day")
    fig_vol.update_layout(template="plotly_white", height=290,
                           title="EBITDA vs daily swap volume",
                           xaxis_title="Daily Swaps/Station",
                           yaxis_title="EBITDA ($)",
                           margin=dict(t=40, b=20))
    st.plotly_chart(fig_vol, use_container_width=True)

st.markdown("---")

# ── SECTION 6: DCF valuation ───────────────────────────────────────────────
st.markdown("### 🏦 DCF Valuation Summary")

d1, d2, d3, d4, d5 = st.columns(5)
d1.metric("Initial Investment",  f"${dcf['initial_investment']:,.0f}")
d2.metric("NPV (operating)",     f"${dcf['npv']:,.0f}",
          delta_color="normal" if dcf["npv"] >= 0 else "inverse")
d3.metric("NPV + Terminal",      f"${dcf['npv_with_terminal']:,.0f}")
d4.metric("36M Total Revenue",   f"${dcf['total_revenue_36m']:,.0f}")
d5.metric("36M Net Income",      f"${dcf['total_net_income_36m']:,.0f}",
          delta_color="normal" if dcf["total_net_income_36m"] >= 0 else "inverse")

r_m = (1 + discount_rate) ** (1/12) - 1
months_sample = [m for m in [1, 6, 12, 18, 24, 30, 36] if m in cf["month"].values]
pv_values = [float(cf.loc[cf["month"] == m, "free_cash_flow"].values[0]) / (1 + r_m) ** m
             for m in months_sample]

fig_dcf = go.Figure()
fig_dcf.add_trace(go.Bar(
    x=[f"Month {m}" for m in months_sample], y=pv_values,
    marker_color=["#1D9E75" if v >= 0 else "#ef4444" for v in pv_values],
    text=[f"${v:,.0f}" for v in pv_values], textposition="outside",
))
fig_dcf.add_hline(y=0, line_dash="dash", line_color="#9ca3af")
fig_dcf.update_layout(template="plotly_white", height=290,
                       title="Discounted free cash flows (sample months)",
                       yaxis_title="PV of FCF ($)", margin=dict(t=40, b=20))
st.plotly_chart(fig_dcf, use_container_width=True)

st.markdown("---")

# ── SECTION 7: Scenario comparison ────────────────────────────────────────
st.markdown("### 🎭 Scenario Analysis — Base / Bull / Bear")

SC_COLORS = {"Base": "#3B8BD4", "Bull": "#1D9E75", "Bear": "#ef4444"}

with st.spinner("Running scenarios..."):
    sc_df = run_all_scenarios(params)

col_sc1, col_sc2 = st.columns(2)
with col_sc1:
    fig_scr = px.bar(sc_df, x="Scenario", y="Monthly Rev/Stn ($)",
                     color="Scenario", color_discrete_map=SC_COLORS,
                     template="plotly_white", text_auto=".0f", height=280,
                     title="Revenue per station/month")
    fig_scr.update_layout(showlegend=False, margin=dict(t=40, b=10))
    st.plotly_chart(fig_scr, use_container_width=True)

with col_sc2:
    fig_scn = px.bar(sc_df, x="Scenario", y="NPV ($)",
                     color="Scenario", color_discrete_map=SC_COLORS,
                     template="plotly_white", text_auto=".0f", height=280,
                     title="NPV by scenario")
    fig_scn.add_hline(y=0, line_dash="dash", line_color="#9ca3af")
    fig_scn.update_layout(showlegend=False, margin=dict(t=40, b=10))
    st.plotly_chart(fig_scn, use_container_width=True)

st.dataframe(
    sc_df.style.format({
        "Monthly Rev/Stn ($)": "${:,.0f}", "EBITDA/Stn ($)":    "${:,.0f}",
        "NPV ($)":             "${:,.0f}", "36M Net Income ($)": "${:,.0f}",
        "EBITDA Margin (%)":   "{:.1f}%",
    }),
    use_container_width=True, hide_index=True,
)

# 36M net income overlay
fig_scpl = go.Figure()
sc_overrides = {
    "Base": {},
    "Bull": {"swap_price_usd": 3.20, "swaps_per_station_day": 25.0},
    "Bear": {"swap_price_usd": 1.80, "swaps_per_station_day": 10.0},
}
for name, ov in sc_overrides.items():
    pl_t = pl_projection({**params, **ov})
    fig_scpl.add_trace(go.Scatter(
        x=pl_t["month"], y=pl_t["net_income"],
        name=name, line=dict(color=SC_COLORS[name], width=2),
    ))
fig_scpl.add_hline(y=0, line_dash="dash", line_color="#9ca3af")
fig_scpl.update_layout(template="plotly_white", height=300,
                        xaxis_title="Month", yaxis_title="Net Income ($)",
                        margin=dict(t=20, b=20),
                        legend=dict(orientation="h"))
st.plotly_chart(fig_scpl, use_container_width=True)

st.markdown("---")

# ── SECTION 8: Monte Carlo ─────────────────────────────────────────────────
st.markdown("### 🎲 Monte Carlo Simulation — Risk Analysis")
st.caption("2,000 simulations sampling swap price, volume, OpEx, churn, and discount rate.")

with st.spinner("Running 2,000 Monte Carlo simulations..."):
    mc = monte_carlo_simulation(params, n_sims=2000)

mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("NPV P10 (downside)",  f"${mc['npv_p10']:,.0f}")
mc2.metric("NPV P50 (median)",    f"${mc['npv_p50']:,.0f}")
mc3.metric("NPV P90 (upside)",    f"${mc['npv_p90']:,.0f}")
mc4.metric("Prob. Positive NPV",  f"{mc['prob_positive_npv']}%")
mc5.metric("VaR 95%",             f"${mc['var_95']:,.0f}")

col_mc1, col_mc2 = st.columns(2)

with col_mc1:
    fig_mcn = go.Figure()
    fig_mcn.add_trace(go.Histogram(x=mc["npv_simulations"], nbinsx=60,
                                    marker_color="#3B8BD4", opacity=0.75))
    fig_mcn.add_vline(x=0,             line_dash="dash", line_color="red",   annotation_text="Zero NPV")
    fig_mcn.add_vline(x=mc["npv_p50"], line_dash="dot",  line_color="#1D9E75", annotation_text="P50")
    fig_mcn.add_vline(x=mc["var_95"],  line_dash="dot",  line_color="#F97316", annotation_text="VaR 95%")
    fig_mcn.update_layout(template="plotly_white", height=310,
                           title="NPV distribution (2,000 sims)",
                           xaxis_title="NPV ($)", yaxis_title="Frequency",
                           margin=dict(t=40, b=20))
    st.plotly_chart(fig_mcn, use_container_width=True)

with col_mc2:
    fig_mcr = go.Figure()
    fig_mcr.add_trace(go.Histogram(x=mc["revenue_simulations"], nbinsx=60,
                                    marker_color="#F97316", opacity=0.75))
    fig_mcr.add_vline(x=mc["rev_p50"], line_dash="dot", line_color="#1D9E75", annotation_text="P50")
    fig_mcr.update_layout(template="plotly_white", height=310,
                           title="36M Revenue distribution (2,000 sims)",
                           xaxis_title="Total Revenue ($)", yaxis_title="Frequency",
                           margin=dict(t=40, b=20))
    st.plotly_chart(fig_mcr, use_container_width=True)

# Tornado chart
st.markdown("### 🌪️ Sensitivity Tornado — NPV Impact")

tornado_defs = [
    ("Swap Price",      "swap_price_usd",         0.80, 1.20),
    ("Swaps/Day",       "swaps_per_station_day",   0.75, 1.25),
    ("OpEx/Station",    "opex_per_station_month",  0.80, 1.20),
    ("Gross Margin",    "gross_margin_pct",         0.85, 1.15),
    ("Station Growth",  "station_growth_monthly",  0.50, 1.50),
    ("Discount Rate",   "discount_rate_annual",    0.75, 1.25),
]

base_npv = dcf["npv"]
tornado_rows = []
for label, key, lo, hi in tornado_defs:
    npv_lo = dcf_valuation({**params, key: params[key] * lo})["npv"]
    npv_hi = dcf_valuation({**params, key: params[key] * hi})["npv"]
    tornado_rows.append({"Parameter": label, "Low": npv_lo - base_npv,
                          "High": npv_hi - base_npv,
                          "Range": abs(npv_hi - npv_lo)})

tornado_df = pd.DataFrame(tornado_rows).sort_values("Range")

fig_tor = go.Figure()
for _, row in tornado_df.iterrows():
    fig_tor.add_trace(go.Bar(
        name=f"{row['Parameter']} ▼",
        x=[row["Low"]], y=[row["Parameter"]], orientation="h",
        marker_color="#ef4444" if row["Low"] < 0 else "#1D9E75",
        showlegend=False,
    ))
    fig_tor.add_trace(go.Bar(
        name=f"{row['Parameter']} ▲",
        x=[row["High"]], y=[row["Parameter"]], orientation="h",
        marker_color="#1D9E75" if row["High"] > 0 else "#ef4444",
        showlegend=False,
    ))

fig_tor.add_vline(x=0, line_dash="dash", line_color="#9ca3af")
fig_tor.update_layout(
    template="plotly_white", barmode="overlay", height=360,
    title="NPV sensitivity (deviation from base case)",
    xaxis_title="NPV Change from Base ($)",
    margin=dict(t=40, b=20, l=140),
)
st.plotly_chart(fig_tor, use_container_width=True)

# ── SECTION 9: Exports ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📥 Export Financial Model")

col_ex1, col_ex2, col_ex3 = st.columns(3)
with col_ex1:
    st.download_button("⬇️ P&L Projection (CSV)",
                       data=pl.to_csv(index=False).encode("utf-8"),
                       file_name="spiro_pl_projection.csv", mime="text/csv")
with col_ex2:
    st.download_button("⬇️ Cash Flow Model (CSV)",
                       data=cf.to_csv(index=False).encode("utf-8"),
                       file_name="spiro_cashflow.csv", mime="text/csv")
with col_ex3:
    snapshot = f"""SPIRO FINANCIAL MODEL SNAPSHOT
{'='*50}
Assumptions
  Swap price          : ${swap_price:.2f}
  Swaps/station/day   : {swaps_day}
  Starting stations   : {n_stations}
  Gross margin        : {gross_margin*100:.0f}%
  Discount rate       : {discount_rate*100:.0f}%

Unit Economics (per station/month)
  Revenue             : ${ue['gross_revenue']:,.2f}
  EBITDA              : ${ue['ebitda']:,.2f}  ({ue['ebitda_margin_pct']:.1f}%)
  NOPAT               : ${ue['nopat']:,.2f}

Breakeven
  Swaps/day needed    : {be['breakeven_swaps_per_day']}
  Margin of safety    : {be['margin_of_safety_pct']:.1f}%
  Payback             : {be['payback_months']} months

Valuation (36M)
  NPV                 : ${dcf['npv']:,.0f}
  IRR                 : {dcf['irr_annual_pct']}%
  Total Revenue       : ${dcf['total_revenue_36m']:,.0f}
  Net Income          : ${dcf['total_net_income_36m']:,.0f}

Monte Carlo (2,000 sims)
  NPV P50             : ${mc['npv_p50']:,.0f}
  Prob +ve NPV        : {mc['prob_positive_npv']}%
  VaR 95%             : ${mc['var_95']:,.0f}
{'='*50}
"""
    st.download_button("⬇️ Model Snapshot (.txt)",
                       data=snapshot.encode("utf-8"),
                       file_name="spiro_financial_snapshot.txt",
                       mime="text/plain")