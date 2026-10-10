# GitEdge

A serverless Git forge deployed on Vercel. GitEdge runs a Git smart HTTP server
(clone, fetch, push) on the edge and ships a web UI for browsing repositories and
managing issues and pull requests.

Git objects are stored in blob storage, Git refs in Redis, and application
metadata in PostgreSQL.

## Features

- Git smart HTTP server backed by blob storage and Redis
- Repository browsing with a file tree, syntax-highlighted file viewer, rendered
  READMEs, and a branch switcher
- Issues and pull requests with a shared number sequence
- Email flows (sign-up, password reset) and an admin UI

## Tech Stack

**Backend:** Python 3.14+ with FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, and
[dulwich](https://www.dulwich.io/) (pure Python Git library).

**Frontend:** TypeScript with React 19, Vite, TanStack Query, TanStack Router,
Tailwind CSS v4, and shadcn/ui, built with Bun.

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python packages and environments
- [Bun](https://bun.sh/) for JavaScript/TypeScript packages
- [Docker](https://www.docker.com/) for local Postgres, Redis, and MinIO (also
  required by the integration tests)

## Quick Start

Install dependencies:

```shell
uv sync --locked
```

```shell
bun install --frozen-lockfile
```

Start the local services (Postgres, Redis, MinIO):

```shell
docker compose up -d
```

Apply the database migrations:

```shell
cd backend
uv run alembic upgrade head
```

Run the backend (serves on <http://localhost:8000>):

```shell
cd backend
uv run python run_app_locally.py
```

In another terminal, run the frontend (serves on <http://localhost:5173> and
proxies `/api` to the backend):

```shell
bun run dev
```

Then open <http://localhost:5173/> and log in with the `FIRST_SUPERUSER` and
`FIRST_SUPERUSER_PASSWORD` from `.env`.

## Configuration

Settings are loaded from the top-level `.env` file into `Settings`
(`backend/app/config.py`). The most important variables:

| Variable | Purpose |
| --- | --- |
| `PROJECT_NAME` | Display name of the project. |
| `SECRET_KEY` | JWT signing key. Must not be `changethis` outside development. |
| `DATABASE_URL` | PostgreSQL connection URL (the `psycopg` driver is applied automatically). |
| `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD` | Initial admin account created on startup. |
| `REDIS_KIND` / `REDIS_URL` / `REDIS_PASSWORD` | Redis backend (`redis` or Upstash `rest`) used for Git refs. |
| `BLOB_STORAGE_KIND` | `s3` (MinIO/S3) or `vercel` (Vercel Blob) for Git objects. |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET` | Credentials and endpoint for the S3/MinIO blob store. |
| `VERCEL_BLOB_TOKEN` / `VERCEL_BLOB_ACCESS` | Token and access mode for the Vercel Blob store. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS` / `SMTP_USER` / `SMTP_PASSWORD` | Outgoing email server. |
| `EMAILS_FROM_EMAIL` / `EMAILS_FROM_NAME` | From address and name for outgoing email. |
| `VERCEL_ENV` / `FRONTEND_HOST` | Deployment environment and production frontend origin (see below). |

Email sending is disabled unless both `SMTP_HOST` and `EMAILS_FROM_EMAIL` are
set. In development, default secrets only produce warnings; in preview and
production they raise an error at startup.

### Dynamic CORS origins

The allowed CORS origins are computed by a single property,
`Settings.cors_origins` in `backend/app/config.py`, based on the current
environment. This lets preview deployments of the frontend call the backend
without manually editing URLs per branch.

#### `VERCEL_ENV`

Vercel injects `VERCEL_ENV` automatically with one of `production`, `preview`
or `development`. The backend switches on it:

| Environment  | Allowed origins                                                          |
| ------------ | ------------------------------------------------------------------------ |
| `production` | `FRONTEND_HOST` (fixed allowlist, the real frontend domain)               |
| `preview`    | Frontend preview host(s) parsed from `VERCEL_RELATED_PROJECTS`            |
| `development`| `http://localhost:5173` and `http://127.0.0.1:5173` (Vite dev server)     |

#### Related Projects and `VERCEL_RELATED_PROJECTS`

Each project declares its related projects in its Vercel configuration
(`frontend/vercel.json` or `backend/vercel.json`):

```json
{
  "relatedProjects": ["prj_<other-project-id>"]
}
```

Vercel then injects `VERCEL_RELATED_PROJECTS` (JSON) into that project's
deployments. The backend's `vercel.json` lists the frontend project, so backend
previews learn the frontend preview host from the `preview.customEnvironment` /
`preview.branch` fields.

Parsing is defensive: missing or malformed JSON logs a warning and yields no
origins rather than crashing (preview simply stays locked down). All origins are
normalized to `scheme://host` (HTTPS is assumed for bare hosts) and deduplicated,
and `*` is never used, so `allow_credentials=True` stays valid.

#### Local development

Nothing extra to configure: the repo `.env` sets `VERCEL_ENV=development`, so the
backend allows the Vite dev server origins automatically.

## Development

### Backend

The backend code lives in `backend/app/`. Dependencies are managed with
[uv](https://docs.astral.sh/uv/). From the repository root, install everything
with:

```shell
uv sync --locked
```

Make sure your editor uses the virtual environment at `.venv/bin/python`.

### Frontend

The frontend lives in `frontend/` and is built with [Vite](https://vitejs.dev/),
[React](https://react.dev/), [TypeScript](https://www.typescriptlang.org/),
[TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router),
and [Tailwind CSS](https://tailwindcss.com/). See `frontend/package.json` for all
available scripts.

### Disabling sign-ups

Self-service registration can be turned off by setting the matching variables on
both projects:

- `SIGNUPS_ENABLED` (backend, default `true`) — when `false`,
  `POST /api/v1/users/signup` responds with `403` and no account is created.
- `VITE_SIGNUPS_ENABLED` (frontend, default `true`) — when `false`, the
  "Sign up" link is hidden on the login page and `/signup` redirects to
  `/login`.

Set both to `false` to close registration end to end.

### Database migrations

Migrations live in `backend/migrations/`. Create and apply them from the
`backend/` directory:

```shell
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

## Testing

### Backend unit tests

```shell
cd backend
uv run pytest tests/unit
```

With coverage:

```shell
cd backend
uv run coverage run -m pytest tests/unit
uv run coverage report
```

### Backend integration tests

The end-to-end tests use Playwright and Docker (testcontainers for Postgres,
Redis, MinIO, and Mailpit). Install the browsers once, then run:

```shell
cd backend
uv run playwright install
uv run pytest tests/integration
```

For more information on writing and running Playwright tests, see the official
[Playwright documentation](https://playwright.dev/docs/intro).

### Frontend tests

```shell
bun run test
```

## Linting and formatting

Run all pre-commit hooks (ruff, ty, biome, codespell, deptry, and more):

```shell
pre-commit run --all-files
```

Type checking alone:

```shell
pre-commit run ty --all-files
```

## API client

The frontend uses an auto-generated TypeScript client (`frontend/src/client/`)
based on the backend's OpenAPI schema. Regenerate it whenever the backend API
changes:

```shell
bash ./scripts/generate-client.sh
```

A pre-commit hook runs the same script, so commit the regenerated client along
with the backend changes.

## Email templates

Transactional emails are React components in `packages/react-email/emails/`.
Preview them locally:

```shell
bun run email:dev
```

Export the compiled HTML into the backend templates directory:

```shell
bun run email:export
```

## Deployment

GitEdge is deployed on [Vercel](https://vercel.com/) as two projects (frontend
and backend), configured by `frontend/vercel.json` and `backend/vercel.json`. The
backend build runs `backend/scripts/prestart.sh` to apply migrations and seed initial data. Preview
deployments discover each other's URLs through Vercel's related projects, which
also feeds the dynamic CORS allowlist described above.

The frontend routing middleware rewrites `/<owner>/<repo>.git/*` to the backend before serving the
SPA fallback, so clone, fetch, and push use the frontend's public domain. These
rewrites use the same backend URL as the API client: `VITE_API_URL` in production
and the related backend deployment in previews. Set `VITE_API_URL` on the frontend
project to the backend's production origin. Redeploy the frontend after changing
its routing configuration or production backend URL.

## License

[MIT](LICENSE)
