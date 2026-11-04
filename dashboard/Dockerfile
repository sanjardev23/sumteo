# Day 6 — the dashboard for the Docker demo: a production build (`next build && next start`, §3).
# NEXT_PUBLIC_* values are baked in at build time: the Kakao key comes from dashboard/.env.local, never from the repo.
FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

EXPOSE 3000
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
