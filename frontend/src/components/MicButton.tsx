import { useEffect, useRef, useState } from "react";

import Waveform from "./Waveform";

interface MicButtonProps {
  recording: boolean;
  processing: boolean;
  disabled?: boolean;
  onStart: () => void;
  onStop: () => void;
}

const MIN_HOLD_MS = 350;

/**
 * The single most important control in the product: a large, obvious, forgiving
 * microphone button. Press-and-hold to record, release to send.
 */
export default function MicButton({
  recording,
  processing,
  disabled = false,
  onStart,
  onStop,
}: MicButtonProps) {
  const [held, setHeld] = useState(false);
  const startedAt = useRef<number>(0);

  useEffect(() => {
    if (!recording && held) setHeld(false);
  }, [recording, held]);

  const begin = () => {
    if (disabled || processing) return;
    startedAt.current = Date.now();
    setHeld(true);
    onStart();
  };

  const end = () => {
    if (!held) return;
    setHeld(false);
    if (Date.now() - startedAt.current < MIN_HOLD_MS) return;
    onStop();
  };

  const label = processing
    ? "सोच रहा है..."
    : recording
      ? "बोलिए... छोड़ने पर भेजा जाएगा"
      : "बोलकर शुरू कीजिए";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative flex h-28 w-28 items-center justify-center">
        {recording && (
          <span
            className="absolute inset-0 rounded-full bg-brand-400/60 animate-pulse-ring"
            aria-hidden="true"
          />
        )}
        <button
          type="button"
          onPointerDown={begin}
          onPointerUp={end}
          onPointerLeave={held ? end : undefined}
          onPointerCancel={() => setHeld(false)}
          onKeyDown={(event) => {
            if (event.key === " " || event.key === "Enter") {
              event.preventDefault();
              if (!held) begin();
              else end();
            }
          }}
          onKeyUp={(event) => {
            if (event.key === " " || event.key === "Enter") end();
          }}
          disabled={disabled || processing}
          aria-label={label}
          className={`relative flex h-24 w-24 items-center justify-center rounded-full text-white shadow-lift transition-all duration-200 select-none ${
            processing
              ? "bg-ink-400 cursor-wait"
              : recording
                ? "bg-alert-600 scale-105"
                : "bg-brand-700 hover:bg-brand-800 active:scale-95"
          } ${disabled ? "opacity-50" : ""}`}
        >
          {processing ? (
            <span className="h-7 w-7 rounded-full border-[3px] border-white/40 border-t-white animate-spin" />
          ) : (
            <svg viewBox="0 0 24 24" className="h-10 w-10" fill="currentColor" aria-hidden="true">
              <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
              <path d="M18 11a1 1 0 1 0-2 0 4 4 0 0 1-8 0 1 1 0 1 0-2 0 6 6 0 0 0 5 5.91V19H9a1 1 0 1 0 0 2h6a1 1 0 1 0 0-2h-2v-2.09A6 6 0 0 0 18 11Z" />
            </svg>
          )}
        </button>
      </div>

      <div className="flex h-9 items-center justify-center">
        {recording ? (
          <Waveform active bars={24} />
        ) : (
          <p className="text-sm font-medium text-ink-500">{label}</p>
        )}
      </div>
    </div>
  );
}
