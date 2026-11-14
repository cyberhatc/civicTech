# JanVaani UP · जनवाणी यूपी

**Voice-first, dialect-aware AI citizen assistant for Uttar Pradesh.**
Ask in **Hindi, Bhojpuri or Awadhi** which government scheme you qualify for,
where your ration card / PM-KISAN instalment is, and lodge a civic grievance by
voice — and get an IGRS-style tracking number back.

Built for **AI Kaushal Hackathon 2026** (InMobi × Government of Uttar Pradesh × IIIT Lucknow).

---

## The problem

| Barrier | Reality for a rural UP citizen |
|---|---|
| **Linguistic** | Millions speak Bhojpuri / Awadhi / Braj, not formal Hindi or English |
| **Portal fragmentation** | Eligibility for PM-KISAN, KCC, PMAY, NFSA, pension lives on five different portals |
| **Rejection** | Applications bounce back because one document is missing |
| **Illiteracy of UI** | Text-heavy portals assume reading, typing and English |

JanVaani UP replaces all four interfaces with **one microphone button**.

---

## What it does

### 1 · Dialect-to-action scheme discovery (RAG)
> *"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"*

The utterance is normalised from Bhojpuri into a canonical intent, the vector store
retrieves the matching **official scheme clauses**, and the answer is spoken back in
simple Hindi — with a **citation chip** (`PM-KISAN §eligibility · pmkisan.gov.in`)
so every claim is traceable to a document.

### 2 · Conversational grievance redressal (Jansunwai / IGRS)
> *"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."*

The assistant extracts `{category: electricity, issue: burnt transformer, duration: 4 days}`,
then asks **only for what is missing** — district, village, mobile number. It files the
ticket, returns a tracking number (`JVUP-2026-0007`), and the grievance appears on the
**District Magistrate dashboard immediately**.

### 3 · Application status tracker
> *"Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?"*

Asks for the **last 4 digits of Aadhaar** or the **registered mobile**, then reads out
the status, amount, reference number and the next step.

### 4 · Officer / DM analytics dashboard (`/admin`)
Live voice grievances by district, department, urgency and sentiment, with a 14-day
trend, scheme-interest ranking, and inline status/priority/notes editing.

---

## Quick start

### Prerequisites
* **Python 3.11+** (the `py` launcher works — `python` is often a Store stub on Windows)
* **Node.js 18+**

### Setup

```powershell
git clone https://github.com/cyberhatc/civicTech.git
cd civicTech
.\scripts\setup.ps1          # venv + pip + npm + icons + DB seed
```

### Run

```powershell
.\scripts\dev.ps1
```

| Surface | URL |
|---|---|
| Citizen PWA | http://127.0.0.1:5173 |
| Officer dashboard | http://127.0.0.1:5173/admin |
| API + OpenAPI docs | http://127.0.0.1:8000/docs |

### Manual start (two terminals)

```powershell
# terminal 1 - backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend

# terminal 2 - frontend
cd frontend; npm run dev
```

---

## Live model vs. offline engine

Every AI call has a **deterministic offline twin**. The app never dies because a key
is missing, the Wi-Fi dropped, or `edge-tts` was unreachable.

| Capability | Live | Offline fallback |
|---|---|---|
| Chat LLM | Groq `llama-3.1-8b-instant` | rule-based intent engine + templated answers |
| Speech-to-text | Groq `whisper-large-v3` | text-mode input + browser speech |
| Text-to-speech | `edge-tts` (`hi-IN-SwaraNeural`) | browser Web Speech API |
| Vector search | hybrid BM25 + char-n-gram (or ChromaDB) | same retriever, no downloads |
| Database | SQLite | same |

`GET /api/health` reports which mode is active, and the UI shows a **LIVE / OFFLINE**
badge so a judge always knows what they are looking at.

### Enable the live model

```bash
# .env
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant
GROQ_STT_MODEL=whisper-large-v3
```

---

## Architecture

```
        ┌──────────────────────────────────────────────┐
        │  Voice (webm/opus)  │  Text  │  WhatsApp    │
        └──────────────┬───────────────────────────────┘
                       ▼
        ┌──────────────────────────────────────────────┐
        │  ASR   Groq Whisper  (hi / bho / awd)       │
        ├──────────────────────────────────────────────┤
        │  NLU   dialect lexicon + LLM tool-call       │
        ├──────────────────────────────────────────────┤
        │  RAG   BM25 ⊕ char-ngram  →  grounded answer │
        ├──────────────────────────────────────────────┤
        │  Tools grievance · status · escalation       │
        ├──────────────────────────────────────────────┤
        │  Store SQLite  ·  sessions  ·  tickets      │
        └──────────────┬───────────────────────────────┘
                       ▼
        ┌──────────────────────────────────────────────┐
        │  TTS edge-tts  →  spoken reply + cards       │
        │  PWA (React + Tailwind)  ·  DM dashboard     │
        └──────────────────────────────────────────────┘
```

Full details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) ·
Build plan: [`docs/PLAN.md`](docs/PLAN.md) · Pitch: [`docs/PITCH.md`](docs/PITCH.md)

---

## Repository layout

```
civicTech/
├── backend/                 FastAPI service
│   ├── app/
│   │   ├── core/            guardrails, logging, response envelope
│   │   ├── data/            scheme corpus, citizens, dialect lexicon
│   │   ├── db/              SQLite layer + idempotent seeding
│   │   ├── routers/         health, voice, chat, schemes, tickets, admin, whatsapp
│   │   └── services/        llm, stt, tts, nlu, rag, orchestrator, analytics
│   └── tests/               pytest suite (62 tests)
├── frontend/                Vite + React 19 + TypeScript + Tailwind v4 PWA
│   ├── public/              manifest, service worker, generated icons
│   └── src/                 citizen app + officer dashboard
├── docs/                    blueprint, plan, architecture, pitch
└── scripts/                 setup, dev, smoke, icon generation
```

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q     # 62 unit + API tests
.\.venv\Scripts\python.exe scripts\smoke.py                # 42 end-to-end checks
cd frontend; npm run build                                  # typecheck + production build
```

The smoke script exercises all three citizen flows against a running server and
verifies that **no Aadhaar or phone number ever appears unmasked** in a payload.

---

## Privacy & responsible AI

* Aadhaar → `XXXX-XXXX-1234`, mobile → `XXXXX-1234` — masked in **every** log line,
  API payload, stored ticket and LLM prompt.
* The LLM only ever sees **retrieved scheme clauses**; any amount or criterion that
  is not in that context is stripped from the answer before it reaches the user.
* Promissory language (*"pakka milega"*) is rewritten to *"योग्यता योजना के नियमों के
  अनुसार तय होगी"*.
* Prompt-injection attempts inside a transcript are rejected before they reach the model.
* The officer dashboard shows the citizen's own words — never their Aadhaar number.

---

## Why these choices

| Choice | Reason |
|---|---|
| **Groq** | Sub-second Llama inference keeps the live demo under 3 s |
| **Hybrid BM25 + char-ngram retrieval** | No model download, instant cold start, and it catches Bhojpuri spelling variants (`bijli` / `bijlee` / `विजली`) |
| **SQLite** | Zero native build steps — `pip install` never fails on a hackathon laptop |
| **edge-tts + browser fallback** | Natural Hindi voice for free, and the demo still speaks without a network |
| **PWA, not native app** | No Play Store wait — the InMobi pitch is "works on any phone, instantly" |
| **Offline twins everywhere** | A demo that dies on a missing key is worth nothing at 2 a.m. in the hall |

---

## Licence

MIT — see [`LICENSE`](LICENSE).

## Acknowledgements

Scheme clauses are summarised from the official portals of the Government of India and
the Government of Uttar Pradesh (pmkisan.gov.in, pmayg.nic.in, pmay-urban.gov.in,
mksy.up.gov.in, socialwelfare.up.gov.in, dfpd.gov.in, upfc.gov.in, upbhulekh.gov.in,
pmfby.gov.in, nabard.org). The citizen and grievance records in `backend/app/data/`
are **synthetic demo data** for prototyping only.
