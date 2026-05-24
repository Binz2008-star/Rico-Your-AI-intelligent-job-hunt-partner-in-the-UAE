> **Archived document.** This file is historical and not the current source of truth.
> See [docs/PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md) for current deployment status.

---

# Rico AI — Production Architecture & Transformation Roadmap
**Prepared by:** Base44 AI Analysis Engine  
**For:** Roben Edwan  
**Date:** May 15, 2026  
**System:** job-automation-system-1 → Rico AI SaaS Platform  

---

## PART 1 — ARCHITECTURAL WEAKNESSES & BOTTLENECKS

### 1.1 Critical Issues (Fix Before Any Deployment)

| # | Issue | Location | Severity | Impact |
|---|-------|----------|----------|--------|
| 1 | Synchronous pipeline blocks GitHub Actions for 68s | `run_daily.py` | Critical | Can't scale to multi-user |
| 2 | Neon free tier ~1600ms DB RTT | `src/db.py` | Critical | Kills real-time chat UX |
| 3 | No WebSocket — chat is polling-based | `src/api/app.py` | Critical | Poor streaming UX |
| 4 | HF_TOKEN whitespace causes keyword-only scoring | GitHub Secrets | High | 50% AI quality loss |
| 5 | No Jotform webhook HMAC verification | `rico_jotform_webhook.py` | High | Spoofable onboarding |
| 6 | JWT in httpOnly cookie but no CSRF protection | `src/api/auth.py` | High | CSRF vulnerability |
| 7 | `rico_chat_api.py` is 1,576 LOC monolith | `src/rico_chat_api.py` | High | Unmaintainable, untestable |
| 8 | No Redis — idempotency uses in-memory TTL | `src/agent/runtime.py` | High | Breaks on multi-instance |
| 9 | Email notifier broken | `src/notifier.py` | Medium | Telegram-only fallback |
| 10 | Feedback loop inactive (<5 outcomes) | `src/feedback_loop.py` | Medium | No learning signal |
| 11 | CV files stored locally (not cloud) | `src/cv_parser.py` | High | Lost on redeploy |
| 12 | No connection pooling | `src/db.py` | High | Exhausts Neon connections |
| 13 | Single-tenant data model | all repos | Critical | Blocks SaaS launch |

### 1.2 Architecture Debt Score

```
Technical Debt Assessment:
─────────────────────────────────────────────────────
  Critical Security Gaps:     ████████░░  3/5 resolved
  Scalability Readiness:      ███░░░░░░░  2/10 done
  Multi-tenant Readiness:     ██░░░░░░░░  1/10 done
  Test Coverage:              ████░░░░░░  35 tests, ~30% coverage
  Observability:              ██░░░░░░░░  Basic logging only
  Production Deployment:      ░░░░░░░░░░  0/10 — not deployed
  AI Orchestration Maturity:  █████░░░░░  Tool registry exists, no execution loop
─────────────────────────────────────────────────────
  Overall Production Readiness: 35/100
```

---

## PART 2 — PRODUCTION DEPLOYMENT ARCHITECTURE

### 2.1 Target Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EDGE / CDN LAYER                           │
│              Cloudflare (WAF + DDoS + CDN + R2 Storage)            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      LOAD BALANCER                                  │
│                   (Render / Railway / Fly.io)                       │
│              ┌─────────────┐   ┌─────────────┐                     │
│              │  API Pod 1  │   │  API Pod 2  │  (auto-scale)       │
│              │  FastAPI    │   │  FastAPI    │                     │
│              │  Uvicorn    │   │  Uvicorn    │                     │
│              └──────┬──────┘   └──────┬──────┘                     │
└─────────────────────┼─────────────────┼───────────────────────────-┘
                      │                 │
          ┌───────────▼─────────────────▼──────────┐
          │           MESSAGE BUS                   │
          │         Redis (Upstash)                 │
          │  ┌──────────────┬──────────────────┐    │
          │  │ Job Queue    │  WebSocket Pub/Sub│    │
          │  │ (Celery/RQ)  │  (Socket.IO)      │    │
          │  └──────┬───────┴────────┬──────────┘    │
          └─────────┼────────────────┼───────────────┘
                    │                │
     ┌──────────────▼──┐    ┌────────▼──────────────┐
     │  WORKER FLEET   │    │    WS GATEWAY          │
     │  ┌───────────┐  │    │  FastAPI + Socket.IO   │
     │  │ pipeline  │  │    │  (streaming chat)      │
     │  │ worker    │  │    └───────────────────────-┘
     │  ├───────────┤  │
     │  │ scorer    │  │
     │  │ worker    │  │
     │  ├───────────┤  │
     │  │ gmail     │  │
     │  │ worker    │  │
     │  ├───────────┤  │
     │  │ report    │  │
     │  │ worker    │  │
     │  └───────────┘  │
     └─────────┬───────┘
               │
   ┌───────────▼──────────────────────────────────┐
   │              DATA LAYER                       │
   │  ┌──────────────────┐  ┌───────────────────┐  │
   │  │  Neon PostgreSQL  │  │   pgvector        │  │
   │  │  + PgBouncer      │  │   (embeddings)    │  │
   │  │  (pooled)         │  └───────────────────┘  │
   │  └──────────────────┘                          │
   │  ┌──────────────────┐  ┌───────────────────┐  │
   │  │  Upstash Redis   │  │  Cloudflare R2    │  │
   │  │  (cache+queues)  │  │  (CV files)       │  │
   │  └──────────────────┘  └───────────────────┘  │
   └──────────────────────────────────────────────-┘
               │
   ┌───────────▼──────────────────────────────────┐
   │          OBSERVABILITY STACK                  │
   │  Sentry (errors) + Grafana Cloud (metrics)   │
   │  + Axiom (logs) + UptimeRobot (uptime)        │
   └──────────────────────────────────────────────-┘
```

### 2.2 Cloud Provider Recommendation

**Primary: Render.com** (best fit for this stack)

| Provider | FastAPI | Workers | WebSockets | Free Tier | Cost @ 1K users |
|----------|---------|---------|------------|-----------|-----------------|
| **Render** ✅ | Native | Background workers | ✅ | $0 → $7/mo | ~$50/mo |
| Railway | Native | Cron jobs | ✅ | $5 credit | ~$40/mo |
| Fly.io | Native | Machines | ✅ | $0 | ~$35/mo |
| AWS ECS | Via Docker | ECS Tasks | ✅ | 12mo free | ~$150/mo |
| GCP Cloud Run | Native | Cloud Tasks | Limited | $300 credit | ~$80/mo |

**Recommendation:** Start on **Render** (cheapest, simplest for FastAPI + workers). Migrate to **Fly.io** when you need multi-region. Only move to AWS/GCP when revenue justifies the ops overhead.

---

## PART 3 — REDIS + CELERY WORKER ARCHITECTURE

### 3.1 Queue Design

```
Upstash Redis
├── Queue: rico:pipeline:high     ← Job scoring, real-time requests
├── Queue: rico:pipeline:default  ← Daily pipeline, Gmail sync
├── Queue: rico:pipeline:low      ← Reports, dashboard generation
├── Queue: rico:notifications     ← Telegram + email sends
└── Queue: rico:scheduler         ← Celery beat scheduled tasks

Worker Fleet (Render Background Workers):
├── worker_pipeline.py   (2 replicas)  ← job fetch + score
├── worker_gmail.py      (1 replica)   ← Gmail sync every 15min
├── worker_notify.py     (1 replica)   ← Telegram/email sends
├── worker_ai.py         (1 replica)   ← AI inference tasks
└── worker_beat.py       (1 replica)   ← Celery Beat scheduler
```

### 3.2 Task Registry

```python
# tasks/pipeline_tasks.py
@celery_app.task(queue="rico:pipeline:default", bind=True, max_retries=3)
def run_daily_pipeline(self, user_id: str = None):
    """Replaces GitHub Actions cron — runs for specific user or all users."""

@celery_app.task(queue="rico:pipeline:high", bind=True)
def score_job_for_user(self, job_id: str, user_id: str):
    """On-demand scoring when new job discovered."""

@celery_app.task(queue="rico:notifications")
def send_telegram_alert(self, user_id: str, message: str, job_ids: list):
    """Non-blocking Telegram notification."""

@celery_app.task(queue="rico:pipeline:low")
def generate_weekly_report(self, user_id: str):
    """Weekly Telegram + email summary."""

@celery_app.task(queue="rico:pipeline:default")
def sync_gmail_for_user(self, user_id: str):
    """Gmail reply scanner — runs every 15 minutes per user."""

# Celery Beat Schedule (replaces GitHub Actions):
CELERYBEAT_SCHEDULE = {
    "daily-pipeline-morning": {
        "task": "tasks.run_daily_pipeline",
        "schedule": crontab(hour=4, minute=0),   # 08:00 UAE
    },
    "daily-pipeline-evening": {
        "task": "tasks.run_daily_pipeline",
        "schedule": crontab(hour=14, minute=0),  # 18:00 UAE
    },
    "gmail-sync": {
        "task": "tasks.sync_gmail_for_user",
        "schedule": crontab(minute="*/15"),       # Every 15 min
    },
    "weekly-report": {
        "task": "tasks.generate_weekly_report",
        "schedule": crontab(day_of_week=1, hour=6, minute=0),  # Monday 10am UAE
    },
}
```

---

## PART 4 — WEBSOCKET STREAMING ARCHITECTURE

### 4.1 Implementation Plan

```python
# src/api/websocket.py — Add to existing FastAPI app

from fastapi import WebSocket, WebSocketDisconnect
import asyncio, json, redis.asyncio as aioredis

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}  # user_id → ws
        self.redis = aioredis.from_url(os.environ["REDIS_URL"])

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active[user_id] = ws
        # Subscribe to user's channel for worker → ws messages
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"rico:chat:{user_id}")
        asyncio.create_task(self._listen(user_id, pubsub))

    async def stream_tokens(self, user_id: str, token: str):
        if user_id in self.active:
            await self.active[user_id].send_json({"type": "token", "content": token})

    async def _listen(self, user_id: str, pubsub):
        async for msg in pubsub.listen():
            if msg["type"] == "message" and user_id in self.active:
                await self.active[user_id].send_json(json.loads(msg["data"]))

manager = ConnectionManager()

@app.websocket("/ws/chat/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: str, token: str = Query(...)):
    verify_jwt(token)  # Validate before accepting
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Stream OpenAI response token-by-token
            async for chunk in openai_stream(data["message"], user_id):
                await manager.stream_tokens(user_id, chunk)
            await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        manager.disconnect(user_id)
```

### 4.2 Frontend Integration (Next.js)

```typescript
// hooks/useRicoChat.ts
export function useRicoChat(userId: string) {
  const [tokens, setTokens] = useState("")
  const ws = useRef<WebSocket>()

  useEffect(() => {
    ws.current = new WebSocket(`wss://api.ricoai.com/ws/chat/${userId}?token=${jwt}`)
    ws.current.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === "token") setTokens(prev => prev + msg.content)
      if (msg.type === "done") setTokens("") // reset for next message
    }
  }, [userId])

  const send = (message: string) => {
    ws.current?.send(JSON.stringify({ message }))
  }

  return { tokens, send }
}
```

---

## PART 5 — VECTOR MEMORY ARCHITECTURE

### 5.1 Recommendation: pgvector on Neon (Already Available)

```sql
-- Enable pgvector (already supported on Neon)
CREATE EXTENSION IF NOT EXISTS vector;

-- Job embeddings table
CREATE TABLE job_embeddings (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    embedding vector(384),  -- MiniLM-L6-v2 dimensions
    created_at TIMESTAMP DEFAULT NOW()
);

-- User memory embeddings (chat history semantic search)
CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    user_id TEXT REFERENCES users(email),
    content TEXT,
    embedding vector(384),
    memory_type TEXT,  -- 'chat', 'preference', 'outcome', 'skill'
    created_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast ANN search
CREATE INDEX ON job_embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON memory_embeddings USING hnsw (embedding vector_cosine_ops);
```

### 5.2 Memory Query in Practice

```python
# src/rico_memory.py — Enhanced with pgvector
class RicoMemoryStore:
    def semantic_recall(self, user_id: str, query: str, k: int = 5) -> list[dict]:
        """Retrieve most relevant memories for a query."""
        query_embedding = hf_embed(query)  # 384-dim vector
        results = db.execute("""
            SELECT content, memory_type,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM memory_embeddings
            WHERE user_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, user_id, query_embedding, k))
        return results

    def store_outcome(self, user_id: str, job: dict, outcome: str):
        """Store application outcome as memory with embedding."""
        content = f"Applied to {job['title']} at {job['company']}. Outcome: {outcome}"
        embedding = hf_embed(content)
        db.execute("""
            INSERT INTO memory_embeddings (user_id, content, embedding, memory_type)
            VALUES (%s, %s, %s, 'outcome')
        """, (user_id, content, embedding))
```

**Best Vector DB Options:**

| Option | Cost | Latency | Integration | Verdict |
|--------|------|---------|-------------|---------|
| **pgvector (Neon)** ✅ | Free (existing) | ~5ms | Native SQL | **Use this first** |
| Pinecone | $70/mo | ~10ms | REST API | Use at scale |
| Weaviate | $25/mo | ~8ms | REST API | Good alternative |
| Qdrant | $0 self-hosted | ~3ms | REST API | Best self-hosted |

---

## PART 6 — MULTI-TENANT SAAS ARCHITECTURE

### 6.1 Database Changes Required

```sql
-- Add tenant_id to all user-scoped tables
ALTER TABLE profiles ADD COLUMN tenant_id UUID DEFAULT gen_random_uuid();
ALTER TABLE jobs ADD COLUMN tenant_id UUID;
ALTER TABLE applications ADD COLUMN tenant_id UUID;
ALTER TABLE chat_history ADD COLUMN tenant_id UUID;
ALTER TABLE learning_signals ADD COLUMN tenant_id UUID;

-- Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_isolation ON profiles
    USING (user_id = current_setting('app.current_user_id')::TEXT
           OR current_setting('app.is_admin')::BOOLEAN);

-- Tenant/subscription table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    plan TEXT DEFAULT 'free',        -- free, starter, pro, enterprise
    max_users INTEGER DEFAULT 1,
    max_jobs_per_day INTEGER DEFAULT 50,
    features JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 6.2 User Isolation Enforcement

```python
# src/api/deps.py — Enhanced tenant isolation
async def get_current_user(request: Request) -> CurrentUser:
    payload = verify_jwt(request.cookies.get("access_token"))
    user = await users_repo.get(payload["sub"])

    # Inject tenant context into DB session
    await db.execute(f"SET app.current_user_id = '{user.id}'")
    await db.execute(f"SET app.tenant_id = '{user.tenant_id}'")

    return CurrentUser(id=user.id, email=user.email, role=user.role,
                       tenant_id=user.tenant_id, plan=user.plan)
```

---

## PART 7 — IMPROVED FOLDER STRUCTURE

```
rico-ai/
├── apps/
│   ├── api/                          # FastAPI backend
│   │   ├── main.py                   # App factory + lifespan
│   │   ├── config.py                 # Pydantic Settings (env validation)
│   │   ├── dependencies.py           # Auth, DB, tenant injection
│   │   ├── middleware/
│   │   │   ├── cors.py
│   │   │   ├── rate_limit.py
│   │   │   ├── request_id.py         # NEW: trace IDs
│   │   │   └── tenant.py             # NEW: tenant context injection
│   │   ├── routers/                  # Thin HTTP handlers only
│   │   ├── websocket/
│   │   │   ├── manager.py            # Connection manager
│   │   │   └── routes.py             # WS endpoints
│   │   └── health.py
│   └── web/                          # Next.js (unchanged)
│
├── packages/
│   ├── agent/                        # Rico Agent (extracted, testable)
│   │   ├── brain.py                  # RicoAgent (cleaned up)
│   │   ├── memory.py                 # pgvector memory store
│   │   ├── safety.py                 # Safety guardrails
│   │   ├── tools/                    # Tool implementations
│   │   ├── intelligence/             # Intent/Role/Score (existing)
│   │   └── runtime.py               # Action dispatcher
│   │
│   ├── pipeline/                     # Legacy pipeline (preserved)
│   │   ├── orchestrator.py           # run_daily.py (refactored)
│   │   ├── job_sources.py
│   │   ├── scorer.py
│   │   ├── gmail_sync.py
│   │   ├── dashboard.py
│   │   └── follow_up.py
│   │
│   ├── workers/                      # NEW: Celery task workers
│   │   ├── celery_app.py
│   │   ├── pipeline_tasks.py
│   │   ├── notification_tasks.py
│   │   ├── ai_tasks.py
│   │   └── scheduler.py             # Celery Beat config
│   │
│   ├── db/                           # Data layer
│   │   ├── connection.py             # PgBouncer pooled connection
│   │   ├── migrations/               # Alembic migrations
│   │   └── repositories/            # (existing, moved here)
│   │
│   └── shared/                       # Cross-cutting
│       ├── config.py                 # Pydantic BaseSettings
│       ├── logging.py               # Structured JSON logging
│       ├── tracing.py               # OpenTelemetry setup
│       └── errors.py                # Typed error classes
│
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── docker-compose.yml
│   ├── kubernetes/                   # Phase 3 only
│   │   ├── api-deployment.yaml
│   │   ├── worker-deployment.yaml
│   │   └── redis-statefulset.yaml
│   └── render/
│       └── render.yaml               # Render deployment config
│
└── tests/
    ├── unit/
    ├── integration/
    └── load/                         # Locust files (already started)
```

---

## PART 8 — SECURITY HARDENING CHECKLIST

### Immediate (Before Any Public Launch)

- [ ] **CSRF protection** — Add `SameSite=Strict` + CSRF double-submit cookie
- [ ] **Jotform HMAC** — Verify `X-Jotform-Signature` on webhook
- [ ] **Telegram webhook** — Verify `X-Telegram-Bot-Api-Secret-Token`
- [ ] **Rate limiting on auth** — Max 5 login attempts / 15min per IP
- [ ] **HF_TOKEN strip** — `.strip()` on all env var reads (fixes scoring bug)
- [ ] **CORS lockdown** — Whitelist only `ricoai.com` + `localhost:3000`
- [ ] **CV storage** — Move to Cloudflare R2 with presigned URLs (never serve locally)
- [ ] **SQL injection audit** — Review all raw queries in `db.py` and `rico_db.py`
- [ ] **Secrets rotation** — Rotate JWT_SECRET, DB passwords, API keys
- [ ] **Dependency audit** — `pip-audit` on all requirements

### Before SaaS Launch

- [ ] **Row Level Security** on all Neon tables
- [ ] **PII encryption at rest** — Encrypt CV text, phone numbers in DB
- [ ] **Audit log immutability** — `action_audit_log` append-only with no DELETE
- [ ] **SOC2 basics** — Logging, access controls, incident response plan
- [ ] **GDPR/UAE PDPL compliance** — Data deletion endpoint, consent records

### Auth Architecture Recommendation

```
Current:  JWT in httpOnly cookie (good start)
Upgrade:  Auth.js v5 (Next.js) + FastAPI JWT validation

Flow:
  User → Auth.js (Next.js) → JWT signed with RS256
  FastAPI validates JWT with public key (no shared secret)
  
Benefits:
  - RS256 asymmetric signing (no shared secret to steal)
  - Auth.js handles OAuth (Google, LinkedIn sign-in)
  - Refresh token rotation built-in
  - No session storage needed
```

---

## PART 9 — OBSERVABILITY STACK

### Recommended Stack (All have generous free tiers)

| Layer | Tool | Why |
|-------|------|-----|
| **Error Tracking** | Sentry | Python + Next.js SDK, 5K errors/mo free |
| **Metrics** | Grafana Cloud | 10K series free, Prometheus-compatible |
| **Logs** | Axiom | 1GB/day free, structured queries |
| **Uptime** | UptimeRobot | 50 monitors free |
| **APM** | OpenTelemetry | Vendor-neutral, auto-instruments FastAPI |

### Implementation (FastAPI)

```python
# src/shared/tracing.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def setup_telemetry(app):
    FastAPIInstrumentor.instrument_app(app)  # Auto-traces all routes
    Psycopg2Instrumentor().instrument()       # Auto-traces all DB queries

# Structured logging
import structlog
logger = structlog.get_logger()
logger.info("pipeline.run", user_id=user_id, jobs_found=43, duration_ms=1240)
```

### Key Metrics to Track

```python
# Custom Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

pipeline_runs = Counter("rico_pipeline_runs_total", "Pipeline executions", ["status"])
job_score_latency = Histogram("rico_job_score_seconds", "Time to score a job")
active_users = Gauge("rico_active_users", "Currently active users")
ai_provider_calls = Counter("rico_ai_calls_total", "AI API calls", ["provider", "status"])
```

---

## PART 10 — DOCKER + DEPLOYMENT STRATEGY

### 10.1 Docker Setup

```dockerfile
# infrastructure/docker/Dockerfile.api
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY migrations/ ./migrations/

# Non-root user for security
RUN useradd -m -u 1000 rico
USER rico

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--loop", "uvloop", "--access-log"]
```

```yaml
# infrastructure/docker/docker-compose.yml
version: "3.9"
services:
  api:
    build: {context: ., dockerfile: infrastructure/docker/Dockerfile.api}
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on: [redis]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build: {context: ., dockerfile: infrastructure/docker/Dockerfile.worker}
    command: celery -A src.workers.celery_app worker -Q rico:pipeline:high,rico:pipeline:default,rico:pipeline:low,rico:notifications -c 4
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}

  beat:
    build: {context: ., dockerfile: infrastructure/docker/Dockerfile.worker}
    command: celery -A src.workers.celery_app beat --scheduler celery.beat:PersistentScheduler
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### 10.2 Render.yaml (Production)

```yaml
# render.yaml
services:
  - type: web
    name: rico-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn src.api.app:app --host 0.0.0.0 --port $PORT --workers 2
    plan: starter  # $7/mo
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: rico-neon
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: rico-redis
          property: connectionString

  - type: worker
    name: rico-pipeline-worker
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A src.workers.celery_app worker -Q rico:pipeline:default -c 2
    plan: starter

  - type: worker
    name: rico-beat-scheduler
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A src.workers.celery_app beat
    plan: starter
```

---

## PART 11 — CI/CD STRATEGY

```yaml
# .github/workflows/deploy-production.yml
name: Deploy Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ -x --tb=short
      - run: pip-audit --vulnerability-service osv  # Security audit

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff mypy
      - run: ruff check src/ && mypy src/ --ignore-missing-imports

  deploy:
    needs: [test, lint]
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK_URL }}

      - name: Run DB migrations
        run: |
          pip install alembic
          alembic upgrade head
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}

      - name: Notify deployment
        run: |
          curl -s -X POST https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage \
            -d chat_id=${{ secrets.ADMIN_CHAT_ID }} \
            -d text="✅ Rico AI deployed: $(git log -1 --format='%s')"
```

---

## PART 12 — MICROSERVICE MIGRATION ROADMAP

### Phase 0 — Stabilise (Weeks 1-2) ← START HERE
```
✅ Fix HF_TOKEN whitespace bug
✅ Add connection pooling (PgBouncer or asyncpg)
✅ Add CSRF protection
✅ Fix Jotform + Telegram webhook HMAC
✅ Move CV files to Cloudflare R2
✅ Add Sentry error tracking
✅ Deploy to Render (single service first)
```

### Phase 1 — Async Workers (Weeks 3-5)
```
→ Add Upstash Redis
→ Extract pipeline tasks to Celery workers
→ Replace GitHub Actions cron with Celery Beat
→ Add WebSocket streaming for chat
→ Add pgvector + semantic memory
→ Enable feedback loop (auto-activates at 5 outcomes)
```

### Phase 2 — Multi-tenant SaaS (Weeks 6-10)
```
→ Add tenant_id to all tables + Row Level Security
→ Add subscription/billing (Stripe)
→ Build user registration + onboarding API
→ Add multi-user pipeline isolation
→ Launch public web app
→ Add Google/LinkedIn OAuth sign-in
```

### Phase 3 — Scale & Intelligence (Weeks 11-16)
```
→ Migrate to Fly.io multi-region
→ Add Kubernetes for worker fleet
→ Full OpenAI tool-calling execution loop
→ Autonomous agent: self-directed job search without user input
→ Multi-agent: separate agents for search, apply, interview, negotiate
→ Add Arabic NLU model (CAMeL-Lab/bert-base-arabic-camelbert-mix)
```

### Phase 4 — Platform (Weeks 17-24)
```
→ Public API (B2B: sell Rico intelligence to recruiters)
→ White-label SaaS (other job markets: KSA, Egypt, UK)
→ AI recruiting copilot (flip the model: help recruiters find candidates)
→ Voice interface (Whisper → Rico → TTS)
```

---

## PART 13 — RICO AI EVOLUTION PATHS

### Path A — Autonomous Job Agent (Highest ROI)
```
Current: User-triggered job search
Target:  Rico searches every day, applies with approval, 
         negotiates interviews, follows up — no manual input

Key additions:
- Approval workflow (Telegram inline buttons for high-impact actions)
- Auto-draft cover letters queued for review
- Calendar integration for interview scheduling
- Email drafts for follow-up (user reviews before send)
```

### Path B — AI Recruiting Copilot (B2B Revenue)
```
Flip the model: sell to recruiters, not job seekers

Rico becomes:
- Candidate sourcing agent (searches LinkedIn, GitHub, portfolios)
- CV ranking engine (API endpoint: POST /rank-candidates)
- Automated outreach drafter
- Interview scheduler

Pricing: $99/mo per recruiter seat
Market: UAE/GCC recruitment agencies
```

### Path C — SaaS Platform (Scale)
```
Productize Rico for any job seeker, not just Roben

What changes:
- Onboarding for any role/location (not ESG/UAE-specific)
- Subscription tiers: Free (3 alerts/day), Pro (unlimited + apply), 
                      Executive (+ networking + salary negotiation)
- Mobile app (React Native reusing Next.js components)
- Referral system (invite friends → free Pro month)
```

### Path D — Multi-Agent Ecosystem (Long-term Vision)
```
Separate specialized agents:
├── Rico Scout      — Job discovery & scoring
├── Rico Writer     — CV optimization & cover letters  
├── Rico Coach      — Interview preparation
├── Rico Negotiator — Salary & offer analysis
└── Rico Network    — LinkedIn & recruiter outreach

Orchestrated by Rico Brain (master agent)
Each agent has its own memory, tools, and improvement loop
```

---

## PART 14 — PRIORITY MATRIX

```
                    HIGH IMPACT
                         │
    Fix HF TOKEN  ───────┼──── Add WebSockets
    Add Redis/Celery     │     Deploy to Render
    Fix DB pooling  ─────┼──── Add pgvector memory
                         │     Multi-tenant RLS
    ─────────────────────┼─────────────────────────
    LOW EFFORT            │              HIGH EFFORT
                         │
    Fix email auth ──────┼──── Kubernetes migration
    Add Sentry      ─────┼──── Multi-agent ecosystem
    CSRF fix             │     Voice interface
                         │
                    LOW IMPACT
```

### Sprint 1 (Do This Week):
1. Strip HF_TOKEN whitespace → fixes AI scoring immediately
2. Add Sentry (10min setup, instant error visibility)
3. Add `asyncpg` connection pooling → cuts DB latency from 1600ms to ~50ms
4. Deploy to Render free tier → public URL, no more GitHub Actions for API

### Sprint 2 (Next 2 Weeks):
1. Add Upstash Redis → unlocks async workers + WebSocket pub/sub
2. Celery workers → replace GitHub Actions cron, adds multi-user support
3. WebSocket chat streaming → biggest UX improvement possible
4. pgvector → semantic memory, better job matching

### Sprint 3 (Month 2):
1. Multi-tenant DB isolation → SaaS readiness
2. Stripe billing → monetisation
3. Public web onboarding → first paying users

---

## PART 15 — ESTIMATED SCALING LIMITS

| Architecture Stage | Concurrent Users | Jobs/day | Cost/mo |
|-------------------|-----------------|----------|---------|
| **Current** (GitHub Actions only) | 1 | 86 | ~$0 |
| **Phase 1** (Render + Redis) | 50 | 10,000 | ~$50 |
| **Phase 2** (Multi-tenant + pooling) | 500 | 100,000 | ~$200 |
| **Phase 3** (Fly.io multi-region) | 5,000 | 1M | ~$800 |
| **Phase 4** (Kubernetes) | 50,000+ | 10M+ | $3,000+ |

---

*End of Rico AI Production Architecture & Transformation Roadmap*  
*Generated: May 15, 2026 — Base44 AI Analysis Engine*
