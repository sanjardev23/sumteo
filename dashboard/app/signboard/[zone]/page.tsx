// Day 5 (extra) — public signboard: full-screen level + short instruction in Korean and English (§2.12).
import { Suspense } from "react";
import { Board } from "./Board";

export default function Signboard({ params }: { params: Promise<{ zone: string }> }) {
  // The zone comes from the URL at request time, so the board renders inside Suspense (Next cacheComponents).
  return (
    <Suspense fallback={<main className="flex min-h-screen items-center justify-center text-zinc-500">…</main>}>
      <Board params={params} />
    </Suspense>
  );
}
