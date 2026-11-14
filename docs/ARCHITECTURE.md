# Architecture — JanVaani UP

## 1. Shape of the system

```
┌───────────────────────────────────────────────────────────────────────┐
│  CLIENTS                                                              │
│                                                                       │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐  │
│  │ Citizen    │   │ Citizen    │   │ WhatsApp   │   │ Officer    │  │
│  │ PWA        │   │ PWA (text  │   │ Cloud API  │   │ Dashboard  │  │
│  │ (voice)    │   │ fallback)  │   │ (stub)     │   │ /admin     │  │
│  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘  │
└────────┼────────────────┼────────────────┼────────────────┼─────────┘
         │ multipart/webm │ JSON           │ JSON webhook   │ JSON
         └────────────────┴────────┬───────┴────────────────┘
                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│  FASTAPI  (backend/app)                                               │
│                                                                       │
│   routers/voice ──► services/stt ──► Groq Whisper large-v3            │
│        │                              (no key → text mode)             │
│        ├──────────► services/nlu ──► lexicon pass + LLM tool-call    │
│        │                              (merge: LLM refines, never      │
│        │                               invents an intent)             │
│        ├──────────► services/rag ──► BM25 ⊕ char-ngram                │
│        │                              → intent-aware re-rank          │
│        │                              → grounded answer + citations    │
│        ├──────────► services/grievances ──► ticket JVUP-YYYY-NNNN    │
│        ├──────────► services/status ─────► beneficiary applications   │
│        ├──────────► services/analytics ──► DM dashboard aggregations │
│        └──────────► services/tts ───────► edge-tts mp3 (cached)      │
│                                                                       │
│   core/guardrails ── masks Aadhaar/phone, strips ungrounded claims    │
│   db/ ──────────────► SQLite (citizens, applications, grievances,    │
│                        sessions, turns) + idempotent seeding          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 2. Backend modules

| Module | Responsibility | Offline twin |
|---|---|---|
| `core/guardrails.py` | Aadhaar/phone masking, ungrounded-claim stripping, prompt-injection detection | — (always on) |
| `core/logging_conf.py` | Redacting log formatter — PII never reaches a log file | — (always on) |
| `core/response.py` | One response envelope: `{ok, data, meta{mode, latencyMs}}` | — (always on) |
| `config.py` | `pydantic-settings`; every AI credential optional | — (always on) |
| `db/database.py` | Thread-safe SQLite wrapper, schema, helpers | — (always on) |
| `db/seed.py` | Idempotent seeding of 12 citizens / 17 applications / 6 grievances | — (always on) |
| `services/llm.py` | Groq chat + JSON-schema tool calls | rule engine in `nlu.py` |
| `services/stt.py` | Groq Whisper multipart upload | returns "unavailable", UI falls back to text |
| `services/tts.py` | edge-tts → cached mp3; Bhashini optional | browser Web Speech API |
| `services/nlu.py` | Dialect intent + entity extraction | **is** the fallback |
| `services/rag.py` | Hybrid retriever over 16 chunks / 9 schemes | same code path |
| `services/schemes.py` | Grounded scheme Q&A + citations | template answer from chunks |
| `services/grievances.py` | Ticket lifecycle, ID allocation, bilingual summaries | template summary |
| `services/status.py` | Application lookup by Aadhaar-last-4 / mobile | same |
| `services/analytics.py` | Dashboard aggregations | same |
| `services/orchestrator.py` | Session state, slot filling, intent routing | same |

---

## 3. The dialect NLU

Two stages, always in this order:

**Stage 1 — lexicon (always runs, offline, microseconds)**

`app/data/synonyms.json` holds ~250 dialect tokens across Hindi, Bhojpuri, Awadhi and
Hinglish. Each utterance is scored against every intent; the longest matching phrase
wins the most weight. Entities are extracted with dedicated rules:

| Entity | Rule | Example |
|---|---|---|
| `landBigha` | number adjacent to *bigha/biga/बिघा* | *"2 bigha zameen"* → 2 |
| `durationDays` | number × unit (*din/hafta/mahine/saal*) | *"4 din se"* → 4 |
| `category` | keyword score over 10 grievance categories | *"transformer jala"* → electricity |
| `district` | match against all 75 UP districts | *"Barabanki"* |
| `block` / `village` | `<name> block` / `<name> gaon`, pronoun-blacklisted | *"Tanda block, Bansipur gaon"* |
| `urgency` | damage keywords + duration | *"jala"*, *"koi nahi sun"* → high |
| `sentiment` | negative/positive word balance | *"koi sun nahi raha"* → negative |
| `aadhaarLast4` / `mobile` | digit patterns | *"4123 5678 9012"* → 4821 |

**Stage 2 — LLM (only when Groq is configured)**

The transcript goes to Groq with a strict JSON schema (`intent`, `confidence`,
`language`, `entities{...}`). The result is **merged over** the lexicon result:

* The LLM may *add* entities or *override* the intent.
* The LLM may **never** introduce an intent outside the known enum.
* If the LLM and the lexicon disagree on intent, the lexicon wins unless the LLM is
  more confident by ≥ 0.05.
* Prompt-injection attempts inside a transcript are rejected before the call.

---

## 4. Retrieval and grounding

The corpus is 9 schemes split into 16 sections. Each section is a retrievable chunk
carrying `{schemeId, sectionId, title, body, eligibility[], documents[], source, page}`.

**Scoring** — `bm25 + 0.85 × cosine(char-3/4-grams)`, with a query expansion step that
maps dialect tokens onto canonical terms (*bijli → electricity, transformer, current*).
The n-gram half is what catches spelling variants across dialects.

**Re-ranking** — pure similarity prefers long, keyword-dense sections, which is often
the *"who is not eligible"* paragraph. A citizen asking *"am I eligible?"* must get the
criteria. `rag.rerank_by_intent` therefore promotes the section type that matches the
question kind:

| Question kind | Preferred section |
|---|---|
| eligibility | `§eligibility` |
| apply / how-to | `§application`, `§process` |
| interest rate | `§interest` |
| land record lookup | `§lookup` |

**Grounding** — the LLM receives *only* the retrieved sections and is told to quote
section ids. After generation, `guardrails.strip_ungrounded_claims` strips any rupee
figure that does not appear in the retrieved context and rewrites promissory phrases.
The citation chips on the UI are built from the same chunk list, so the spoken answer
and the visible provenance can never disagree.

**Swapping in a real vector DB** — `services/chroma_adapter.py` implements the same
interface. Set `VECTOR_BACKEND=chroma` and install `chromadb`; nothing else changes.

---

## 5. The grievance conversation

```
citizen: "Hamare gaon ke transformer 4 din se jala pada hai"
  → intent=grievance_file, category=electricity, durationDays=4, urgency=high
  → missing: district, location, contact
  → reply: "आप किस जिले में हैं?"

citizen: "Barabanki"
  → district=Barabanki        → still missing: location, contact
  → reply: "आपके गाँव या मोहल्ले का नाम और ब्लॉक बताइए।"

citizen: "Tanda block, Bansipur gaon"
  → block=Tanda, village=Bansipur   → still missing: contact
  → reply: "शिकायत की सूचना देने के लिए आपका मोबाइल नंबर बताइए।"

citizen: "9876543210"
  → ticket JVUP-2026-0007 created, contact masked to XXXXX-3210
  → reply: "आपकी शिकायत दर्ज हो गई है। शिकायत संख्या JVUP-2026-0007 है…"
```

Slot state lives in `sessions.state_json`, so a reload does not lose the conversation.
If the citizen answers a location question with something the pattern matcher does not
recognise, the raw answer is accepted as the place name — the conversation never loops
on the same question.

---

## 6. Privacy model

| Where | Rule |
|---|---|
| Log formatter | Every record passes through `mask_all` before it is written |
| LLM prompts | `guardrails.safe_user_text` masks and truncates user text |
| Stored turns | `record_turn` masks before insert |
| Stored tickets | `issue` and `transcript` masked before insert |
| API payloads | Aadhaar → `XXXX-XXXX-1234`, mobile → `XXXXX-1230` |
| Dashboard | Shows the citizen's words, never their identifier |

A 12-digit run starting with `91` is recognised as a phone number, not an Aadhaar —
so `+91` numbers are masked as phones rather than mis-classified.

---

## 7. Frontend

**Citizen app** (`/`)

* One enormous mic button (96 px) with a pulse ring and live equaliser.
* Press-and-hold to record, release to send; the minimum hold is 350 ms.
* Replies render as chat bubbles plus structured cards (scheme, documents, ticket,
  application with a timeline).
* Citation chips show the source document for every factual claim.
* Bottom nav: **बोलें · योजनाएँ · स्थिति · शिकायत**.
* Text input everywhere — the low-bandwidth path.
* TTS auto-plays; if the server has no audio, the browser speaks instead.

**Officer dashboard** (`/admin`)

* Dark, dense, four charts (14-day trend, department donut, district bars, priority bars).
* Live ticket table with filters, a detail drawer, and inline status / priority /
  notes editing. Auto-refreshes every 15 s.

**PWA** — hand-written `manifest.webmanifest` + `sw.js` (network-first for the API,
cache-first for static assets), installable on any Android phone.

---

## 8. Performance

| Stage | Offline | Live (Groq) |
|---|---|---|
| ASR | — | ~400 ms |
| NLU (lexicon) | < 5 ms | < 5 ms |
| NLU (LLM pass) | — | ~300 ms |
| Retrieval | ~3 ms | ~3 ms |
| Answer generation | ~1 ms | ~600 ms |
| TTS | ~700 ms (edge-tts) | ~700 ms |
| **Total** | **~0.8 s** | **~2.0 s** |

The live path stays inside the 3-second target from the blueprint; the offline path is
effectively instant.

---

## 9. Extending it

| Want to add… | Do this |
|---|---|
| A new scheme | Append a block to `backend/app/data/schemes.json` — sections, criteria, documents, source. The RAG, citations and UI pick it up with no code change. |
| A new dialect | Extend `backend/app/data/synonyms.json` (intent phrases, category map, district list). |
| A new grievance category | Add to `CATEGORIES` / `CATEGORY_HI` in `services/nlu.py` and to `category_map` in the lexicon. |
| A real vector DB | Implement `services/chroma_adapter.py` and set `VECTOR_BACKEND=chroma`. |
| WhatsApp for real | Set `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN`; the webhook already runs the same orchestrator. |
