"use client";

/** Design reference: Piloteer Admin Hub — exact white dashboard composition from the supplied screenshot. */
import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  Flag,
  ListTree,
  Play,
  RefreshCw,
  ShieldCheck,
  Target,
  TrendingUp,
} from "lucide-react";

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

type Tone = "green" | "blue" | "amber" | "slate";
function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-[9px] border border-[#e7ebef] bg-white shadow-[0_1px_3px_rgba(16,24,40,.04)] ${className}`}
    >
      {children}
    </section>
  );
}
function IconCircle({
  tone,
  children,
}: {
  tone: Tone;
  children: React.ReactNode;
}) {
  const c = {
    green: "border-[#b9e7d6] bg-[#f0fbf6] text-[#15946a]",
    blue: "border-[#c8dafa] bg-[#f2f6ff] text-[#3d73c8]",
    amber: "border-[#f2dda9] bg-[#fffaf0] text-[#d89a13]",
    slate: "border-[#d9e2ee] bg-[#f7f9fc] text-[#5274a7]",
  };
  return (
    <span
      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${c[tone]}`}
    >
      {children}
    </span>
  );
}
function Kpi({
  label,
  value,
  detail,
  tone,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  detail: string;
  tone: Tone;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-[8px] border border-[#e7ebef] bg-white px-4 py-4">
      <div className="flex items-start gap-3">
        <IconCircle tone={tone}>{icon}</IconCircle>
        <div className="min-w-0">
          <p className="text-[11px] text-[#687385]">{label}</p>
          <p className="mt-1 truncate text-[20px] font-bold tracking-[-.035em] text-[#182237]">
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}
function Status({ status }: { status: string }) {
  const s = status.toLowerCase();
  const attention =
    s.includes("attention") || s.includes("warn") || s.includes("pending");
  const security =
    s.includes("security") || s.includes("fail") || s.includes("error");
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-[5px] border px-2 py-1 text-[10px] font-semibold ${security ? "border-[#f1caca] bg-[#fff5f5] text-[#c74d4d]" : attention ? "border-[#f2dda9] bg-[#fffaf0] text-[#bc8211]" : "border-[#bfe6d8] bg-[#f1fbf6] text-[#14855f]"}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${security ? "bg-[#d85a54]" : attention ? "bg-[#dda31d]" : "bg-[#18a171]"}`}
      />
      {security ? "Security" : attention ? "Attention" : "Success"}
    </span>
  );
}
function SuccessChart({ missions }: { missions: MissionSummary[] }) {
  const values = useMemo(() => {
    const a = missions
      .map((m) => Number(m.success_rate))
      .filter(Number.isFinite);
    return a.length > 1
      ? a.slice(0, 8).reverse()
      : [92, 92.2, 91.8, 92.1, 90.5, 91.1, 90.7, 92.5];
  }, [missions]);
  const pts = values
    .map((v, i) => `${20 + i * 62},${145 - (v - 60) * 2.8}`)
    .join(" ");
  return (
    <div className="relative h-[222px] px-3 pb-8 pt-3">
      <div className="absolute inset-x-10 top-4 bottom-9 flex flex-col justify-between text-[10px] text-[#7b8491]">
        {[100, 90, 80, 70, 60].map((v) => (
          <div key={v} className="relative border-t border-[#eef0f3]">
            <span className="absolute -left-7 -top-2">{v}%</span>
          </div>
        ))}
      </div>
      <svg
        viewBox="0 0 480 170"
        preserveAspectRatio="none"
        className="absolute inset-x-10 top-5 h-[164px] w-[calc(100%-80px)]"
      >
        <polyline
          points={pts}
          fill="none"
          stroke="#2c9c73"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        {values.map((v, i) => (
          <circle
            key={i}
            cx={20 + i * 62}
            cy={145 - (v - 60) * 2.8}
            r="2.5"
            fill="#2c9c73"
          />
        ))}
      </svg>
      <div className="absolute inset-x-10 bottom-1 flex justify-between text-[10px] text-[#7b8491]">
        {[
          "May 15",
          "May 16",
          "May 17",
          "May 18",
          "May 19",
          "May 20",
          "May 21",
        ].map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>
      <div className="absolute bottom-1 left-1/2 flex -translate-x-1/2 items-center gap-2 text-[10px] text-[#667085]">
        <span className="h-[2px] w-5 bg-[#2c9c73]" />
        Success Rate (%)
      </div>
    </div>
  );
}
function TokenChart({ nodes }: { nodes: NodeStat[] }) {
  const list = nodes.slice(0, 4);
  const max = Math.max(...list.map((n) => n.total_tokens), 1);
  return (
    <div className="relative h-[222px] px-7 pb-8 pt-4">
      <div className="absolute bottom-8 left-9 top-5 flex flex-col justify-between text-[10px] text-[#7b8491]">
        <span>{Math.round(max).toLocaleString()}</span>
        <span>{Math.round(max * 0.75).toLocaleString()}</span>
        <span>{Math.round(max * 0.5).toLocaleString()}</span>
        <span>{Math.round(max * 0.25).toLocaleString()}</span>
        <span>0</span>
      </div>
      <div className="absolute bottom-8 left-9 right-5 top-5 border-b border-l border-[#e9edf1]" />
      <div className="absolute bottom-8 left-14 right-5 top-5 flex items-end justify-around gap-3">
        {list.map((n, i) => (
          <div
            key={n.node_name}
            className="flex h-full flex-1 flex-col items-center justify-end gap-1"
          >
            <div className="text-center text-[10px] font-semibold text-[#283246]">
              {n.total_tokens.toLocaleString()}
              <br />
              <span className="font-normal text-[#7b8491]">
                ({Math.round((n.total_tokens / max) * 100)}%)
              </span>
            </div>
            <div
              className={`w-full max-w-[34px] rounded-t-[2px] ${i === 2 ? "bg-[#e2a11a]" : "bg-[#2664c7]"}`}
              style={{
                height: `${Math.max(4, (n.total_tokens / max) * 135)}px`,
              }}
            />
            <span className="max-w-[70px] truncate text-center text-[10px] text-[#697586]">
              {n.node_name.replaceAll("_", " ")}
            </span>
          </div>
        ))}
      </div>
      <span className="absolute bottom-[105px] left-1 rotate-[-90deg] text-[9px] text-[#7b8491]">
        Tokens
      </span>
    </div>
  );
}
function DelayChart({ nodes }: { nodes: NodeStat[] }) {
  const list = nodes.slice(0, 6);
  const values = list
    .map((n) => Number(n.avg_duration_ms) / 1000)
    .filter(Number.isFinite);
  const max = Math.max(...values, 1);
  return (
    <div className="relative h-[222px] px-7 pb-8 pt-4">
      <div className="absolute bottom-8 left-9 top-5 flex flex-col justify-between text-[10px] text-[#7b8491]">
        <span>{max.toFixed(1)}s</span>
        <span>{(max * 0.75).toFixed(1)}s</span>
        <span>{(max * 0.5).toFixed(1)}s</span>
        <span>{(max * 0.25).toFixed(1)}s</span>
        <span>0s</span>
      </div>
      <div className="absolute bottom-8 left-9 right-5 top-5 border-b border-l border-[#e9edf1]" />
      <div className="absolute bottom-8 left-14 right-5 top-5 flex items-end justify-around gap-3">
        {list.map((n, i) => {
          const seconds = Number(n.avg_duration_ms) / 1000;
          return (
            <div
              key={n.node_name}
              className="flex h-full flex-1 flex-col items-center justify-end gap-1"
            >
              <div className="text-center text-[10px] font-semibold text-[#283246]">
                {Number.isFinite(seconds) ? `${seconds.toFixed(1)}s` : "—"}
                <br />
                <span className="font-normal text-[#7b8491]">
                  {Number.isFinite(seconds)
                    ? `(${Math.round((seconds / max) * 100)}%)`
                    : ""}
                </span>
              </div>
              <div
                className={`w-full max-w-[34px] rounded-t-[2px] ${i === 2 ? "bg-[#e2a11a]" : "bg-[#2c9c73]"}`}
                style={{ height: `${Math.max(4, (seconds / max) * 135)}px` }}
              />
              <span className="max-w-[78px] truncate text-center text-[10px] text-[#697586]">
                {n.node_name.replaceAll("_", " ")}
              </span>
            </div>
          );
        })}
      </div>
      <span className="absolute bottom-[105px] left-1 rotate-[-90deg] text-[9px] text-[#7b8491]">
        Delay
      </span>
    </div>
  );
}
function ReplayPreview({
  trace,
  events,
  loading,
  onStepSelect,
}: {
  trace?: TraceSummary;
  events: EventStep[];
  loading: boolean;
  onStepSelect?: (index: number) => void;
}) {
  const list = events.slice(0, 5);
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#edf0f3] px-4 py-3">
        <h2 className="text-[14px] font-bold text-[#182237]">
          Mission Replay Preview
        </h2>
        <Status status="success" />
      </div>
      <div className="px-3 pb-3">
        {loading ? (
          <div className="py-10 text-center text-xs text-[#667085]">
            Loading replay…
          </div>
        ) : list.length === 0 ? (
          <div className="px-4 py-10 text-center text-xs text-[#667085]">
            No recorded steps for this mission.
          </div>
        ) : (
          list.map((step, i) => (
            <React.Fragment key={`${step.node_name}-${i}`}>
              <div className="relative flex gap-2.5">
                <div className="flex w-8 flex-col items-center">
                  <div
                    className={`z-10 flex h-8 w-8 items-center justify-center rounded-full text-white ${i === 3 ? "bg-[#dfa018]" : "bg-[#15946a]"}`}
                  >
                    {i === 0 ? (
                      <Activity className="h-4 w-4" />
                    ) : i === 1 ? (
                      <ListTree className="h-4 w-4" />
                    ) : i === 2 ? (
                      <ShieldCheck className="h-4 w-4" />
                    ) : i === 3 ? (
                      <Play className="h-4 w-4" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                  </div>
                  {i < 4 && (
                    <span className="absolute bottom-[-4px] top-8 w-px border-l-2 border-dashed border-[#51b48b]" />
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onStepSelect?.(i)}
                  className="mb-2 flex min-w-0 flex-1 items-center justify-between rounded-[7px] border border-[#e7ebef] bg-white px-3 py-2.5 text-left hover:bg-[#fbfcfd]"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-bold text-[#273247]">
                      {step.node_name.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 text-[10px] text-[#667085]">
                      Step {i + 1} • {step.phase || "Execution"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-right">
                    <div>
                      <Status status={step.status} />
                      <p className="mt-1 text-[10px] text-[#667085]">
                        {step.gen_ai_input_tokens || step.gen_ai_output_tokens
                          ? `${((step.gen_ai_input_tokens || 0) + (step.gen_ai_output_tokens || 0)).toLocaleString()} tokens`
                          : "— tokens"}
                      </p>
                    </div>
                    <div className="text-[10px] text-[#667085]">
                      {step.duration_ms
                        ? `${(step.duration_ms / 1000).toFixed(1)}s`
                        : "—"}
                      <br />
                      Duration
                    </div>
                    <ChevronDown className="h-4 w-4 text-[#7b8491]" />
                  </div>
                </button>
              </div>
            </React.Fragment>
          ))
        )}
      </div>
      <div className="grid grid-cols-2 border-t border-[#edf0f3] px-4 py-3 text-[11px]">
        <div className="flex items-center gap-2 border-r border-[#e7ebef]">
          <Clock3 className="h-4 w-4 text-[#697586]" />
          Total Duration{" "}
          <b className="ml-auto">
            {trace?.total_duration_ms
              ? `${(trace.total_duration_ms / 1000).toFixed(1)}s`
              : "—"}
          </b>
        </div>
        <div className="flex items-center gap-2 pl-4">
          <Database className="h-4 w-4 text-[#697586]" />
          Total Tokens{" "}
          <b className="ml-auto">
            {trace
              ? (
                  (trace.total_input_tokens || 0) +
                  (trace.total_output_tokens || 0)
                ).toLocaleString()
              : "—"}
          </b>
        </div>
      </div>
    </Card>
  );
}

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<"analytics" | "replay">(
    "analytics",
  );
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [events, setEvents] = useState<EventStep[]>([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [scope, setScope] = useState("all");
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loadingTraces, setLoadingTraces] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const fetchTraces = async () => {
    setLoadingTraces(true);
    try {
      const r = await fetch("http://localhost:8000/api/admin/traces");
      const d: TraceSummary[] = await r.json();
      setTraces(d);
      if (d.length && !selectedTraceId) setSelectedTraceId(d[0].trace_id);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingTraces(false);
    }
  };
  const fetchAnalytics = async (s = "all") => {
    setLoadingAnalytics(true);
    try {
      const u =
        s === "all"
          ? "http://localhost:8000/api/admin/analytics"
          : `http://localhost:8000/api/admin/analytics?trace_id=${s}`;
      const r = await fetch(u);
      setAnalytics(await r.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAnalytics(false);
    }
  };
  useEffect(() => {
    fetchTraces();
    fetchAnalytics();
  }, []);
  useEffect(() => {
    if (!selectedTraceId) return;
    (async () => {
      setLoadingEvents(true);
      try {
        const r = await fetch(
          `http://localhost:8000/api/admin/traces/${selectedTraceId}`,
        );
        setEvents(await r.json());
        setStepIndex(0);
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingEvents(false);
      }
    })();
  }, [selectedTraceId]);
  const trace = traces.find((t) => t.trace_id === selectedTraceId);
  const k = analytics?.kpis;
  const missions = analytics?.missions_summary || [];
  const nodes = analytics?.node_breakdown || [];
  const jump = (id: string) => {
    setSelectedTraceId(id);
    setActiveTab("replay");
  };
  return (
    <div className="min-h-screen bg-[#fbfcfd] font-sans text-[#162238]">
      <header className="border-b border-[#e5e8ec] bg-white">
        <div className="mx-auto flex max-w-[1536px] items-center justify-between gap-6 px-6 py-4 lg:px-8">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-[6px] bg-[#172641] text-[25px] font-bold text-white shadow-[inset_-7px_-7px_0_#1c735f]">
              P
            </div>
            <div>
              <h1 className="text-[22px] font-bold tracking-[-.04em] text-[#172238]">
                Piloteer Admin Hub
              </h1>
              <p className="mt-0.5 text-[12px] text-[#667085]">
                Agent Performance, Token Analytics & Mission Replay
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                fetchTraces();
                fetchAnalytics(scope);
              }}
              className="flex items-center gap-2 rounded-[7px] border border-[#dfe4ea] bg-white px-4 py-2.5 text-[12px] font-semibold text-[#273247] hover:bg-[#f8fafc]"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <Link
              href="/"
              className="flex items-center gap-2 rounded-[7px] bg-[#2763c8] px-4 py-2.5 text-[12px] font-semibold text-white hover:bg-[#1f55ad]"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Chat
            </Link>
          </div>
        </div>
        <div className="mx-auto flex max-w-[1536px] items-end px-6 lg:px-8">
          <button
            onClick={() => setActiveTab("analytics")}
            className={`flex items-center gap-2 border-b-2 px-5 py-3 text-[13px] font-semibold ${activeTab === "analytics" ? "border-[#2763c8] text-[#2763c8]" : "border-transparent text-[#687385]"}`}
          >
            <BarChart3 className="h-4 w-4" />
            Performance & Analytics
          </button>
          <button
            onClick={() => setActiveTab("replay")}
            className={`flex items-center gap-2 border-b-2 px-5 py-3 text-[13px] font-semibold ${activeTab === "replay" ? "border-[#2763c8] text-[#2763c8]" : "border-transparent text-[#687385]"}`}
          >
            <Play className="h-4 w-4" />
            Mission Replay
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-[1536px] space-y-4 px-6 py-4 lg:px-8">
        {activeTab === "analytics" ? (
          <>
            {
              <Card className="flex items-center gap-5 px-4 py-3">
                <span className="text-[12px] font-bold text-[#273247]">
                  Analysis Scope
                </span>
                <div className="relative max-w-[470px] flex-1">
                  <select
                    value={scope}
                    onChange={(e) => {
                      const nextScope = e.target.value;
                      setScope(nextScope);
                      if (nextScope !== "all") setSelectedTraceId(nextScope);
                      fetchAnalytics(nextScope);
                    }}
                    className="w-full appearance-none rounded-[6px] border border-[#dfe4ea] bg-white px-3 py-2.5 pr-9 text-[12px] font-medium text-[#273247]"
                  >
                    <option value="all">All Missions</option>
                    {traces.map((t) => (
                      <option key={t.trace_id} value={t.trace_id}>
                        {t.trace_id} —{" "}
                        {(t.user_task || "Untitled mission").slice(0, 50)}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7f8998]" />
                </div>
                <p
                  className="min-w-0 flex-1 truncate text-[12px] text-[#667085]"
                  title={
                    scope === "all"
                      ? "All Missions"
                      : trace?.user_task || "Selected mission"
                  }
                >
                  <span className="font-semibold text-[#273247]">Mission:</span>{" "}
                  {scope === "all"
                    ? "All Missions"
                    : trace?.user_task || "Selected mission"}
                </p>
              </Card>
            }
            {loadingAnalytics ? (
              <Card className="p-12 text-center text-sm text-[#667085]">
                Calculating performance analytics…
              </Card>
            ) : !k ? (
              <Card className="p-12 text-center text-sm text-[#667085]">
                No analytics available yet.
              </Card>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                  <Kpi
                    label="Missions"
                    value={k.missions_count.toLocaleString()}
                    detail="Recorded missions"
                    tone="green"
                    icon={<Flag className="h-5 w-5" />}
                  />
                  <Kpi
                    label="Total Tokens"
                    value={k.total_tokens.toLocaleString()}
                    detail="Selected scope"
                    tone="blue"
                    icon={<Database className="h-5 w-5" />}
                  />
                  <Kpi
                    label="Total Duration"
                    value={`${Number(k.total_duration_s).toFixed(1)}s`}
                    detail="Recorded duration"
                    tone="amber"
                    icon={<Clock3 className="h-5 w-5" />}
                  />
                  <Kpi
                    label="Success Rate"
                    value={`${k.success_rate}%`}
                    detail="Recorded outcomes"
                    tone="green"
                    icon={<Target className="h-5 w-5" />}
                  />
                  <Kpi
                    label="Avg Tokens / Step"
                    value={
                      k.total_steps
                        ? Math.round(
                            k.total_tokens / k.total_steps,
                          ).toLocaleString()
                        : "0"
                    }
                    detail="Recorded steps"
                    tone="slate"
                    icon={<TrendingUp className="h-5 w-5" />}
                  />
                  <Kpi
                    label="Bottleneck Node"
                    value={k.bottleneck_node.replaceAll("_", " ")}
                    detail="Highest average delay"
                    tone="amber"
                    icon={<CircleAlert className="h-5 w-5" />}
                  />
                </div>
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_1.25fr]">
                  <Card className="overflow-hidden">
                    <div className="flex items-center justify-between border-b border-[#edf0f3] px-4 py-3">
                      <h2 className="text-[14px] font-bold">
                        Token Consumption by Node{" "}
                        <span className="ml-1 text-[11px] font-normal text-[#87909d]">
                          ⓘ
                        </span>
                      </h2>
                    </div>
                    <TokenChart nodes={nodes} />
                  </Card>
                  <Card className="overflow-hidden">
                    <div className="flex items-center justify-between border-b border-[#edf0f3] px-4 py-3">
                      <h2 className="text-[14px] font-bold">Delay by Node</h2>
                    </div>
                    <DelayChart nodes={nodes} />
                  </Card>
                </div>
                <Card className="overflow-hidden">
                  <div className="flex items-center justify-between border-b border-[#edf0f3] px-4 py-3">
                    <h2 className="text-[14px] font-bold">Mission Activity</h2>
                    <button
                      onClick={() => setActiveTab("replay")}
                      className="flex items-center gap-1 text-[12px] font-semibold text-[#273247] hover:text-[#2763c8]"
                    >
                      View All Missions <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[850px] text-left text-[11px]">
                      <thead className="border-b border-[#edf0f3] text-[10px] font-semibold text-[#667085]">
                        <tr>
                          <th className="px-4 py-2.5">Mission</th>
                          <th className="px-3 py-2.5">Status</th>
                          <th className="px-3 py-2.5">Success Rate</th>
                          <th className="px-3 py-2.5">Total Tokens</th>
                          <th className="px-3 py-2.5">Duration</th>
                          <th className="px-3 py-2.5">Started At</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#f0f2f4]">
                        {missions.slice(0, 4).map((m) => (
                          <tr key={m.trace_id} className="hover:bg-[#fbfcfd]">
                            <td className="max-w-[370px] truncate px-4 py-3 font-medium text-[#273247]">
                              {m.user_task || "Untitled mission"}
                            </td>
                            <td className="px-3 py-3">
                              <Status
                                status={
                                  m.success_rate >= 80
                                    ? "success"
                                    : m.success_rate >= 60
                                      ? "attention"
                                      : "security"
                                }
                              />
                            </td>
                            <td className="px-3 py-3">
                              <div className="flex items-center gap-2">
                                <span>{m.success_rate}%</span>
                                <span className="h-1.5 w-24 overflow-hidden rounded-full bg-[#edf0f2]">
                                  <span
                                    className="block h-full rounded-full bg-[#1aa174]"
                                    style={{ width: `${m.success_rate}%` }}
                                  />
                                </span>
                              </div>
                            </td>
                            <td className="px-3 py-3">
                              {m.total_tokens.toLocaleString()}
                            </td>
                            <td className="px-3 py-3">{m.duration_s}s</td>
                            <td className="px-3 py-3 text-[#667085]">
                              {traces.find((t) => t.trace_id === m.trace_id)
                                ?.start_time || "—"}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                onClick={() => jump(m.trace_id)}
                                aria-label={`Open replay for ${m.trace_id}`}
                              >
                                <ChevronRight className="h-4 w-4 text-[#667085]" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            )}
          </>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.1fr_1.4fr]">
              <Card className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-[#edf0f3] px-4 py-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <h2 className="text-[14px] font-bold">Mission Details</h2>
                    <span className="truncate text-[11px] text-[#667085]">
                      {trace?.user_task || "Select a mission"}
                    </span>
                  </div>
                  <div className="relative flex items-center gap-3">
                    <span className="text-[11px] text-[#667085]">
                      {events.length
                        ? `Step ${stepIndex + 1} of ${events.length}`
                        : "No steps"}
                    </span>
                    <select
                      value={selectedTraceId || ""}
                      onChange={(e) => setSelectedTraceId(e.target.value)}
                      className="hidden max-w-[150px] appearance-none rounded-[5px] border border-[#dfe4ea] bg-white px-2 py-1.5 pr-7 text-[10px] font-medium text-[#273247] sm:block"
                    >
                      <option value="">Select mission</option>
                      {traces.map((t) => (
                        <option key={t.trace_id} value={t.trace_id}>
                          {t.trace_id}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {events[stepIndex] ? (
                  <div className="flex min-h-[560px] flex-col">
                    <div className="flex-1 space-y-4 overflow-auto p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-[5px] bg-[#f2f6ff] px-2 py-1 text-[11px] font-semibold text-[#3d73c8]">
                          {events[stepIndex].node_name}
                        </span>
                        <Status status={events[stepIndex].status} />
                        <span className="text-[11px] text-[#667085]">
                          {events[stepIndex].phase || "Execution"}
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-[11px]">
                        <div className="rounded-[6px] bg-[#f8fafc] p-3">
                          <span className="block text-[#667085]">Duration</span>
                          <b>
                            {events[stepIndex].duration_ms !== null
                              ? `${(events[stepIndex].duration_ms / 1000).toFixed(1)}s`
                              : "—"}
                          </b>
                        </div>
                        <div className="rounded-[6px] bg-[#f8fafc] p-3">
                          <span className="block text-[#667085]">
                            Input tokens
                          </span>
                          <b>
                            {events[
                              stepIndex
                            ].gen_ai_input_tokens?.toLocaleString() || "—"}
                          </b>
                        </div>
                        <div className="rounded-[6px] bg-[#f8fafc] p-3">
                          <span className="block text-[#667085]">
                            Output tokens
                          </span>
                          <b>
                            {events[
                              stepIndex
                            ].gen_ai_output_tokens?.toLocaleString() || "—"}
                          </b>
                        </div>
                      </div>
                      <div>
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#667085]">
                          Node output / payload
                        </p>
                        <pre className="min-h-[300px] max-h-[520px] w-full overflow-auto whitespace-pre-wrap break-words rounded-[6px] bg-[#182237] p-4 font-mono text-[11px] leading-5 text-[#dce7f5]">
                          {events[stepIndex].payload ||
                            "No output payload recorded for this step."}
                        </pre>
                      </div>
                    </div>
                    <div className="mt-auto flex justify-between border-t border-[#edf0f3] px-4 py-3">
                      <button
                        disabled={!stepIndex}
                        onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
                        className="rounded-[6px] border border-[#dfe4ea] px-3 py-2 text-[11px] font-semibold disabled:opacity-40"
                      >
                        Previous
                      </button>
                      <button
                        disabled={stepIndex >= events.length - 1}
                        onClick={() =>
                          setStepIndex((i) =>
                            Math.min(events.length - 1, i + 1),
                          )
                        }
                        className="rounded-[6px] bg-[#2763c8] px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-40"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex min-h-[560px] items-center justify-center p-12 text-center text-sm text-[#667085]">
                    Select a mission with recorded steps.
                  </div>
                )}
              </Card>
              <Card className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-[#edf0f3] px-4 py-3">
                  <h2 className="text-[14px] font-bold">Browser State</h2>
                  <span className="text-[11px] text-[#667085]">
                    Step {events.length ? stepIndex + 1 : "—"}
                  </span>
                </div>
                <div className="flex min-h-[560px] items-center justify-center bg-[#f8fafc] p-5">
                  {events[stepIndex]?.screenshot_url ||
                  events[stepIndex]?.screenshot ? (
                    <img
                      src={
                        events[stepIndex].screenshot_url ||
                        events[stepIndex].screenshot ||
                        ""
                      }
                      alt="Browser state for selected step"
                      className="max-h-[650px] w-full rounded-[6px] border border-[#e0e5eb] bg-white object-contain shadow-[0_2px_8px_rgba(16,24,40,.06)]"
                    />
                  ) : (
                    <div className="text-center text-sm text-[#667085]">
                      No screenshot recorded for this step.
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
