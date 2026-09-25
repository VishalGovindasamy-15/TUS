# TrustUs demo + verification kit

| Script | What it does | Where it runs |
|--------|--------------|---------------|
| `run_demo.py` | Live end-to-end demo against a running API: 21 sections, ~80 assertions covering every workflow (OTP/MFA, catalogue, disclosures, batches, custody chain, 4 verify states, sync 403 authz, transfer exceptions, detection + auto-flag, recall, csv/pdf/zpl exports, **QR decode proof**, network tiers, containers, social listings, KYC + admin lifecycle, team guards, sessions, webhooks, fraud/regulator analytics, multi-location rule, redis-logic) | anywhere with Python + `httpx` (server venv has it) |
| `check_web_contract.py` | Proves every API call in `web/src` matches a real server route (method + path) | anywhere with the server importable |
| `screenshots/demo.spec.ts` | Playwright: logs in via UI, walks **every page**, clicks key buttons (new batch, generate units, export download, invite create, KYC upload, listing/container lifecycle, regulator grant), screenshots each to `demo/shots/`, fails on console/page errors | **local machine only** (needs a real browser; the sandbox has none) |

## Run the live demo

```bash
# terminal 1 — API (Postgres via compose, or sqlite for a quick run)
cd server
ENV=dev DATABASE_URL=sqlite+aiosqlite:////tmp/demodb.db REDIS_URL= EAGER_DETECTION=true \
  JWT_SECRET=<long-random> python3 -m app.seed
ENV=dev DATABASE_URL=sqlite+aiosqlite:////tmp/demodb.db REDIS_URL= EAGER_DETECTION=true \
  JWT_SECRET=<long-random> python3 -m uvicorn app.main:app --port 8000

# terminal 2 — the demo
python3 demo/run_demo.py http://localhost:8000/api/v1
python3 demo/check_web_contract.py
```

## Run the screenshot suite (local machine)

```bash
docker compose up --build -d
docker compose exec api python -m app.seed
cd demo/screenshots
npm i -D @playwright/test && npx playwright install chromium
WEB_URL=http://localhost:3000 npx playwright test
# screenshots land in demo/shots/
```
