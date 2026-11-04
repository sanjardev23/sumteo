"use client";
// Day 5 — after a page reload the browser blocks sound until a click; this bar offers that click (§2.12).
import { useState, useSyncExternalStore } from "react";
import { soundReady, unlockAlerts } from "@/lib/alert";

export function SoundGate() {
  const audioOn = useSyncExternalStore(noSubscribe, soundReady, () => true);
  const [clicked, setClicked] = useState(false);
  if (audioOn || clicked) return null;
  return (
    <button
      onClick={() => {
        unlockAlerts();
        setClicked(true);
      }}
      className="z-20 w-full border-b border-[#F0D9A8] bg-[#FFF6E5] py-1.5 text-[13px] font-medium text-[#7A4B00]"
    >
      Tap to turn on alert sound and notifications
    </button>
  );
}

const noSubscribe = () => () => {};
