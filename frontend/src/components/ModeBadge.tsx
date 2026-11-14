import type { Health } from "@/lib/types";

interface ModeBadgeProps {
  health: Health | null;
}

function Dot({ className }: { className: string }) {
  return <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${className}`} />;
}

/** Shows whether the assistant is running on a live model or the offline engine. */
export default function ModeBadge({ health }: ModeBadgeProps) {
  if (!health) {
    return (
      <span className="chip bg-ink-100 text-ink-500">
        <Dot className="bg-ink-300" />
        जुड़ रहा है...
      </span>
    );
  }

  const live = health.mode === "live";
  const llmOk = health.llm.available;
  const asrOk = health.asr.available;
  const ttsOk = health.tts.edgeTtsAvailable || health.tts.bhashiniAvailable;

  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`chip ${live ? "bg-brand-100 text-brand-800" : "bg-saffron-100 text-saffron-700"}`}
        title={live ? "Live model active" : "Offline deterministic engine - no API key configured"}
      >
        <Dot className={live ? "bg-brand-500" : "bg-saffron-500"} />
        {live ? "LIVE" : "OFFLINE"}
      </span>
      <span className="hidden gap-1.5 sm:flex">
        <span
          className={`chip ${llmOk ? "bg-brand-50 text-brand-700" : "bg-ink-100 text-ink-500"}`}
          title="Language model"
        >
          LLM {llmOk ? "✓" : "—"}
        </span>
        <span
          className={`chip ${asrOk ? "bg-brand-50 text-brand-700" : "bg-ink-100 text-ink-500"}`}
          title="Speech recognition"
        >
          ASR {asrOk ? "✓" : "—"}
        </span>
        <span
          className={`chip ${ttsOk ? "bg-brand-50 text-brand-700" : "bg-ink-100 text-ink-500"}`}
          title="Speech synthesis"
        >
          TTS {ttsOk ? "✓" : "—"}
        </span>
      </span>
    </div>
  );
}
