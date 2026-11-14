# Pitch — JanVaani UP (जनवाणी यूपी)

**AI Kaushal Hackathon 2026** · InMobi × Government of Uttar Pradesh × IIIT Lucknow

---

## Slide 1 — The problem

**7 crore Uttar Pradeshis. One voice. Zero portals.**

* A farmer in Barabanki speaks **Bhojpuri**. Every government portal is in formal Hindi or English.
* Eligibility for PM-KISAN, KCC, PMAY, NFSA and pension lives on **five different portals**.
* Applications bounce back because **one document is missing** — and the rule is buried in a PDF.
* Text-heavy portals assume you can **read, type and search**.

> The schemes are designed for the file. The citizen has a voice.

---

## Slide 2 — The product

**One microphone button. Everything else happens by itself.**

| Flow | What the citizen says | What they get |
|---|---|---|
| **Scheme discovery** | *"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"* | PM-KISAN criteria, required documents, **with a citation to pmkisan.gov.in** |
| **Grievance redressal** | *"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."* | Ticket `JVUP-2026-0007` — and it is on the DM dashboard **immediately** |
| **Status tracker** | *"Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?"* | Status, amount, reference number, next step |
| **Officer view** | — | Live grievances by district, department, urgency and sentiment |

Works in **Hindi · Bhojpuri · Awadhi · Hinglish**.

---

## Slide 3 — How it works

```
VOICE (webm/opus) ─► Whisper large-v3 ─► DIALECT NLU ─► HYBRID RAG ─► GROUNDED ANSWER ─► edge-tts
                      (Groq, ~400ms)    (lexicon + LLM)  (BM25 ⊕ n-gram)   (cited, no      (Hindi
                                                            + intent-aware     hallucination)  voice)
                                                                            re-rank)
                                                        │
                                                        └──► grievance ticket ──► SQLite ──► /admin dashboard
```

**Every claim is cited.** Every answer carries a chip like `PM-KISAN §eligibility · pmkisan.gov.in`.
If the model invents a rupee figure that is not in the retrieved clause, the figure is **stripped
before it reaches the citizen**.

---

## Slide 4 — Why we built it this way

| Decision | Why it matters in the hall |
|---|---|
| **Offline twins for every AI call** | The demo cannot die on a missing key, a rate limit or hall Wi-Fi. A LIVE/OFFLINE badge is always on screen — no bluffing. |
| **Hybrid BM25 + character n-grams** | No model download, instant cold start, and it catches dialect spelling variants (*bijli / bijlee / विजली*) that a pure embedding model flattens. |
| **PWA, not a native app** | No Play Store wait. The InMobi story is *"it works on any phone, instantly, on 3G"*. |
| **Conversational slot filling** | The assistant asks only for what is missing — it never asks the citizen to fill a form. |
| **Privacy built in, not bolted on** | Aadhaar is masked in every log, prompt, payload and ticket. |
| **A real officer view** | The judge can see the governance value in one screen — this is not a chatbot demo. |

---

## Slide 5 — The ask & the vision

**Today:** a working end-to-end prototype — 9 schemes with official clauses, 3 citizen flows,
a live DM dashboard, 62 tests, 42 end-to-end checks.

**Next 30 days:**
1. **WhatsApp channel** — the webhook already speaks the same protocol; a number turns it live.
2. **Bhashini / Sarvam ASR + TTS** for native Bhojpuri and Awadhi voices.
3. **Real UP open data** — 40+ scheme PDFs ingested into the same vector store.
4. **UP district integration** — JanSeva Kendra, NHAI, Jal Nigam, Nigam tenders.
5. **Chatterji / in-mobility scale** — lock-screen widget and SMS fallback for feature phones.

> *"Har kisan ka apna sarkari kendra."*
> **Every farmer gets their own government office — in their own language.**

---

## Live demo script (90 seconds)

| # | Action | What the judge sees |
|---|---|---|
| 1 | Open http://localhost:5173 | PWA, Devanagari-first, **OFFLINE badge** (no key needed) |
| 2 | Press the big mic, say *"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"* | Bhojpuri transcribed, intent `scheme_eligibility`, `landBigha = 2` |
| 3 | Read the reply | PM-KISAN criteria + documents, **spoken aloud**, **3 citation chips** |
| 4 | Tap the mic, say *"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."* | `category=electricity`, `durationDays=4`, `urgency=high` |
| 5 | Answer the three slot questions | Ticket `JVUP-2026-0007` created, contact masked to `XXXXX-3210` |
| 6 | Open http://localhost:5173/admin | The grievance is **already in the live table** — KPIs and 4 charts updated |
| 7 | Change the status to `IN_PROGRESS`, add a note | Chart and counters move immediately |
| 8 | Go back, tap **स्थिति**, type `4821` | PM-KISAN + KCC status read out, Aadhaar shown as `XXXX-XXXX-4821` |
| 9 | Show `GET /api/health` | `mode: mock` — proof it runs without any API key |

---

## Contingencies

| If this breaks | Do this |
|---|---|
| Hall Wi-Fi drops | The app is a PWA with a service worker; the offline engine still answers. |
| Groq rate-limits | The backend falls back to the deterministic engine automatically — the badge flips to OFFLINE. |
| `edge-tts` unreachable | The browser's own Hindi voice reads the reply aloud. |
| The mic is blocked | The text input is right below the button and does the same thing. |
| Everything dies | `scripts/smoke.py` re-runs the whole demo in 3 seconds. |
