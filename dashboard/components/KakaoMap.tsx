"use client";
// Day 6 — the one place that knows the map provider (Kakao Maps JS SDK, ARCHITECTURE §2.12); swap providers here.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

// The SDK ships no types; it stays behind this file.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Kakao = any;
declare global {
  interface Window {
    kakao?: Kakao;
  }
}

const KEY = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY;
let loading: Promise<Kakao> | null = null;

function loadKakao(): Promise<Kakao> {
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false`;
    s.onload = () => window.kakao.maps.load(() => resolve(window.kakao));
    s.onerror = () => {
      loading = null;
      reject(new Error("Kakao SDK did not load (key, domain list in Kakao Developers, or network)"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

export interface LatLon {
  lat: number;
  lon: number;
}

export interface Pin extends LatLon {
  id: string;
  color: string;
  label: string;
  value?: string;
  pulse?: boolean;
}

export interface Ring extends LatLon {
  radius: number; // meters
  color: string;
}

export function KakaoMap({
  center,
  level,
  pins = [],
  selected = null,
  onPin,
  popup = null,
  focus = null,
  rings = [],
  interactive = true,
  className = "",
}: {
  center: LatLon;
  level: number; // Kakao zoom: 1 = street, 14 = country
  pins?: Pin[];
  selected?: string | null;
  onPin?: (id: string) => void;
  popup?: (LatLon & { node: ReactNode }) | null; // React card anchored under a map point
  focus?: LatLon | null; // pan here whenever a new object is passed
  rings?: Ring[];
  interactive?: boolean;
  className?: string; // must position the box (relative / absolute) and give it a size
}) {
  const box = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<Kakao>(null);
  const [error, setError] = useState(KEY ? "" : "NEXT_PUBLIC_KAKAO_MAP_KEY is not set in dashboard/.env.local");
  const [popupEl, setPopupEl] = useState<HTMLDivElement | null>(null);
  const overlays = useRef(new Map<string, { overlay: Kakao; el: HTMLDivElement }>());
  const onPinRef = useRef(onPin);
  useEffect(() => {
    onPinRef.current = onPin;
  });

  useEffect(() => {
    if (!KEY) return;
    let alive = true;
    loadKakao().then(
      (k) => {
        if (!alive || !box.current) return;
        setMap(
          new k.maps.Map(box.current, {
            center: new k.maps.LatLng(center.lat, center.lon),
            level,
            draggable: interactive,
            scrollwheel: interactive,
            disableDoubleClickZoom: !interactive,
          }),
        );
      },
      (e: Error) => setError(e.message),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the map is made once; later moves go through `focus`
  }, []);

  // Pins are updated in place (states arrive every second), so a click is never lost to a re-created element.
  useEffect(() => {
    if (!map) return;
    const k = window.kakao;
    const seen = new Set<string>();
    for (const p of pins) {
      seen.add(p.id);
      let o = overlays.current.get(p.id);
      if (!o) {
        const el = document.createElement("div");
        el.onclick = () => onPinRef.current?.(p.id);
        const overlay = new k.maps.CustomOverlay({ content: el, xAnchor: 0, yAnchor: 0.5, clickable: true });
        overlay.setMap(map);
        o = { overlay, el };
        overlays.current.set(p.id, o);
      }
      o.overlay.setPosition(new k.maps.LatLng(p.lat, p.lon));
      o.overlay.setZIndex(p.id === selected ? 5 : 3);
      o.el.className = `sumteo-pin${p.id === selected ? " is-selected" : ""}${p.pulse ? " is-pulse" : ""}`;
      o.el.innerHTML =
        `<span class="sumteo-pin-dot" style="--c:${p.color}"></span>` +
        `<span class="sumteo-pin-label">${esc(p.label)}${p.value ? ` <b>${esc(p.value)}</b>` : ""}</span>`;
    }
    for (const [id, o] of overlays.current)
      if (!seen.has(id)) {
        o.overlay.setMap(null);
        overlays.current.delete(id);
      }
  }, [map, pins, selected]);

  useEffect(() => {
    if (!map) return;
    const k = window.kakao;
    const made = rings.map(
      (r) =>
        new k.maps.Circle({
          map,
          center: new k.maps.LatLng(r.lat, r.lon),
          radius: r.radius,
          strokeWeight: 2,
          strokeColor: r.color,
          strokeOpacity: 0.9,
          fillColor: r.color,
          fillOpacity: 0.18,
        }),
    );
    return () => made.forEach((c) => c.setMap(null));
  }, [map, rings]);

  const popLat = popup?.lat;
  const popLon = popup?.lon;
  useEffect(() => {
    if (!map || popLat == null || popLon == null) return;
    const k = window.kakao;
    const el = document.createElement("div");
    el.className = "sumteo-popup";
    // Clicks, drags and scrolls inside the card belong to the card, not the map.
    for (const ev of ["mousedown", "touchstart", "wheel", "dblclick"]) el.addEventListener(ev, (e) => e.stopPropagation());
    const overlay = new k.maps.CustomOverlay({
      content: el,
      position: new k.maps.LatLng(popLat, popLon),
      xAnchor: 0,
      yAnchor: 0,
      zIndex: 10,
      clickable: true,
    });
    overlay.setMap(map);
    // The card hangs below its point: lift the point into the upper third so the whole card stays on screen.
    const at = map.getProjection().containerPointFromCoords(new k.maps.LatLng(popLat, popLon));
    const height = box.current?.clientHeight ?? 0;
    if (at.y > height * 0.35) map.panBy(0, at.y - height * 0.3);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the portal target only exists once the overlay does
    setPopupEl(el);
    return () => {
      overlay.setMap(null);
      setPopupEl(null);
    };
  }, [map, popLat, popLon]);

  // Focused points land in the upper third, like a point with an open card (see above).
  useEffect(() => {
    if (!map || !focus) return;
    const k = window.kakao;
    const projection = map.getProjection();
    const at = projection.containerPointFromCoords(new k.maps.LatLng(focus.lat, focus.lon));
    const height = box.current?.clientHeight ?? 0;
    map.panTo(projection.coordsFromContainerPoint(new k.maps.Point(at.x, at.y + height * 0.2)));
  }, [map, focus]);

  return (
    <div className={className}>
      <div ref={box} className="sumteo-map absolute inset-0" />
      {error && (
        <div className="absolute inset-0 grid place-items-center bg-[#EEF1F4] p-4 text-center text-sm text-[#5B6675]">
          Map unavailable: {error}
        </div>
      )}
      {popupEl && popup && createPortal(popup.node, popupEl)}
    </div>
  );
}

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}
