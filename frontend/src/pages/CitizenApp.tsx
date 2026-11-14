import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import BottomNav, { type TabKey } from "@/components/BottomNav";
import CitationList from "@/components/CitationList";
import MicButton from "@/components/MicButton";
import ModeBadge from "@/components/ModeBadge";
import ReplyCard from "@/components/ReplyCard";
import { api } from "@/lib/api";
import { createRecorder, playServerAudio, type Recorder } from "@/lib/audio";
import { browserSpeechSupported, speak, stopSpeaking } from "@/lib/speech";
import type { Health, ResponseCard, TurnResult } from "@/lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  cards: ResponseCard[];
  citations: TurnResult["citations"];
  quickReplies: string[];
  intentName?: string;
  language?: string;
  pending?: boolean;
}

const WELCOME: Message = {
  id: "welcome",
  role: "assistant",
  text: "नमस्ते! मैं जनवाणी यूपी हूँ। हिंदी, भोजपुरी या अवधी में बोलिए — मैं आपकी योजना बताऊँगा, आवेदन की स्थिति देखूँगा, और शिकायत दर्ज करा दूँगा।",
  cards: [],
  citations: [],
  quickReplies: [
    "मेरे पास 2 बीघा जमीन है, कौन सी योजना मिलेगी?",
    "मेरा राशन कार्ड कहाँ है?",
    "गाँव का ट्रांसफॉर्मर 4 दिन से जला पड़ा है",
  ],
};

let messageCounter = 0;
const nextId = () => `m${Date.now().toString(36)}${(messageCounter += 1)}`;

export default function CitizenApp() {
  const [health, setHealth] = useState<Health | null>(null);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("voice");
  const [draft, setDraft] = useState("");
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [schemeCards, setSchemeCards] = useState<ResponseCard[]>([]);
  const [lookupId, setLookupId] = useState("");
  const [lookupResult, setLookupResult] = useState<Record<string, unknown> | null>(null);
  const [lookupBusy, setLookupBusy] = useState(false);

  const recorderRef = useRef<Recorder | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api
      .schemes()
      .then((data) => setSchemeCards(data.cards))
      .catch(() => setSchemeCards([]));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const pushAssistant = useCallback((result: TurnResult) => {
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        role: "assistant",
        text: result.reply.text,
        cards: result.cards ?? [],
        citations: result.citations ?? [],
        quickReplies: result.quickReplies ?? [],
        intentName: result.intent?.name,
        language: result.intent?.language,
      },
    ]);
  }, []);

  const speakReply = useCallback(
    async (result: TurnResult) => {
      if (!autoSpeak) return;
      const played = await playServerAudio(result.reply.audioUrl);
      if (!played) {
        speak(result.reply.text, result.reply.lang === "bho" ? "hi-IN" : "hi-IN");
      }
    },
    [autoSpeak],
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      setError(null);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", text: trimmed, cards: [], citations: [], quickReplies: [] },
      ]);
      setProcessing(true);
      try {
        const result = await api.chat({ text: trimmed, sessionId, lang: "hi" });
        setSessionId(result.sessionId);
        pushAssistant(result);
        void speakReply(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "कुछ गड़बड़ हो गई।");
      } finally {
        setProcessing(false);
      }
    },
    [pushAssistant, sessionId, speakReply],
  );

  const startRecording = useCallback(async () => {
    setError(null);
    stopSpeaking();
    const recorder = createRecorder();
    if (!recorder) {
      setError("इस ब्राउज़र में माइक उपलब्ध नहीं है। नीचे लिखकर भेजिए।");
      setTab("voice");
      return;
    }
    try {
      await recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setError("माइक की अनुमति नहीं मिली। ब्राउज़र सेटिंग में अनुमति दीजिए।");
    }
  }, []);

  const stopRecording = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    setRecording(false);
    setProcessing(true);
    try {
      const blob = await recorder.stop();
      recorderRef.current = null;
      if (!blob) {
        setError("आवाज़ रिकॉर्ड नहीं हो पाई। दोबारा बोलिए।");
        return;
      }
      const result = await api.voiceTurn({ blob, sessionId, lang: "hi" });
      setSessionId(result.sessionId);
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "user",
          text: result.transcript.text || "(आवाज़ सुनाई नहीं गई)",
          cards: [],
          citations: [],
          quickReplies: [],
          intentName: result.intent?.name,
          language: result.intent?.language,
        },
      ]);
      pushAssistant(result);
      void speakReply(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "आवाज़ प्रोसेस नहीं हो पाई।");
    } finally {
      setProcessing(false);
    }
  }, [pushAssistant, sessionId, speakReply]);

  const onCardAction = useCallback(
    (action: string, payload: string) => {
      if (action === "ask_eligibility") {
        void send(`${payload} योजना के लिए मैं पात्र हूँ क्या?`);
      } else if (action === "ask_documents") {
        void send(`${payload} के लिए कौन कौन से दस्तावेज़ चाहिए?`);
      } else if (action === "ask_apply") {
        void send(`${payload} का आवेदन कैसे करें?`);
      }
      setTab("voice");
    },
    [send],
  );

  const runLookup = useCallback(async () => {
    const digits = lookupId.replace(/\D/g, "");
    if (digits.length < 4) {
      setError("कृपया आधार के अंतिम 4 अंक या 10 अंकों का मोबाइल नंबर डालिए।");
      return;
    }
    setLookupBusy(true);
    setError(null);
    try {
      const payload =
        digits.length >= 10
          ? { mobile: digits.slice(-10) }
          : { aadhaarLast4: digits.slice(-4) };
      const result = await api.lookup(payload);
      setLookupResult(result as unknown as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "लुकअप नहीं हो पाया।");
    } finally {
      setLookupBusy(false);
    }
  }, [lookupId]);

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "सुप्रभात";
    if (hour < 17) return "नमस्कार";
    return "शुभ संध्या";
  }, []);

  return (
    <div className="flex min-h-dvh flex-col bg-ink-50">
      {/* ------------------------------------------------------------------ */}
      <header className="sticky top-0 z-20 border-b border-ink-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-md items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-700 text-lg font-black text-white"
            >
              ज
            </span>
            <div className="leading-tight">
              <p className="text-[15px] font-extrabold text-ink-900">जनवाणी यूपी</p>
              <p className="text-[11px] text-ink-500">{greeting} • आपकी आवाज़, आपकी योजना</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ModeBadge health={health} />
            <Link
              to="/admin"
              title="Officer dashboard"
              aria-label="Officer dashboard"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-ink-200 text-sm text-ink-600 hover:bg-ink-100"
            >
              📊
            </Link>
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col">
        {tab === "voice" && (
          <>
            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
              {messages.map((message) => (
                <div key={message.id} className="animate-float-up">
                  {message.role === "user" ? (
                    <div className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-700 px-4 py-2.5 text-[15px] leading-relaxed text-white shadow-soft">
                        {message.text}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex gap-2.5">
                        <span
                          aria-hidden="true"
                          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-base"
                        >
                          🎙️
                        </span>
                        <div className="max-w-[92%] rounded-2xl rounded-tl-md border border-ink-200 bg-white px-4 py-3 text-[15px] leading-relaxed text-ink-800 shadow-soft">
                          {message.text}
                          {message.intentName && (
                            <span className="mt-2 block text-[10px] font-medium uppercase tracking-wide text-ink-400">
                              {message.intentName}
                              {message.language ? ` · ${message.language}` : ""}
                            </span>
                          )}
                        </div>
                      </div>

                      {message.citations.length > 0 && (
                        <div className="pl-[42px]">
                          <CitationList citations={message.citations} />
                        </div>
                      )}

                      {message.cards.map((card, index) => (
                        <div key={`${card.title}-${index}`} className="pl-[42px]">
                          <ReplyCard card={card} onAction={onCardAction} />
                        </div>
                      ))}

                      {message.quickReplies.length > 0 && (
                        <div className="flex flex-wrap gap-2 pl-[42px]">
                          {message.quickReplies.map((reply) => (
                            <button
                              key={reply}
                              type="button"
                              onClick={() => void send(reply)}
                              className="chip border border-brand-300 bg-white px-3 py-1.5 text-[13px] font-medium text-brand-800 hover:bg-brand-50"
                            >
                              {reply}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {processing && (
                <div className="flex gap-2.5">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-base"
                  >
                    🎙️
                  </span>
                  <div className="flex items-center gap-1 rounded-2xl rounded-tl-md border border-ink-200 bg-white px-4 py-4 shadow-soft">
                    {[0, 1, 2].map((index) => (
                      <span
                        key={index}
                        className="h-2 w-2 rounded-full bg-brand-400"
                        style={{ animation: `float-up 900ms ${index * 140}ms infinite alternate` }}
                      />
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <div role="alert" className="rounded-xl border border-alert-500/30 bg-alert-500/10 px-4 py-3 text-sm text-alert-700">
                  {error}
                </div>
              )}
            </div>

            {/* ------------------------------------------------------------ */}
            <div className="safe-bottom border-t border-ink-200 bg-white px-4 pb-3 pt-3">
              <div className="mx-auto flex max-w-md flex-col items-center gap-3">
                <MicButton
                  recording={recording}
                  processing={processing}
                  onStart={() => void startRecording()}
                  onStop={() => void stopRecording()}
                />

                <form
                  className="flex w-full items-center gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const value = draft.trim();
                    setDraft("");
                    void send(value);
                  }}
                >
                  <input
                    ref={inputRef}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="यहाँ लिखकर भी पूछ सकते हैं…"
                    aria-label="अपना सवाल लिखें"
                    className="min-w-0 flex-1 rounded-full border border-ink-200 bg-ink-50 px-4 py-3 text-[15px] outline-none focus:border-brand-400 focus:bg-white"
                  />
                  <button
                    type="submit"
                    disabled={!draft.trim() || processing}
                    className="btn btn-primary !min-h-12 !w-12 !px-0"
                    aria-label="भेजें"
                  >
                    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
                      <path d="M3.4 20.4 21 12 3.4 3.6 3.39 10l12.1 2-12.1 2z" />
                    </svg>
                  </button>
                </form>

                <label className="flex w-full cursor-pointer items-center justify-center gap-2 text-xs text-ink-500">
                  <input
                    type="checkbox"
                    checked={autoSpeak}
                    onChange={(event) => setAutoSpeak(event.target.checked)}
                    className="h-4 w-4 accent-brand-700"
                  />
                  जवाब सुनकर दिखाएँ (TTS)
                  {!browserSpeechSupported() && (
                    <span className="chip bg-ink-100 text-ink-500">browser TTS unavailable</span>
                  )}
                </label>
              </div>
            </div>
          </>
        )}

        {/* ---------------------------------------------------------------- */}
        {tab === "schemes" && (
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-5">
            <header>
              <h1 className="text-lg font-extrabold text-ink-900">योजनाएँ</h1>
              <p className="text-sm text-ink-500">
                उत्तर प्रदेश की मुख्य योजनाएँ — किसी पर भी टैप करके सवाल पूछिए।
              </p>
            </header>
            {schemeCards.map((card) => (
              <ReplyCard
                key={card.id ?? card.title}
                card={card}
                onAction={(action, payload) => {
                  if (action === "ask_eligibility") {
                    void send(`${payload} योजना के लिए मैं पात्र हूँ क्या?`);
                  } else if (action === "ask_documents") {
                    void send(`${payload} के लिए कौन कौन से दस्तावेज़ चाहिए?`);
                  }
                  setTab("voice");
                }}
              />
            ))}
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {tab === "status" && (
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
            <header>
              <h1 className="text-lg font-extrabold text-ink-900">आवेदन की स्थिति</h1>
              <p className="text-sm text-ink-500">
                आधार के आखिरी 4 अंक या पंजीकृत मोबाइल नंबर डालिए।
              </p>
            </header>

            <form
              className="surface space-y-3 p-4"
              onSubmit={(event) => {
                event.preventDefault();
                void runLookup();
              }}
            >
              <label className="block text-sm font-semibold text-ink-700" htmlFor="lookup">
                पहचान संख्या
              </label>
              <input
                id="lookup"
                value={lookupId}
                inputMode="numeric"
                onChange={(event) => setLookupId(event.target.value)}
                placeholder="XXXX XXXX 4821  या  9876543210"
                className="w-full rounded-xl border border-ink-200 bg-ink-50 px-4 py-3 font-mono text-[15px] outline-none focus:border-brand-400 focus:bg-white"
              />
              <button type="submit" disabled={lookupBusy} className="btn btn-primary w-full">
                {lookupBusy ? "खोज रहे हैं..." : "स्थिति देखें"}
              </button>
              <p className="text-[11px] leading-relaxed text-ink-400">
                🔒 आपका आधार नंबर हमेशा मास्क करके दिखाया जाता है (XXXX-XXXX-1234) और लॉग में कभी नहीं लिखा जाता।
              </p>
            </form>

            {lookupResult && (
              <div className="space-y-3">
                <div className="surface p-4">
                  <p className="text-sm text-ink-700">
                    {String((lookupResult as { message?: string }).message ?? "")}
                  </p>
                </div>
                {(
                  (lookupResult as { applications?: Record<string, unknown>[] }).applications ?? []
                ).map((app) => (
                  <ReplyCard
                    key={String(app.id)}
                    card={{
                      type: "application",
                      icon: String(app.icon ?? "📄"),
                      title: String(app.schemeNameHi ?? app.schemeName ?? ""),
                      subtitle: String(app.shortName ?? ""),
                      body: String(app.statusLabelHi ?? ""),
                      status: String(app.status ?? ""),
                      fields: [
                        { label: "स्थिति", value: String(app.statusLabelHi ?? "") },
                        { label: "राशि", value: String(app.amountLabel ?? "—") },
                        { label: "अंतिम अद्यतन", value: String(app.last_updated ?? "—") },
                        { label: "संदर्भ", value: String(app.reference ?? "—") },
                        { label: "अगला कदम", value: String(app.nextStep ?? "—") },
                      ],
                      timeline: (app.events as TurnResult["citations"]) as never,
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {tab === "grievance" && (
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
            <header>
              <h1 className="text-lg font-extrabold text-ink-900">शिकायत दर्ज कराइए</h1>
              <p className="text-sm text-ink-500">
                अपनी समस्या बोलिए — बिजली, पानी, सड़क, स्वास्थ्य, पानी की टंकी, स्कूल, आदि।
              </p>
            </header>

            <div className="surface space-y-3 p-4">
              <h2 className="text-sm font-bold text-ink-800">कैसे काम करता है</h2>
              <ol className="space-y-2 text-sm text-ink-600">
                <li className="flex gap-2">
                  <span className="font-bold text-brand-700">1.</span>
                  माइक दबाकर अपनी समस्या बोलिए — जैसे “गाँव का ट्रांसफॉर्मर 4 दिन से जला पड़ा है”
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-brand-700">2.</span>
                  जनवाणी ज़िला, ब्लॉक, गाँव और मोबाइल नंबर पूछ लेगी
                </li>
                <li className="flex gap-2">
                  <span className="font-bold text-brand-700">3.</span>
                  शिकायत संख्या मिलेगी — वही नंबर DM डैशबोर्ड पर तुरंत दिखेगा
                </li>
              </ol>
              <button
                type="button"
                className="btn btn-primary w-full"
                onClick={() => {
                  setTab("voice");
                  inputRef.current?.focus();
                }}
              >
                🎙️ बोलकर शिकायत करें
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {[
                { icon: "⚡", label: "बिजली" },
                { icon: "💧", label: "पानी" },
                { icon: "🛣️", label: "सड़क" },
                { icon: "🏥", label: "स्वास्थ्य" },
                { icon: "🧹", label: "सफाई" },
                { icon: "🎓", label: "शिक्षा" },
              ].map((item) => (
                <button
                  key={item.label}
                  type="button"
                  className="surface flex items-center gap-2 px-4 py-3 text-sm font-semibold text-ink-800 hover:bg-ink-50"
                  onClick={() => {
                    setTab("voice");
                    void send(`${item.label} से जुड़ी शिकायत करानी है`);
                  }}
                >
                  <span aria-hidden="true" className="text-xl">
                    {item.icon}
                  </span>
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>

      <BottomNav active={tab} onChange={setTab} badge={messages.filter((m) => m.cards.some((c) => c.type === "ticket")).length} />
    </div>
  );
}
