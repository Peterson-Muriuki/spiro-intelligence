"""
pages/7_AI_Analyst.py
Conversational AI analyst — chat with your Spiro data using Mistral via Ollama or Groq.

Features:
  - Free-form chat with full data context injected automatically
  - Quick-action buttons for common country manager questions
  - Conversation history persisted in session_state
  - Shows which AI backend is active
"""
import streamlit as st
import pandas as pd
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.ai_engine import (
    ask_ai, stream_ai, ai_available, active_backend,
    prompt_market_summary, prompt_churn_explain,
    prompt_deployment_recommendation, prompt_report_narrative,
)
from utils.kpis import compute_station_kpis, country_summary
from models.churn_model import train_churn_model, score_customers
from models.ltv_model import compute_ltv
from models.financial_model import unit_economics, breakeven_analysis, dcf_valuation, DEFAULTS

# ── Guard ──────────────────────────────────────────────────────────────────
if "stations" not in st.session_state:
    st.warning("Please open the app via **app.py** (`streamlit run app.py`).")
    st.stop()

stations  = st.session_state["stations"]
customers = st.session_state["customers"]
swaps     = st.session_state["swaps"]
revenue   = st.session_state["revenue"]
country   = st.session_state.get("selected_country", "All")

# ── Header ─────────────────────────────────────────────────────────────────
st.markdown("## 🤖 AI Analyst")
st.caption(f"Market: **{country}** · Powered by Mistral · Ask anything about your data.")

# ── Backend status badge ───────────────────────────────────────────────────
backend = active_backend()
if backend == "unavailable":
    st.error(
        "**AI backend not configured.** "
        "Add `GROQ_API_KEY` to Streamlit secrets, or run Ollama locally with `ollama pull mistral`."
    )
else:
    st.success(f"✅ AI backend: **{backend}**")

st.markdown("---")

# ── Build data context (injected into every prompt) ────────────────────────
@st.cache_data(show_spinner=False)
def build_context(_stations, _customers, _swaps, _revenue, ctry):
    """Assembles a compact data context dict to pass to the AI."""
    if ctry != "All":
        sids = _stations[_stations["country"] == ctry]["station_id"].tolist()
        st_f = _stations[_stations["country"] == ctry]
        cu_f = _customers[_customers["country"] == ctry]
        sw_f = _swaps[_swaps["station_id"].isin(sids)]
        rv_f = _revenue[_revenue["country"] == ctry]
    else:
        st_f, cu_f, sw_f, rv_f = _stations, _customers, _swaps, _revenue

    kpis = compute_station_kpis(st_f, sw_f, rv_f)

    # Churn
    try:
        model, feat = train_churn_model(cu_f)
        scored, _   = score_customers(cu_f, model, feat)
        scored      = compute_ltv(scored)
        churn_ctx   = {
            "high_risk_count":      int((scored["churn_score"] >= 0.6).sum()),
            "medium_risk_count":    int(((scored["churn_score"] >= 0.3) & (scored["churn_score"] < 0.6)).sum()),
            "at_risk_revenue":      round(float(scored[scored["churn_score"] >= 0.5]["monthly_revenue"].sum()), 2),
            "avg_ltv":              round(float(scored["ltv"].mean()), 2),
            "top_at_risk":          scored[scored["churn_score"] >= 0.6][
                ["customer_id","segment","churn_score","monthly_revenue","ltv","tenure_months"]
            ].head(5).to_dict("records"),
        }
    except Exception:
        churn_ctx = {}

    # Financial
    ue  = unit_economics({})
    be  = breakeven_analysis({})
    dcf = dcf_valuation({})

    # Country summary
    cs = country_summary(_stations, _swaps, _customers, _revenue).to_dict("records")

    return {
        "market":          ctry,
        "kpis":            kpis,
        "churn":           churn_ctx,
        "station_summary": {
            "total":    int(st_f["station_id"].count()),
            "active":   int((st_f["status"] == "active").sum()),
            "inactive": int((st_f["status"] == "inactive").sum()),
            "by_city":  st_f.groupby("city")["station_id"].count().to_dict(),
        },
        "financial_snapshot": {
            "revenue_per_station_month": ue["gross_revenue"],
            "ebitda_per_station":        ue["ebitda"],
            "ebitda_margin_pct":         ue["ebitda_margin_pct"],
            "breakeven_swaps_per_day":   be["breakeven_swaps_per_day"],
            "margin_of_safety_pct":      be["margin_of_safety_pct"],
            "npv_36m":                   dcf["npv"],
            "payback_months":            be["payback_months"],
        },
        "country_comparison": cs,
    }

with st.spinner("Building data context..."):
    ctx = build_context(stations, customers, swaps, revenue, country)

# ── Quick action buttons ───────────────────────────────────────────────────
st.markdown("### ⚡ Quick Actions")
st.caption("One-click AI insights — no typing needed.")

qa_cols = st.columns(4)

quick_actions = {
    "📊 Market Summary":         prompt_market_summary(ctx.get("kpis", {}), country),
    "🚨 Top Churn Risk":         f"Who are the top churning customers and what should I do? Use the churn data provided.",
    "💹 Financial Health Check": f"Assess the financial health of the {country} market. Is the station economics model sustainable?",
    "🗺️ Deployment Advice":      f"Based on the station data, which cities need more swap stations most urgently and why?",
}

for i, (label, prompt_text) in enumerate(quick_actions.items()):
    with qa_cols[i]:
        if st.button(label, use_container_width=True, disabled=not ai_available()):
            if "messages" not in st.session_state:
                st.session_state["messages"] = []
            st.session_state["messages"].append({"role": "user", "content": label})
            with st.spinner("Thinking..."):
                response = ask_ai(prompt_text, context=ctx)
            st.session_state["messages"].append({"role": "assistant", "content": response})

st.markdown("---")

# ── Conversation history ───────────────────────────────────────────────────
st.markdown("### 💬 Chat with Your Data")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Render history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

# ── Chat input ─────────────────────────────────────────────────────────────
if prompt := st.chat_input(
    "Ask anything — e.g. 'Which market has the best unit economics?' or 'Why is churn high?'",
    disabled=not ai_available(),
):
    # Show user message
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)

    # Stream AI response
    with st.chat_message("assistant", avatar="🤖"):
        response_placeholder = st.empty()
        full_response = ""
        try:
            for chunk in stream_ai(prompt, context=ctx):
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
            response_placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"Error generating response: {e}"
            response_placeholder.markdown(full_response)

    st.session_state["messages"].append({"role": "assistant", "content": full_response})

# ── Clear chat ─────────────────────────────────────────────────────────────
st.markdown("---")
col_clr, col_ctx = st.columns([1, 3])
with col_clr:
    if st.button("🗑️ Clear conversation"):
        st.session_state["messages"] = []
        st.rerun()

with col_ctx:
    with st.expander("🔍 View data context sent to AI"):
        st.json(ctx)