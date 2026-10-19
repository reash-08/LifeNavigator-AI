# LifeNavigator AI frontend

From this directory, run `npm install` and `npm run dev`. The Vite development server proxies `/api` and `/health` to `http://127.0.0.1:8000`; set `VITE_DEV_API_TARGET` if the backend runs elsewhere.

For a separately hosted production frontend, set `VITE_API_URL` at build time to the API origin and configure that API host's CORS allowlist or a same-origin reverse proxy.

Run `npm run build`, `npm run lint`, and `npm test` for the production build and local checks.
