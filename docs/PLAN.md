# Build Plan — JanVaani UP (जनवाणी यूपी)

> Voice-first, dialect-aware AI citizen assistant for Uttar Pradesh.
> Target: AI Kaushal Hackathon 2026 (InMobi × Govt. of UP × IIIT Lucknow)

---

## 0. Constraints discovered in this environment

| Check | Result | Consequence |
|---|---|---|
| `python` on PATH | ❌ Windows Store stub | Use `py` launcher (3.12.10) — `py -m venv`, `py -m pip` |
| `pip` on PATH | ❌ | Always invoke via `py -m pip` inside the venv |
| Node / npm | ✅ 24.9.0 / 11.6.0 | Frontend toolchain fine |
| `gh` CLI | ✅ 2.103.3, authed as `cyberhatc`, scopes `repo`,`read:org`,`gist` | Can create + push repo |
| Groq key | ✅ provided by user | Primary LLM **and** Whisper ASR host |
| Network to npm / pypi | ✅ | Normal installs work |

**Hard rule:** the demo must never die because a key is missing, a network call fails, or
`edge-tts` is unreachable. Every AI call has a deterministic offline twin.

---

## 1. Repository layout

```
civicTech/
├── README.md
├── LICENSE                     MIT
├── .gitignore
├── .env.example
├── docs/
│   ├── project_blueprint_janvaani_up.md   (original blueprint, untouched)
│   ├── PLAN.md                             (this file)
│   ├── PITCH.md                           (5-slide pitch + live demo script)
│   └── ARCHITECTURE.md
├── backend/                   FastAPI service
│   ├── app/
│   │   ├── main.py                    app factory, CORS, router wiring
│   │   ├── config.py                  pydantic-settings, env parsing
│   │   ├── core/
│   │   │   ├── guardrails.py          Aadhaar/phone masking, refusal rules
│   │   │   ├── logging_conf.py        redacting logger
│   │   │   └── response.py            uniform envelope + error codes
│   │   ├── db/
│   │   │   ├── database.py            sqlite3 connection, migrations
│   │   │   ├── models.py              dataclass-ish row mappers
│   │   │   └── seed.py                idempotent seeding
│   │   ├── data/
│   │   │   ├── schemes.json           8 official-style scheme docs
│   │   │   ├── citizens.json          12 UP citizen profiles
│   │   │   └── synonyms.json          dialect lexicon (bho/awd/hin/hinglish)
│   │   ├── services/
│   │   │   ├── llm.py                 Groq chat + tool-calling + mock twin
│   │   │   ├── stt.py                 Groq Whisper + mock twin
│   │   │   ├── tts.py                 edge-tts + Bhashini + browser fallback
│   │   │   ├── nlu.py                 dialect intent + entity extraction
│   │   │   ├── rag.py                 hybrid BM25 + char-ngram vector retriever
│   │   │   ├── chroma_adapter.py      drop-in ChromaDB backend (optional)
│   │   │   ├── schemes.py             scheme QA over RAG (grounded)
│   │   │   ├── grievances.py          ticket lifecycle
│   │   │   ├── status.py              application lookup
│   │   │   └── analytics.py           DM dashboard aggregations
│   │   └── routers/
│   │       ├── health.py  voice.py  chat.py  schemes.py
│   │       ├── grievances.py  applications.py  admin.py  whatsapp.py
│   ├── tests/                         pytest suite
│   └── requirements.txt
├── frontend/                Vite + React + TS + Tailwind v4 PWA
│   ├── public/            manifest.webmanifest, sw.js, icons
│   └── src/
│       ├── pages/         CitizenApp, AdminDashboard, SchemeDetail
│       ├── components/    MicButton, Waveform, ReplyCard, TicketCard, ...
│       ├── lib/           api.ts, audio.ts, speech.ts (browser TTS fallback)
│       └── styles/
└── scripts/
    ├── setup.ps1          create venv, install deps, install npm deps, seed
    ├── dev.ps1            run backend + frontend together
    └── smoke.ps1          end-to-end smoke test against a running server
```

---

## 2. Backend design

### 2.1 Configuration (`config.py`)
`pydantic-settings` reads `.env`; every AI key is optional.

| Var | Default | Meaning |
|---|---|---|
| `GROQ_API_KEY` | – | Enables Groq LLM + Whisper ASR |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Chat model (swap to `llama-3.3-70b-versatile`) |
| `GROQ_STT_MODEL` | `whisper-large-v3` | ASR model |
| `BHASHINI_API_KEY` | – | Optional Bhashini ASR/TTS for native dialect audio |
| `TTS_PROVIDER` | `auto` | `auto` → edge-tts → bhashini → browser |
| `VECTOR_BACKEND` | `local` | `local` (BM25+ngram) or `chroma` |
| `AUDIO_OUT_DIR` | `./.runtime/audio` | Generated mp3 cache |
| `DB_PATH` | `./.runtime/janvaani.db` | SQLite file |

### 2.2 AI service layer — every service has a twin

| Service | Primary | Offline twin | Quality of twin |
|---|---|---|---|
| `llm.py` | Groq `/chat/completions` with JSON-schema tool calls | `MockLLM` | Template + slot-fill engine that produces the *same JSON shape* |
| `stt.py` | Groq Whisper multipart upload | `MockSTT` | Returns a scripted transcript when given `?demo=` hint; audio w/o key → empty transcript + `asr_unavailable` |
| `tts.py` | `edge-tts` (`hi-IN-SwaraNeural`, `hi-IN-MadhurNeural`) → mp3 | No audio | Frontend falls back to Web Speech API so the demo still speaks |
| `rag.py` | Hybrid BM25 + char-3/4-gram cosine over scheme docs | same | Same code path — retrieval never needs a network |

Mock vs. live is surfaced by `GET /api/health` and shown as a badge in the UI, so a judge
always knows which mode is running.

### 2.3 Dialect NLU (`nlu.py`)

Two-stage:
1. **Lexicon pass** — `synonyms.json` maps dialect tokens → canonical intent + entity
   (e.g. `jala pada` → `electricity`, `bigha` → `land_holding`, `khata` → `land_record`,
   `mahtari` → `mother`, `gaon` → `village`).
   Detects language: `bho` / `awd` / `hin` / `hinglish`.
2. **LLM pass** — Groq tool call `extract_intent` with a strict enum; result is merged over
   the lexicon result. When Groq is absent, the lexicon result *is* the result.

Intents: `greeting` · `scheme_list` · `scheme_eligibility` · `scheme_documents` ·
`grievance_file` · `status_track` · `contact_human` · `help` · `unknown`.

### 2.4 RAG (`rag.py`)

- Corpus: 8 scheme documents, each split into `section` chunks carrying
  `{schemeId, title, section, eligibility[], documents[], amount, source, page}`.
- Retrieval = **hybrid**: BM25 lexical score ⊕ character n-gram cosine (catches
  Bhojpuri spelling variants like *zameen/ज़मीन*, *bijli/बिजली*).
- Answer generation is **grounded**: the LLM receives only retrieved chunks and must
  quote `section` ids; any claim not present in a chunk is dropped by a post-check.
  This is the "no hallucinated payouts" guardrail from the blueprint.
- `chroma_adapter.py` implements the same `VectorStore` interface so switching is a
  one-line env change.

### 2.5 Grievance flow (`grievances.py`)

1. NLU extracts `{category, issue, duration_days, urgency_hint, sentiment_hint}`.
2. Slot filler asks conversationally for missing `district`, `block`, `village`, `contact`.
3. On completion → ticket `JVUP-YYYY-NNNN`, formal Hindi/English summary generated by
   the LLM (grounded in the extracted fields), inserted into SQLite, surfaced on the
   admin dashboard.
4. Categories: electricity · roads · water · sanitation · health · education ·
   agriculture · housing · policing · others. Urgency derived from keyword heat
   (`jala`, `band`, `mar gaya`, `chaiyee`) + duration days.

### 2.6 Status tracker (`status.py`)

Lookup by **Aadhaar last 4 digits** or **registered mobile** → seeded applications
(PM-KISAN installments, ration card, PM Awas, pension, KCC) with timeline events.
Responses always mask Aadhaar (`XXXX-XXXX-1234`).

### 2.7 Admin / DM analytics (`analytics.py`)

Aggregations for the dashboard: totals, by category, by district, by urgency, by status,
14-day timeline, sentiment split, scheme-interest bars, plus a live feed of newest tickets.

### 2.8 API surface (contract frozen before frontend work)

```
GET    /api/health
GET    /api/schemes
GET    /api/schemes/{scheme_id}
POST   /api/schemes/search          {query, lang?, topK?}
POST   /api/voice/turn              multipart: audio?, text?, sessionId?, lang?
POST   /api/chat/text               {text, sessionId?, lang?}
GET    /api/voice/session/{id}
GET    /api/tickets                 ?status=&category=&district=&limit=
GET    /api/tickets/{id}
PATCH  /api/tickets/{id}            {status?, priority?, assignee?, notes?}
GET    /api/admin/stats
GET    /api/applications/lookup     ?aadhaarLast4=&mobile=&schemeId=
POST   /api/whatsapp/webhook        (Twilio/WhatsApp stub)
GET    /api/whatsapp/verify         (hub.challenge echo)
```

All responses use one envelope:
```json
{ "ok": true, "data": {...}, "meta": {"mode":"live|mock","latencyMs": 812} }
```

### 2.9 Guardrails & privacy (`core/guardrails.py`)
- Regex mask for Aadhaar (12-digit, grouped) and phone numbers in **all** logs & LLM context.
- System prompt forbids inventing scheme amounts or criteria; the answer is re-checked
  against retrieved chunks before being returned.
- Grievance summaries never echo a raw Aadhaar.

---

## 3. Frontend design

**Two surfaces, one PWA:**

1. **Citizen app (`/`)** — mobile-first, big mic button, zero-typing default.
   - Animated waveform while recording, auto-submit on release.
   - Big reply card with the answer + citation chips (`PM-KISAN §3.1`).
   - Colour-coded category icons for grievance tickets.
   - Persistent "call a human" escape hatch and a text-mode fallback for low bandwidth.
   - Auto-plays TTS; if no server audio, uses browser SpeechSynthesis.
   - Bottom nav: `बोलें` (speak) · `योजनाएँ` (schemes) · `स्थिति` (status) · `शिकायत` (grievance).
2. **Officer / DM dashboard (`/admin`)** — dark, dense, data-dense.
   - KPI tiles, category & district bar charts, urgency donut, 14-day timeline,
     live ticket table with inline status changes, ticket detail drawer.

**Stack:** Vite 6 + React 19 + TypeScript + Tailwind v4 (`@tailwindcss/vite`),
`recharts` for charts, hand-rolled `manifest.webmanifest` + `sw.js` (no extra plugin).
Design language: high-contrast, Devanagari-first type stack, generous touch targets
(≥ 56px), no colour-only meaning (icon + label always paired).

---

## 4. Seed data

- **8 schemes**: PM-KISAN, Kisan Credit Card, PM Awas Yojana (Gramin), Mukhyamantri Kanya
  Sumangala Yojana, Mukhyamantri Pension Yojana, NFSA/Ration Card, Pradhan Mantri
  Fasal Bima Yojana, UP Bhulekh / Khasra checking (read-only).
  Each with realistic eligibility criteria, document lists, and amounts.
- **12 citizens** across 8 UP districts (Barabanki, Varanasi, Lucknow, Gorakhpur,
  Prayagraj, Kanpur, Agra, Mathura) with Aadhaar (masked in seed docs), mobiles,
  land holdings, caste/family info, and applications.
- **Synonym lexicon**: ~250 dialect tokens for bho/awd/hin/hinglish.

---

## 5. Execution order

| # | Step | Output |
|---|---|---|
| 1 | Plan doc, git init, `.gitignore`, `.env.example` | repo skeleton |
| 2 | Backend core: config, guardrails, db, seed data | `backend/app/data/*` |
| 3 | Services: rag, nlu, llm, stt, tts | AI layer + offline twins |
| 4 | Routers + main app | working REST API |
| 5 | pytest suite (rag recall, NLU intents, ticket lifecycle, API smoke) | green tests |
| 6 | Frontend scaffold + Tailwind + PWA shell | runs |
| 7 | Citizen app components & flows | usable PWA |
| 8 | Admin dashboard | DM view |
| 9 | README, PITCH.md, ARCHITECTURE.md, setup/dev scripts | handoff docs |
| 10 | Smoke test end-to-end, then `git commit` + `gh repo create cyberhatc/civicTech --public` + push | live on GitHub |

---

## 6. Definition of Done

- [ ] `scripts/setup.ps1` provisions venv + node deps + seeds the DB on a clean machine.
- [ ] `scripts/dev.ps1` starts both servers; citizen app works at `http://localhost:5173`.
- [ ] With **no** `GROQ_API_KEY`, all three citizen flows still complete end-to-end.
- [ ] With a `GROQ_API_KEY`, the same flows use live LLM + Whisper (badge shows "LIVE").
- [ ] Audio round trip under 3 s on a normal connection (measured, printed by `/api/health`).
- [ ] Every grievance ticket appears on `/admin` within one refresh.
- [ ] Aadhaar/phone never appear unmasked in logs, API payloads, or LLM prompts.
- [ ] `pytest` green; `scripts/smoke.ps1` green.
- [ ] Repo public at `github.com/cyberhatc/civicTech` with a green build/CI check.
