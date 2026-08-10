"""
replay.py — Piloteer Session Replay Viewer
Step through what the Agent saw and thought, step by step.
"""
import streamlit as st
import sqlite3
import pandas as pd
import json
import pathlib
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
SRC_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DB_PATH = SRC_DIR / "loggings" / "database" / "piloteer_logs.db"

st.set_page_config(layout="wide", page_title="Piloteer - Session Replay")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background:#f8f9fa; }
    [data-testid="stHeader"]           { background:#f8f9fa; }
    .block-container                   { padding-top:2rem; }
    .page-title  { font-size:1.8rem; font-weight:800; color:#1f2937; margin-bottom:0; }
    .page-sub    { font-size:0.9rem; color:#6b7280; margin-bottom:1.5rem; }
    .divider     { border:none; border-top:1px solid #e5e7eb; margin:1.2rem 0; }
    .badge-success { background:#d1fae5; color:#065f46; border-radius:4px; padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .badge-error   { background:#fee2e2; color:#991b1b; border-radius:4px; padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .badge-node    { background:#ede9fe; color:#5b21b6; border-radius:4px; padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .step-counter  { background:#fff; border:1px solid #e5e7eb; border-radius:6px; padding:0.4rem 1rem; color:#374151; font-size:0.9rem; }
    div[data-testid="metric-container"] { background:#fff; border:1px solid #e5e7eb; border-radius:8px; padding:0.8rem; }
    div[data-testid="metric-container"] label { color:#6b7280 !important; font-size:0.8rem !important; }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#1f2937 !important; font-size:1.4rem !important; font-weight:700 !important; }
    .stButton button { border-radius:6px; font-weight:600; border:1px solid #d1d5db; background:#fff; color:#374151; }
    .stButton button:hover { background:#f3f4f6; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">Session Replay</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Step through what the Agent saw and thought during each mission.</div>', unsafe_allow_html=True)

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

# ── Mission selector ──────────────────────────────────────────────────────────
col_sel, col_info = st.columns([2, 1])
with col_sel:
    traces = df['trace_id'].unique().tolist()
    selected = st.selectbox("Select a mission", traces)

trace_df = df[df['trace_id'] == selected].reset_index(drop=True)
total = len(trace_df)

with col_info:
    st.metric("Steps in this mission", total)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Navigation buttons ────────────────────────────────────────────────────────
if "step_idx" not in st.session_state or st.session_state.get("replay_trace") != selected:
    st.session_state.step_idx = 0
    st.session_state.replay_trace = selected

nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 2, 1, 1])
with nav1:
    if st.button("First", use_container_width=True):
        st.session_state.step_idx = 0
with nav2:
    if st.button("Previous", use_container_width=True):
        if st.session_state.step_idx > 0:
            st.session_state.step_idx -= 1
with nav4:
    if st.button("Next", use_container_width=True):
        if st.session_state.step_idx < total - 1:
            st.session_state.step_idx += 1
with nav5:
    if st.button("Last", use_container_width=True):
        st.session_state.step_idx = total - 1

idx = st.session_state.step_idx
ev  = trace_df.iloc[idx]
ok  = ev.get("status") == "success"

with nav3:
    st.markdown(f"""
    <div style="text-align:center;padding:0.5rem">
        <span class="step-counter">Step <b>{idx+1}</b> of {total}</span>
        &nbsp;
        <span class="badge-node">{str(ev['node_name']).upper()}</span>
        &nbsp;
        <span class="{'badge-success' if ok else 'badge-error'}">{'success' if ok else 'error'}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── Step content ──────────────────────────────────────────────────────────────
col_img, col_brain = st.columns([1, 1])

with col_img:
    st.markdown("#### Screenshot")
    path = ev.get("screenshot")
    if pd.notna(path) and isinstance(path, str) and os.path.exists(path):
        try:
            st.image(path, caption="Page state before the action", use_container_width=True)
        except Exception as e:
            st.error(f"Cannot read image: {e}")
    else:
        st.info("No screenshot for this node (expected for Planner and Validator steps).")

with col_brain:
    st.markdown("#### Agent Reasoning")
    dur = ev.get("duration_ms")
    inp = ev.get("gen_ai_input_tokens")
    out = ev.get("gen_ai_output_tokens")

    m1, m2, m3 = st.columns(3)
    m1.metric("Duration",      f"{int(dur)} ms"  if pd.notna(dur) else "—")
    m2.metric("Input Tokens",  f"{int(inp):,}"    if pd.notna(inp) else "—")
    m3.metric("Output Tokens", f"{int(out):,}"    if pd.notna(out) else "—")

    payload_str = ev.get("payload")
    if pd.notna(payload_str) and str(payload_str).strip() and str(payload_str) != "{}":
        try:
            st.json(json.loads(payload_str))
        except Exception:
            st.text(payload_str)
    else:
        st.info("No reasoning payload for this step.")
