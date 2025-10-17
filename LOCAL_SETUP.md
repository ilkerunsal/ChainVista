
# Local Setup & Run Guide

This project has four main parts:

1. **API** — ASP.NET Core Web API (`apps/api`, default port `5000`)
2. **Indexer** — TypeScript service that indexes blockchain events (`apps/indexer`)
3. **UI** — React (Vite) frontend (`apps/ui`, default dev port `5173`)
4. **AI Anomaly** — FastAPI microservice (`apps/ai-anomaly`, default port `8011`)

Infra (Postgres + Redis) is defined in `infra/docker/docker-compose.yml` (fill in missing sections).

---

## 0) Prerequisites

- **Docker Desktop** (recommended for Postgres + Redis)
- **.NET 8 SDK**
- **Node.js 20+** (and npm or pnpm)
- **Python 3.11+** (FastAPI + Uvicorn for the AI microservice)

> On Windows, use **PowerShell**. On macOS/Linux, use **bash/zsh**.

---

## 1) Start Infra (Postgres + Redis)

### Option A — Docker (recommended)

```powershell
cd infra/docker
# Edit docker-compose.yml if needed (ports/passwords).
docker compose up -d
```

This exposes Postgres at `localhost:5432` (user `postgres`, pass `postgres`, db `blockchain_analytics`), Redis at `localhost:6379`.

### Option B — Local installs

Install PostgreSQL and Redis locally and align connection strings with `.env.example` files.

---

## 2) Run the AI Anomaly microservice (works standalone)

```powershell
cd apps/ai-anomaly
# (Optional) Create venv, then:
# python -m venv .venv; .\.venv\Scripts\Activate.ps1
# pip install fastapi uvicorn pydantic

python -m uvicorn main:app --port 8011 --reload
```

### Test it
```powershell
# Risk scores
curl -X POST http://localhost:8011/risk_scores -H "Content-Type: application/json" -d "{""addresses"": [""0x0"", ""0x742d35Cc6634C0532925a3b844Bc454e4438f44e""]}"

# Analyze contract
curl -X POST http://localhost:8011/analyze_contract -H "Content-Type: application/json" -d "{""bytecode"": ""0x60016001016000""}"
```

A Postman collection is included: `ai_anomaly_postman_collection.json`.

---

## 3) Configure environment files

Copy the templates and adjust:

```powershell
Copy-Item apps\api\.env.example apps\api\.env
Copy-Item apps\indexer\.env.example apps\indexer\.env
Copy-Item apps\ui\.env.example apps\ui\.env
```

- Set `ConnectionStrings__Default` in `apps/api/.env` if DB settings differ.
- Set `RPC_URL` and `CONTRACT_ADDRESS` in `apps/indexer/.env`.
- Ensure `VITE_API_URL` in `apps/ui/.env` points to your API (default `http://localhost:5000`).

---

## 4) Run the API (.NET 8)

```powershell
cd apps/api
dotnet restore
dotnet build
dotnet run --urls "http://0.0.0.0:5000"
```

Check:
- `GET http://localhost:5000/status`
- `GET http://localhost:5000/metrics`
- `POST http://localhost:5000/nl-to-sql` (if available; see Program.cs)

---

## 5) Run the Indexer (Node.js)

```powershell
cd apps/indexer
npm install
npm run build
npm start
# or: npm run dev
```

It will connect to `RPC_URL`, listen for contract events, and write to Postgres at `DATABASE_URL`.

---

## 6) Run the UI (Vite + React)

```powershell
cd apps/ui
npm install
npm run dev
```

Open **http://localhost:5173**. The UI talks to the API using `VITE_API_URL`.

---

## 7) Common Issues

- **CORS**: If the UI cannot reach API, enable CORS in API or set correct `VITE_API_URL`.
- **Migrations**: Apply DB migrations from `packages/schema` before running API/indexer.
- **Ports in use**: Change ports in `.env` or launch commands.
- **JWT**: If API requires auth, set `JWT__Key`, `JWT__Issuer`, `JWT__Audience` accordingly.

---

## 8) Minimal Test Plan

1. Start Postgres/Redis.
2. Start **AI Anomaly** and verify `/risk_scores` and `/analyze_contract` return 200.
3. Start **API** and verify `/status` returns 200; `/metrics` exposes counters.
4. Start **Indexer** pointing to a testnet (e.g., Sepolia), confirm events inserted into DB.
5. Start **UI**, load homepage, and confirm it fetches status/metrics from API.

---

Happy hacking!
