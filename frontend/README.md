# Frontend (React + Vite)

## Prereqs
- Node.js 18+

## Run
```bash
npm install
npm run dev
```

Then open http://localhost:5173

## Backend
This UI expects the FastAPI backend running on http://localhost:8000 and proxies `/codex/*` to it via `vite.config.ts`.

## Useful scripts
- `npm run typecheck`
- `npm run lint`
- `npm run build`
