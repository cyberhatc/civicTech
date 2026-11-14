export type Lang = "hi" | "bho" | "awd" | "hinglish";

export interface Citation {
  schemeId: string;
  schemeName: string;
  shortName: string;
  sectionId: string;
  title: string;
  titleHi: string;
  quote: string;
  quoteHi: string;
  source: string;
  page: number;
  icon: string;
  citation: string;
}

export interface CardField {
  label: string;
  value: string;
}

export interface CardAction {
  label: string;
  action: string;
  payload: string;
}

export interface TimelineEvent {
  date: string;
  label: string;
  label_hi?: string;
  status: string;
}

export interface ResponseCard {
  type: string;
  id?: string;
  icon: string;
  title: string;
  subtitle?: string;
  body?: string;
  category?: string;
  amount?: string;
  status?: string;
  ticketId?: string;
  fields?: CardField[];
  actions?: CardAction[];
  timeline?: TimelineEvent[];
}

export interface Ticket {
  id: string;
  citizen_name: string | null;
  contact: string | null;
  category: string;
  category_hi: string | null;
  categoryLabel?: string;
  icon?: string;
  issue: string | null;
  district: string | null;
  block: string | null;
  village: string | null;
  duration_days: number;
  urgency: string;
  sentiment: string;
  status: string;
  priority: string;
  assigned_to: string | null;
  summary: string | null;
  summary_en: string | null;
  transcript: string | null;
  language: string;
  channel: string;
  created_at: string;
  updated_at: string | null;
  notes?: { note: string; author: string; created_at: string }[];
}

export interface Intent {
  name: string;
  confidence: number;
  language: string;
  entities: Record<string, unknown>;
  source: string;
}

export interface TurnResult {
  sessionId: string;
  transcript: { text: string; lang: string; confidence: number; provider: string; error?: string | null };
  intent: Intent;
  reply: { text: string; lang: string; speech: string; audioUrl?: string | null; speechError?: string };
  answerEn?: string;
  cards: ResponseCard[];
  citations: Citation[];
  tickets: Ticket[];
  quickReplies: string[];
  awaiting?: string | null;
}

export interface Health {
  status: string;
  service: string;
  version: string;
  mode: "live" | "mock";
  llm: { provider: string; model: string; available: boolean; lastError?: string | null };
  asr: { provider: string; model: string; available: boolean; lastError?: string | null };
  tts: {
    provider: string;
    edgeTtsAvailable: boolean;
    bhashiniAvailable: boolean;
    voices: number;
    defaultVoice: string;
    lastError?: string | null;
  };
  vector: { backend: string; chunks: number; schemes: number };
  database: { engine: string; path: string; seeded: boolean };
  languages: string[];
}

export interface AdminStats {
  totals: {
    tickets: number;
    resolved: number;
    open: number;
    avgResolutionHours: number;
    citizens: number;
  };
  byCategory: { category: string; label: string; count: number }[];
  byDistrict: { district: string; count: number }[];
  byUrgency: { urgency: string; count: number }[];
  byStatus: { status: string; count: number }[];
  bySentiment: { sentiment: string; count: number }[];
  timeline: { date: string; count: number }[];
  schemeInterest: { id: string; label: string; icon: string; count: number; share: number }[];
  generatedAt: string;
}

export interface SchemeSummary {
  id: string;
  name: string;
  nameHi: string;
  shortName: string;
  category: string;
  categoryHi: string;
  authority: string;
  state: string;
  launched: string;
  summary: string;
  summaryHi: string;
  amount: string;
  icon: string;
  tags: string[];
  sectionCount: number;
}
