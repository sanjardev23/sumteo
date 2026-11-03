# Dashboard (Day 5)

Next.js (TypeScript + Tailwind) + Recharts. Talks only to the API (ARCHITECTURE §3).

```bash
python scripts/serve.py --cameras configs/cameras/crowd_demo.yaml configs/cameras/crossing_demo.yaml   # API on :8000
cd dashboard && npm install && npm run dev                                                              # http://127.0.0.1:3000
```

- `/` — pick a role (demo login). The click also allows alert sound and asks for browser notifications.
- `/admin` — control room: camera grid (MJPEG), priority pop-up on WARNING / CRITICAL until acknowledged, alert feed
  with "NO RESPONSE" escalation marks, density chart per zone on its level bands, event detail with the blurred snapshot.
- `/security` — on-site guards, built for a phone: big alert cards with Acknowledge, zone levels.
- `/signboard/<zone>` — public signboard: full-screen level and a short instruction in Korean and English.

Every camera that overrides `crowd.levels_ppm2` shows the red "DEMO THRESHOLDS … (not the real levels)" line.
Set `NEXT_PUBLIC_API` to point at another API host.
