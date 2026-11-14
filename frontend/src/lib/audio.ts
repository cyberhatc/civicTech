import { audioUrl } from "./api";

/** Preferred low-bandwidth audio formats, best first. */
const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

export function supportedMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  for (const candidate of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported?.(candidate)) return candidate;
  }
  return null;
}

export interface Recorder {
  start(): Promise<void>;
  stop(): Promise<Blob | null>;
  cancel(): void;
  readonly active: boolean;
}

export function createRecorder(): Recorder | null {
  if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) return null;
  let recorder: MediaRecorder | null = null;
  let stream: MediaStream | null = null;
  let chunks: BlobPart[] = [];

  return {
    get active() {
      return recorder?.state === "recording";
    },
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const mimeType = supportedMimeType();
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunks = [];
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunks.push(event.data);
      };
      recorder.start();
    },
    async stop() {
      return new Promise<Blob | null>((resolve) => {
        if (!recorder) {
          resolve(null);
          return;
        }
        recorder.onstop = () => {
          const blob = chunks.length ? new Blob(chunks, { type: recorder?.mimeType || "audio/webm" }) : null;
          stream?.getTracks().forEach((track) => track.stop());
          recorder = null;
          stream = null;
          resolve(blob && blob.size > 0 ? blob : null);
        };
        try {
          recorder.stop();
        } catch {
          resolve(null);
        }
      });
    },
    cancel() {
      try {
        recorder?.stop();
      } catch {
        /* ignore */
      }
      stream?.getTracks().forEach((track) => track.stop());
      recorder = null;
      stream = null;
      chunks = [];
    },
  };
}

/** Play a server-generated mp3. Returns false when it cannot be played. */
export async function playServerAudio(path?: string | null): Promise<boolean> {
  const url = audioUrl(path);
  if (!url) return false;
  try {
    const response = await fetch(url);
    if (!response.ok) return false;
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const element = new Audio(objectUrl);
    await new Promise<void>((resolve, reject) => {
      element.onended = () => resolve();
      element.onerror = () => reject(new Error("audio playback failed"));
      element.play().catch(reject);
    });
    URL.revokeObjectURL(objectUrl);
    return true;
  } catch {
    return false;
  }
}

/** Rough amplitude samples for the waveform animation (0..1). */
export function useAnalyserLevel(): number {
  return 0;
}
