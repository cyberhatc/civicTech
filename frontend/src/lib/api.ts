import type { AdminStats, Citation, Health, ResponseCard, SchemeSummary, Ticket, TurnResult } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

interface Envelope<T> {
  ok: boolean;
  data: T;
  meta: { mode?: string; latencyMs?: number };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body?.detail ?? body?.error?.message ?? detail;
    } catch {
      /* keep the default message */
    }
    throw new Error(detail);
  }
  const body = (await response.json()) as Envelope<T>;
  return body.data;
}

export const api = {
  health: () => request<Health>("/api/health"),

  /** Voice turn. Either `blob` (recorded audio) or `text` must be provided. */
  async voiceTurn(params: {
    blob?: Blob | null;
    text?: string;
    sessionId?: string | null;
    lang?: string;
    channel?: string;
  }): Promise<TurnResult> {
    const form = new FormData();
    if (params.blob) {
      form.append("audio", params.blob, "recording.webm");
    }
    if (params.text) form.append("text", params.text);
    if (params.sessionId) form.append("sessionId", params.sessionId);
    if (params.lang) form.append("lang", params.lang);
    form.append("channel", params.channel ?? "voice");

    const response = await fetch(`${BASE}/api/voice/turn`, { method: "POST", body: form });
    if (!response.ok) throw new Error(`voice turn failed: ${response.status}`);
    const body = (await response.json()) as Envelope<TurnResult>;
    return body.data;
  },

  chat: (payload: { text: string; sessionId?: string | null; lang?: string; speak?: boolean }) =>
    request<TurnResult>("/api/chat/text", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  schemes: () => request<{ schemes: SchemeSummary[]; cards: ResponseCard[] }>("/api/schemes"),

  scheme: (id: string) => request<{ scheme: Record<string, unknown>; card: ResponseCard }>(`/api/schemes/${id}`),

  searchSchemes: (query: string) =>
    request<{ answer: string; answerEn: string; citations: Citation[]; schemes: unknown[] }>(
      "/api/schemes/search",
      { method: "POST", body: JSON.stringify({ query }) },
    ),

  tickets: (params: Record<string, string> = {}) => {
    const search = new URLSearchParams(
      Object.entries(params).filter(([, v]) => Boolean(v)) as [string, string][],
    ).toString();
    return request<{ tickets: Ticket[]; counts: Record<string, number>; total: number }>(
      `/api/tickets${search ? `?${search}` : ""}`,
    );
  },

  updateTicket: (id: string, payload: Record<string, string>) =>
    request<{ ticket: Ticket; stats: AdminStats }>(`/api/tickets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  adminStats: () => request<{ stats: AdminStats; feed: Ticket[] }>("/api/admin/stats"),

  lookup: (params: { aadhaarLast4?: string; mobile?: string; schemeId?: string }) => {
    const search = new URLSearchParams(
      Object.entries(params).filter(([, v]) => Boolean(v)) as [string, string][],
    ).toString();
    return request<{ found: boolean; message: string; applications: Record<string, unknown>[] }>(
      `/api/applications/lookup?${search}`,
    );
  },
};

export function audioUrl(path?: string | null): string | null {
  if (!path) return null;
  return path.startsWith("http") ? path : `${BASE}${path}`;
}
