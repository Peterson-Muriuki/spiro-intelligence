"""
utils/ai_engine.py
Unified AI engine for Spiro Intelligence Dashboard.

Routing logic:
  1. If GROQ_API_KEY is set in environment or Streamlit secrets  -> Groq (cloud)
  2. Else try Ollama locally (http://localhost:11434) with mistral -> local
  3. Both unavailable -> graceful fallback message

Local dev  : install Ollama + run `ollama pull mistral`  (no API key needed)
Streamlit  : add GROQ_API_KEY to app secrets in share.streamlit.io
"""

import os
import json
import requests
import streamlit as st
from typing import Generator

OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "mistral"
GROQ_MODEL   = "mixtral-8x7b-32768"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S    = 60
MAX_TOKENS   = 1024

SYSTEM_PROMPT = """You are an expert analytics AI assistant inside the Spiro Swap Station
Intelligence Dashboard — a decision-support tool for country managers overseeing EV battery
swap station networks across Africa (Kenya, Nigeria, Rwanda, Uganda).

Your role:
- Interpret operational, financial, and customer data presented to you
- Give clear, concise, actionable insights a country manager can act on today
- Flag risks and opportunities backed by the numbers provided
- Use plain business English — no jargon, no hedging
- Structure responses with bullet points where helpful
- Always ground answers in the data provided — never invent numbers

About Spiro: operates EV battery swap stations for motorcycles/boda-bodas.
Key metrics: station utilisation, swap turnover, customer churn, LTV, revenue per station.
"""


def _get_groq_key():
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        return key
    try:
        return st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        return ""


def ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def groq_available() -> bool:
    return bool(_get_groq_key())


def ai_available() -> bool:
    return groq_available() or ollama_available()


def active_backend() -> str:
    if groq_available():
        return "Groq (Mixtral-8x7B)"
    if ollama_available():
        return "Ollama (Mistral local)"
    return "unavailable"


def ask_ai(prompt: str, context: dict = None, system_override: str = None) -> str:
    """Non-streaming call. Returns full response string."""
    system = system_override or SYSTEM_PROMPT
    full_prompt = prompt
    if context:
        full_prompt += "\n\nDATA CONTEXT:\n" + json.dumps(context, indent=2, default=str)

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": full_prompt},
    ]

    if groq_available():
        return _ask_groq(messages)
    if ollama_available():
        return _ask_ollama(messages)
    return (
        "AI assistant unavailable. "
        "Local: install Ollama and run `ollama pull mistral`. "
        "Cloud: add GROQ_API_KEY to Streamlit secrets."
    )


def stream_ai(prompt: str, context: dict = None, system_override: str = None) -> Generator:
    """Streaming call for use with st.write_stream()."""
    system = system_override or SYSTEM_PROMPT
    full_prompt = prompt
    if context:
        full_prompt += "\n\nDATA CONTEXT:\n" + json.dumps(context, indent=2, default=str)

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": full_prompt},
    ]

    if groq_available():
        yield from _stream_groq(messages)
    elif ollama_available():
        yield from _stream_ollama(messages)
    else:
        yield (
            "⚠️ AI assistant unavailable. "
            "Add GROQ_API_KEY to Streamlit secrets or run Ollama locally."
        )


# ── Groq backend ──────────────────────────────────────────────────────────────

def _ask_groq(messages: list) -> str:
    try:
        r = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {_get_groq_key()}",
                     "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages,
                  "max_tokens": MAX_TOKENS, "temperature": 0.3, "stream": False},
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq error: {e}"


def _stream_groq(messages: list) -> Generator:
    try:
        with requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {_get_groq_key()}",
                     "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": messages,
                  "max_tokens": MAX_TOKENS, "temperature": 0.3, "stream": True},
            timeout=TIMEOUT_S, stream=True,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8")
                if text.startswith("data: "):
                    text = text[6:]
                if text.strip() == "[DONE]":
                    break
                try:
                    delta = json.loads(text)["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue
    except Exception as e:
        yield f"Groq streaming error: {e}"


# ── Ollama backend ────────────────────────────────────────────────────────────

def _ask_ollama(messages: list) -> str:
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": MAX_TOKENS}},
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
    except Exception as e:
        return f"Ollama error: {e}"


def _stream_ollama(messages: list) -> Generator:
    try:
        with requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": True,
                  "options": {"temperature": 0.3, "num_predict": MAX_TOKENS}},
            timeout=TIMEOUT_S, stream=True,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    delta = chunk.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if chunk.get("done"):
                        break
                except Exception:
                    continue
    except Exception as e:
        yield f"Ollama streaming error: {e}"


# ── Pre-built prompt builders used by each page ───────────────────────────────

def prompt_market_summary(kpis: dict, country: str) -> str:
    return f"""Analyse the Spiro {country} market KPIs below and provide:
1. A 2-sentence executive summary of market health
2. The single biggest opportunity right now
3. The single biggest risk right now
4. Three specific actions the country manager should take this week
Be direct. Use the numbers. No generic advice."""


def prompt_churn_explain(customer: dict) -> str:
    return f"""Explain in plain language why this Spiro customer is at high churn risk
and recommend the single best retention action. Keep to 3-4 sentences.
Customer: {json.dumps(customer, default=str)}"""


def prompt_financial_qa(question: str) -> str:
    return f"""A Spiro country manager asks: "{question}"
Answer using only the financial data provided. Be specific with numbers.
If the data does not support an answer, say so clearly."""


def prompt_deployment_recommendation(top_sites: list, city: str) -> str:
    return f"""Based on deployment scoring for {city}:
1. Which site to prioritise first and why (2 sentences)
2. What conditions would change this recommendation
3. One key risk to deploying in this location
Sites: {json.dumps(top_sites, default=str)}"""


def prompt_report_narrative(summary: dict, country: str) -> str:
    return f"""Write a professional weekly narrative for the Spiro {country} country manager.
Structure: Market pulse → Operations → Customer health → Financial → Actions next 7 days.
Under 300 words. Confident, direct business prose. Use the data provided."""