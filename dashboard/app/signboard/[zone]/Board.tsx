"use client";
// Day 5 (extra) — the signboard itself; polls GET /signboard/{zone} every 2 s.
import { use, useEffect, useState } from "react";
import { API, LEVEL_COLOR, type Level } from "@/lib/api";

interface Board { zone: string; level: Level; label: string; message_ko: string; message_en: string; demo: boolean }

export function Board({ params }: { params: Promise<{ zone: string }> }) {
  const { zone } = use(params);
  const [board, setBoard] = useState<Board | null>(null);
  useEffect(() => {
    const load = () => fetch(`${API}/signboard/${zone}`).then((r) => (r.ok ? r.json() : null)).then(setBoard).catch(() => {});
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [zone]);
  if (!board) return <main className="flex min-h-screen items-center justify-center text-zinc-500">…</main>;
  const dark = board.level === "YELLOW" || board.level === "ORANGE";
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center gap-6 p-8 text-center"
      style={{ background: LEVEL_COLOR[board.level], color: dark ? "#111" : "#fff" }}
    >
      <div className="text-7xl font-black">{board.label}</div>
      <div className="text-5xl font-bold">{board.message_ko}</div>
      <div className="text-3xl">{board.message_en}</div>
      {board.demo && <div className="rounded bg-black/70 px-3 py-1 text-sm font-semibold text-red-400">DEMO THRESHOLDS (not the real levels)</div>}
    </main>
  );
}
