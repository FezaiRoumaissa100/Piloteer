"""
performance.py — Piloteer Performance Dashboard
Token usage, execution time, and success rate analytics per node and per mission.
"""
import streamlit as st
import sqlite3
import pandas as pd
import pathlib


SRC_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DB_PATH = SRC_DIR / "loggings" / "database" / "piloteer_logs.db"

st.set_page_config(layout="wide", page_title="Piloteer - Performance")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background:#f8f9fa; }
    [data-testid="stHeader"]           { background:#f8f9fa; }
    .block-container                   { padding-top:2rem; }
    .page-title  { font-size:1.8rem; font-weight:800; color:#1f2937; margin-bottom:0; }
    .page-sub    { font-size:0.9rem; color:#6b7280; margin-bottom:1.5rem; }
    .divider     { border:none; border-top:1px solid #e5e7eb; margin:1.5rem 0; }
    div[data-testid="metric-container"] { background:#fff; border:1px solid #e5e7eb; border-radius:8px; padding:1rem; }
    div[data-testid="metric-container"] label { color:#6b7280 !important; font-size:0.8rem !important; }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#1f2937 !important; font-size:1.6rem !important; font-weight:700 !important; }
    .stDataFrame { border:1px solid #e5e7eb; border-radius:8px; }
    h3, h4 { color:#1f2937; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">Performance Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Token usage, execution time, and success rate analytics per node and per mission.</div>', unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def load_events():
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM events ORDER BY event_id ASC", conn)
    conn.close()
    return df

df = load_events()

if df.empty:
    st.error(f"Database not found or empty: {DB_PATH}")
    st.stop()

# ── Scope selector ────────────────────────────────────────────────────────────
options = ["All missions"] + df['trace_id'].unique().tolist()
scope   = st.selectbox("Analyze", options)

df_m = df.copy() if scope == "All missions" else df[df['trace_id'] == scope].copy()
st.caption(f"Scope: {scope}")
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Global KPIs ───────────────────────────────────────────────────────────────
st.markdown("### Global Summary")

n_missions    = df_m['trace_id'].nunique()
total_in      = int(df_m['gen_ai_input_tokens'].sum(skipna=True))
total_out     = int(df_m['gen_ai_output_tokens'].sum(skipna=True))
total_dur_s   = round(df_m['duration_ms'].sum(skipna=True) / 1000, 1)
n_success     = int((df_m['status'] == 'success').sum())
success_rate  = round(n_success / len(df_m) * 100, 1) if len(df_m) > 0 else 0

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Missions",       n_missions)
k2.metric("Input Tokens",   f"{total_in:,}")
k3.metric("Output Tokens",  f"{total_out:,}")
k4.metric("Total Duration", f"{total_dur_s} s")
k5.metric("Successes",      n_success)
k6.metric("Success Rate",   f"{success_rate} %")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Breakdown by node ─────────────────────────────────────────────────────────
st.markdown("### Breakdown by Node")

node_df = df_m.groupby("node_name").agg(
    Calls          = ("event_id",            "count"),
    Input_Tokens   = ("gen_ai_input_tokens",  "sum"),
    Output_Tokens  = ("gen_ai_output_tokens", "sum"),
    Avg_Duration   = ("duration_ms",          "mean"),
    Total_Duration = ("duration_ms",          "sum"),
    Successes      = ("status",               lambda x: (x == "success").sum()),
).reset_index()

node_df["Avg_Duration"]   = node_df["Avg_Duration"].round(0).astype("Int64")
node_df["Total_Duration"] = node_df["Total_Duration"].round(0).astype("Int64")
node_df["Input_Tokens"]   = node_df["Input_Tokens"].astype("Int64")
node_df["Output_Tokens"]  = node_df["Output_Tokens"].astype("Int64")

node_df = node_df.rename(columns={
    "node_name":      "Node",
    "Input_Tokens":   "Input Tokens",
    "Output_Tokens":  "Output Tokens",
    "Avg_Duration":   "Avg Duration (ms)",
    "Total_Duration": "Total Duration (ms)",
    "Successes":      "Successes",
})

st.dataframe(node_df, use_container_width=True, hide_index=True)
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Charts ────────────────────────────────────────────────────────────────────
st.markdown("### Charts")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.markdown("**Token consumption by Node**")
    chart_tok = df_m.groupby("node_name")[["gen_ai_input_tokens","gen_ai_output_tokens"]].sum()
    chart_tok.columns = ["Input", "Output"]
    st.bar_chart(chart_tok, use_container_width=True)

with col_g2:
    st.markdown("**Average execution time by Node (ms)**")
    chart_dur = df_m.groupby("node_name")["duration_ms"].mean().round(0).rename("Avg Duration (ms)")
    st.bar_chart(chart_dur, use_container_width=True)

# ── Per-mission table (only when all missions selected) ───────────────────────
if scope == "All missions":
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("### Summary by Mission")

    mission_df = df_m.groupby("trace_id").agg(
        Steps         = ("event_id",            "count"),
        Input_Tokens  = ("gen_ai_input_tokens",  "sum"),
        Output_Tokens = ("gen_ai_output_tokens", "sum"),
        Duration_s    = ("duration_ms",          lambda x: round(x.sum() / 1000, 1)),
        Success_Rate  = ("status",               lambda x: f"{round((x=='success').mean()*100,1)} %"),
    ).reset_index()

    mission_df = mission_df.rename(columns={
        "trace_id":     "Mission (Trace ID)",
        "Steps":        "Steps",
        "Input_Tokens": "Input Tokens",
        "Output_Tokens":"Output Tokens",
        "Duration_s":   "Duration (s)",
        "Success_Rate": "Success Rate",
    })

    st.dataframe(mission_df, use_container_width=True, hide_index=True)
