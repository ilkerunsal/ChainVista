# Mock Indexer Usage

Bring up only the mock-indexer:
```bash
cd infra/docker
docker compose up -d --build mock-indexer
curl http://localhost:4000/healthz
curl http://localhost:4000/mock/events
```

Bring up full stack with mock-indexer (Indexer skipped):
```bash
docker compose up -d --build db redis ai-anomaly api ui mock-indexer
```

API can reach it via `http://mock-indexer:4000` (env `MOCK_INDEXER_URL`).

Update UI/API as needed to consume `/mock/events` while the real indexer is disabled.
