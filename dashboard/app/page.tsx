"use client";
// Day 5 — role pick (demo only; a real deployment needs proper accounts, ARCHITECTURE §2.8).
// Day 6 — public-service landing (§2.12): why Sumteo exists (10.29 Itaewon, told with facts and the memorial — never
// images of that night, DATA.md §2), how it responds, what it does, and the role pick. Our own branding only.
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BellIcon,
  CctvIcon,
  DensityZone,
  FlowIcon,
  LevelsIcon,
  MapIcon,
  Pipeline,
  Reveal,
  ShieldIcon,
  WalkIcon,
} from "@/components/landing";
import { CARD, FONT, LangSwitch } from "@/components/wall";
import { unlockAlerts } from "@/lib/alert";
import { API, getEvents, type Camera, type Role } from "@/lib/api";
import { dict, useLang } from "@/lib/i18n";

interface Status {
  cameras: number;
  replay: number;
  open: number;
}

const FEATURE_ICONS = [LevelsIcon, FlowIcon, BellIcon, MapIcon, WalkIcon, ShieldIcon];

export default function Landing() {
  const router = useRouter();
  const t = dict[useLang()];
  const l = t.landing;
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([fetch(`${API}/cameras`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : [])), getEvents(200)])
      .then(([cameras, events]: [Camera[], Awaited<ReturnType<typeof getEvents>>]) => {
        if (!alive) return;
        setStatus({
          cameras: cameras.length,
          replay: cameras.filter((c) => c.mode === "replay").length,
          // Last hour only: older open rows from earlier runs would overstate what needs attention now.
          open: events.filter((e) => e.severity !== "INFO" && !e.acknowledged && e.created_at > Date.now() / 1000 - 3600).length,
        });
      })
      .catch(() => alive && setStatus({ cameras: 0, replay: 0, open: 0 }));
    return () => {
      alive = false;
    };
  }, []);

  const pick = (role: Role) => {
    unlockAlerts(); // this click allows sound and asks for notification permission
    router.push(`/${role}`);
  };

  return (
    <div className="min-h-screen bg-[#F4F6F9] text-[#1B2430]" style={{ fontFamily: FONT }}>
      <header className="sticky top-0 z-30 border-b border-[#D5DBE3] bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-5 py-3">
          <div className="flex items-center gap-3">
            <Mark />
            <div className="leading-tight">
              <div className="text-[18px] font-semibold tracking-tight">
                Sumteo <span className="font-normal text-[#5B6675]">숨터</span>
              </div>
              <div className="text-[12px] text-[#5B6675]">{l.platform}</div>
            </div>
          </div>
          <div className="flex items-center gap-4 text-[13px]">
            <a href="#roles" className="sumteo-press hidden rounded bg-[#1D4F91] px-3 py-1.5 font-medium text-white hover:bg-[#163E73] sm:inline-block">
              {l.enterRoles}
            </a>
            <LangSwitch />
          </div>
        </div>
      </header>

      <section className="bg-[#1D4F91] text-white">
        <div className="mx-auto max-w-5xl px-5 py-12">
          <Reveal>
            <h1 className="max-w-3xl text-balance text-[28px] font-semibold leading-snug sm:text-[36px]">{l.heroTitle}</h1>
          </Reveal>
          <Reveal delay={60}>
            <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-[#D6E3F5]">{l.heroText}</p>
          </Reveal>
          <Reveal delay={120}>
            <dl className="mt-7 grid max-w-xl grid-cols-3 gap-3">
              <Stat label={l.statCameras} value={status ? String(status.cameras) : "—"} />
              <Stat label={l.statOpen} value={status ? String(status.open) : "—"} />
              <Stat label={l.statMode} value={status ? (status.replay ? l.modeReplay(status.replay) : l.modeLive) : "—"} />
            </dl>
            <p className="mt-2 max-w-xl text-[11px] text-[#C9D8EE]">{l.statNote}</p>
          </Reveal>
        </div>
      </section>

      <main>
        {/* Why: 10.29 Itaewon — facts and the memorial, no images of the night (DATA.md §2) */}
        <section className="mx-auto max-w-5xl px-5 py-14">
          <Kicker>{l.whyKicker}</Kicker>
          <Reveal>
            <h2 className="text-[26px] font-semibold">{l.whyTitle}</h2>
            <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[#3A4553]">{l.whyLead}</p>
          </Reveal>
          <div className="mt-6 grid items-start gap-6 md:grid-cols-[1.05fr_1fr]">
            <Reveal>
              <figure className={`${CARD} overflow-hidden`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/landing/memorial-alley.jpg" alt={l.memorialCaption} className="sumteo-wipe aspect-[4/3] w-full object-cover" />
                <figcaption className="space-y-0.5 px-3 py-2.5">
                  <div className="text-[12px] font-medium">{l.memorialCaption}</div>
                  <a
                    href="https://commons.wikimedia.org/wiki/File:Itaewon_Halloween_crowd_crush_memorial_alley_01.jpg"
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-[#5B6675] underline-offset-2 hover:underline"
                  >
                    {l.memorialCredit}
                  </a>
                </figcaption>
              </figure>
            </Reveal>
            <ol className="space-y-3">
              {l.facts.map((f, i) => (
                <li key={i}>
                  <Reveal delay={i * 60}>
                    <div className={`${CARD} border-l-4 border-l-[#1D4F91] px-4 py-3 text-[14px] leading-relaxed`}>
                      {f.text}
                      <sup className="ml-1 text-[11px] text-[#1D4F91]">
                        <a href={`#src-${f.src}`}>[{f.src}]</a>
                      </sup>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* What density means: a generic zone, never the alley (no re-enactment) */}
        <section className="border-y border-[#D5DBE3] bg-white">
          <div className="mx-auto max-w-5xl px-5 py-14">
            <Reveal>
              <DensityZone t={t} />
            </Reveal>
          </div>
        </section>

        {/* How Sumteo responds: failure → feature */}
        <section className="mx-auto max-w-5xl px-5 py-14">
          <Kicker>{l.respondKicker}</Kicker>
          <Reveal>
            <h2 className="text-[26px] font-semibold">{l.respondTitle}</h2>
          </Reveal>
          <div className="mt-6 space-y-3">
            {l.respond.map((r, i) => (
              <Reveal key={i} delay={i * 60}>
                <div className={`${CARD} grid items-center gap-3 p-4 md:grid-cols-[1fr_auto_1.2fr]`}>
                  <p className="text-[14px] text-[#5B6675]">{r.problem}</p>
                  <span className="hidden text-[20px] text-[#1D4F91] md:block" aria-hidden>
                    →
                  </span>
                  <p className="text-[14px] font-medium">{r.answer}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal>
            <p className="mt-4 rounded-md border border-[#F0D9A8] bg-[#FFF8EA] px-4 py-3 text-[13px] leading-relaxed text-[#6B4A00]">{l.limits}</p>
          </Reveal>
        </section>

        {/* What the platform does */}
        <section className="border-y border-[#D5DBE3] bg-white">
          <div className="mx-auto max-w-5xl px-5 py-14">
            <Kicker>{l.featuresKicker}</Kicker>
            <Reveal>
              <h2 className="text-[26px] font-semibold">{l.featuresTitle}</h2>
            </Reveal>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {l.features.map((f, i) => {
                const Icon = FEATURE_ICONS[i];
                return (
                  <Reveal key={f.title} delay={(i % 3) * 60}>
                    <div className={`${CARD} h-full p-5`}>
                      <span className="grid size-10 place-items-center rounded-lg bg-[#EEF3FA] text-[#1D4F91]">
                        <Icon className="size-5" />
                      </span>
                      <div className="mt-3 text-[15px] font-semibold">{f.title}</div>
                      <p className="mt-1 text-[13px] leading-relaxed text-[#5B6675]">{f.text}</p>
                    </div>
                  </Reveal>
                );
              })}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="mx-auto max-w-5xl px-5 py-14">
          <Kicker>{l.howKicker}</Kicker>
          <Reveal>
            <h2 className="mb-8 text-[26px] font-semibold">{l.howTitle}</h2>
          </Reveal>
          <Pipeline t={t} />
        </section>

        {/* After 2022: Seoul's AI crowd cameras — KOGL Type 4 image shown whole, unmodified, credited */}
        <section className="border-y border-[#D5DBE3] bg-white">
          <div className="mx-auto grid max-w-5xl items-center gap-8 px-5 py-14 md:grid-cols-2">
            <div>
              <Kicker>{l.afterKicker}</Kicker>
              <Reveal>
                <h2 className="text-[26px] font-semibold">{l.afterTitle}</h2>
                <p className="mt-3 text-[14px] leading-relaxed text-[#3A4553]">
                  {l.afterText}
                  <sup className="ml-1 text-[11px] text-[#1D4F91]">
                    <a href="#src-3">[3]</a>
                  </sup>
                </p>
                <p className="mt-3 text-[14px] font-medium leading-relaxed">{l.afterOurs}</p>
              </Reveal>
            </div>
            <Reveal delay={60}>
              <figure className={`${CARD} overflow-hidden`}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/landing/seoul-ai-cctv.png" alt={l.afterCaption} width={760} height={475} className="h-auto w-full" />
                <figcaption className="space-y-0.5 px-3 py-2.5">
                  <div className="text-[12px] font-medium">{l.afterCaption}</div>
                  <a
                    href="https://mediahub.seoul.go.kr/archives/2009275"
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-[#5B6675] underline-offset-2 hover:underline"
                  >
                    {l.afterCredit}
                  </a>
                </figcaption>
              </figure>
            </Reveal>
          </div>
        </section>

        {/* Roles */}
        <section id="roles" className="mx-auto max-w-5xl scroll-mt-20 px-5 py-14">
          <Reveal>
            <h2 className="mb-4 text-[26px] font-semibold">{l.chooseRole}</h2>
          </Reveal>
          <div className="grid gap-4 sm:grid-cols-2">
            <Reveal>
              <RoleCard icon={<MapIcon />} title={l.adminTitle} sub="관제실 · Control room" text={l.adminText} cta={l.enter} onClick={() => pick("admin")} />
            </Reveal>
            <Reveal delay={60}>
              <RoleCard icon={<CctvIcon />} title={l.guardTitle} sub="현장 요원 · Field guard" text={l.guardText} cta={l.enter} onClick={() => pick("security")} />
            </Reveal>
          </div>
        </section>

        {/* Sources */}
        <section className="mx-auto max-w-5xl px-5 pb-12">
          <h2 className="mb-2 text-[13px] font-semibold">{l.sourcesTitle}</h2>
          <ol className="space-y-1 text-[12px] text-[#5B6675]">
            {l.sources.map((s) => (
              <li key={s.n} id={`src-${s.n}`} className="scroll-mt-24">
                [{s.n}]{" "}
                <a href={s.href} target="_blank" rel="noreferrer" className="underline-offset-2 hover:text-[#1D4F91] hover:underline">
                  {s.label}
                </a>
              </li>
            ))}
          </ol>
          <a href={l.seeAlso.href} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[12px] text-[#5B6675] underline-offset-2 hover:text-[#1D4F91] hover:underline">
            {l.seeAlso.label}
          </a>
        </section>
      </main>

      <footer className="border-t border-[#D5DBE3] bg-white">
        <div className="mx-auto max-w-5xl space-y-1.5 px-5 py-6 text-[12px] leading-relaxed text-[#5B6675]">
          <div className="font-medium text-[#1B2430]">Sumteo 숨터 · {l.platform}</div>
          <div>{l.footerNote}</div>
          <div>{l.credit}</div>
        </div>
      </footer>
    </div>
  );
}

function Kicker({ children }: { children: React.ReactNode }) {
  return <div className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-[#1D4F91]">{children}</div>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white/10 px-3 py-2.5 ring-1 ring-white/20">
      <dt className="text-[11px] text-[#C9D8EE]">{label}</dt>
      <dd className="text-[20px] font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function RoleCard({ icon, title, sub, text, cta, onClick }: {
  icon: React.ReactNode; title: string; sub: string; text: string; cta: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`${CARD} sumteo-press group flex h-full w-full gap-4 p-5 text-left transition-[border-color,box-shadow] duration-200 hover:border-[#1D4F91] hover:shadow-md`}
    >
      <span className="grid size-12 shrink-0 place-items-center rounded-lg bg-[#EEF3FA] text-[#1D4F91]">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-[17px] font-semibold">{title}</span>
        <span className="block text-[12px] text-[#5B6675]">{sub}</span>
        <span className="mt-2 block text-[13px] leading-relaxed text-[#3A4553]">{text}</span>
        <span className="mt-3 inline-block text-[13px] font-semibold text-[#1D4F91] group-hover:underline">{cta} →</span>
      </span>
    </button>
  );
}

/** Our own mark: a calm wave inside a rounded square (숨터 = a place to breathe). */
function Mark() {
  return (
    <svg viewBox="0 0 40 40" className="size-9" aria-hidden>
      <rect width="40" height="40" rx="9" fill="#1D4F91" />
      <path d="M8 23c4-5 8-5 12 0s8 5 12 0" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
      <path d="M8 16c4-5 8-5 12 0s8 5 12 0" fill="none" stroke="#9EC0EC" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
