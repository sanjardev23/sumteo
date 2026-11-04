"use client";
// Day 5 — live state from WS /ws?role=…: camera states every second, events routed by role, acks, escalations.
import { useCallback, useEffect, useRef, useState } from "react";
import { announce, announceOrder } from "./alert";
import { WS_URL, getEvents, getOrders, type Camera, type Order, type Role, type SumteoEvent } from "./api";

export interface Point {
  t: number; // wall clock, epoch s
  density: number;
}

const SERIES_S = 300;

export interface Live {
  connected: boolean;
  series: Record<string, Point[]>; // "<camera>/<zone>" → density pushed live, once a second
  cameras: Camera[];
  events: SumteoEvent[]; // newest first
  popups: SumteoEvent[]; // open WARNING / CRITICAL for this role: live ones and those still open when we (re)connect
  escalated: Set<string>;
  orders: Order[]; // newest first (§2.8)
  applyAck: (event: SumteoEvent) => void;
  applyOrder: (order: Order) => void;
}

export function useLive(role: Role): Live {
  const [connected, setConnected] = useState(false);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<SumteoEvent[]>([]);
  const [popups, setPopups] = useState<SumteoEvent[]>([]);
  const [escalated, setEscalated] = useState<Set<string>>(new Set());
  const [series, setSeries] = useState<Record<string, Point[]>>({});
  const [orders, setOrders] = useState<Order[]>([]);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyAck = useCallback((event: SumteoEvent) => {
    setEvents((list) => list.map((e) => (e.id === event.id ? event : e)));
    setPopups((list) => list.filter((e) => e.id !== event.id));
  }, []);

  const applyOrder = useCallback((order: Order) => {
    setOrders((list) => [order, ...list.filter((o) => o.id !== order.id)].sort((a, b) => b.created_at - a.created_at));
  }, []);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let closed = false;
    // The history fills the feed; pop-ups come from live alerts and from the open ones the server sends on connect.
    getEvents().then((rows) => setEvents((live) => mergeEvents(live, rows)));
    getOrders().then((rows) => rows.forEach(applyOrder));

    const connect = () => {
      socket = new WebSocket(`${WS_URL}/ws?role=${role}`);
      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry.current = setTimeout(connect, 2000);
      };
      socket.onmessage = (raw) => {
        const msg = JSON.parse(raw.data);
        if (msg.type === "hello") {
          setCameras(msg.cameras);
          const open: SumteoEvent[] = msg.open ?? [];
          setPopups((list) => [...list, ...open.filter((e) => !list.some((x) => x.id === e.id))]);
          setEvents((list) => mergeEvents(list, open));
          if (open.length) announce(open[0]);
        }
        else if (msg.type === "camera") {
          const cam: Camera = msg.camera;
          setCameras((list) => [...list.filter((c) => c.id !== cam.id), cam].sort((a, b) => a.id.localeCompare(b.id)));
          const now = Date.now() / 1000;
          setSeries((all) => {
            const next = { ...all };
            for (const z of cam.zones) {
              if (z.density_ppm2 == null) continue;
              const key = `${cam.id}/${z.id}`;
              next[key] = [...(all[key] ?? []).filter((p) => p.t > now - SERIES_S), { t: now, density: z.density_ppm2 }];
            }
            return next;
          });
        }
        else if (msg.type === "event") {
          const e: SumteoEvent = msg.event;
          setEvents((list) => [e, ...list.filter((x) => x.id !== e.id)].slice(0, 300));
          if (e.severity !== "INFO") setPopups((list) => [e, ...list]);
          announce(e);
        } else if (msg.type === "ack") applyAck(msg.event);
        else if (msg.type === "order") {
          applyOrder(msg.order);
          announceOrder();
        } else if (msg.type === "order_update") applyOrder(msg.order);
        else if (msg.type === "escalation") {
          const e: SumteoEvent = msg.event;
          setEscalated((s) => new Set(s).add(e.id));
          setEvents((list) => [e, ...list.filter((x) => x.id !== e.id)]);
          setPopups((list) => [e, ...list.filter((x) => x.id !== e.id)]);
          announce(e, true);
        }
      };
    };
    connect();
    return () => {
      closed = true;
      if (retry.current) clearTimeout(retry.current);
      socket?.close();
    };
  }, [role, applyAck, applyOrder]);

  return { connected, series, cameras, events, popups, escalated, orders, applyAck, applyOrder };
}

function mergeEvents(live: SumteoEvent[], history: SumteoEvent[]): SumteoEvent[] {
  const seen = new Set(live.map((e) => e.id));
  return [...live, ...history.filter((e) => !seen.has(e.id))].sort((a, b) => b.created_at - a.created_at);
}
