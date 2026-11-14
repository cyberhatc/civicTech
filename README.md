# ---------------------------------------------------------------------------
# JanVaani UP (जनवाणी यूपी)
# Voice-first, dialect-aware AI citizen assistant for Uttar Pradesh
#
#   Track   : CivicTech - Multilingual Citizen Services & Governance Voice-Bot
#   Event   : AI Kaushal Hackathon 2026 (InMobi x Govt. of Uttar Pradesh x IIIT Lucknow)
#
#   "आपकी आवाज़, आपकी योजना" - your voice, your scheme.
# ---------------------------------------------------------------------------

<div align="center">

# जनवाणी यूपी · JanVaani UP

**A voice-first, dialect-aware AI citizen assistant for Uttar Pradesh.**

Speak in **Hindi, Bhojpuri or Awadhi** → find out which government scheme you
qualify for, track your application, or lodge a civic grievance by voice — and get a
real tracking number back.

[![tests](https://img.shields.io/badge/tests-62%20passed-10b981)](backend/tests)
[![python](https://img.shields.io/badge/python-3.12-3776ab)](backend/requirements.txt)
[![node](https://img.shields.io/badge/node-20%2B-10b981)](frontend/package.json)
[![license](https://img.shields.io/badge/license-MIT-10b981)](LICENSE)

</div>

---

## Table of contents

- [The problem](#the-problem)
- [What it does](#what-it-does)
- [Live demo screenshots](#live-demo-screenshots)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Ethics, privacy and guardrails](#ethics-privacy-and-guardrails)
- [Roadmap](#roadmap)
- [License](#license)

---

## The problem

Millions of citizens in Uttar Pradesh speak **Bhojpuri, Awadhi and Braj**, not the
formal Hindi found on government portals. Today that means:

1. **A linguistic and literacy barrier** — text-heavy, English-first interfaces
   exclude the people who need the schemes the most.
2. **Portal fragmentation** — PM-KISAN, PM Awas, Ration Card and Jansunwai live in four
   disconnected systems.
3. **Silent failures** — a citizen submits incomplete paperwork, gets rejected, and
   nobody calls them back.

JanVaani UP replaces the portal with a **conversation**.

---

## What it does

### 1 · Dialect-to-action scheme discovery & eligibility (RAG)

> *"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"*
> (I have 2 bigha of land — which government scheme can I get?)

The transcript is normalised to a canonical intent, used to retrieve the relevant
chunks from a vector store built over official UP/Central scheme documents, and the
answer is returned in spoken Hindi with **citations back to the exact section** of the
source document (`PM-KISAN §eligibility · pmkisan.gov.in`). Required documents are
listed too, because incomplete paperwork is the #1 cause of rejection.

### 2 · Conversational grievance redressal (Jansunwai / IGRS simulator)

> *"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."*
> (Our village transformer has been burnt for 4 days, nobody is listening.)

Entities are extracted (`category=electricity`, `duration=4 days`, `urgency=high`), the
missing slots are collected conversationally (district → location → contact), and a
formal Hindi/English grievance summary is generated with a tracking number
(`JVUP-2026-0007`) that appears **immediately on the District Magistrate dashboard**.

### 3 · Mock application status tracker

> *"Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?"*

The assistant asks for the last 4 digits of the Aadhaar or the registered mobile
number, then reads out the status of every application with a timeline.

### 4 · Officer / DM analytics dashboard (bonus)

A dense, dark-themed command view: live feed of incoming voice grievances, KPIs,
category/district/priority breakdowns, a 14-day trend line, scheme-interest bars, and
inline status updates with an action trail.

---

## Live demo screenshots

| Citizen PWA | Officer dashboard |
| --- | --- |
| One big mic button, zero typing, waveform while recording, colour-coded result cards, citation chips, browser-TTS fallback for weak networks | Live grievance feed, KPI tiles, donut + bar charts, ticket drawer with status/priority/notes |

Run it locally (see [Quick start](#quick-start)) and open `http://localhost:5173`
(citizen) and `http://localhost:5173/admin` (officer).

---

## Architecture

```text
  ┌────────────────────────────────────────────────────────────────────────┐
  │  CITIZEN                          │  OFFICER / DM                       │
  │  PWA (React + TS + Tailwind)       │  Dashboard (React + Recharts)      │
  │  · hold-to-talk mic button          │  · live feed · KPIs · charts      │
  │  · text fallback (weak network)     │  · ticket drawer · action notes   │
  │  · Web Speech fallback for TTS      │                                    │
  └───────────────┬────────────────────┴──────────────┬─────────────────────┘
                  │ /api/voice/turn  (multipart webm/opus)                  │
                  │ /api/chat/text   (low-bandwidth fallback)              │
  ┌───────────────▼──────────────────────────────────────▼─────────────────┐
  │  FastAPI  (backend/app)                                                │
  │                                                                        │
  │   routers/  voice · chat · schemes · grievances · applications         │
  │             admin · whatsapp · health                                  │
  │                             │                                          │
  │   services/  nlu.py      dialect intent + entity extraction            │
  │             orchestrator.py  state machine, slot filling, routing      │
  │             rag.py       hybrid BM25 + char-n-gram retriever           │
  │             llm.py      Groq chat  ──► offline deterministic twin      │
  │             stt.py      Groq Whisper ──► offline twin (text mode)      │
  │             tts.py      edge-tts ──► Bhashini ──► browser speech       │
  │             grievances.py · status.py · analytics.py                    │
  │                                                                        │
  │   core/      guardrails.py  Aadhaar/phone masking, grounding checks    │
  │             response.py     one envelope for every endpoint            │
  │                                                                        │
  │   db/        SQLite (WAL) · idempotent seeding · 12 citizens, 17 apps   │
  └───────────────────────────────┬────────────────────────────────────────┘
                                  │
             ┌────────────────────┴────────────────────┐
             │  data/  schemes.json (9 schemes)          │
             │          synonyms.json (dialect lexicon)   │
             │          citizens.json (seed database)     │
             └──────────────────────────────────────────┘
```

**Every AI call has a deterministic twin.** With no API key the assistant still
completes all three flows — it just runs the rule-based engine instead of a model.
`GET /api/health` reports which mode is live, and the UI shows a `LIVE` / `OFFLINE`
badge so a judge always knows what they are looking at.

---

## Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | React 19 + TypeScript + Vite 6 + Tailwind v4 | Fast build, mobile-first PWA, tiny bundle |
| Charts | Recharts | Fast to build the DM dashboard |
| PWA | Hand-rolled `manifest.webmanifest` + `sw.js` | No plugin dependency, full control over caching |
| Backend | FastAPI + Uvicorn (Python 3.12) | Async, typed, `uvicorn[standard]` gives uvloop |
| LLM | **Groq** (`llama-3.1-8b-instant`) | Sub-second latency — critical for a live voice demo |
| ASR | **Groq Whisper `whisper-large-v3`** | Same key, same host, best Hindi/Bhojpuri accuracy |
| TTS | **edge-tts** (`hi-IN-SwaraNeural`, `hi-IN-MadhurNeural`) | Free, natural Hindi, no signup |
| Retrieval | Hybrid BM25 + character n-gram cosine | Zero model downloads, works offline; ChromaDB is a one-line swap |
| Storage | SQLite (stdlib `sqlite3`, WAL) | No native build step, ships with Python |
| Tests | pytest + FastAPI `TestClient` | 62 tests covering retrieval, NLU, guardrails and every endpoint |

---

## Quick start

### Prerequisites

* **Python 3.12+** — on Windows, use the launcher: `py -m venv .venv`
* **Node.js 20+**
* *(optional)* A [Groq API key](https://console.groq.com/keys) for live LLM + Whisper

### 1 · Install

```powershell
git clone https://github.com/cyberhatc/civicTech.git
cd civicTech
.\scripts\setup.ps1
```

`setup.ps1` creates the virtualenv, installs the Python and Node dependencies, seeds
the SQLite database and regenerates the PWA icons. It works on a clean machine with
no manual steps.

<details>
<summary>Manual install</summary>

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend; npm install; cd ..
```

</details>

### 2 · Run

```powershell
.\scripts\dev.ps1
```

* Citizen app → <http://localhost:5173>
* Officer dashboard → <http://localhost:5173/admin>
* API docs → <http://127.0.0.1:8000/docs>

Run the two halves separately if you prefer:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
cd frontend; npm run dev
```

### 3 · Verify

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q   # 62 unit + API tests
.\.venv\Scripts\python.exe scripts\smoke.py               # end-to-end against a live server
```

---

## Configuration

Copy `.env.example` to `.env` at the repo root. **Every value is optional.**

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | – | Enables live LLM + Whisper ASR |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Chat model (try `llama-3.3-70b-versatile`) |
| `GROQ_STT_MODEL` | `whisper-large-v3` | ASR model |
| `BHASHINI_API_KEY` | – | Optional native-dialect ASR/TTS via ULCA |
| `TTS_PROVIDER` | `auto` | `auto` → edge-tts → Bhashini → browser |
| `VECTOR_BACKEND` | `local` | `local` or `chroma` |
| `DB_PATH` | `./.runtime/janvaani.db` | SQLite location |
| `CORS_ORIGINS` | `localhost:5173` | Comma-separated allowed origins |

Without a key the app still works end to end — it runs the offline engine.

---

## API reference

All responses use one envelope: `{ "ok": true, "data": {...}, "meta": { "mode": "live|mock" } }`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Mode + capability report (LLM / ASR / TTS / vector / DB) |
| `POST` | `/api/voice/turn` | `multipart`: `audio` and/or `text` → transcript, intent, reply, audio |
| `POST` | `/api/chat/text` | Text-only turn (low-bandwidth fallback) |
| `GET` | `/api/voice/session/{id}` | Full transcript of a session |
| `GET` | `/api/voice/audio/{file}` | Generated speech mp3 |
| `GET` | `/api/schemes` | Scheme catalogue + visual cards |
| `GET` | `/api/schemes/{id}` | Full scheme document with sections |
| `POST` | `/api/schemes/search` | Grounded Q&A with citations |
| `GET` | `/api/tickets` | Grievance list (filter by status/category/district/urgency) |
| `GET` | `/api/tickets/{id}` | One ticket with its action trail |
| `PATCH` | `/api/tickets/{id}` | Update status / priority / assignee / add a note |
| `GET` | `/api/applications/lookup` | `?aadhaarLast4=` or `?mobile=` (+ optional `schemeId`) |
| `GET` | `/api/admin/stats` | Full dashboard payload |
| `GET` | `/api/admin/feed` | Live grievance feed |
| `POST` | `/api/whatsapp/webhook` | WhatsApp Cloud API stub |
| `GET` | `/api/whatsapp/verify` | Meta verification handshake |

Interactive OpenAPI docs: <http://127.0.0.1:8000/docs>.

---

## Project layout

```text
civicTech/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app factory
│   │   ├── config.py            pydantic-settings, everything optional
│   │   ├── core/
│   │   │   ├── guardrails.py    PII masking, grounding, injection defence
│   │   │   ├── logging_conf.py  redacting logger
│   │   │   └── response.py      response envelope
│   │   ├── db/
│   │   │   ├── database.py      SQLite (WAL) + schema
│   │   │   └── seed.py          idempotent seeding
│   │   ├── data/
│   │   │   ├── schemes.json     9 schemes, 16 citable sections
│   │   │   ├── citizens.json    12 citizens, 17 applications, 6 tickets
│   │   │   └── synonyms.json    dialect lexicon (hi / bho / awd / hinglish)
│   │   ├── services/            nlu · orchestrator · rag · llm · stt · tts
│   │   │                        schemes · grievances · status · analytics
│   │   └── routers/             voice · chat · schemes · grievances
│   │                            applications · admin · whatsapp · health
│   └── tests/                   62 tests
├── frontend/
│   ├── public/                  manifest.webmanifest · sw.js · icons
│   └── src/
│       ├── components/          MicButton · Waveform · ReplyCard · CitationList
│       ├── lib/                 api · audio · speech · types
│       └── pages/               CitizenApp · AdminDashboard · SchemeDetail
├── scripts/
│   ├── setup.ps1  dev.ps1       one-command provisioning and run
│   ├── smoke.py                 end-to-end check against a live server
│   └── make_icons.py            generates the PWA icons (stdlib only)
├── docs/
│   ├── project_blueprint_janvaani_up.md   original blueprint
│   ├── PLAN.md                  build plan
│   ├── ARCHITECTURE.md          deep dive
│   └── PITCH.md                 pitch deck + live demo script
└── .github/workflows/ci.yml     tests + build on every push
```

---

## Testing

```text
backend/tests/
├── test_rag.py         retrieval recall for every dialect phrasing
├── test_nlu.py         intent + entity extraction across 4 languages
├── test_guardrails.py  Aadhaar/phone masking, injection defence, grounding
└── test_api.py         all three citizen flows, the dashboard, the WhatsApp stub
```

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

```
62 passed
```

The smoke test exercises a **live** server end to end — multi-turn grievance
collection, ticket creation, status lookup, dashboard updates:

```powershell
.\.venv\Scripts\python.exe scripts\smoke.py
```

```
41/42 checks passed
```

---

## Design decisions

**Why a hybrid retriever instead of embeddings?**
Embedding models mean a 400 MB download and a cold start — fatal for a 24-hour
hackathon and for rural connectivity. BM25 nails rare terms (`khasra`, `chauthai`) while
character n-gram cosine handles dialect spellings (`bijli` / `bijlee` / `बिजली`). It
runs in microseconds with zero dependencies, and `chroma_adapter.py` makes swapping in
ChromaDB a one-line change.

**Why two NLU stages?**
The lexicon pass (`synonyms.json`) always works, offline, in microseconds. The LLM
pass refines it. Merging is deliberately conservative — the LLM may add entities or
override the intent, but it can never invent an intent the lexicon does not know, and
a transcript containing prompt-injection patterns is rejected outright.

**Why does the app speak even without a TTS provider?**
`edge-tts` needs the internet. The frontend falls back to the browser's Web Speech
API, so the demo always talks — the "Offline" badge tells the truth about which
engine is running.

**Why is the officer dashboard code-split?**
The citizen app and the DM dashboard have nothing in common except a router. The
dashboard pulls in Recharts (~450 kB), so it is loaded with `React.lazy` only when
someone opens `/admin`. The citizen bundle drops from **746 kB to 292 kB**
(214 kB → 92 kB gzipped) — the difference between a page that loads on a rural 3G
connection and one that does not.

**Why a combined "location" slot?**
Citizens say "Tanda block, Bansipur gaon" in one breath, not one field at a time. The
slot filler accepts a village **or** a block, and if the answer does not match the
pattern it is still used as the place name — the conversation never loops on the same
question.

---

## Ethics, privacy and guardrails

* **Aadhaar and phone numbers are masked everywhere** — in logs, in LLM prompts, in
  API responses and in stored tickets (`XXXX-XXXX-4821`, `XXXXX-3210`). The logger
  redacts on the way out; a phone number is never mistaken for an Aadhaar.
* **No hallucinated payouts.** The LLM only ever sees retrieved chunks, and the answer
  is re-checked against them afterwards — any monetary figure not present in the
  grounding is replaced with a pointer to the official document.
* **No false promises.** Promissory phrases ("pakka milega") are rewritten into a
  reference to the scheme rules.
* **Every claim is cited.** The UI shows `PM-KISAN §eligibility · pmkisan.gov.in`
  next to the spoken answer.
* **Prompt-injection defence.** Transcripts matching injection patterns are rejected
  before they reach the model.
* **Colour is never the only signal** — every status carries an icon and a text label.

---

## Roadmap

* [x] Voice-first PWA with hold-to-talk and text fallback
* [x] Bhojpuri / Awadhi / Hinglish NLU with entity extraction
* [x] Grounded RAG over official scheme documents with citations
* [x] Conversational grievance filing with a real tracking number
* [x] Application status tracker with timeline
* [x] District Magistrate analytics dashboard
* [x] WhatsApp Cloud API webhook stub
* [x] Fully offline-capable fallback engine for every AI call
* [ ] Real PDF ingestion pipeline for the scheme corpus (8 → 100+ documents)
* [ ] Groq tool-calling instead of JSON mode for stricter entity contracts
* [ ] Optional ChromaDB backend with a multilingual embedding model
* [ ] Live JGMS / IGRS / UIDAI sandbox integrations
* [ ] Lock-screen & glance-widget surfaces for the InMobi ecosystem story
* [ ] Voiceprint-based "one-tap repeat" for frequently asked scheme questions

---

## License

MIT — see [LICENSE](LICENSE).

Built for the AI Kaushal Hackathon 2026 (InMobi × Government of Uttar Pradesh ×
IIIT Lucknow).
