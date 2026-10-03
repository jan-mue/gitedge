# GitEdge

Serverless Git forge deployed on Vercel.

## Dynamic CORS origins

The allowed CORS origins are computed by a single property,
`Settings.cors_origins` in `backend/app/config.py`, based on the current
environment. This lets preview deployments of the frontend call the backend
without manually editing URLs per branch.

### `VERCEL_ENV`

Vercel injects `VERCEL_ENV` automatically with one of `production`, `preview`
or `development`. The backend switches on it:

| Environment  | Allowed origins                                                          |
| ------------ | ------------------------------------------------------------------------ |
| `production` | `FRONTEND_HOST` (fixed allowlist, the real frontend domain)               |
| `preview`    | Frontend preview host(s) parsed from `VERCEL_RELATED_PROJECTS`            |
| `development`| `http://localhost:5173` and `http://127.0.0.1:5173` (Vite dev server)     |

### Related Projects and `VERCEL_RELATED_PROJECTS`

Each project declares its related projects in its `vercel.json`:

```json
{
  "relatedProjects": ["prj_<other-project-id>"]
}
```

Vercel then injects `VERCEL_RELATED_PROJECTS` (JSON) into that project's
deployments. The backend's `vercel.json` lists the frontend project
(`prj_92SvWxH1QhfvTMuCw6F7aMcvq895`), so backend previews learn the frontend
preview host from the `preview.customEnvironment` / `preview.branch` fields.

Parsing is defensive: missing or malformed JSON logs a warning and yields no
origins rather than crashing (preview simply stays locked down). All origins are
normalized to `scheme://host` (HTTPS is assumed for bare hosts) and deduplicated,
and `*` is never used, so `allow_credentials=True` stays valid.

### Environment variables

- `FRONTEND_HOST` — production frontend origin (`https://gitedge-app.vercel.app`).
  Required for strict production CORS; managed in `infra/vercel.tf`.

### Disabling sign-ups

Self-service registration can be turned off by setting the matching variables on
both projects:

- `SIGNUPS_ENABLED` (backend, default `true`) — when `false`,
  `POST /api/v1/users/signup` responds with `403` and no account is created.
- `VITE_SIGNUPS_ENABLED` (frontend, default `true`) — when `false`, the
  "Sign up" link is hidden on the login page and `/signup` redirects to
  `/login`.

Set both to `false` to close registration end to end.

### Local development

Nothing extra to configure: the repo `.env` sets `VERCEL_ENV=development`, so
the backend allows the Vite dev server origins automatically.
