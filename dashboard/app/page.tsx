"use client";
// Day 5 — role pick (demo only; a real deployment needs proper accounts, ARCHITECTURE §2.8).
import { useRouter } from "next/navigation";
import { unlockAlerts } from "@/lib/alert";
import type { Role } from "@/lib/api";

const ROLES: { role: Role; title: string; ko: string; text: string }[] = [
  { role: "security", title: "Security", ko: "현장 보안요원", text: "On-site guards · phone or tablet · WARNING and CRITICAL alerts for the zones" },
  { role: "admin", title: "Admin", ko: "관제실", text: "Control room · all cameras, priority pop-ups, history, charts" },
];

export default function Login() {
  const router = useRouter();
  const pick = (role: Role) => {
    unlockAlerts(); // this click allows sound and asks for notification permission
    router.push(`/${role}`);
  };
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">숨터 Sumteo</h1>
        <p className="text-zinc-400">AI crowd-safety early warning · 인파 안전 조기경보</p>
      </div>
      {ROLES.map((r) => (
        <button
          key={r.role}
          onClick={() => pick(r.role)}
          className="rounded-xl border border-zinc-700 bg-zinc-900 p-5 text-left hover:border-zinc-400"
        >
          <div className="text-xl font-semibold">
            {r.title} <span className="text-zinc-400">· {r.ko}</span>
          </div>
          <div className="text-sm text-zinc-400">{r.text}</div>
        </button>
      ))}
      <p className="text-xs text-zinc-500">Demo login: pick a role. Faces are blurred; no identities are stored.</p>
    </main>
  );
}
