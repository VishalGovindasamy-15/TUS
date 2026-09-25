# TrustUs — live demo + verification report (2026-09-25)

Environment: API (uvicorn, SQLite, `EAGER_DETECTION=true`, no Redis → fail-open paths)
+ Vite dev server with `/api` proxy. Seeded demo data. Re-runnable via `demo/run_demo.py`.

## Results

| Check | Result |
|-------|--------|
| Live API demo `run_demo.py` (21 sections) | **79/79 assertions PASS** |
| Server unit suite `pytest tests/` | **27/27 PASS** |
| Web↔server contract `check_web_contract.py` | **50/50 web calls match real routes** |
| SPA routes served (login → admin → public verify) | **23/23 HTTP 200** |
| `tsc + vite build` | clean |
| QR scannability | generated QR PNG **decoded with OpenCV** → byte-exact verify URL |
| Label exports | CSV (12 rows + URLs), PDF sheet (valid 140KB PDF), ZPL (12 labels, `^BQN`) |

Workflows proven end-to-end: OTP+MFA login for all 6 roles · disclosures (9 Schedule-H2
fields, required-enforcement) · batch/unit lifecycle · GPS custody chain
DISPATCH→RECEIVE→SALE→RETURN + history · all 4 verify states · sync 403 authz ·
transfer exceptions · impossible-travel auto-flag + review + UNFLAG · recall ·
network invites/tiers/tree (+retailer 403, soft unauthorized-route flag) · containers
(pack/nest/custody/disaggregate/409) · social listings CRUD · KYC upload + admin
approve/reject-with-reason · team invite + last-admin guard · session revoke ·
3PL/e-commerce webhooks (bad-secret 401, exhausted pool 409, secret rotation) ·
events query · fraud patterns · regulator grant lifecycle · admin alerts ·
multi-location-verify rule (10 distinct areas) · rate-limit logic via fakeredis.

## Bugs found and fixed during this demo

1. **Real server bug:** `PUT /products/{id}/disclosures` wrongly required
   `batch_number/mfg_date/expiry_date`, which the Fix Plan maps to Batch columns.
   Fixed in `server/app/api/v1/disclosures.py` (excluded from required check).
2. Demo-script issues (not product bugs): GPS points 2km apart correctly tripped
   impossible-travel (made happy-path scans co-located); helper JSON-parsed a CSV;
   rerun isolation for role/MFA mutation tests (fresh orgs per run).

## Screenshots

Not capturable in this sandbox: no browser binaries, browser CDNs blocked at the
network level, and zero GUI system libs (libnss3 etc.), so Chromium/Electron/Qt
cannot run here. The full screenshot suite is committed at
`demo/screenshots/demo.spec.ts` — run it on any local machine per `demo/README.md`
(24 screenshots across every page + button clicks + console-error gate).

## Known v1 gaps (API-complete, no web UI yet — future)

- Disclosure field management / product disclosure form (verify page already renders values)
- Webhook secret display/rotate + listing-link management in Settings
- Add-children-to-existing-container in Containers page
- Single-alert / single-listing detail fetch (pages use list data)
- Scan-frequency rule, verify rate-limit/cache need real Redis (docker compose)
