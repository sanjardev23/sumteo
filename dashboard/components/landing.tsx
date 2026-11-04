"use client";
// Day 6 — landing page pieces: scroll reveal, the density-zone illustration and the pipeline. Motion follows
// the design-engineering rules: transform/opacity only, a strong ease-out, short staggers, off for reduced motion.
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { LEVEL_COLOR, type Level } from "@/lib/api";
import type { Dict } from "@/lib/i18n";

/** Fades and lifts its content in once, when it scrolls into view. */
export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -80px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} data-shown={shown} className={`sumteo-reveal ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

const reducedQuery = "(prefers-reduced-motion: reduce)";
const subscribeReduced = (f: () => void) => {
  const m = window.matchMedia(reducedQuery);
  m.addEventListener("change", f);
  return () => m.removeEventListener("change", f);
};
const useReducedMotion = () =>
  useSyncExternalStore(subscribeReduced, () => window.matchMedia(reducedQuery).matches, () => false);

// Steps of the illustration: people per m² and the level each maps to (configs/default.yaml real thresholds:
// yellow 2, orange 4, red 5). A generic zone, on purpose: the 2022 event is never re-enacted (DATA.md §2).
const STEPS: { density: number; level: Level }[] = [
  { density: 1, level: "GREEN" },
  { density: 2, level: "YELLOW" },
  { density: 4, level: "ORANGE" },
  { density: 5, level: "RED" },
  { density: 6, level: "RED" },
];
const ZONE_W_M = 10;
const ZONE_H_M = 4;
const AREA = ZONE_W_M * ZONE_H_M;
const MAX_DOTS = Math.round(STEPS[STEPS.length - 1].density * AREA);

// Fixed pseudo-random positions (same on server and client), in metres inside the stretch.
const DOTS = Array.from({ length: MAX_DOTS }, (_, i) => {
  const r = (n: number) => {
    const x = Math.sin(i * 12.9898 + n * 78.233) * 43758.5453;
    return x - Math.floor(x);
  };
  return { x: 0.15 + r(1) * (ZONE_W_M - 0.3), y: 0.15 + r(2) * (ZONE_H_M - 0.3) };
});

/** A generic 10 × 4 m zone seen from above, filling with people step by step — what each density means. */
export function DensityZone({ t }: { t: Dict }) {
  const reduced = useReducedMotion();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setTick((n) => n + 1), 1800);
    return () => clearInterval(id);
  }, [reduced]);
  const step = reduced ? STEPS.length - 1 : Math.min(tick % (STEPS.length + 2), STEPS.length - 1); // hold the last step
  const { density, level } = STEPS[step];
  const visible = Math.round(density * AREA);
  const px = 64; // px per metre in the drawing
  const l = t.landing;
  return (
    <figure className="overflow-hidden rounded-lg border border-[#D5DBE3] bg-white">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[#E3E8EE] px-4 py-3">
        <figcaption className="text-[13px] font-semibold">{l.zoneTitle}</figcaption>
        <div className="flex items-baseline gap-2">
          <span className="text-[22px] font-semibold tabular-nums" style={{ color: level === "YELLOW" ? "#8A6A00" : LEVEL_COLOR[level] }}>
            {density}
          </span>
          <span className="text-[12px] text-[#5B6675]">{l.perM2}</span>
          <span
            className="rounded px-1.5 py-0.5 text-[11px] font-semibold transition-colors duration-300"
            style={{ background: LEVEL_COLOR[level], color: level === "YELLOW" || level === "ORANGE" ? "#1B2430" : "#fff" }}
          >
            {t.levels[level]}
          </span>
        </div>
      </div>
      <div className="overflow-x-auto px-4 py-4">
        <svg viewBox={`-8 -8 ${ZONE_W_M * px + 16} ${ZONE_H_M * px + 32}`} className="w-full min-w-[480px]" role="img" aria-label={l.zoneAria(density, t.levels[level])}>
          <rect x="0" y="0" width={ZONE_W_M * px} height={ZONE_H_M * px} rx="6" fill="#F4F6F9" stroke="#9AA4B2" strokeWidth="2" strokeDasharray="6 5" />
          {DOTS.map((d, i) => (
            <circle
              key={i}
              cx={d.x * px}
              cy={d.y * px}
              r={5.2}
              className="sumteo-dot"
              data-on={i < visible}
              style={{ fill: LEVEL_COLOR[level], transitionDelay: reduced ? "0ms" : `${(i % 40) * 6}ms` }}
            />
          ))}
          <text x={ZONE_W_M * px} y={ZONE_H_M * px + 18} textAnchor="end" fontSize="12" fill="#5B6675">
            {l.zoneScale}
          </text>
        </svg>
      </div>
      <p className="border-t border-[#E3E8EE] px-4 py-2.5 text-[11px] leading-relaxed text-[#5B6675]">{l.zoneNote}</p>
    </figure>
  );
}

/** Camera → AI → level & alert → guard, with a pulse travelling the line. */
export function Pipeline({ t }: { t: Dict }) {
  const l = t.landing;
  const steps = [
    { title: l.pipeCamera, text: l.pipeCameraText, icon: <CctvIcon /> },
    { title: l.pipeAi, text: l.pipeAiText, icon: <ChipIcon /> },
    { title: l.pipeAlert, text: l.pipeAlertText, icon: <BellIcon /> },
    { title: l.pipeGuard, text: l.pipeGuardText, icon: <WalkIcon /> },
  ];
  return (
    <div className="relative">
      <div className="pointer-events-none absolute left-[12%] right-[12%] top-7 hidden h-0.5 overflow-hidden bg-[#D5DBE3] [container-type:inline-size] md:block">
        <span className="sumteo-pulse absolute top-0 h-0.5 w-24 bg-[#1D4F91]" />
      </div>
      <ol className="relative grid gap-4 md:grid-cols-4">
        {steps.map((s, i) => (
          <li key={s.title}>
            <Reveal delay={i * 60}>
              <div className="flex flex-col items-center text-center">
                <span className="grid size-14 place-items-center rounded-full border-2 border-[#1D4F91] bg-white text-[#1D4F91]">{s.icon}</span>
                <span className="mt-1 text-[11px] font-semibold text-[#8A94A3]">{i + 1}</span>
                <span className="text-[15px] font-semibold">{s.title}</span>
                <span className="mt-1 max-w-[220px] text-[12px] leading-relaxed text-[#5B6675]">{s.text}</span>
              </div>
            </Reveal>
          </li>
        ))}
      </ol>
    </div>
  );
}

const svg = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function CctvIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <path d="M16.75 12h3.632a1 1 0 0 1 .894 1.447l-2.034 4.069a1 1 0 0 1-1.708.134l-2.124-2.97" />
      <path d="M17.106 9.053a1 1 0 0 1 .447 1.341l-3.106 6.211a1 1 0 0 1-1.342.447L3.61 12.3a2.92 2.92 0 0 1-1.3-3.91L3.69 5.6a2.92 2.92 0 0 1 3.92-1.3z" />
      <path d="M2 19h3.76a2 2 0 0 0 1.8-1.1L9 15" />
      <path d="M2 21v-4" />
      <path d="M7 9h.01" />
    </svg>
  );
}

export function ChipIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <rect x="5" y="5" width="14" height="14" rx="2" />
      <path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
    </svg>
  );
}

export function BellIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

export function WalkIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <circle cx="13" cy="4" r="2" />
      <path d="m9 20 3-6 3 2v4M11 9l-3 3 2 2M11 9l4 2 2-3M11 9l1 5" />
    </svg>
  );
}

export function FlowIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <path d="M3 8h13l-3-3M21 16H8l3 3" />
    </svg>
  );
}

export function LevelsIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <path d="M4 20V14M10 20V10M16 20V6M22 20V2" />
    </svg>
  );
}

export function MapIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" />
    </svg>
  );
}

export function ShieldIcon({ className = "size-6" }: { className?: string }) {
  return (
    <svg {...svg} className={className}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}
