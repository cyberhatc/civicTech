import { useEffect, useRef, useState } from "react";

interface WaveformProps {
  active: boolean;
  bars?: number;
  className?: string;
}

/** Animated equaliser used while the microphone is recording. */
export default function Waveform({ active, bars = 28, className = "" }: WaveformProps) {
  const [phases, setPhases] = useState<number[]>(() => new Array(bars).fill(0).map(() => Math.random()));
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      if (timer.current) window.clearInterval(timer.current);
      timer.current = null;
      return;
    }
    timer.current = window.setInterval(() => {
      setPhases((prev) => prev.map(() => Math.random()));
    }, 120);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, [active]);

  return (
    <div
      className={`flex items-center justify-center gap-[3px] ${className}`}
      aria-hidden="true"
    >
      {Array.from({ length: bars }).map((_, index) => {
        const phase = phases[index] ?? 0;
        const height = active ? 6 + phase * 26 : 4;
        return (
          <span
            key={index}
            className={`w-[3px] rounded-full transition-[height] duration-100 ${
              active ? "bg-white/85" : "bg-white/30"
            }`}
            style={{ height: `${height}px` }}
          />
        );
      })}
    </div>
  );
}
