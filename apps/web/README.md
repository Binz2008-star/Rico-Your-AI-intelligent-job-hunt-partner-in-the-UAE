# Rico Web App

Next.js frontend for Rico AI.

## Features

- Chat-style Rico interface
- Mobile-friendly layout
- Streaming-style interaction feel
- Persistent conversation UX
- FastAPI backend integration

## Local development

```bash
cd apps/web
npm install
npm run dev
```

## Environment

```bash
cp .env.example .env.local
```

Required runtime variables:

```bash
BACKEND_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_APP_URL=https://ricohunt.com
```

For production, set these in Vercel Project Settings instead of hardcoding backend URLs in `vercel.json`.

## Expected backend routes

```http
POST /api/v1/rico/chat
POST /api/v1/agent/chat
POST /api/v1/rico/upload-cv
POST /api/v1/rico/confirm-cv-profile
GET  /api/v1/jobs/{job_id}
GET  /api/v1/pipeline/status
```

## Planned upgrades

- WebSocket streaming
- Rich job cards
- Semantic memory timeline
- Notification center
- Interview prep cards
- Mobile push notifications
- Voice interaction
