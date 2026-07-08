# Local Docker Development

This document describes how to run Rico locally using Docker Compose.

## Prerequisites

- Docker Desktop for Windows with WSL2 enabled
- Git repository cloned locally

## Quick Start

### Start all services

```powershell
docker compose up --build
```

This builds and starts:

- **Backend**: FastAPI on <http://localhost:8000>
- **Frontend**: Next.js on <http://localhost:3000>
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Stop all services

```powershell
docker compose down
```

### Reset local database

```powershell
docker compose down -v
```

This removes the PostgreSQL volume and recreates a fresh database on next start.

## Local URLs

- Backend API: <http://localhost:8000>
- Frontend: <http://localhost:3000>
- API Docs: <http://localhost:8000/api/docs>
- Health Check: <http://localhost:8000/health>
- Version: <http://localhost:8000/version>

## Required Environment Variables

The docker-compose.yml includes safe local defaults for development. For full functionality, you may need to add:

### Backend (in docker-compose.yml under `backend.environment`)

```yaml
# AI Providers (choose one or more)
OPENAI_API_KEY: your_openai_key_here
DEEPSEEK_API_KEY: your_deepseek_key_here
HF_TOKEN: your_huggingface_token_here

# Job Search APIs
RAPIDAPI_KEY: your_rapidapi_key_here
JSEARCH_API_KEY: your_jsearch_key_here

# Email (for password reset, notifications)
EMAIL_USER: your_email@gmail.com
EMAIL_PASS: your_app_password
EMAIL_TO: your_email@gmail.com

# Telegram (optional)
TELEGRAM_BOT_TOKEN: your_bot_token
TELEGRAM_CHAT_ID: your_chat_id
```

### Frontend (in docker-compose.yml under `web.environment`)

The frontend uses the backend via Docker network, so defaults work:

- `BACKEND_API_BASE_URL: http://backend:8000` (server-side)
- `NEXT_PUBLIC_API_BASE_URL: http://localhost:8000` (client-side)

## Development Workflow

### Backend hot reload

The backend mounts the project directory, so Python code changes trigger auto-reload via uvicorn `--reload`.

### Frontend hot reload

The frontend mounts the apps/web directory (excluding node_modules), so Next.js hot-reload works.

### View logs

```powershell
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f web
```

### Run commands in containers

```powershell
# Backend shell
docker compose exec backend bash

# Frontend shell
docker compose exec web bash

# Run backend tests
docker compose exec backend pytest

# Run frontend tests
docker compose exec web npm test
```

## Database Access

Connect to PostgreSQL from your host:

```powershell
# Using psql (if installed)
psql -h localhost -U rico -d rico

# Using Docker
docker compose exec postgres psql -U rico -d rico
```

Default credentials:

- User: `rico`
- Password: `rico`
- Database: `rico`

## Optional Neon Dev/Staging Usage

**IMPORTANT**: The default docker-compose.yml uses local PostgreSQL. This is the safest and recommended configuration for local development.

### When to use Neon with Docker

Only connect Docker to Neon if you need to:
- Test against a specific dev/staging Neon branch
- Reproduce an issue that only occurs on Neon
- Share a database state with another developer

**Never connect to production Neon from local Docker.**

### Using a Neon Dev/Staging Branch

To use a Neon dev/staging branch instead of local PostgreSQL:

1. Create a `docker-compose.override.yml` file (gitignored):

```yaml
services:
  backend:
    environment:
      # Replace with your Neon dev/staging branch URL only
      # NEVER use production Neon URL here
      DATABASE_URL: postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
    depends_on:
      # Remove postgres dependency when using Neon
      postgres: null
```

2. Or use a local `.env` file (gitignored):

```bash
# .env (gitignored - never commit this)
DATABASE_URL=postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
```

Then update docker-compose.yml to read from .env:

```yaml
services:
  backend:
    environment:
      DATABASE_URL: ${DATABASE_URL}
```

### Switching Back to Local PostgreSQL

To revert to local PostgreSQL:

1. Delete `docker-compose.override.yml` if you created it
2. Delete `.env` if you created it
3. Ensure docker-compose.yml has the original local DATABASE_URL:

```yaml
DATABASE_URL: postgresql://rico:rico@postgres:5432/rico
```

4. Restart services:

```powershell
docker compose down
docker compose up --build
```

### Safety Rules

- **NEVER** use production Neon URL in local Docker
- **NEVER** commit real Neon URLs to version control
- **NEVER** run migrations against production Neon from local Docker
- Only use dev/staging Neon branches
- Always use `.gitignore` to protect Neon credentials
- Test Neon changes in a separate branch first

### Verification

After switching to Neon, verify you're not using production:

```powershell
# Check the DATABASE_URL in the running container
docker compose exec backend printenv DATABASE_URL
```

The URL should contain a dev/staging branch identifier, not production.

## Troubleshooting

### Port conflicts

If ports 3000, 8000, 5432, or 6379 are already in use, edit the `ports` section in docker-compose.yml.

### Backend fails to start

Check that postgres and redis are healthy:

```powershell
docker compose ps
```

### Frontend cannot connect to backend

Ensure the backend service name in docker-compose.yml matches `BACKEND_API_BASE_URL` (currently `backend`).

### Permission errors (WSL2)

If you see permission errors, ensure Docker Desktop has access to your WSL2 distribution:

- Docker Desktop → Settings → Resources → WSL Integration → Enable integration

## Security

- Never commit real API keys, tokens, or credentials into `docker-compose.yml`,
  `.env` files, or this document. Use placeholder values in version control and
  keep real secrets in a local, gitignored `.env` file.
- Both `.dockerignore` files exclude `.env`, `.env.*` (except `.env.example`),
  and common credential/certificate file types (`*.pem`, `*.key`, `*.crt`) so
  they are never baked into an image layer.
- If you used a personal access token (e.g. a Docker Hub PAT) to pull or push
  images while setting up this environment, revoke it from your Docker account
  settings once local setup is confirmed working, and generate a new one only
  when you actually need it again.

## Production Deployment

This Docker setup is for local development only. For production:

- Backend: Deployed on Render (see render.yaml)
- Frontend: Deployed on Vercel
- Database: Neon (managed PostgreSQL)
- Redis: Render Redis

Do not use this docker-compose.yml for production deployments.
