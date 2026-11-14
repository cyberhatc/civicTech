# Architecture — JanVaani UP

A deep dive into the technical decisions behind the voice-first citizen assistant.

---

## 1. The shape of the problem

The naive version of this product is: *record → Whisper → GPT → Edge-TTS → play*.
That works, but it is a toy. Three things make it a product:

1. **The corpus is official.** A citizen acting on a wrong eligibility rule is worse
   than a citizen who got no answer. Every factual claim must be traceable.
2. **The dialect is the product.** Bhojpuri is not "bad Hindi". Treating it as a
   translation target is what makes most Indian government voice bots fail.
3. **The demo is adversarial.** Venue Wi-Fi fails. The judge asks for a feature that
   was not planned. The model hallucinates a number.

Everything below follows from those three constraints.

---

## 2. Request lifecycle

```text
  MediaRecorder (webm/opus, 16 kbps-class)
        │  multipart/form-data
        ▼
  POST /api/voice/turn
        │
        ├─► stt.transcribe()  ──► Groq Whisper large-v3   (or: text passthrough)
        │      └─ failure → the client falls back to the text input automatically
        │
        ├─► nlu.analyze(text)
        │      ├─ lexicon_analyze()   always runs · ~0.3 ms · offline
        │      └─ llm_analyze()       Groq · only when a key is present
        │             └─ merge_intents()  LLM may refine, never invent an intent
        │
        ├─► orchestrator.handle_turn()
        │      ├─ session state (SQLite `sessions.state_json`)
        │      ├─ intent routing
        │      ├─ grievance slot filling  (district → location → contact)
        │      └─ domain service
        │             ├─ schemes.answer_question()  → RAG + grounded generation
        │             ├─ grievances.create_ticket() → ticket + summary
        │             └─ status.lookup()            → applications + timeline
        │
        ├─► tts.synthesize()  ──► edge-tts mp3 (cached by content hash)
        │      └─ failure → the client uses the browser SpeechSynthesis API
        │
        └─► envelope { ok, data, meta:{ mode, latencyMs } }
```

---

## 3. The retrieval layer

### 3.1 Why not embeddings?

An embedding model means a 400 MB–2 GB download, a torch dependency, and a cold start.
For a 24-hour hackathon that is time you do not have, and for a rural deployment it is
bandwidth you do not have. The corpus is also small and highly lexical: `khasra`,
`khatauni`, `chaurasi`, `Awaas+` — rare tokens that BM25 handles perfectly.

### 3.2 What we do instead

A **hybrid retriever** over 16 citable chunks from 9 schemes:

```
score(chunk) = BM25(query, chunk) + 0.85 · cosine(char_ngrams(query), char_ngrams(chunk))
```

* **BM25** (`k1=1.5`, `b=0.75`) rewards rare terms — `khasra`, `bigha`, `Awaas+`.
* **Character 3- and 4-gram cosine** is the dialect bridge. `bijli`, `bijlee`, `bhiJli`
  and `बिजली` share almost no whitespace tokens but plenty of character n-grams.
* The query is **expanded** with a dialect→canonical map before scoring
  (`zamin → zameen, land, khatauni`), and tokens are **lightly stemmed** with a
  conservative Hindi suffix stripper.
* Tokenisation keeps Devanagari intact — `[\w\u0900-\u097F]+` with `re.UNICODE`.

The result is sub-millisecond retrieval with zero model downloads and zero network.

### 3.3 Swapping in ChromaDB

`backend/app/services/chroma_adapter.py` implements the same interface. Setting
`VECTOR_BACKEND=chroma` is the only change required. The adapter is intentionally
optional so the default install stays small.

---

## 4. The NLU layer

### 4.1 Two stages, merged conservatively

```python
def analyze(text, use_llm=True) -> Intent:
    lexicon = lexicon_analyze(text)          # always runs
    return merge_intents(lexicon, llm_analyze(text))
```

The merge rules:

* The LLM may **add** entities.
* The LLM may **override** the intent — but only if it is at least 0.05 more confident.
* The LLM may **never** introduce an intent outside the known enum.
* A transcript matching a prompt-injection pattern is **rejected outright** and the
  lexicon result is used alone.

### 4.2 The lexicon

`backend/app/data/synonyms.json` holds ~260 entries across four languages:

| Section | Purpose | Example |
| --- | --- | --- |
| `lang_markers` | language detection | `hamare`, `keemat`, `jala pada` → Bhojpuri |
| `intents` | intent scoring | `kaun sa yojana`, `कौन सी योजना` → `scheme_eligibility` |
| `category_map` | grievance routing | `transformer`, `bijli`, `nala`, `toot gaya` → 10 categories |
| `entities` | slot extraction | `bigha`, `dur` `din`, `urgency_high`, `district`, `documents` |
| `number_words` | Devanagari numerals | `चार` → 4 |
| `small_talk` | confirmations | `हाँ`, `नहीं`, `धन्यवाद` |

Longer phrases score higher (`1.0 + 0.25 · word_count`), which makes
`"kaun sa yojana"` a stronger signal than a single common token.

### 4.3 Slot extraction

| Entity | Method |
| --- | --- |
| `landBigha` | `(\d+)\s*(bigha\|biga\|बिघा)` plus the Devanagari number map |
| `durationDays` | `(\d+)\s*(din\|hafta\|mahine\|saal)` → normalised to days |
| `category` | Highest-scoring category in `category_map` |
| `urgency` | `urgency_high` keyword hits, else duration ≥ 7 days → medium |
| `district` | Match against the 75 UP districts |
| `block` / `village` | `<name> block|tehsil` and `<name> gaon|village|mohalla` |
| `mobile` | `(?<!\d)([6-9]\d{4}[\s\-]?\d{5})(?!\d)` |
| `aadhaarLast4` | Last group of a 12-digit run |
| `sentiment` | Negative/positive lexicon, negative wins on a tie |

Pronouns are excluded from place names via a stopword list, so
*"Hamare gaon ke transformer"* yields `village=None`, not `village=Hamare`.

---

## 5. Grounded generation

The LLM receives **only** the retrieved chunks and is told to answer in spoken Hindi
and to quote section ids. Then two post-checks run:

1. **Amount check** — every monetary figure in the output is compared against the
   amounts present in the grounding. A figure that is not grounded is replaced with
   `[राशि सत्यापित हेतु योजना दस्तावेज़ देखें]`.
2. **Promise check** — promissory phrases (`pakka milega`, `guaranteed`) are rewritten
   into a reference to the scheme rules.

When the LLM is unavailable, `schemes._offline_answer` assembles the same answer
deterministically from the same chunks — so the **citation chips on screen always match
the spoken words**.

---

## 6. Grievance state machine

```text
                ┌─────────────┐
                │  IDLE       │
                └──────┬──────┘
        "shikayat…"   │      "kaun sa yojana"
                       ▼               ▼
              ┌────────────────┐  ┌──────────────┐
              │ COLLECTING     │  │  ANSWERED    │
              │                │  └──────────────┘
              │ district? ─────┼──► ask ──► fill
              │ location? ─────┼──► ask ──► fill
              │ contact?  ─────┼──► ask ──► fill
              └───────┬────────┘
                      │ all slots filled
                      ▼
              ┌────────────────┐
              │ FILED          │ → ticket + summary + tracking number
              └────────────────┘
```

* The state lives in `sessions.state_json` so a refresh does not lose the conversation.
* **Combined location slot.** A village **or** a block is enough; if the answer does
  not match the pattern it is still used as the place name, so the flow never loops.
* **Contact is optional** — "skip" files the grievance without a phone number.
* The ticket gets a formal Hindi + English summary from the LLM, or a deterministic
  template offline. The summary only contains extracted facts — never an invented
  remedy, deadline or compensation.

---

## 7. Privacy

| Layer | Treatment |
| --- | --- |
| Logs | `RedactingFormatter` masks Aadhaar/phone on **every** record, before it is written |
| LLM prompts | `guardrails.safe_user_text()` masks and truncates user input |
| LLM output | `strip_ungrounded_claims()` removes ungrounded figures and promises |
| Stored tickets | `transcript`, `issue` and `contact` are masked before insert |
| API responses | Aadhaar → `XXXX-XXXX-4821`, mobile → `XXXXX-3210` |
| Prompt injection | Transcripts matching injection patterns never reach the model |

The mask order matters: a 12-digit number starting with `91` is a phone, not an
Aadhaar, and `mask_aadhaar` checks that before it masks.

---

## 8. The offline twin pattern

Every AI service follows the same shape:

```python
class Service:
    available: bool          # is the live provider usable?

    def do_the_thing(self):
        if not self.available:
            return self.offline_twin()   # deterministic, always works
        try:
            return self.live()
        except ProviderUnavailable:
            return self.offline_twin()
```

| Service | Live | Offline twin |
| --- | --- | --- |
| `llm.py` | Groq chat + JSON mode | The rule-based NLU + template generators in `nlu.py` / `schemes.py` / `grievances.py` |
| `stt.py` | Groq Whisper | The client's text input |
| `tts.py` | edge-tts → Bhashini | The browser's `speechSynthesis` |
| `rag.py` | *(the same code — retrieval never needs the network)* | — |

`GET /api/health` reports `mode: live|mock` per capability, and the UI badge tells the
truth. This is a **feature**, not a workaround: it is how the demo survives a dead
venue router, and it is a strong answer to "what if the model is down?".

---

## 9. Frontend architecture

### 9.1 Citizen PWA

* **Hold-to-talk** (`onPointerDown` / `onPointerUp`) with a 350 ms minimum, so an
  accidental tap does not send an empty turn.
* `MediaRecorder` with `audio/webm;codecs=opus` first, falling back through
  `audio/ogg`, `audio/mp4` — Safari gets `audio/mp4`.
* **Three-level audio fallback**: server mp3 → browser `speechSynthesis` → the text
  stays on screen.
* A waveform animation that reflects real recording state.
* Tabs: `बोलें` · `योजनाएँ` · `स्थिति` · `शिकायत`.

### 9.2 Service worker

* The **app shell** is precached → the PWA opens instantly and offline.
* **API** calls are network-first with a cache fallback.
* **Navigations** fall back to the cached `index.html`.
* Static assets are cache-first.

### 9.3 Officer dashboard

* Dark theme, Recharts, 15-second polling.
* KPI tiles → trend area chart → category donut → district and priority bars →
  scheme-interest bars → live ticket table → a detail drawer with status, priority
  and an action trail.
* Every ticket row is clickable; status and priority are editable inline and the
  dashboard re-aggregates from the response.

---

## 10. Performance targets

| Stage | Target | Notes |
| --- | --- | --- |
| ASR (Whisper large-v3 on Groq) | ~300–600 ms for a 6 s utterance | |
| NLU (lexicon) | < 1 ms | |
| NLU (+ LLM) | ~200–400 ms | Groq `llama-3.1-8b-instant` |
| Retrieval | < 5 ms | pure numpy-free Python |
| TTS (edge-tts) | ~400–900 ms | cached by content hash |
| **Total voice round trip** | **< 3 s** | matches the blueprint target |

`/api/health` and every response envelope carry `meta.latencyMs` so the numbers are
observable rather than claimed.

---

## 11. Known limitations

* The scheme corpus is **9 hand-curated documents**, not a live PDF pipeline.
* The citizen database is a **seeded mock** — the integration points are real, the
  data is not.
* The dialect lexicon is broad but not deep — it handles the top ~250 tokens, not
  arbitrary Bhojpuri.
* Wake-word detection is not implemented; the button is the trigger.
* Audio is **not** stored — only the masked transcript — which is the right default but
  means there is no "replay my complaint" recording for the officer.

---

## 12. What we would build next

1. **PDF ingestion** — a scheduled scraper for `pmkisan.gov.in`, `pmayg.nic.in`,
   `mksy.up.gov.in` and the UP revenue portal, chunked and embedded.
2. **Groq tool-calling** instead of JSON mode — a stricter contract for entity
   extraction than "please return JSON".
3. **Bhashini ASR** for native-dialect accuracy, falling back to Whisper.
4. **A real vector backend** with a multilingual embedding model, selected by
   `VECTOR_BACKEND`.
5. **JGMS / IGRS sandbox** writes so the tracking number resolves to a real record.
