"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";

interface TraceSummary {
  trace_id: string;
  user_task: string | null;
  start_time: string | null;
  end_time: string | null;
  step_count: number;
  total_duration_ms: number | null;
  total_input_tokens: number | null;
  total_output_tokens: number | null;
}

interface EventStep {
  event_id: number;
  trace_id: string;
  user_task: string | null;
  subgoal_id: string | null;
  step_id: string | null;
  node_name: string;
  phase: string | null;
  status: string;
  timestamp_start: string | null;
  timestamp_end: string | null;
  duration_ms: number | null;
  gen_ai_model: string | null;
  gen_ai_input_tokens: number | null;
  gen_ai_output_tokens: number | null;
  payload: string | null;
  screenshot: string | null;
  screenshot_url: string | null;
}

interface NodeStat {
  node_name: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  avg_duration_ms: number;
  total_duration_ms: number;
  success_rate: number;
}

interface MissionSummary {
  trace_id: string;
  user_task: string;
  steps: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  duration_s: number;
  success_rate: number;
}

interface AnalyticsData {
  kpis: {
    missions_count: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_tokens: number;
    total_duration_s: number;
    success_rate: number;
    total_steps: number;
    bottleneck_node: string;
  };
  node_breakdown: NodeStat[];
  missions_summary: MissionSummary[];
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<"analytics" | "replay">("analytics");
  
  // Traces & Replay State
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [events, setEvents] = useState<EventStep[]>([]);
  const [stepIndex, setStepIndex] = useState<number>(0);
  
  // Analytics State
  const [analyticsScope, setAnalyticsScope] = useState<string>("all");
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  
  // Loading states
  const [loadingTraces, setLoadingTraces] = useState<boolean>(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState<boolean>(true);
  const [loadingEvents, setLoadingEvents] = useState<boolean>(false);

  // Fetch traces list
  const fetchTraces = async () => {
    setLoadingTraces(true);
    try {
      const res = await fetch("http://localhost:8000/api/admin/traces");
      const data: TraceSummary[] = await res.json();
      setTraces(data);
      if (data.length > 0 && !selectedTraceId) {
        setSelectedTraceId(data[0].trace_id);
      }
    } catch (err) {
      console.error("Failed to fetch traces:", err);
    } finally {
      setLoadingTraces(false);
    }
  };

  // Fetch analytics data
  const fetchAnalytics = async (scope: string = "all") => {
    setLoadingAnalytics(true);
    try {
      const url = scope === "all" 
        ? "http://localhost:8000/api/admin/analytics" 
        : `http://localhost:8000/api/admin/analytics?trace_id=${scope}`;
      const res = await fetch(url);
      const data: AnalyticsData = await res.json();
      setAnalytics(data);
    } catch (err) {
      console.error("Failed to fetch analytics:", err);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  // Initial Load
  useEffect(() => {
    fetchTraces();
    fetchAnalytics("all");
  }, []);

  // Fetch events when selected trace changes in Replay tab
  useEffect(() => {
    if (!selectedTraceId) return;

    const fetchEvents = async () => {
      setLoadingEvents(true);
      try {
        const res = await fetch(`http://localhost:8000/api/admin/traces/${selectedTraceId}`);
        const data: EventStep[] = await res.json();
        setEvents(data);
        setStepIndex(0);
      } catch (err) {
        console.error(`Failed to fetch events for ${selectedTraceId}:`, err);
      } finally {
        setLoadingEvents(false);
      }
    };

    fetchEvents();
  }, [selectedTraceId]);

  const handleScopeChange = (scope: string) => {
    setAnalyticsScope(scope);
    fetchAnalytics(scope);
  };

  const jumpToReplay = (traceId: string) => {
    setSelectedTraceId(traceId);
    setActiveTab("replay");
  };

  const currentTrace = traces.find((t) => t.trace_id === selectedTraceId);
  const currentEvent = events[stepIndex];
  const totalSteps = events.length;

  const getNodeBadgeColor = (nodeName: string) => {
    switch (nodeName.toLowerCase()) {
      case "task_director":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "planner":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "actor":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "validator":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "output_guardrail":
        return "bg-rose-50 text-rose-700 border-rose-200";
      default:
        return "bg-gray-50 text-gray-700 border-gray-200";
    }
  };

  const parsedPayload = () => {
    if (!currentEvent?.payload) return null;
    try {
      return JSON.parse(currentEvent.payload);
    } catch {
      return currentEvent.payload;
    }
  };

  // Max values for chart scaling with safe fallbacks
  const nodeBreakdown = analytics?.node_breakdown || [];
  const maxNodeTokens = nodeBreakdown.length > 0 ? Math.max(...nodeBreakdown.map((n) => n.total_tokens || 0), 1) : 1;
  const maxNodeDuration = nodeBreakdown.length > 0 ? Math.max(...nodeBreakdown.map((n) => n.avg_duration_ms || 0), 1) : 1;

  return (
    <div className="min-h-screen bg-[#f9fafb] text-gray-900 font-sans flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 px-6 py-3.5 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 rounded-lg bg-black text-white font-bold flex items-center justify-center text-sm shadow-sm">
            P
          </div>
          <div>
            <h1 className="text-base font-bold text-gray-900 tracking-tight flex items-center gap-2">
              Piloteer Admin Hub
            </h1>
            <p className="text-xs text-gray-500">Agent Performance, Token Analytics & Mission Replay</p>
          </div>
        </div>

        {/* Tab Navigator */}
        <div className="flex items-center bg-gray-100 p-1 rounded-xl border border-gray-200">
          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "analytics"
                ? "bg-white text-black shadow-xs"
                : "text-gray-600 hover:text-black"
            }`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
            Performance & Analytics
          </button>
          <button
            onClick={() => setActiveTab("replay")}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "replay"
                ? "bg-white text-black shadow-xs"
                : "text-gray-600 hover:text-black"
            }`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Mission Replay
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              fetchTraces();
              fetchAnalytics(analyticsScope);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors shadow-2xs"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
            Refresh
          </button>
          <Link
            href="/"
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-black rounded-lg hover:bg-gray-800 transition-colors shadow-2xs"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            Back to Chat
          </Link>
        </div>
      </header>

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* ========================================================================= */}
        {/* TAB 1: PERFORMANCE & ANALYTICS                                            */}
        {/* ========================================================================= */}
        {activeTab === "analytics" && (
          <div className="space-y-6">
            {/* Scope Filter Banner */}
            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center font-bold">
                  📊
                </div>
                <div>
                  <h2 className="text-sm font-bold text-gray-900">Analysis Scope</h2>
                  <p className="text-xs text-gray-500">Filter metrics globally or evaluate a specific mission run</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">Scope:</label>
                <select
                  value={analyticsScope}
                  onChange={(e) => handleScopeChange(e.target.value)}
                  className="text-xs font-semibold bg-gray-50 border border-gray-300 rounded-xl px-3 py-2 outline-none focus:border-black transition-colors min-w-[260px]"
                >
                  <option value="all">🌍 All Missions (Global Aggregate)</option>
                  {(traces || []).map((t) => (
                    <option key={t.trace_id} value={t.trace_id}>
                      {t.trace_id} {t.user_task ? `— "${t.user_task.substring(0, 30)}..."` : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {loadingAnalytics ? (
              <div className="p-12 text-center text-gray-400">Calculating performance analytics...</div>
            ) : !analytics || analytics.kpis.total_steps === 0 ? (
              <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center shadow-xs">
                <p className="text-gray-600 font-medium">No event analytics available yet.</p>
                <p className="text-xs text-gray-400 mt-1">Execute tasks in the chat to see comprehensive performance stats here.</p>
              </div>
            ) : (
              <>
                {/* Global KPI Cards */}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                  <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-xs">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Missions</span>
                    <span className="text-2xl font-bold text-gray-900 mt-1 block">{analytics.kpis.missions_count}</span>
                    <span className="text-[10px] text-gray-400 mt-1 block">Total Tasks</span>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-xs">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Total Tokens</span>
                    <span className="text-2xl font-bold text-gray-900 mt-1 block">{analytics.kpis.total_tokens.toLocaleString()}</span>
                    <span className="text-[10px] text-purple-600 font-medium mt-1 block">
                      In: {analytics.kpis.total_input_tokens.toLocaleString()} | Out: {analytics.kpis.total_output_tokens.toLocaleString()}
                    </span>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-xs">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Total Duration</span>
                    <span className="text-2xl font-bold text-gray-900 mt-1 block">{analytics.kpis.total_duration_s}s</span>
                    <span className="text-[10px] text-gray-400 mt-1 block">Execution Time</span>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-xs">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Success Rate</span>
                    <span className="text-2xl font-bold text-emerald-600 mt-1 block">{analytics.kpis.success_rate}%</span>
                    <span className="text-[10px] text-gray-400 mt-1 block">{analytics.kpis.total_steps} Total Actions</span>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-xs">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Avg Tokens / Step</span>
                    <span className="text-2xl font-bold text-gray-900 mt-1 block">
                      {analytics.kpis.total_steps > 0 
                        ? Math.round(analytics.kpis.total_tokens / analytics.kpis.total_steps).toLocaleString() 
                        : 0}
                    </span>
                    <span className="text-[10px] text-gray-400 mt-1 block">Per LLM Node</span>
                  </div>

                  {/* Bottleneck Highlight Card */}
                  <div className="bg-rose-50/70 border border-rose-200 rounded-2xl p-4 shadow-xs">
                    <span className="text-[11px] font-bold text-rose-700 uppercase tracking-wider block flex items-center gap-1">
                      ⚠️ Bottleneck Node
                    </span>
                    <span className="text-lg font-black text-rose-900 mt-1 block uppercase">
                      {analytics.kpis.bottleneck_node}
                    </span>
                    <span className="text-[10px] text-rose-600 mt-1 block font-medium">Slowest average latency</span>
                  </div>
                </div>

                {/* Visual Comparative Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Chart 1: Token Breakdown per Node */}
                  <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-gray-900">Token Consumption by Node</h3>
                        <p className="text-xs text-gray-500">Input (prompt) vs Output (completion) tokens per agent</p>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] font-medium">
                        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-blue-500 inline-block"></span> Input</span>
                        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-purple-500 inline-block"></span> Output</span>
                      </div>
                    </div>

                    <div className="space-y-3 pt-2">
                      {(analytics?.node_breakdown || []).map((node) => {
                        const inPct = (node.input_tokens / maxNodeTokens) * 100;
                        const outPct = (node.output_tokens / maxNodeTokens) * 100;
                        return (
                          <div key={node.node_name} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-bold text-gray-700 uppercase text-[11px]">{node.node_name}</span>
                              <span className="text-gray-500 font-mono text-[11px]">
                                {node.total_tokens.toLocaleString()} tokens ({Math.round((node.total_tokens / analytics.kpis.total_tokens) * 100)}%)
                              </span>
                            </div>
                            <div className="w-full h-4 bg-gray-100 rounded-full overflow-hidden flex">
                              <div
                                style={{ width: `${inPct}%` }}
                                className="bg-blue-500 h-full transition-all duration-500"
                                title={`Input: ${node.input_tokens.toLocaleString()}`}
                              ></div>
                              <div
                                style={{ width: `${outPct}%` }}
                                className="bg-purple-500 h-full transition-all duration-500"
                                title={`Output: ${node.output_tokens.toLocaleString()}`}
                              ></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Chart 2: Average Execution Time per Node (Latency Bottleneck) */}
                  <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-gray-900">Average Execution Latency by Node</h3>
                        <p className="text-xs text-gray-500">Detecting slowest nodes & latency bottlenecks (ms)</p>
                      </div>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
                        In Milliseconds
                      </span>
                    </div>

                    <div className="space-y-3 pt-2">
                      {(analytics?.node_breakdown || []).map((node) => {
                        const durPct = (node.avg_duration_ms / maxNodeDuration) * 100;
                        const isBottleneck = node.node_name === analytics.kpis.bottleneck_node;
                        return (
                          <div key={node.node_name} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="font-bold text-gray-700 uppercase text-[11px] flex items-center gap-1.5">
                                {node.node_name}
                                {isBottleneck && (
                                  <span className="text-[9px] bg-rose-100 text-rose-700 px-1.5 py-0.2 rounded font-bold">
                                    SLOWEST
                                  </span>
                                )}
                              </span>
                              <span className="text-gray-800 font-mono text-[11px] font-bold">
                                {node.avg_duration_ms.toLocaleString()} ms
                              </span>
                            </div>
                            <div className="w-full h-4 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                style={{ width: `${durPct}%` }}
                                className={`h-full transition-all duration-500 ${
                                  isBottleneck ? "bg-rose-500" : "bg-emerald-500"
                                }`}
                              ></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Node Detailed Breakdown Table */}
                <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs space-y-3">
                  <h3 className="text-sm font-bold text-gray-900">Node Performance Breakdown</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                          <th className="py-2.5 px-3">Agent Node</th>
                          <th className="py-2.5 px-3">Invocations</th>
                          <th className="py-2.5 px-3">Input Tokens</th>
                          <th className="py-2.5 px-3">Output Tokens</th>
                          <th className="py-2.5 px-3">Total Tokens</th>
                          <th className="py-2.5 px-3">Avg Latency (ms)</th>
                          <th className="py-2.5 px-3">Total Latency (s)</th>
                          <th className="py-2.5 px-3">Success Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 font-medium">
                        {(analytics?.node_breakdown || []).map((node) => (
                          <tr key={node.node_name} className="hover:bg-gray-50/80 transition-colors">
                            <td className="py-3 px-3">
                              <span className={`px-2.5 py-1 rounded-lg border font-bold text-[11px] uppercase ${getNodeBadgeColor(node.node_name)}`}>
                                {node.node_name}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-gray-800 font-bold">{node.calls}</td>
                            <td className="py-3 px-3 text-gray-600 font-mono">{node.input_tokens.toLocaleString()}</td>
                            <td className="py-3 px-3 text-gray-600 font-mono">{node.output_tokens.toLocaleString()}</td>
                            <td className="py-3 px-3 text-purple-700 font-bold font-mono">{node.total_tokens.toLocaleString()}</td>
                            <td className="py-3 px-3 text-gray-800 font-mono font-semibold">{node.avg_duration_ms.toLocaleString()} ms</td>
                            <td className="py-3 px-3 text-gray-600 font-mono">{(node.total_duration_ms / 1000).toFixed(1)}s</td>
                            <td className="py-3 px-3">
                              <span className="text-emerald-700 font-bold bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                                {node.success_rate}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Mission Summary Table (When Scope = All) */}
                {analyticsScope === "all" && (analytics?.missions_summary || []).length > 0 && (
                  <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs space-y-3">
                    <h3 className="text-sm font-bold text-gray-900">Per-Mission Execution Summary</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-gray-200 text-gray-400 font-bold uppercase tracking-wider">
                            <th className="py-2.5 px-3">Mission Prompt (User Task)</th>
                            <th className="py-2.5 px-3">Trace ID</th>
                            <th className="py-2.5 px-3">Steps</th>
                            <th className="py-2.5 px-3">Total Tokens</th>
                            <th className="py-2.5 px-3">Duration (s)</th>
                            <th className="py-2.5 px-3">Success Rate</th>
                            <th className="py-2.5 px-3 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 font-medium">
                          {(analytics?.missions_summary || []).map((m) => (
                            <tr key={m.trace_id} className="hover:bg-gray-50/80 transition-colors">
                              <td className="py-3 px-3 font-semibold text-gray-900 max-w-xs truncate" title={m.user_task}>
                                {m.user_task || <span className="text-gray-400 italic">No prompt text</span>}
                              </td>
                              <td className="py-3 px-3 text-gray-500 font-mono text-[11px]">{m.trace_id}</td>
                              <td className="py-3 px-3 font-bold text-gray-800">{m.steps}</td>
                              <td className="py-3 px-3 text-purple-700 font-bold font-mono">{m.total_tokens.toLocaleString()}</td>
                              <td className="py-3 px-3 text-gray-800 font-mono">{m.duration_s}s</td>
                              <td className="py-3 px-3">
                                <span className="text-emerald-700 font-bold bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                                  {m.success_rate}%
                                </span>
                              </td>
                              <td className="py-3 px-3 text-right">
                                <button
                                  onClick={() => jumpToReplay(m.trace_id)}
                                  className="px-2.5 py-1 text-[11px] font-bold text-blue-700 bg-blue-50 border border-blue-200 hover:bg-blue-100 rounded-lg transition-colors"
                                >
                                  Replay 🎬
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: STEP-BY-STEP REPLAY                                                */}
        {/* ========================================================================= */}
        {activeTab === "replay" && (
          <div className="space-y-6">
            {loadingTraces ? (
              <div className="p-12 text-center text-gray-400">Loading mission records...</div>
            ) : traces.length === 0 ? (
              <div className="bg-white border border-gray-200 rounded-2xl p-12 text-center shadow-xs">
                <p className="text-gray-600 font-medium">No mission traces recorded yet.</p>
                <p className="text-xs text-gray-400 mt-1">Execute tasks in the chat to see full replay traces here.</p>
              </div>
            ) : (
              <>
                {/* User Task Banner */}
                <div className="bg-blue-50/70 border border-blue-200/80 rounded-2xl px-5 py-4 flex items-start gap-3 shadow-xs">
                  <span className="px-2 py-0.5 text-[10px] font-bold tracking-wider text-blue-700 bg-blue-100 rounded uppercase shrink-0 mt-0.5">
                    User Task
                  </span>
                  <p className="text-sm font-semibold text-blue-950 leading-relaxed">
                    {currentTrace?.user_task || "No prompt text recorded."}
                  </p>
                </div>

                {/* Mission Selector & Metadata */}
                <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="w-full md:w-80">
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">
                        Select Mission Run
                      </label>
                      <select
                        value={selectedTraceId || ""}
                        onChange={(e) => setSelectedTraceId(e.target.value)}
                        className="w-full text-sm font-medium bg-gray-50 border border-gray-300 rounded-xl px-3 py-2 outline-none focus:border-black transition-colors"
                      >
                        {(traces || []).map((t) => (
                          <option key={t.trace_id} value={t.trace_id}>
                            {t.trace_id}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* KPI chips */}
                    <div className="flex flex-wrap items-center gap-3 text-xs">
                      <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                        <span className="text-gray-400 block font-medium">Total Steps</span>
                        <span className="text-sm font-bold text-gray-800">{currentTrace?.step_count || 0}</span>
                      </div>
                      <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                        <span className="text-gray-400 block font-medium">Total Tokens</span>
                        <span className="text-sm font-bold text-gray-800">
                          {((currentTrace?.total_input_tokens || 0) + (currentTrace?.total_output_tokens || 0)).toLocaleString()}
                        </span>
                      </div>
                      <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                        <span className="text-gray-400 block font-medium">Total Duration</span>
                        <span className="text-sm font-bold text-gray-800">
                          {currentTrace?.total_duration_ms ? `${(currentTrace.total_duration_ms / 1000).toFixed(1)}s` : "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Step Navigation Controller */}
                {loadingEvents ? (
                  <div className="p-8 text-center text-gray-400">Loading step sequence...</div>
                ) : totalSteps === 0 ? (
                  <div className="p-8 text-center text-gray-400">No event steps in this mission.</div>
                ) : (
                  <div className="space-y-4">
                    <div className="bg-white border border-gray-200 rounded-2xl p-3 shadow-xs flex flex-wrap items-center justify-between gap-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setStepIndex(0)}
                          disabled={stepIndex === 0}
                          className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                          ⏮ First
                        </button>
                        <button
                          onClick={() => setStepIndex((prev) => Math.max(0, prev - 1))}
                          disabled={stepIndex === 0}
                          className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                          ◀ Prev
                        </button>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold text-gray-600 bg-gray-100 px-3 py-1 rounded-full border border-gray-200">
                          Step {stepIndex + 1} of {totalSteps}
                        </span>
                        {currentEvent && (
                          <>
                            <span className={`text-xs font-bold px-2.5 py-1 rounded-full border uppercase ${getNodeBadgeColor(currentEvent.node_name)}`}>
                              {currentEvent.node_name}
                            </span>
                            <span
                              className={`text-xs font-bold px-2.5 py-1 rounded-full uppercase ${
                                currentEvent.status === "success"
                                  ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                  : "bg-rose-100 text-rose-800 border border-rose-200"
                              }`}
                            >
                              {currentEvent.status}
                            </span>
                          </>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setStepIndex((prev) => Math.min(totalSteps - 1, prev + 1))}
                          disabled={stepIndex === totalSteps - 1}
                          className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                          Next ▶
                        </button>
                        <button
                          onClick={() => setStepIndex(totalSteps - 1)}
                          disabled={stepIndex === totalSteps - 1}
                          className="px-3 py-1.5 text-xs font-semibold bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
                        >
                          Last ⏭
                        </button>
                      </div>
                    </div>

                    {/* Dual-Panel View: Visual Screenshot & Agent Mind */}
                    {currentEvent && (
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        {/* Left: Browser Screenshot Card */}
                        <div className="lg:col-span-6 bg-white border border-gray-200 rounded-2xl p-5 shadow-xs flex flex-col">
                          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 flex items-center justify-between">
                            <span>Browser Screenshot (What Agent Saw)</span>
                            {currentEvent.screenshot_url && (
                              <a
                                href={currentEvent.screenshot_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline text-[11px] normal-case"
                              >
                                Open Full Image ↗
                              </a>
                            )}
                          </h3>

                          <div className="flex-1 bg-gray-100 border border-gray-200 rounded-xl overflow-hidden flex items-center justify-center min-h-[380px]">
                            {currentEvent.screenshot_url ? (
                              <img
                                src={currentEvent.screenshot_url}
                                alt="Browser page state before action"
                                className="w-full h-auto object-contain max-h-[550px]"
                              />
                            ) : (
                              <div className="text-center p-6 text-gray-400">
                                <svg className="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                                <p className="text-xs font-medium">No screenshot for this node</p>
                                <p className="text-[11px] text-gray-400 mt-0.5">(Screenshots are captured automatically before Actor actions)</p>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Right: Agent Reasoning & Metrics */}
                        <div className="lg:col-span-6 bg-white border border-gray-200 rounded-2xl p-5 shadow-xs flex flex-col space-y-4">
                          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                            Agent Reasoning & Step Metrics
                          </h3>

                          {/* Step Metric Chips */}
                          <div className="grid grid-cols-3 gap-3">
                            <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                              <span className="text-[11px] font-medium text-gray-400 block">Duration</span>
                              <span className="text-sm font-bold text-gray-800">
                                {currentEvent.duration_ms !== null ? `${currentEvent.duration_ms} ms` : "—"}
                              </span>
                            </div>
                            <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                              <span className="text-[11px] font-medium text-gray-400 block">Input Tokens</span>
                              <span className="text-sm font-bold text-gray-800">
                                {currentEvent.gen_ai_input_tokens !== null ? currentEvent.gen_ai_input_tokens.toLocaleString() : "—"}
                              </span>
                            </div>
                            <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                              <span className="text-[11px] font-medium text-gray-400 block">Output Tokens</span>
                              <span className="text-sm font-bold text-gray-800">
                                {currentEvent.gen_ai_output_tokens !== null ? currentEvent.gen_ai_output_tokens.toLocaleString() : "—"}
                              </span>
                            </div>
                          </div>

                          {/* Step ID & Phase */}
                          <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-50 px-3 py-2 rounded-xl border border-gray-200">
                            <span className="font-semibold text-gray-700">Step ID:</span>
                            <code className="text-gray-600 font-mono text-[11px]">{currentEvent.step_id || "N/A"}</code>
                            {currentEvent.phase && (
                              <>
                                <span className="text-gray-300">•</span>
                                <span className="font-semibold text-gray-700">Phase:</span>
                                <span className="text-gray-600">{currentEvent.phase}</span>
                              </>
                            )}
                          </div>

                          {/* JSON Payload Inspector */}
                          <div className="flex-1 flex flex-col">
                            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1.5">
                              Node Payload (Reasoning / Action Plan)
                            </span>
                            <div className="flex-1 bg-gray-900 text-gray-100 rounded-xl p-4 font-mono text-xs overflow-auto max-h-[380px] shadow-inner">
                              {parsedPayload() ? (
                                <pre className="whitespace-pre-wrap leading-relaxed">
                                  {JSON.stringify(parsedPayload(), null, 2)}
                                </pre>
                              ) : (
                                <p className="text-gray-500 italic">No structured payload recorded for this step.</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
