# Project Blueprint: **JanVaani UP** (जनवाणी यूपी)
**Track:** CivicTech / Multilingual Citizen Services & Governance Voice-Bot  
**Target Event:** AI Kaushal Hackathon 2026 (InMobi × Govt. of Uttar Pradesh × IIIT Lucknow)

---

## 1. Executive Summary
**JanVaani UP** is a voice-first, dialect-aware AI citizen assistant designed to bridge the digital divide in Uttar Pradesh. Instead of forcing rural and semi-urban citizens to navigate text-heavy English or formal Hindi government portals, JanVaani allows them to speak naturally in **Hindi, Bhojpuri, or Awadhi** via a lightweight Progressive Web App (PWA) or WhatsApp interface to check welfare scheme eligibility, track application statuses, and lodge civic grievances.

---

## 2. Core Problem Statement
* **Linguistic & Literacy Barrier:** Millions of citizens in UP speak regional dialects (Bhojpuri, Awadhi, Braj) and struggle with formal Hindi or English interfaces.
* **Portal Fragmentation:** Checking eligibility or status across schemes (PM-KISAN, PM Awas Yojana, Ration Card/NFSA, Jansunwai/IGRS) requires navigating multiple disjointed portals.
* **High Rejection Rates:** Citizens frequently submit incomplete documents because scheme guidelines are buried in complex PDFs.

---

## 3. What to Build (MVP Scope for 24-Hour Hackathon)

To win at IIIT Lucknow, build a **working end-to-end prototype** focusing on **3 high-impact user flows** rather than trying to cover every government department.

### Feature 1: Dialect-to-Action Scheme Discovery & Eligibility Checker (RAG)
* **User Action:** User taps the mic and asks in Bhojpuri/Hindi: *"Hamre paas 2 bigha zameen ba, kaun sarkari yojana mili?"* (I have 2 bigha of land, what government scheme can I get?)
* **System Action:** 
  1. Transcribes audio & normalizes dialect to standard intent.
  2. Queries a Vector Database loaded with official UP & Central scheme PDFs (PM-KISAN, Kisan Credit Card, UP Pension Schemes, PM Awas).
  3. Responds in simple, spoken local audio with exact eligibility criteria and required documents.

### Feature 2: Conversational Grievance Redressal (Jansunwai / IGRS Simulator)
* **User Action:** User reports a local issue by voice: *"Hamare gaon ke transformer 4 din se jala pada hai, koi sun nahi raha."* (Our village transformer has been burnt for 4 days, nobody is listening.)
* **System Action:**
  1. Extracts structured entities using LLM function calling: `Category: Electricity`, `Issue: Burnt Transformer`, `Duration: 4 days`.
  2. Prompts user for missing details (District/Block/Village) conversationally.
  3. Auto-generates a formal Hindi/English grievance ticket, assigns a mock IGRS Tracking ID, and displays it on an **Admin/Officer Dashboard**.

### Feature 3: Mock Application Status Tracker
* **User Action:** User asks: *"Mera ration card ya PM Kisan ka paisa kahan tak pahuncha?"* (What is the status of my ration card or PM Kisan installment?)
* **System Action:**
  1. Asks for Aadhaar last 4 digits or Registered Mobile Number (using a seeded mock SQLite/PostgreSQL database for demo purposes).
  2. Fetches status and reads it out clearly in the user's preferred language.

### Feature 4: Officer / District Magistrate (DM) Analytics Dashboard (Bonus "Wow" Factor)
* A clean web view showing real-time incoming voice grievances categorized by district, sentiment/urgency, and department—demonstrating immediate value to UP Government judges.

---

## 4. Technical Architecture & Recommended Stack

```text
[User Voice Input (Hindi/Bhojpuri/Awadhi)]
       │
       ▼
[Frontend: Mobile-First PWA (React / Next.js + Tailwind)] ──(Optional)──► [WhatsApp Cloud API / Twilio]
       │
       ▼
[Speech-to-Text (ASR): AI4Bharat IndicWhisper / Bhashini API / OpenAI Whisper]
       │
       ▼
[Backend Orchestrator: FastAPI (Python) + LangChain / LlamaIndex]
       ├──► [Vector DB (ChromaDB / FAISS)] ──► Official UP Scheme PDFs (RAG)
       ├──► [LLM Engine (Llama-3-8B / Sarvam-2B / GPT-4o-mini)] ──► Intent & Entity Extraction
       └──► [Mock Govt Database (SQLite/PostgreSQL)] ──► Beneficiary & Grievance Records
       │
       ▼
[Text-to-Speech (TTS): AI4Bharat IndicTTS / Bhashini / Edge-TTS]
       │
       ▼
[Natural Spoken Audio + Visual Summary Card on User Screen]
```

### Recommended Tools & APIs (Fastest for 24-Hour Build)
* **Speech-to-Text & Text-to-Speech:** 
  * **Bhashini API (ULCA)** or **Sarvam AI APIs** (Best native support for Indian languages & dialects).
  * *Fallback:* OpenAI Whisper API (`whisper-1`) for reliable Hindi/Hinglish transcription + `edge-tts` (`hi-IN-SwaraNeural`) for free, fast, natural Hindi voice synthesis.
* **LLM & Reasoning:** `GPT-4o-mini` or `Llama-3.1-70B` (via Groq for sub-second latency—crucial for live voice demos!).
* **Knowledge Base (RAG):** `ChromaDB` or `FAISS` with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
* **Backend:** Python `FastAPI` (clean, fast, easy to connect with AI libraries).
* **Frontend:** `Next.js` or `React (Vite)` styled as a simple, high-contrast mobile app with big mic buttons, visual icons, and minimal text.

---

## 5. Step-by-Step Build Roadmap

### Phase 1: Pre-Hackathon Prep (Before Dec 8)
- [ ] **Data Collection:** Download 5–8 official UP government scheme guidelines (PM-KISAN, PM Awas Gramin, UP Old Age/Widow Pension, Mukhyamantri Kanya Sumangala Yojana, Ration Card rules).
- [ ] **API Keys & Setup:** Set up Groq API, Bhashini/Sarvam/OpenAI keys, and test audio recording/playback in browser.
- [ ] **Mock Database:** Create a JSON/SQLite seed file with 10 realistic UP citizen profiles (e.g., Ramesh Kumar from Barabanki, Sunita Devi from Varanasi) and sample grievance tickets.

### Phase 2: 24-Hour Sprint Execution (At IIIT Lucknow)
* **Hours 1–4 (Core Pipeline):** Set up FastAPI backend + Audio Upload endpoint -> STT -> Groq LLM -> TTS -> Audio Response. Achieve < 3 seconds round-trip latency.
* **Hours 5–10 (RAG & Function Calling):** Ingest scheme PDFs into ChromaDB. Build structured tool-calling for Grievance Filing and Status Lookup.
* **Hours 11–16 (Frontend & Admin View):** Build the accessible Citizen PWA (large mic button, waveform animation, simple visual cards) + the Officer Grievance Dashboard.
* **Hours 17–20 (Dialect Prompt Engineering):** Test and tune system prompts with Bhojpuri/Awadhi phrases so the LLM understands colloquialisms (e.g., *mahtari*, *zameen*, *bijli*, *khata*) and responds warmly.
* **Hours 21–24 (Pitch & Demo Polish):** Record a backup demo video (in case hall Wi-Fi drops), prepare a 5-slide pitch deck, and rehearse live voice queries.

---

## 6. How to Impress the Judges (Winning Differentiators)

1. **Zero-Typing UX:** Design the interface so an illiterate user can use it purely via audio cues and color-coded icons.
2. **Privacy & Responsible AI:** Mask Aadhaar numbers in logs (`XXXX-XXXX-1234`) and add a strict guardrail so the LLM never hallucinates fake scheme payouts—citing exact official document sections instead.
3. **Low-Bandwidth Mode:** Compress audio payloads (`webm`/`opus`) and show a lightweight text fallback so it works on patchy 3G/4G rural networks.
4. **InMobi Ecosystem Synergy:** Mention in your pitch how this voice engine can scale via lock-screen/glance cards or lightweight mobile web widgets to reach millions of smartphone users across UP without requiring heavy app downloads.