"use client";
// Day 6 — English first, Korean second (ARCHITECTURE §2.12). One dictionary; the choice is kept in this browser.
import { useSyncExternalStore } from "react";
import type { Level, Severity } from "./api";

export type Lang = "en" | "ko";

const STORE_KEY = "sumteo.lang";
const listeners = new Set<() => void>();

function read(): Lang {
  try {
    return localStorage.getItem(STORE_KEY) === "ko" ? "ko" : "en";
  } catch {
    return "en";
  }
}

export function setLang(lang: Lang): void {
  try {
    localStorage.setItem(STORE_KEY, lang);
  } catch {
    // private window: the switch still works until reload
  }
  listeners.forEach((f) => f());
}

const subscribe = (f: () => void) => {
  listeners.add(f);
  return () => {
    listeners.delete(f);
  };
};

export function useLang(): Lang {
  return useSyncExternalStore(subscribe, read, () => "en");
}

const EN = {
  title: "Crowd Safety Monitor",
  area: "Itaewon · Yongsan-gu",
  live: "Live",
  reconnecting: "Reconnecting…",
  events: "Events",
  filters: { all: "All", open: "Open", critical: "Critical", warning: "Warning" },
  noEvents: "No alerts yet.",
  acknowledge: "Acknowledge",
  acknowledgedBy: "Acknowledged",
  noResponse: "NO RESPONSE",
  seoul: "Seoul overview",
  hotspot: "Monitored area: Itaewon, Yongsan-gu",
  camerasOnline: "Cameras online",
  openAlerts: "Open alerts",
  peakDensity: "Peak density",
  peopleNow: "People now",
  densityChart: "Density, last 5 min",
  cameras: "Cameras",
  snapshot: "Snapshot at the alert (faces blurred)",
  noSnapshot: "No snapshot for this event",
  when: "Time",
  videoTime: "Video time",
  notYet: "not yet",
  density: "Density",
  people: "People",
  speed: "Speed",
  zone: "Zone",
  enlarge: "Enlarge",
  close: "Close",
  notCalibrated: "not calibrated",
  cameraProblem: "Camera problem — zones hold last level",
  blurred: "faces blurred",
  moreWaiting: "more waiting",
  legend: "Crowd level",
  legendNote: "Thresholds per camera, in people/m²",
  demo: (y: number, o: number, r: number) => `DEMO THRESHOLDS: yellow ${y} / orange ${o} / red ${r} /m² (not the real levels)`,
  levels: { GREEN: "Normal", YELLOW: "Caution", ORANGE: "Alert", RED: "Severe" } as Record<Level, string>,
  severity: { INFO: "Info", WARNING: "Warning", CRITICAL: "Critical" } as Record<Severity, string>,
  rules: {
    CROWD_LEVEL: "Crowd level",
    STAGNATION: "Stagnation",
    DENSITY_RISING: "Density rising",
    COUNTER_FLOW: "Counter-flow",
    INFLOW_IMBALANCE: "Inflow imbalance",
    CAMERA_HEALTH: "Camera problem",
    ALL_CLEAR: "All clear",
  } as Record<string, string>,
  camerasOnlineTicker: "cameras online · stock clips at demo positions",
};

export type Dict = typeof EN;

const KO: Dict = {
  title: "인파 안전 관제",
  area: "이태원 · 용산구",
  live: "실시간",
  reconnecting: "재연결 중…",
  events: "이벤트",
  filters: { all: "전체", open: "미확인", critical: "심각", warning: "경고" },
  noEvents: "아직 경보가 없습니다.",
  acknowledge: "확인",
  acknowledgedBy: "확인됨",
  noResponse: "무응답",
  seoul: "서울 개요",
  hotspot: "관제 구역: 용산구 이태원",
  camerasOnline: "가동 카메라",
  openAlerts: "미확인 경보",
  peakDensity: "최고 밀도",
  peopleNow: "현재 인원",
  densityChart: "밀도 (최근 5분)",
  cameras: "카메라",
  snapshot: "경보 시점 스냅샷 (얼굴 흐림 처리)",
  noSnapshot: "이 이벤트의 스냅샷 없음",
  when: "시각",
  videoTime: "영상 시각",
  notYet: "미확인",
  density: "밀도",
  people: "인원",
  speed: "속도",
  zone: "구역",
  enlarge: "크게 보기",
  close: "닫기",
  notCalibrated: "보정 전",
  cameraProblem: "카메라 이상 — 구역은 마지막 단계 유지",
  blurred: "얼굴 흐림 처리",
  moreWaiting: "건 대기",
  legend: "밀집 단계",
  legendNote: "기준값은 카메라별, 단위 명/m²",
  demo: (y: number, o: number, r: number) => `데모 기준값: 주의 ${y} / 경계 ${o} / 심각 ${r} 명/m² (실제 기준 아님)`,
  levels: { GREEN: "관심", YELLOW: "주의", ORANGE: "경계", RED: "심각" },
  severity: { INFO: "알림", WARNING: "경고", CRITICAL: "심각" },
  rules: {
    CROWD_LEVEL: "밀집 단계",
    STAGNATION: "정체",
    DENSITY_RISING: "급증",
    COUNTER_FLOW: "역류",
    INFLOW_IMBALANCE: "유입 과다",
    CAMERA_HEALTH: "카메라 이상",
    ALL_CLEAR: "해제",
  },
  camerasOnlineTicker: "대 가동 · 스톡 영상, 데모 위치",
};

export const dict: Record<Lang, Dict> = { en: EN, ko: KO };
