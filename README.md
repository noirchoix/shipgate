# ShipGate — Launch Readiness Auditor

ShipGate is a production launch-readiness auditor for GitHub repository ZIPs. It inspects the files that usually determine whether a project can actually ship: environment templates, package manifests, backend runtime files, deployment configuration, CI/CD, docs, storage/database setup, frontend API configuration and rollback/smoke-test evidence.

## Features

- Repository ZIP upload with safe extraction guard
- Default target selection for README, env templates, package/requirements files, SvelteKit/FastAPI configs, API clients, routers, schemas, deployment files and workflows
- Deterministic launch-readiness checks
- Optional DeepSeek or Gemini synthesis
- SQLite session, audit, memory and cache storage
- Launch score and readiness state
- File-level findings with blocker/warning/suggestion/nit/pass severities
- Environment variable matrix
- Build command recommendations
- Smoke-test checklist
- Rollback plan
- Copyable Markdown report


## Automated assurance

The backend assurance suite covers ZIP traversal and aggregate expansion limits, secret/public-environment detection, nested stack detection, deterministic scoring, and both offline and provider-failure LLM fallback behavior.

```bash
cd apps/api
pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions runs the same suite on pushes and pull requests. Core readiness decisions remain deterministic; LLM synthesis is optional and failure-safe.

## Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8005
```

Useful routes:

```text
GET  /api/v1/shipgate/health
POST /api/v1/shipgate/upload
GET  /api/v1/shipgate/files/{session_id}
POST /api/v1/shipgate/audit
GET  /api/v1/shipgate/sessions
GET  /api/v1/shipgate/skills
GET  /api/v1/shipgate/memory/{session_id}
```

## Frontend

```bash
cd apps/web
npm install --registry=https://registry.npmjs.org/
cp .env.example .env
npm run dev -- --host 0.0.0.0
```

`apps/web/.env`:

```env
VITE_API_BASE_URL=http://localhost:8005
```

## LLM mode

Static audit works without any key. For production synthesis:

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL=deepseek-chat
```

or:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-1.5-flash
```
