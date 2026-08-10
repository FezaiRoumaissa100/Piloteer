import streamlit as st
import sqlite3
import pandas as pd
import json
import pathlib
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
SRC_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DB_PATH = SRC_DIR / "loggings" / "database" / "piloteer_logs.db"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Admin Dash")

st.markdown("""
<style>
    [data-testid="stAppViewContainer"]  { background: #f8f9fa; }
    [data-testid="stHeader"]            { background: #f8f9fa; }
    [data-testid="stSidebar"]           { background: #ffffff; }
    .block-container                    { padding-top: 2rem; }

    .main-title { font-size:2rem; font-weight:800; color:#1f2937; margin-bottom:0; }
    .sub-title  { font-size:0.95rem; color:#6b7280; margin-top:0.2rem; margin-bottom:1.5rem; }

    .divider    { border:none; border-top:1px solid #e5e7eb; margin:1.5rem 0; }

    .badge-success { background:#d1fae5; color:#065f46; border-radius:4px; padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .badge-error   { background:#fee2e2; color:#991b1b; border-radius:4px; padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .badge-node    { background:#ede9fe; color:#5b21b6; border-radius:4px; padding:2px 8px; font-size:0.8rem; font-weight:600; }
    .step-counter  { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; padding:0.5rem 1.2rem; color:#374151; font-size:0.9rem; display:inline-block; }

    div[data-testid="metric-container"] { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; padding:1rem; }
    div[data-testid="metric-container"] label { color:#6b7280 !important; font-size:0.8rem !important; }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#1f2937 !important; font-size:1.6rem !important; font-weight:700 !important; }

    .stTabs [data-baseweb="tab-list"]  { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; padding:4px; gap:4px; }
    .stTabs [data-baseweb="tab"]       { border-radius:6px; color:#6b7280; font-weight:600; padding:0.5rem 1.5rem; }
    .stTabs [aria-selected="true"]     { background:#1f2937 !important; color:#ffffff !important; }

    .stButton button                   { border-radius:6px; font-weight:600; border:1px solid #d1d5db; background:#ffffff; color:#374151; }
    .stButton button:hover             { background:#f3f4f6; border-color:#9ca3af; }

    .stDataFrame                       { border:1px solid #e5e7eb; border-radius:8px; }

    h3, h4                             { color:#1f2937; }
    p, li                              { color:#374151; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Piloteer Administration</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Administration dashboard and performance analytics for your Autonomous Agent</div>', unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def load_all_events():
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM events ORDER BY event_id ASC", conn)
    conn.close()
    return df

events_df = load_all_events()

if events_df.empty:
    st.error(f"Database not found or empty: {DB_PATH}")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["Session Replay", "Metrics & Performance"])

with tab1:
    col_sel, col_info = st.columns([2, 1])

    with col_sel:
        traces = events_df['trace_id'].unique().tolist()
        selected_trace = st.selectbox("Select a mission", traces)

    trace_events = events_df[events_df['trace_id'] == selected_trace].reset_index(drop=True)
    total_steps = len(trace_events)

    with col_info:
        st.metric("Steps in this mission", total_steps)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Navigation buttons ────────────────────────────────────────────────────
    if "step_index" not in st.session_state or st.session_state.get("last_trace") != selected_trace:
        st.session_state.step_index = 0
        st.session_state.last_trace = selected_trace

    nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 2, 1, 1])

    with nav1:
        if st.button("First", use_container_width=True):
            st.session_state.step_index = 0
    with nav2:
        if st.button("Previous", use_container_width=True):
            if st.session_state.step_index > 0:
                st.session_state.step_index -= 1
    with nav4:
        if st.button("Next", use_container_width=True):
            if st.session_state.step_index < total_steps - 1:
                st.session_state.step_index += 1
    with nav5:
        if st.button("Last", use_container_width=True):
            st.session_state.step_index = total_steps - 1

    step_idx = st.session_state.step_index
    current_event = trace_events.iloc[step_idx]
    is_success = current_event.get("status") == "success"
    status_badge = "badge-success" if is_success else "badge-error"
    status_text  = "success" if is_success else "error"

    with nav3:
        st.markdown(f"""
        <div style="text-align:center; padding:0.5rem">
            <span class="step-counter">Step <b>{step_idx + 1}</b> of {total_steps}</span>
            &nbsp;&nbsp;
            <span class="badge-node">{str(current_event['node_name']).upper()}</span>
            &nbsp;
            <span class="{status_badge}">{status_text}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Step content ──────────────────────────────────────────────────────────
    col_img, col_brain = st.columns([1, 1])

    with col_img:
        st.markdown("#### Screenshot")
        screenshot_path = current_event.get('screenshot_before')

        if pd.notna(screenshot_path) and isinstance(screenshot_path, str) and os.path.exists(screenshot_path):
            try:
                st.image(screenshot_path, caption="Page state before the action", use_container_width=True)
            except Exception as e:
                st.error(f"Cannot read image: {e}")
        else:
            st.info("No screenshot available for this node (expected for Planner and Validator steps).")

    with col_brain:
        st.markdown("#### Agent Reasoning")

        dur = current_event.get('duration_ms')
        inp = current_event.get('gen_ai_input_tokens')
        out = current_event.get('gen_ai_output_tokens')

        m1, m2, m3 = st.columns(3)
        m1.metric("Duration",      f"{int(dur)} ms"   if pd.notna(dur) else "—")
        m2.metric("Input Tokens",  f"{int(inp):,}"     if pd.notna(inp) else "—")
        m3.metric("Output Tokens", f"{int(out):,}"     if pd.notna(out) else "—")

        payload_str = current_event.get('payload')
        if pd.notna(payload_str) and str(payload_str).strip() and str(payload_str) != "{}":
            try:
                st.json(json.loads(payload_str))
            except Exception:
                st.text(payload_str)
        else:
            st.info("No reasoning payload for this step.")


# ==============================================================================
#  TAB 2 — METRICS & PERFORMANCE
# ==============================================================================
with tab2:

    # ── Scope selector ────────────────────────────────────────────────────────
    trace_options = ["All missions"] + events_df['trace_id'].unique().tolist()
    selected_metric_trace = st.selectbox("Analyze", trace_options)

    if selected_metric_trace == "All missions":
        df_m = events_df.copy()
        scope_label = "All missions"
    else:
        df_m = events_df[events_df['trace_id'] == selected_metric_trace].copy()
        scope_label = f"Mission: {selected_metric_trace}"

    st.caption(f"Scope: {scope_label}")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Global KPIs ───────────────────────────────────────────────────────────
    st.markdown("### Global Summary")

    n_missions    = df_m['trace_id'].nunique()
    total_in_tok  = int(df_m['gen_ai_input_tokens'].sum(skipna=True))
    total_out_tok = int(df_m['gen_ai_output_tokens'].sum(skipna=True))
    total_dur_s   = round(df_m['duration_ms'].sum(skipna=True) / 1000, 1)
    n_success     = int((df_m['status'] == 'success').sum())
    success_rate  = round(n_success / len(df_m) * 100, 1) if len(df_m) > 0 else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Missions",        n_missions)
    k2.metric("Input Tokens",    f"{total_in_tok:,}")
    k3.metric("Output Tokens",   f"{total_out_tok:,}")
    k4.metric("Total Duration",  f"{total_dur_s} s")
    k5.metric("Successes",       n_success)
    k6.metric("Success Rate",    f"{success_rate} %")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Per-node breakdown ────────────────────────────────────────────────────
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
        "Calls":          "Calls",
        "Input_Tokens":   "Input Tokens",
        "Output_Tokens":  "Output Tokens",
        "Avg_Duration":   "Avg Duration (ms)",
        "Total_Duration": "Total Duration (ms)",
        "Successes":      "Successes",
    })

    st.dataframe(node_df, use_container_width=True, hide_index=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown("### Charts")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Token consumption by Node**")
        chart_tokens = df_m.groupby("node_name")[["gen_ai_input_tokens", "gen_ai_output_tokens"]].sum()
        chart_tokens.columns = ["Input", "Output"]
        st.bar_chart(chart_tokens, use_container_width=True)

    with col_g2:
        st.markdown("**Average execution time by Node (ms)**")
        chart_dur = df_m.groupby("node_name")["duration_ms"].mean().round(0).rename("Avg Duration (ms)")
        st.bar_chart(chart_dur, use_container_width=True)

    # ── Per-mission summary ───────────────────────────────────────────────────
    if selected_metric_trace == "All missions":
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
