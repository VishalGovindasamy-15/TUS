# TUS — TrustUs

Product-authenticity / anti-counterfeit platform. A manufacturer prints a QR (plain URL)
on each pack; every supply-chain actor scans it as custody moves; consumers scan the same
QR on a public no-login page to check **genuine / not_yet_in_circulation / flagged / recalled**.

Built from scratch from the spec docs in [`docs/`](docs/) (Option B).

## Repo layout

| Path | What |
|------|------|
| `server/` | FastAPI + PostgreSQL + Redis API + Celery worker (39 base endpoints + Fix-Plan additions) |
| `web/` | React 18 + TS + Vite dashboard (manufacturer → social_seller + platform_admin) |
| `mobile/` | Flutter field app (scan, offline-first event queue) |
| `docs/` | The 4 normative spec PDFs this repo is built against |
| `docker-compose.yml` | `db` + `redis` + `api` + `worker` |

Spec → code map:
- `TrustUs_Server_Production_Reference.pdf` → `server/` base contract (routes, state machine, detection, auth)
- `TrustUs_Server_Consolidated_Fix_Plan (1).pdf` → `server/` additions (disclosures, sync authz, QR/labels, MFA, webhooks…)
- `TrustUs_Web_Dashboard_Complete_Documentation.pdf` → `web/`
- `TrustUs_Mobile_Build_Spec.pdf` → `mobile/`

## Quickstart (Docker)

```bash
cp server/.env.example server/.env
# edit server/.env — at minimum set a long random JWT_SECRET
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed   # demo orgs, product, batch, disclosure seeds
```

- API: http://localhost:8000 — OpenAPI docs at `/docs` (dev/staging only, disabled in prod)
- Health: `GET /health` and `GET /api/v1/health`
- Web dashboard: http://localhost:5173 (see `web/README.md`)
- Demo logins: phones printed by the seed script; with `SMS_PROVIDER=dummy` the OTP is
  returned as `debug_otp` in the `/auth/otp/request` response (non-prod only).

## Key product decisions (from the Fix Plan)

- `POST /events` enforces custody authorization **synchronously** (403 `UNAUTHORIZED_ROUTE`
  when the actor org has no network edge with the manufacturer and no live transfer exception).
- A unit in `ISSUED` with zero custody events verifies as `not_yet_in_circulation`, never `genuine`.
- Consumer verify scans increment an **anonymous aggregate** `verify_count` only (no IP/device
  retained) and feed the `multi_location_verify` detection rule.
- QR images: error-correction **Q**; label export supports `csv`, `pdf_sheet`, `zpl`.
- MFA (TOTP) is enforced for `org_admin` / `platform_admin` roles.
- 3PL / e-commerce webhooks are off by default (no secret = no access) and pass through the
  same synchronous authorization check as manual scans.

## Roles & org types

- User roles: `platform_admin` (no org), `org_admin`, `member`
- Org types: `manufacturer`, `regional_agent`, `distributor_authorized`, `distributor_sub`,
  `retailer`, `transporter`, `social_seller`
