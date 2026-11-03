// Day 5 — getting noticed: a beep (Web Audio, no file) and a browser notification that works in a background tab.
import type { SumteoEvent } from "./api";

let audio: AudioContext | null = null;

/** Call from a click: browsers only allow sound after a user gesture. */
export function unlockAlerts(): void {
  audio ??= new AudioContext();
  void audio.resume();
  if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
}

export const soundReady = () => audio?.state === "running";

function beep(freq: number, start: number, length: number): void {
  if (!audio) return;
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.25, audio.currentTime + start);
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + start + length);
  osc.connect(gain).connect(audio.destination);
  osc.start(audio.currentTime + start);
  osc.stop(audio.currentTime + start + length);
}

export function announce(event: SumteoEvent, escalated = false): void {
  if (event.severity === "INFO") return;
  const critical = event.severity === "CRITICAL";
  const tones = critical ? [880, 660, 880, 660] : [660];
  tones.forEach((f, i) => beep(f, i * 0.25, 0.22));
  if ("Notification" in window && Notification.permission === "granted") {
    const what = (event.details.reasons ?? [event.type]).join(" + ");
    new Notification(`${escalated ? "NO RESPONSE — " : ""}${event.severity} · ${event.zone_id ?? event.camera_id}`, {
      body: `${what} on ${event.camera_id}`,
      tag: event.id,
      requireInteraction: critical,
    });
  }
}
