"use client";
import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { soundReady, unlockAlerts } from "@/lib/alert";
import type { Role } from "@/lib/api";

export function TopBar({ role, connected }: { role: Role; connected: boolean }) {
  return (
    <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
      <Link href="/" className="font-bold">숨터 Sumteo</Link>
      <span className="text-sm text-zinc-400">
        {role === "admin" ? "Admin · 관제실" : "Security · 현장"} ·{" "}
        <span className={connected ? "text-emerald-400" : "text-red-400"}>{connected ? "live" : "reconnecting…"}</span>
      </span>
    </header>
  );
}

/** After a page reload the browser blocks sound until a click; offer that click. */
export function SoundGate({ light = false }: { light?: boolean }) {
  const audioOn = useSyncExternalStore(noSubscribe, soundReady, () => true);
  const [clicked, setClicked] = useState(false);
  if (audioOn || clicked) return null;
  return (
    <button
      onClick={() => {
        unlockAlerts();
        setClicked(true);
      }}
      className={
        light
          ? "z-20 w-full border-b border-[#F0D9A8] bg-[#FFF6E5] py-1.5 text-[13px] font-medium text-[#7A4B00]"
          : "w-full bg-amber-500 py-2 text-sm font-semibold text-black"
      }
    >
      Tap to turn on alert sound and notifications
    </button>
  );
}

const noSubscribe = () => () => {};
