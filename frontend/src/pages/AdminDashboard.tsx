import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import type { AdminStats, Ticket } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  electricity: "#f59e0b",
  roads: "#64748b",
  water: "#0ea5e9",
  sanitation: "#22c55e",
  health: "#ef4444",
  education: "#8b5cf6",
  agriculture: "#10b981",
  housing: "#f97316",
  policing: "#3b82f6",
  others: "#94a3b8",
};

const STATUS_TONE: Record<string, string> = {
  NEW: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  IN_PROGRESS: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  RESOLVED: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  REJECTED: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
  ESCALATED: "bg-red-500/15 text-red-300 ring-red-500/30",
};

const PRIORITY_TONE: Record<string, string> = {
  P1: "bg-red-500/15 text-red-300 ring-red-500/30",
  P2: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  P3: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
};

function KpiTile({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-night-500 bg-night-700/70 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-extrabold tabular-nums text-white">{value}</p>
      {hint && <p className="mt-1 text-[11px] text-slate-400">{hint}</p>}
      {accent && <div className="mt-3 h-1 rounded-full" style={{ background: accent }} />}
    </div>
  );
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [feed, setFeed] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [filter, setFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await api.adminStats();
      setStats(data.stats);
      setFeed(data.feed);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "डेटा लोड नहीं हुआ।");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  const updateTicket = useCallback(
    async (id: string, patch: Record<string, string>) => {
      try {
        const result = await api.updateTicket(id, patch);
        setStats(result.stats);
        setFeed((prev) => prev.map((ticket) => (ticket.id === id ? result.ticket : ticket)));
        setSelected((prev) => (prev && prev.id === id ? result.ticket : prev));
      } catch (err) {
        setError(err instanceof Error ? err.message : "अपडेट नहीं हुआ।");
      }
    },
    [],
  );

  const visibleFeed = useMemo(
    () => (filter ? feed.filter((ticket) => ticket.status === filter) : feed),
    [feed, filter],
  );

  const categoryData = useMemo(
    () =>
      (stats?.byCategory ?? []).map((row) => ({
        name: row.label,
        count: row.count,
        color: CATEGORY_COLORS[row.category] ?? "#94a3b8",
      })),
    [stats],
  );

  const districtData = useMemo(
    () => (stats?.byDistrict ?? []).slice(0, 8).map((row) => ({ name: row.district, count: row.count })),
    [stats],
  );

  const timelineData = useMemo(
    () =>
      (stats?.timeline ?? []).map((row) => ({
        date: row.date.slice(5),
        count: row.count,
      })),
    [stats],
  );

  const urgencyData = useMemo(
    () =>
      (stats?.byUrgency ?? []).map((row) => ({
        name: row.urgency.toUpperCase(),
        count: row.count,
      })),
    [stats],
  );

  return (
    <div className="min-h-dvh bg-night-900 text-slate-200">
      {/* -------------------------------------------------------------- */}
      <header className="sticky top-0 z-20 border-b border-night-500 bg-night-900/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-3.5">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-700 text-base font-black text-white"
            >
              ज
            </span>
            <div className="leading-tight">
              <p className="text-sm font-extrabold text-white">जनवाणी यूपी · अधिकारी डैशबोर्ड</p>
              <p className="text-[11px] text-slate-400">
                District Magistrate Analytics — live voice grievances
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 text-[11px] text-slate-400 sm:flex">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
              auto-refresh 15s
            </span>
            <Link
              to="/"
              className="rounded-lg border border-night-500 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-night-700"
            >
              नागरिक ऐप ↗
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-5 py-6">
        {error && (
          <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading && !stats ? (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-28 rounded-2xl bg-night-700/60 shimmer" />
            ))}
          </div>
        ) : (
          stats && (
            <>
              {/* KPI row ---------------------------------------------------- */}
              <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <KpiTile
                  label="कुल शिकायतें"
                  value={stats.totals.tickets}
                  hint={`${stats.totals.citizens} नागरिक सेवा में`}
                  accent="#10b981"
                />
                <KpiTile
                  label="खुली (Open)"
                  value={stats.totals.open}
                  hint="कार्यवाही बाकी"
                  accent="#f59e0b"
                />
                <KpiTile
                  label="समाधान"
                  value={stats.totals.resolved}
                  hint={`औसत ${stats.totals.avgResolutionHours} घंटे`}
                  accent="#0ea5e9"
                />
                <KpiTile
                  label="ज्ञात स्कीम"
                  value={stats.schemeInterest.reduce((sum, item) => sum + item.count, 0)}
                  hint="आवेदनों में रुचि"
                  accent="#8b5cf6"
                />
              </section>

              {/* Charts ----------------------------------------------------- */}
              <section className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-2xl border border-night-500 bg-night-700/60 p-4 lg:col-span-2">
                  <h2 className="mb-3 text-sm font-bold text-white">14 दिनों की शिकायतें</h2>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={timelineData}>
                      <defs>
                        <linearGradient id="fillTrend" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10b981" stopOpacity={0.55} />
                          <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis
                        tick={{ fill: "#64748b", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        allowDecimals={false}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#0b1220",
                          border: "1px solid #1e293b",
                          borderRadius: 10,
                          fontSize: 12,
                        }}
                      />
                      <Area type="monotone" dataKey="count" stroke="#10b981" strokeWidth={2} fill="url(#fillTrend)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                <div className="rounded-2xl border border-night-500 bg-night-700/60 p-4">
                  <h2 className="mb-3 text-sm font-bold text-white">विभाग अनुसार</h2>
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={categoryData}
                        dataKey="count"
                        nameKey="name"
                        innerRadius={48}
                        outerRadius={78}
                        paddingAngle={2}
                        stroke="none"
                      >
                        {categoryData.map((entry) => (
                          <Cell key={entry.name} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "#0b1220",
                          border: "1px solid #1e293b",
                          borderRadius: 10,
                          fontSize: 12,
                        }}
                      />
                      <Legend
                        iconType="circle"
                        iconSize={8}
                        wrapperStyle={{ fontSize: 11, color: "#94a3b8" }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-2xl border border-night-500 bg-night-700/60 p-4">
                  <h2 className="mb-3 text-sm font-bold text-white">ज़िला अनुसार</h2>
                  <ResponsiveContainer width="100%" height={230}>
                    <BarChart data={districtData} layout="vertical" margin={{ left: 4, right: 12 }}>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" horizontal={false} />
                      <XAxis
                        type="number"
                        tick={{ fill: "#64748b", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        allowDecimals={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={82}
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(148,163,184,0.08)" }}
                        contentStyle={{
                          background: "#0b1220",
                          border: "1px solid #1e293b",
                          borderRadius: 10,
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="count" fill="#0ea5e9" radius={[0, 6, 6, 0]} barSize={14} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="rounded-2xl border border-night-500 bg-night-700/60 p-4">
                  <h2 className="mb-3 text-sm font-bold text-white">प्राथमिकता</h2>
                  <ResponsiveContainer width="100%" height={230}>
                    <BarChart data={urgencyData}>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: "#94a3b8", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: "#64748b", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        allowDecimals={false}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(148,163,184,0.08)" }}
                        contentStyle={{
                          background: "#0b1220",
                          border: "1px solid #1e293b",
                          borderRadius: 10,
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="count" radius={[6, 6, 0, 0]} barSize={38}>
                        {urgencyData.map((entry) => (
                          <Cell
                            key={entry.name}
                            fill={entry.name === "HIGH" ? "#ef4444" : entry.name === "MEDIUM" ? "#f59e0b" : "#64748b"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="rounded-2xl border border-night-500 bg-night-700/60 p-4">
                  <h2 className="mb-3 text-sm font-bold text-white">योजना रुचि</h2>
                  <ul className="space-y-2.5">
                    {stats.schemeInterest.map((item) => (
                      <li key={item.id} className="flex items-center gap-3">
                        <span aria-hidden="true" className="w-6 text-center">
                          {item.icon}
                        </span>
                        <span className="w-32 shrink-0 truncate text-xs text-slate-300">{item.label}</span>
                        <span className="h-2 flex-1 overflow-hidden rounded-full bg-night-500">
                          <span
                            className="block h-full rounded-full bg-brand-500"
                            style={{ width: `${Math.max(4, item.share * 100)}%` }}
                          />
                        </span>
                        <span className="w-6 shrink-0 text-right text-xs font-semibold tabular-nums text-slate-400">
                          {item.count}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </section>

              {/* Live feed -------------------------------------------------- */}
              <section className="rounded-2xl border border-night-500 bg-night-700/60">
                <header className="flex flex-wrap items-center justify-between gap-3 border-b border-night-500 px-4 py-3">
                  <h2 className="text-sm font-bold text-white">
                    नई आवाज़ से आई शिकायतें{" "}
                    <span className="ml-1 rounded-full bg-night-500 px-2 py-0.5 text-[11px] font-semibold text-slate-300">
                      {visibleFeed.length}
                    </span>
                  </h2>
                  <div className="flex flex-wrap gap-1.5">
                    {["", "NEW", "IN_PROGRESS", "RESOLVED"].map((status) => (
                      <button
                        key={status || "all"}
                        type="button"
                        onClick={() => setFilter(status)}
                        className={`rounded-full px-3 py-1 text-[11px] font-semibold transition-colors ${
                          filter === status
                            ? "bg-brand-600 text-white"
                            : "bg-night-600 text-slate-300 hover:bg-night-500"
                        }`}
                      >
                        {status === "" ? "सभी" : status.replace("_", " ")}
                      </button>
                    ))}
                  </div>
                </header>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-night-500 text-[11px] uppercase tracking-wider text-slate-500">
                        <th className="px-4 py-2.5 font-semibold">शिकायत</th>
                        <th className="px-4 py-2.5 font-semibold">विभाग</th>
                        <th className="px-4 py-2.5 font-semibold">स्थान</th>
                        <th className="px-4 py-2.5 font-semibold">प्राथमिकता</th>
                        <th className="px-4 py-2.5 font-semibold">स्थिति</th>
                        <th className="px-4 py-2.5 font-semibold">समय</th>
                        <th className="px-4 py-2.5 font-semibold">कार्रवाई</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleFeed.map((ticket) => (
                        <tr
                          key={ticket.id}
                          className="cursor-pointer border-b border-night-600/70 text-slate-300 transition-colors hover:bg-night-600/40"
                          onClick={() => setSelected(ticket)}
                        >
                          <td className="px-4 py-3">
                            <p className="font-mono text-[11px] text-slate-500">{ticket.id}</p>
                            <p className="line-clamp-2 max-w-md text-[13px] leading-snug text-slate-200">
                              {ticket.summary || ticket.issue}
                            </p>
                          </td>
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-1.5 text-xs">
                              <span aria-hidden="true">{ticket.icon}</span>
                              {ticket.categoryLabel || ticket.category_hi}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-400">
                            {[ticket.village, ticket.block, ticket.district].filter(Boolean).join(", ") || "—"}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`chip ring-1 ${PRIORITY_TONE[ticket.priority] ?? PRIORITY_TONE.P3}`}
                            >
                              {ticket.priority}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`chip ring-1 ${STATUS_TONE[ticket.status] ?? STATUS_TONE.NEW}`}>
                              {ticket.status.replace("_", " ")}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-[11px] text-slate-500">
                            {ticket.created_at?.slice(0, 16).replace("T", " ")}
                          </td>
                          <td className="px-4 py-3">
                            <button
                              type="button"
                              className="rounded-lg border border-night-500 px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:bg-night-600"
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelected(ticket);
                              }}
                            >
                              देखें
                            </button>
                          </td>
                        </tr>
                      ))}
                      {!visibleFeed.length && (
                        <tr>
                          <td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-500">
                            कोई शिकायत नहीं मिली।
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )
        )}
      </main>

      {/* -------------------------------------------------------------- */}
      {selected && (
        <div
          className="fixed inset-0 z-40 flex justify-end bg-black/60"
          role="dialog"
          aria-modal="true"
          onClick={() => setSelected(null)}
        >
          <div
            className="h-full w-full max-w-lg overflow-y-auto border-l border-night-500 bg-night-800 p-5"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <p className="font-mono text-xs text-slate-500">{selected.id}</p>
                <h2 className="text-lg font-extrabold text-white">
                  {selected.icon} {selected.categoryLabel || selected.category_hi}
                </h2>
                <p className="text-xs text-slate-400">
                  {[selected.village, selected.block, selected.district].filter(Boolean).join(", ") || "स्थान अज्ञात"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                aria-label="बंद करें"
                className="rounded-lg border border-night-500 px-2.5 py-1 text-slate-300 hover:bg-night-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-night-500 bg-night-700/60 p-4">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  आधार सारांश
                </p>
                <p className="text-sm leading-relaxed text-slate-200">{selected.summary}</p>
                {selected.summary_en && (
                  <p className="mt-2 text-xs leading-relaxed text-slate-400">{selected.summary_en}</p>
                )}
              </div>

              <div className="rounded-xl border border-night-500 bg-night-700/60 p-4">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  नागरिक का वक्तव्य
                </p>
                <p className="text-sm italic leading-relaxed text-slate-300">
                  “{selected.transcript || "—"}”
                </p>
                <p className="mt-2 text-[11px] text-slate-500">
                  भाषा: {selected.language} • अवधि: {selected.duration_days} दिन • माध्यम: {selected.channel}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs font-semibold text-slate-400">
                  स्थिति
                  <select
                    value={selected.status}
                    onChange={(event) => void updateTicket(selected.id, { status: event.target.value })}
                    className="mt-1 w-full rounded-lg border border-night-500 bg-night-700 px-3 py-2 text-sm text-slate-200 outline-none focus:border-brand-500"
                  >
                    {["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED", "ESCALATED"].map((status) => (
                      <option key={status} value={status}>
                        {status.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs font-semibold text-slate-400">
                  प्राथमिकता
                  <select
                    value={selected.priority}
                    onChange={(event) => void updateTicket(selected.id, { priority: event.target.value })}
                    className="mt-1 w-full rounded-lg border border-night-500 bg-night-700 px-3 py-2 text-sm text-slate-200 outline-none focus:border-brand-500"
                  >
                    {["P1", "P2", "P3"].map((priority) => (
                      <option key={priority} value={priority}>
                        {priority}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  कार्यवाही नोट
                </p>
                <NoteBox ticketId={selected.id} onAdd={load} />
              </div>

              {selected.notes && selected.notes.length > 0 && (
                <ul className="space-y-2">
                  {selected.notes.map((note, index) => (
                    <li key={index} className="rounded-lg border border-night-500 bg-night-700/40 px-3 py-2">
                      <p className="text-xs text-slate-300">{note.note}</p>
                      <p className="mt-1 text-[10px] text-slate-500">
                        {note.author} • {note.created_at?.slice(0, 16).replace("T", " ")}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NoteBox({ ticketId, onAdd }: { ticketId: string; onAdd: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!note.trim()) return;
    setBusy(true);
    try {
      await api.updateTicket(ticketId, { note: note.trim(), author: "DM Office" });
      setNote("");
      onAdd();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex gap-2">
      <input
        value={note}
        onChange={(event) => setNote(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") void submit();
        }}
        placeholder="कार्रवाई का विवरण लिखिए…"
        className="min-w-0 flex-1 rounded-lg border border-night-500 bg-night-700 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-brand-500"
      />
      <button
        type="button"
        onClick={() => void submit()}
        disabled={busy || !note.trim()}
        className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        जोड़ें
      </button>
    </div>
  );
}
