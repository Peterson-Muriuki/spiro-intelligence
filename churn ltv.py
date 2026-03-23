"""
pages/3_Churn_LTV.py
Customer churn prediction, at-risk riders, and LTV analysis.

Integration: reads customers from st.session_state.
             Trains churn model on the fly and caches via @st.cache_data.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.churn_model import train_churn_model, score_customers, get_at_risk_customers
from models.ltv_model   import compute_ltv, ltv_summary_by_segment, ltv_country_heatmap

if "customers" not in st.session_state:
    st.warning("Please open the app via **app.py** (`streamlit run app.py`).")
    st.stop()

customers = st.session_state["customers"]
country   = st.session_state.get("selected_country", "All")
if country != "All":
    customers = customers[customers["country"] == country]

st.markdown("## 🔮 Churn Prediction & Customer Lifetime Value")
st.caption(f"Market: **{country}** · Identify at-risk riders and their revenue impact.")

# ── Train / score (cached by customer hash) ───────────────────────────────
@st.cache_data(show_spinner="Training churn model...")
def get_scored(df: pd.DataFrame):
    model, feat_cols      = train_churn_model(df)
    scored, importances   = score_customers(df, model, feat_cols)
    scored                = compute_ltv(scored)
    return scored, importances

scored, importances = get_scored(customers)

# ── KPI cards ──────────────────────────────────────────────────────────────
high_risk    = (scored["churn_score"] >= 0.6).sum()
medium_risk  = ((scored["churn_score"] >= 0.3) & (scored["churn_score"] < 0.6)).sum()
low_risk     = (scored["churn_score"] < 0.3).sum()
at_risk_rev  = scored[scored["churn_score"] >= 0.5]["monthly_revenue"].sum()
avg_ltv      = scored["ltv"].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("High Risk",         high_risk,   f"{high_risk/len(scored)*100:.1f}%")
c2.metric("Medium Risk",       medium_risk, f"{medium_risk/len(scored)*100:.1f}%")
c3.metric("Low Risk",          low_risk)
c4.metric("At-Risk Monthly Rev", f"${at_risk_rev:,.0f}")
c5.metric("Avg Customer LTV",    f"${avg_ltv:,.0f}")

st.markdown("---")

col_l, col_r = st.columns(2)

with col_l:
    st.markdown("### 🎯 Churn Score Distribution")
    fig_hist = px.histogram(
        scored, x="churn_score", nbins=40,
        color="churn_risk",
        color_discrete_map={"Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444"},
        template="plotly_white",
        labels={"churn_score": "Churn Score", "churn_risk": "Risk"},
        category_orders={"churn_risk": ["Low", "Medium", "High"]},
    )
    fig_hist.add_vline(x=0.5, line_dash="dash", line_color="red",
                       annotation_text="Threshold 0.5")
    fig_hist.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig_hist, use_container_width=True)

with col_r:
    st.markdown("### 🔑 Churn Drivers")
    imp_df = pd.DataFrame(list(importances.items()), columns=["Feature", "Importance"])
    imp_df["Feature"] = imp_df["Feature"].replace({
        "swap_freq_monthly":  "Monthly Swap Frequency",
        "last_swap_days_ago": "Days Since Last Swap",
        "tenure_months":      "Customer Tenure (months)",
        "monthly_revenue":    "Monthly Revenue",
        "segment_enc":        "Customer Segment",
    })
    imp_df = imp_df.sort_values("Importance", ascending=True)
    fig_imp = px.bar(
        imp_df, x="Importance", y="Feature", orientation="h",
        template="plotly_white", color="Importance",
        color_continuous_scale="Teal",
    )
    fig_imp.update_layout(margin=dict(t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig_imp, use_container_width=True)

# ── LTV charts ─────────────────────────────────────────────────────────────
st.markdown("### 💰 Customer Lifetime Value")

col_ltv1, col_ltv2 = st.columns(2)

with col_ltv1:
    ltv_seg_df = scored.groupby("ltv_segment").agg(
        count   = ("customer_id", "count"),
        avg_ltv = ("ltv", "mean"),
    ).reset_index()
    fig_ltv = px.bar(
        ltv_seg_df, x="ltv_segment", y="avg_ltv",
        color="ltv_segment",
        color_discrete_map={"Bronze": "#cd7f32", "Silver": "#c0c0c0", "Gold": "#ffd700"},
        template="plotly_white", text_auto=".0f",
        labels={"ltv_segment": "LTV Tier", "avg_ltv": "Avg LTV ($)"},
        title="Avg LTV by segment",
    )
    fig_ltv.update_layout(margin=dict(t=40, b=20), showlegend=False)
    st.plotly_chart(fig_ltv, use_container_width=True)

with col_ltv2:
    sample = scored.sample(min(500, len(scored)), random_state=42)
    fig_scatter = px.scatter(
        sample,
        x="tenure_months", y="ltv",
        color="churn_risk", size="monthly_revenue",
        color_discrete_map={"Low": "#22c55e", "Medium": "#f59e0b", "High": "#ef4444"},
        template="plotly_white",
        title="LTV vs tenure (bubble = monthly revenue)",
        labels={"tenure_months": "Tenure (months)", "ltv": "LTV ($)", "churn_risk": "Risk"},
    )
    fig_scatter.update_layout(margin=dict(t=40, b=20))
    st.plotly_chart(fig_scatter, use_container_width=True)

# ── At-risk table ──────────────────────────────────────────────────────────
st.markdown("### 🚨 At-Risk Customers — Action List")
threshold = st.slider("Churn score threshold", 0.3, 0.9, 0.5, 0.05)
at_risk   = get_at_risk_customers(scored, threshold)

st.caption(
    f"**{len(at_risk)}** customers above {threshold:.2f} threshold · "
    f"Monthly revenue at risk: **${at_risk['monthly_revenue'].sum():,.0f}**"
)

display_cols = [c for c in
    ["customer_id","country","city","segment","churn_score","churn_risk",
     "monthly_revenue","ltv","tenure_months","swap_freq_monthly","last_swap_days_ago"]
    if c in at_risk.columns]

st.dataframe(
    at_risk[display_cols].head(50)
    .style.format({"churn_score": "{:.2f}", "monthly_revenue": "${:.0f}", "ltv": "${:.0f}"}),
    use_container_width=True, hide_index=True,
)

# ── LTV by country ─────────────────────────────────────────────────────────
st.markdown("### 🌍 LTV by Country")
ltv_ctry = ltv_country_heatmap(scored)
fig_ctry = px.bar(
    ltv_ctry, x="country", y="avg_ltv",
    color="total_ltv", color_continuous_scale="Teal",
    template="plotly_white", text_auto=".0f",
    labels={"avg_ltv": "Avg LTV ($)", "total_ltv": "Total LTV ($)"},
)
fig_ctry.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig_ctry, use_container_width=True)

with st.expander("📋 LTV by Segment Table"):
    st.dataframe(
        ltv_summary_by_segment(scored)
        .style.format({"avg_ltv": "${:.0f}", "total_ltv": "${:,.0f}", "avg_revenue": "${:.0f}"}),
        use_container_width=True, hide_index=True,
    )

# ── AI Churn Analysis ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🤖 AI Churn & Retention Analysis")
if st.button("Analyse churn with AI", key="ai_churn"):
    from utils.ai_engine import narrate_churn
    churn_kpis = {
        "active_stations": 0, "total_stations": 0,
        "daily_turnover": 0, "monthly_revenue": 0,
        "revenue_growth_pct": 0, "swap_success_rate": 0,
        "idle_hours_daily": 0,
    }
    with st.spinner("Analysing customer risk with AI..."):
        insight = narrate_churn(scored, churn_kpis)
    st.markdown(insight)
else:
    st.caption("Click above for AI-generated churn analysis and retention recommendations.")

# ── AI Churn Explainer ─────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🤖 AI Churn Explainer")

from utils.ai_engine import ask_ai, ai_available, active_backend, prompt_churn_explain

if not ai_available():
    st.info("AI insights unavailable. Add GROQ_API_KEY to Streamlit secrets or run Ollama locally.")
else:
    st.caption(f"Backend: {active_backend()}")
    st.markdown("**Select a customer to explain their churn risk:**")

    if len(at_risk) > 0:
        selected_id = st.selectbox(
            "At-risk customer",
            at_risk["customer_id"].head(20).tolist(),
            key="churn_explainer_select",
        )
        customer_row = at_risk[at_risk["customer_id"] == selected_id].iloc[0]
        customer_dict = {
            "customer_id":       customer_row["customer_id"],
            "segment":           customer_row.get("segment", ""),
            "tenure_months":     customer_row.get("tenure_months", ""),
            "swap_freq_monthly": customer_row.get("swap_freq_monthly", ""),
            "last_swap_days_ago":customer_row.get("last_swap_days_ago", ""),
            "monthly_revenue":   customer_row.get("monthly_revenue", ""),
            "churn_score":       round(float(customer_row["churn_score"]), 3),
            "ltv":               round(float(customer_row.get("ltv", 0)), 2),
        }
        st.json(customer_dict)

        if st.button("🔍 Explain This Customer's Risk", key="ai_churn_explain"):
            with st.spinner("Analysing customer profile..."):
                explanation = ask_ai(prompt_churn_explain(customer_dict))
            st.markdown(explanation)
    else:
        st.info("No at-risk customers found at current threshold.")

    st.markdown("**AI Portfolio Churn Assessment:**")
    if st.button("📊 Assess Overall Churn Portfolio", key="ai_churn_portfolio"):
        churn_ctx = {
            "country": country,
            "total_customers":    len(scored),
            "high_risk":          int((scored["churn_score"] >= 0.6).sum()),
            "medium_risk":        int(((scored["churn_score"] >= 0.3) & (scored["churn_score"] < 0.6)).sum()),
            "at_risk_revenue":    round(float(at_risk["monthly_revenue"].sum()), 2),
            "avg_ltv":            round(float(scored["ltv"].mean()), 2),
            "segment_breakdown":  scored.groupby("segment")["churn_score"].mean().round(3).to_dict(),
            "avg_churn_score":    round(float(scored["churn_score"].mean()), 3),
        }
        with st.spinner("Assessing churn portfolio..."):
            assessment = ask_ai(
                f"Assess the churn risk portfolio for the Spiro {country} market. "
                "What does the distribution tell us? Which segment needs most urgent attention? "
                "What retention strategy would have highest ROI?",
                context=churn_ctx,
            )
        st.markdown(assessment)