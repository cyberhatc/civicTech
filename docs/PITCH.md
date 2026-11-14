# JanVaani UP — Pitch Deck & Live Demo Script

**Event:** AI Kaushal Hackathon 2026 — InMobi × Government of Uttar Pradesh × IIIT Lucknow
**Team:** JanVaani UP
**Tagline:** *आपकी आवाज़, आपकी योजना* — Your voice, your scheme.

---

## Slide 1 — The problem (60 seconds)

> **60 million people in UP speak Bhojpuri and Awadhi. The government portal speaks formal Hindi and English.**

Three facts, in order:

1. **The language barrier is real.** Millions of rural and semi-urban citizens speak
   regional dialects. Text-heavy English-first portals exclude them.
2. **The portals are fragmented.** PM-KISAN, PM Awas, Ration Card and Jansunwai are four
   disconnected systems. A citizen needs a working phone, a bank passbook, a laptop and
   a lot of patience.
3. **The failures are silent.** Incomplete paperwork → rejection → no callback. The
   citizen never learns *why*.

> **"We did not fail because the schemes do not exist. We failed because the schemes
> are not reachable."**

---

## Slide 2 — The insight (45 seconds)

> **The cheapest, most universal input device in rural India is not a keyboard. It is a voice — and it is already in every pocket.**

- Every smartphone in UP already has a microphone.
- Speech removes literacy as a gatekeeper.
- Dialect is not a defect to be normalised away — it is the **address** of the user.
  We should speak *to* Bhojpuri users in Bhojpuri, not in translated Hindi.

> **Design principle: zero typing. One big button. The system does the rest.**

---

## Slide 3 — What we built (75 seconds)

**JanVaani UP** — a voice-first, dialect-aware PWA.

| | |
| --- | --- |
| 🎙️ **Eligibility** | *"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"* → the right scheme, the exact criteria, the documents, **with citations to the official section**. |
| 📣 **Grievance** | *"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."* → entity extraction → conversational slot filling → formal Hindi summary → tracking number `JVUP-2026-0007`. |
| 🔎 **Status** | *"Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?"* → ask for Aadhaar last-4 or mobile → read out the status and timeline. |
| 📊 **Officer view** | The same grievance appears on a District Magistrate dashboard within one refresh — categorised by department, district, urgency and sentiment. |

**The engineering that makes it demo-able:**

- **Grounded RAG.** The LLM only sees retrieved chunks from official scheme documents;
  every answer carries `PM-KISAN §eligibility · pmkisan.gov.in`. Un-sourced money
  figures are stripped automatically.
- **Two-stage NLU.** A hand-built Bhojpuri/Awadhi/Hinglish lexicon always runs; the LLM
  refines it and can never invent an intent.
- **Every AI call has an offline twin.** No key? No problem — the deterministic engine
  completes all three flows. The UI badge says `LIVE` or `OFFLINE`, honestly.
- **Privacy by construction.** Aadhaar and phone numbers are masked in logs, in prompts,
  in API responses and in stored tickets.

---

## Slide 4 — Why this wins (60 seconds)

| Judge's worry | Our answer |
| --- | --- |
| *"It will hallucinate scheme amounts."* | Grounded generation + an automatic post-check that strips any figure not present in the retrieved source. |
| *"It will not work in a village with 2 bars."* | Audio is compressed to `webm/opus`; the UI has a text fallback; the PWA shell is cached; and the browser speaks the reply if the server's TTS is unreachable. |
| *"The demo needs the internet."* | The offline engine is not a mock — it is a real rule-based path, and `/api/health` reports which one is running. |
| *"A real citizen will not type an Aadhaar number."* | They do not have to. The tracker accepts a registered mobile number, and every identifier is masked before it is spoken or stored. |
| *"Will it scale past the demo?"* | The WhatsApp Cloud API webhook is already wired to the same orchestrator — the same voice engine serves a phone call, a PWA and a lock-screen widget. |

**The InMobi angle:** this voice engine does not need an app download. It can ride on
lock-screen glances, lightweight web widgets and WhatsApp — reaching millions of UP
smartphone users at the cost of a web page.

---

## Slide 5 — The ask (30 seconds)

> **Pilot in one district. 100 citizens. 30 days. One number: how many applications got filed correctly the first time.**

- **Now:** the full stack is running — backend, citizen PWA, officer dashboard, 62 tests
  and an end-to-end smoke test.
- **Next:** real IGRS/JGMS sandbox integration, real scheme PDFs (8 → 100+ documents),
  and a Bhashini ASR model tuned on UP dialect recordings.
- **Ask:** a UP district office to let us sit with 100 citizens for 30 days and measure
  the first-time-correct-filing rate.

---

# 🎬 Live Demo Script

**Setup before you walk on stage**

```powershell
.\scripts\setup.ps1          # once
.\scripts\dev.ps1            # backend :8000 + web :5173
```

Open these two tabs, side by side, in fullscreen:

* Tab A — `http://localhost:5173` (citizen)
* Tab B — `http://localhost:5173/admin` (officer dashboard)

Make sure `http://localhost:5173/admin` shows a green **LIVE** badge. If the venue
Wi-Fi is down, the badge will read **OFFLINE** — the demo still works, and *saying so
out loud* actually makes the reliability point for you.

---

### Beat 1 — The hook (0:00)

> "Yeh koi chatbot nahi hai. Yeh ek nayi zuban hai."

Press-and-hold the mic, speak in Bhojpuri:

> **"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"**

Release. The answer arrives with a **citation chip**: `PM-KISAN §eligibility · pmkisan.gov.in`.

**Say:** *"Bhojpuri mein bola, Bhojpuri mein jawab mila — aur jawab ke neeche sawaal ka
soura hai. Jhooth nahi, source."*

---

### Beat 2 — The grievance (0:30)

> "Ab ek problem dikhati hoon."

Hold the mic:

> **"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."**

JanVaani recognises the category (**electricity**), the duration (**4 days**) and the
urgency (**high**), then asks for the district.

Answer conversationally:

> **"Barabanki"**
> **"Tanda block, Bansipur gaon"**
> **"9876543210"**

A ticket card appears: **`JVUP-2026-0007`**, priority **P1**, with a formal Hindi
summary.

**Say:** *"Chatbot nahi — ek clerk jo aapki baat samajhta hai, formality mein likhta hai,
aur number deta hai."*

---

### Beat 3 — The payoff (1:00)

> "Ab dekhiye yeh kahan gaya."

Switch to **Tab B** (officer dashboard). The new grievance is already at the top of the
live feed — categorised, prioritised, placed on the map of districts.

Open the ticket drawer. Change **NEW → IN_PROGRESS**. Add a note. Watch the KPI tiles
move.

**Say:** *"Ek bhi operator ki zaroorat nahi. Awaaz se shikayat, dashboard par bhaag.
Yahi UP ke 75 district collector chahiye."*

---

### Beat 4 — The status tracker (1:30)

Switch back to **Tab A**. Tap **स्थिति**. Type the last 4 digits `4821`.

The PM-KISAN and KCC applications appear with a full timeline.

**Say:** *"Aur haan — jo bhi number diya, wo sirf usi ke mojhe dikhta hai. Log me kuch
bhi raw nahi jaata. Ye privacy nahi, yeh product design hai."*

---

### Beat 5 — The reliability point (2:00)

> "Ek last cheez — jo judges sabse zyada poochte hain."

Kill the Wi-Fi (or unplug the network cable) and repeat a query in text mode. The app
still answers, from the offline engine. The badge flips to **OFFLINE**.

**Say:** *"Hall ka Wi-Fi gir gaya — demo gir nahi gaya. Kyunki har AI call ke paas ek
offline jodi hai. Judges ka demo kabhi fail nahi hota."*

---

### Beat 6 — The close (2:15)

> "Humne portal nahi banaya. Humne **zuban** banayi.
>
> UP ke 60 million bhojpuri-bole kisan ko sirf ek button chahiye — aur ek system jo
> unki baat samjhe, unka kaam kare, aur unhe jawaab de.
>
> JanVaani UP. Aapki awaaz. Aapki yojana."

---

## Anticipated questions

**Q: What if the citizen speaks with no internet?**
A: The PWA shell is cached; the last API responses are cached too; the text mode works
on 3G. The server does the heavy lifting, but the citizen never needs more than a
`webm/opus` blob.

**Q: How do you know which scheme is right?**
A: Hybrid retrieval — BM25 for exact terms like `khasra` and `chauthai`, character
n-gram cosine for dialect spellings like *bijli / bijlee / बिजली*. Then the LLM answers
**only** from the retrieved chunks, and we cite the section.

**Q: What if the model invents a rupee amount?**
A: There is an automated post-check. Any monetary figure that does not appear in the
retrieved context is stripped and replaced with a pointer to the official document. It
is also covered by a unit test.

**Q: Is the government database real?**
A: No — it is a seeded mock with 12 realistic UP citizen profiles and 17 applications,
clearly marked in the README. The WhatsApp and IGRS integration points are stubbed but
the orchestrator behind them is production-shaped.

**Q: Why not WhatsApp only?**
A: Both. The webhook is already wired to the same orchestrator, so a WhatsApp message
takes the identical path as the PWA. The PWA adds the visual cards and the dashboard.

**Q: What is the cost per conversation?**
A: Groq's `llama-3.1-8b-instant` plus `whisper-large-v3` on short utterances is a small
fraction of a rupee, and the offline engine is free.

**Q: What about other states?**
A: The dialect lexicon and the scheme corpus are data, not code. A Bhojpuri lexicon
already covers Eastern UP; the same structure scales to Marathi, Kannada and Telugu.

---

## The one-line summary

> **Every year UP pays for schemes that reach the wrong people, and rejects the right
> ones for missing a photocopy. JanVaani UP removes the literacy barrier, the portal
> fragmentation and the silent rejection — by letting a citizen simply speak.**
