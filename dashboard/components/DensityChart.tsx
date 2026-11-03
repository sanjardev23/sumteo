"use client";
// Day 5 — people/m² per zone over the last minutes, on the camera's own level bands.
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LEVEL_COLOR, getMetrics, type Camera } from "@/lib/api";
import type { Point } from "@/lib/useLive";

const WINDOW_S = 300;

export function DensityChart({ camera, zoneId, live }: { camera: Camera; zoneId: string; live: Point[] }) {
  const [history, setHistory] = useState<Point[]>([]);
  const zone = camera.zones.find((z) => z.id === zoneId);

  useEffect(() => {
    getMetrics(camera.id, Date.now() / 1000 - WINDOW_S).then((rows) =>
      setHistory(rows.filter((r) => r.zone_id === zoneId).map((r) => ({ t: r.wall_ts, density: r.density_ppm2 }))),
    );
  }, [camera.id, zoneId]);

  // Stored rows up to where the live stream (one point a second over the WebSocket) begins.
  const firstLive = live[0]?.t ?? Infinity;
  const points = [...history.filter((p) => p.t < firstLive), ...live];
  const th = zone?.thresholds;
  if (!th) return <p className="text-sm text-zinc-500">{zoneId}: not calibrated</p>;
  const top = Math.max(th.red * 1.25, ...points.map((p) => p.density * 1.1));
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <ReferenceArea y1={0} y2={th.yellow} fill={LEVEL_COLOR.GREEN} fillOpacity={0.12} />
          <ReferenceArea y1={th.yellow} y2={th.orange} fill={LEVEL_COLOR.YELLOW} fillOpacity={0.14} />
          <ReferenceArea y1={th.orange} y2={th.red} fill={LEVEL_COLOR.ORANGE} fillOpacity={0.16} />
          <ReferenceArea y1={th.red} y2={top} fill={LEVEL_COLOR.RED} fillOpacity={0.18} />
          <CartesianGrid stroke="#27272a" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(t) => new Date(t * 1000).toLocaleTimeString([], { minute: "2-digit", second: "2-digit" })}
            stroke="#71717a"
            fontSize={11}
          />
          <YAxis domain={[0, top]} stroke="#71717a" fontSize={11} tickFormatter={(v) => v.toFixed(1)} />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
            labelFormatter={(t) => new Date(Number(t) * 1000).toLocaleTimeString()}
            formatter={(v) => [`${Number(v).toFixed(2)} /m²`, "density"]}
          />
          <Line type="monotone" dataKey="density" stroke="#fafafa" dot={false} strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
