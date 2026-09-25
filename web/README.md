# TrustUs Web Dashboard

React 18 + TypeScript + Vite + React Query + Tailwind. Built against
`docs/TrustUs_Web_Dashboard_Complete_Documentation.pdf`.

## Run

```bash
npm install
npm run dev        # http://localhost:5173, /api proxied to localhost:8000
```

The API must be running (`docker compose up` from the repo root, or the server
locally). For a production build pointing elsewhere:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run build
```

## Conventions (from the spec)

- Access token in memory, refresh token in `sessionStorage`, single-flight
  refresh with request queuing — see `src/api/client.ts`. No changes needed.
- Every list page: skeleton loader → empty state with CTA → error state with retry.
- Destructive actions always behind a confirmation dialog; toasts for mutations.
- Role-gated controls are **disabled with a tooltip**, never hidden.
