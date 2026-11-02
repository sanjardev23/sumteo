# Dashboard (Day 5)

```bash
npx create-next-app@latest . --ts --tailwind --app
npm install recharts
```

Pages: camera grid (MJPEG `<img src="http://127.0.0.1:8000/cameras/{id}/stream">`),
live alert feed over `ws://127.0.0.1:8000/ws`, density chart, event detail with Acknowledge.
