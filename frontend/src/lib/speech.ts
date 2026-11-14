/**
 * Browser speech fallback.
 *
 * When the server cannot synthesise audio (no TTS provider, offline demo, rural
 * connection dropped) the app still *speaks* using the Web Speech API, which ships
 * with every modern browser and supports hi-IN.
 */

let voices: SpeechSynthesisVoice[] = [];

function loadVoices(): SpeechSynthesisVoice[] {
  if (typeof speechSynthesis === "undefined") return [];
  voices = speechSynthesis.getVoices();
  return voices;
}

if (typeof speechSynthesis !== "undefined") {
  loadVoices();
  speechSynthesis.onvoiceschanged = () => loadVoices();
}

function pickVoice(lang: string): SpeechSynthesisVoice | undefined {
  const list = voices.length ? voices : loadVoices();
  const want = lang.toLowerCase().startsWith("hi") ? "hi-in" : lang.toLowerCase();
  return (
    list.find((v) => v.lang.toLowerCase() === want) ??
    list.find((v) => v.lang.toLowerCase().startsWith(want.slice(0, 2))) ??
    list.find((v) => v.lang.toLowerCase().startsWith("hi"))
  );
}

export function browserSpeechSupported(): boolean {
  return typeof speechSynthesis !== "undefined";
}

/** Speak the text. Returns false when the browser cannot. */
export function speak(text: string, lang = "hi-IN"): boolean {
  if (!text || !browserSpeechSupported()) return false;
  try {
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 0.96;
    utterance.pitch = 1;
    const voice = pickVoice(lang);
    if (voice) utterance.voice = voice;
    speechSynthesis.speak(utterance);
    return true;
  } catch {
    return false;
  }
}

export function stopSpeaking(): void {
  if (browserSpeechSupported()) speechSynthesis.cancel();
}
