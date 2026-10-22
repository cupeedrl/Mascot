# Mascot — Deployment Guide

This document provides complete instructions for deploying Mascot to production (Neon PostgreSQL + Render + Vercel) and running containerized environments with Docker.

---

## 1. Production Architecture Overview

| Component | Provider / Platform | Purpose |
|---|---|---|
| **Frontend** | [Vercel](https://vercel.com) | React 19 Single Page Application |
| **Backend API** | [Render](https://render.com) | FastAPI REST API Web Service |
| **Database** | [Neon](https://neon.tech) | Serverless PostgreSQL 16 |
| **AI Provider** | [Groq](https://console.groq.com) | LLM inference API |
| **Email Delivery** | [Gmail SMTP](https://myaccount.google.com/apppasswords) / [Resend](https://resend.com) / [Brevo](https://www.brevo.com) | Password recovery emails |

---

## 2. Step-by-Step Production Deployment

### Step 1: Provision Neon PostgreSQL
1. Create a project on [Neon](https://neon.tech).
2. Obtain the secure connection string:
   ```text
   postgresql+psycopg://<user>:<password>@<ep-xyz>.region.aws.neon.tech/<dbname>?sslmode=require
   ```

### Step 2: Execute Database Migrations
Run Alembic against Neon to apply all migrations up to the current head (`20260908_0014`):

```bash
cd backend
DATABASE_URL="postgresql+psycopg://<user>:<password>@<ep-xyz>.region.aws.neon.tech/<dbname>?sslmode=require" \
python -m alembic upgrade head
```

### Step 3: Deploy Backend on Render
1. Create a new **Web Service** on [Render](https://render.com) connected to the Mascot GitHub repository.
2. Configure settings:
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -e .`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add Backend Environment Variables (see table below).

### Step 4: Deploy Frontend on Vercel
1. Import the repository into [Vercel](https://vercel.com).
2. Configure settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Add Environment Variable:
   - `VITE_API_BASE_URL`: `https://<your-render-service>.onrender.com/api/v1`
4. *Note*: `frontend/vercel.json` provides rewrite rules for client-side routing.

### Step 5: Configure CORS & Run Smoke Test
1. Set `CORS_ORIGINS` on Render to your Vercel domain (e.g. `["https://mascot-ai-learn.vercel.app"]`).
2. Run the production smoke-test checklist.

### Step 6: Keep the Render Backend Awake (Free Tier)
Render spins down a free web service after **15 minutes without inbound traffic**, and the next request waits about a minute while it starts again ([Render docs](https://render.com/docs/free)). To avoid that cold start:

1. Create a free job on [cron-job.org](https://console.cron-job.org/signup) that requests `https://<render-service>.onrender.com/api/v1/health` **every 10 minutes**. Ten minutes leaves room for one missed or delayed ping before the 15-minute limit.
2. Ping `/api/v1/health`, not `/api/v1/health/database`, so the job does not keep Neon compute awake.
3. Free instance hours are **750 per workspace per month**. One service awake all month uses at most 744, so keep only **one** free service pinged around the clock; if the hours run out, Render suspends every free service until the next month.

Free web services cannot send traffic on ports 25, 465 or 587, so SMTP email (`EMAIL_PROVIDER=gmail_smtp`) fails on Render free. Use `brevo` or `resend`, which send over HTTPS.

---

## 3. Environment Variables Reference

### Backend (Render Web Service)

| Variable | Required | Example Value | Description |
|---|---|---|---|
| `ENVIRONMENT` | Yes | `production` | Disables `/docs` and `/openapi.json` in production |
| `DATABASE_URL` | Yes | `postgresql+psycopg://...` | Connection URI to Neon PostgreSQL |
| `CORS_ORIGINS` | Yes | `["https://mascot.vercel.app"]` | Allowed CORS origins (JSON array or comma-separated) |
| `JWT_SECRET_KEY` | Yes | `(32+ character random string)` | Cryptographic secret for signing HS256 JWT tokens |
| `JWT_ALGORITHM` | No | `HS256` | Default signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifespan in minutes |
| `AI_PROVIDER` | Yes | `groq` | Active AI provider (`groq` or `openai`) |
| `GROQ_API_KEY` | Yes (if Groq) | `gsk_...` | API key from Groq Console |
| `GROQ_MODEL` | No | `openai/gpt-oss-20b` | Groq model for the chat assistant |
| `GROQ_EXERCISE_MODEL` | No | `openai/gpt-oss-120b` | Groq model for exercise generation |
| `AI_PROVIDER` | No | `groq` or `openai` | Active AI provider (`OPENAI_API_KEY` / `OPENAI_MODEL` for `openai`) |
| `GROQ_BASE_URL` | No | `https://api.groq.com/openai/v1` | Groq API endpoint |
| `AI_REQUEST_TIMEOUT_SECONDS` | No | `20` | HTTP timeout for external AI calls |
| `EMAIL_PROVIDER` | Yes | `gmail_smtp`, `resend` or `brevo` | Active email provider for password resets |
| `SMTP_HOST` | Conditional | `smtp.gmail.com` | SMTP server host (for `gmail_smtp`) |
| `SMTP_PORT` | Conditional | `587` | SMTP port |
| `SMTP_USERNAME` | Conditional | `your-email@gmail.com` | SMTP account email |
| `SMTP_APP_PASSWORD` | Conditional | `16-char app password` | Google App Password |
| `RESEND_API_KEY` | Conditional | `re_...` | API key from Resend (for `resend`) |
| `BREVO_API_KEY` | Conditional | `xkeysib-...` | API key from Brevo (for `brevo`) |
| `EMAIL_FROM` | Yes | `Mascot <support@mascot.io>` | Sender email address |
| `FRONTEND_BASE_URL` | Yes | `https://mascot.vercel.app` | Base URL used to construct password reset links |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | No | `20` | Reset token lifetime in minutes |

### Frontend (Vercel)

| Variable | Required | Example Value | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Yes | `https://<render-service>.onrender.com/api/v1` | Public URL of the FastAPI backend |

---

## 4. Docker Containerization (Local / Staging)

To run the complete system locally with Docker Compose:

The compose file runs the backend and frontend only. Start PostgreSQL 16 on `localhost:5432` first (see the [Development Guide](DEVELOPMENT.md)); the backend container reaches it through `host.docker.internal`.

```bash
# Start Backend and Frontend
docker compose up -d --build

# Run database migrations in container
docker compose exec backend python -m alembic upgrade head

# Check running services
docker compose ps
```

Local service ports:
- **Frontend SPA**: `http://localhost:5173`
- **FastAPI Backend**: `http://localhost:8000`
- **API Health Check**: `http://localhost:8000/api/v1/health`
- **PostgreSQL** (started separately): `localhost:5432`
