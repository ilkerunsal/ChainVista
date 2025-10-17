# Blockchain Analytics AI Project (Mini Scenario)

This repository contains a multi-component system to index blockchain contract events, provide analytics via a web API, surface insights through an AI-powered query assistant, raise alerts on anomalous activities, and serve a web-based dashboard. The goal is to bootstrap a minimal viable product (MVP) that can be extended to multiple chains and tenants.

## Repository Structure

- `apps/api` – ASP.NET Core Web API providing endpoints for querying data (`/ask`), listing alerts (`/alerts`), checking system status (`/status`) and exposing metrics (`/metrics`).
- `apps/indexer` – A TypeScript service using ethers.js to connect to an Ethereum-compatible RPC endpoint, listen for contract events and persist them into a database (PostgreSQL).
- `apps/ui` – A React-based frontend built with Vite. It exposes a single "Ask" input that sends natural language questions to the API and displays JSON responses. It also shows alerts and indexer suggestions.
- `apps/ai-anomaly` – A placeholder FastAPI microservice for anomaly detection and summarisation; to be extended with z‑score/ESD logic and optional LLM summarisation.
- `packages/contracts` – Contains ABI definitions and typed event schemas for supported smart contracts.
- `packages/schema` – Database schema definitions and SQL migrations.
- `packages/shared` – Shared DTOs and client libraries used by multiple services.
- `infra/docker` – Docker Compose configuration for local development (PostgreSQL, Redis, etc.).
- `.github/workflows` – Continuous integration pipelines.

Each component is intentionally minimal to serve as a starting point. See individual `README.md` files for details.
