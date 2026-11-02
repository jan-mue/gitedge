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
- [Bun](https://bun.sh/) for JavaScript/TypeScript packages (version in `.bun-version`)
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

Each project declares its related projects in its `vercel.json`:

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

Run `bun run fallow` from the repository root to check unused code, dependencies,
duplication, and complexity. Each analysis fails on findings. Health allows up to
45 cyclomatic complexity, 45 cognitive complexity, and a CRAP score below 450,
with no per-function exceptions.

Pre-commit runs the full Fallow suite when JavaScript, TypeScript, CSS, MDX,
package manifests, `bun.lock`, or `.fallowrc.json` change. Each run scans the full
project, including application code, tests, stories, and email templates, using
`.fallowrc.json`. Generated API client and route-tree files are excluded, and
vendored shadcn components are excluded from health analysis.

#### Storybook

Run the component explorer:

```shell
bun run --filter frontend storybook
```

Storybook runs at <http://localhost:6006>. The MCP addon exposes component
documentation and story development tools at <http://localhost:6006/mcp> while
the dev server is running. Add that URL as an HTTP MCP server in your agent's
configuration. Component manifests are enabled for the documentation tools.

Build the static Storybook with `bun run --filter frontend build-storybook`.
Both scripts disable all Storybook telemetry, including the startup event.

### GitEdge Actions

Workflows in `.gitedge/workflow/` use GitHub/Gitea Actions syntax. The Bun
compiler in `packages/actions-compiler` validates them with the official
`@actions/workflow-parser` and emits version-two JSON IR. The independent
`packages/actions-runner` agent validates its execution schema and evaluates
runtime expressions using `@actions/expressions`. Agent manifests use version 4
with a job UUID, attempt UUID, generation and fence; rebuild prepared images and
snapshots when upgrading the manifest. Each job gets its own Docker
container or Vercel Sandbox. Prepared images contain actions and toolchains;
checkout transfers source at the immutable commit. JavaScript actions run under
Node, while the agent runs under Bun.

Start the local compiler from the repository root:

```shell
bun run --filter @gitedge/actions-compiler dev
```

Set `ACTIONS_COMPILER_URL=http://127.0.0.1:8765/api/compile` on the backend.
`COMPILER_PORT` changes the default port. Local unauthenticated access is limited
to loopback in development; production uses an on-demand Function and never
starts a compiler subprocess. Build the agent with
`bun run --filter @gitedge/actions-runner build` before preparing an image or
snapshot.

Jobs select x64 Ubuntu 22.04, 24.04 or 26.04 with `runs-on: ubuntu-22.04`,
`ubuntu-24.04` or `ubuntu-26.04`. `ubuntu-latest` resolves to 24.04. Static
matrix expressions and compatible label arrays select the same images;
conflicting versions, unsupported architectures and other OS labels fail
compilation. These are GitEdge toolchain images, with 2 vCPUs per sandbox.

`ACTIONS_RUNNERS` maps each canonical label to an `image` and optional
`snapshot_id`. Docker uses preloaded `gitedge-actions:ubuntu-<version>` tags;
Vercel resolves these names in the backend project's VCR. For production,
configure immutable image digests and only use a snapshot made from the same
release. `ACTIONS_RUNNERS` replaces the single-image `ACTIONS_IMAGE` and
`ACTIONS_VERCEL_SNAPSHOT` settings. No image pull or tool installation happens
in the Docker job-start path.

The integration workflow builds all three images once with
`docker/build-push-action` and per-version BuildKit caches. Test jobs download
those image archives instead of rebuilding. After integration
and browser checks pass on `main`, CI publishes OCI images with zstd compression
to `vcr.vercel.com/jan-mue-projects/gitedge-backend/gitedge-actions`, tagged by
Ubuntu release and commit SHA. Build summaries expose their digests.

Configure a Vercel team OIDC policy granting VCR read/write access to GitHub
repository `jan-mue/gitedge`, restricted to `refs/heads/main` and the publishing
workflow. The pinned `vercel/vcr-action/login` exchanges the GitHub identity
for short-lived credentials and revokes them afterward. No registry token is
stored in GitHub secrets. Publication is disabled for PRs. The image publisher
and CodeQL security check run only in GitHub; CodeQL tools and its GitEdge
fixture are excluded from runner images.

Cache metadata is repository-scoped in PostgreSQL. Immutable, checksummed cache
archives use the existing Blob/S3 provider; sandbox agents transfer them through
scoped controller capabilities. Cache archives are bounded to 32 MiB.

Supported events are push, pull request and manual dispatch. Static matrices
support include/exclude and require `fail-fast: false` for multiple variants.
Filters use minimatch with ordered exclusion and re-inclusion. Dynamic matrices,
reusable workflows, containers/services, concurrency and deployment environments
fail explicitly. Permissions are limited to `contents: read`. Compiler requests,
source and IR are bounded to 2, 1 and 4 MiB respectively; invalid workflows
return structured 422 diagnostics.

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

Integration tests use Docker (testcontainers for Postgres, Redis, MinIO, Mailpit,
and the official QStash dev server), without starting the frontend or a browser:

```shell
cd backend
uv run pytest tests/integration
```

### Browser end-to-end tests

End-to-end tests use the same Docker services, Bun, and Playwright. Install the
browsers once, then run:

```shell
cd backend
uv run playwright install chromium --with-deps
uv run pytest --tracing=retain-on-failure tests/e2e
```

Run these suites in separate pytest processes, as in GitHub Actions, to keep
Playwright's event loop separate from pytest-asyncio.

For more information on writing and running Playwright tests, see the official
[Playwright documentation](https://playwright.dev/docs/intro).

### Frontend tests

```shell
bun run test:frontend
```

API requests are intercepted by MSW. Import `server` from `@/test/server` and
register handlers from `@/client/msw.gen` with `server.use(...)` in each test or
`beforeEach`. The Hey API MSW plugin generates these typed handlers alongside
the client. Handlers are reset after each test, and unhandled requests are errors.
Use `vi.mock()` for non-API dependencies such as navigation.
The ast-grep pre-commit hook rejects API client and TanStack Query module mocks,
direct API client spies or replacements, and global fetch stubs in frontend tests.

### Actions compiler and runner tests

```shell
bun run typecheck:actions
bun run test:actions
```

The root Vitest projects configuration runs compiler and agent tests together
under Bun, including compilation-to-execution integration tests. Frontend tests
and V8 coverage run under Node. `bun run test` runs both groups. The workflow in
`.gitedge/workflow/` symlinks to its GitHub definition. CI reads `.bun-version`;
Renovate groups updates with the root `packageManager` and Docker Bun image.
Snapshot preparation restores the executing Bun version.

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

The root `css-tree` development dependency lets the React Email CLI resolve its
external CSS parser when rendering files in the backend templates directory.

## Deployment

GitEdge deploys its frontend and backend to separate
[Vercel](https://vercel.com/) projects, each with its own configuration. The backend build runs
`backend/scripts/prestart.sh` to apply migrations and seed initial data. Preview
deployments discover each other's URLs through Vercel's related projects, which
also feeds the dynamic CORS allowlist described above.

### Actions compiler Function

Deploy the compiler with project root `packages/actions-compiler` and source
files outside that root enabled for the workspace lockfile. Its `vercel.json`
selects Vercel's managed Bun 1.4.x runtime and a ten-second duration limit;
`api/compile.ts` uses the native `Bun.serve()` entrypoint described in the
[Bun runtime documentation](https://vercel.com/docs/functions/runtimes/bun).

Enable Vercel Authentication on the compiler and OIDC on the backend. Configure
[Trusted Sources](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/trusted-sources)
to allow backend preview → compiler preview and backend production → compiler
production. Set `COMPILER_CALLER_PROJECT_ID` on the compiler to the backend's
project ID, and `ACTIONS_COMPILER_URL` on the backend to the HTTPS `/api/compile`
endpoint. The Python SDK obtains the backend's current OIDC identity and
forwards `x-vercel-trusted-oidc-idp-token`. The compiler verifies its signature,
expiry, project and matching environment with `@vercel/oidc`; missing identity
or configuration fails closed. No shared compiler secret is used.

### Actions dispatch

PostgreSQL owns run state, fenced job attempts and outbox commands. QStash
performs signed HTTP dispatch, liveness checks, cleanup and recovery. Provider calls
run outside database transactions; history and PR check reads never schedule
jobs. Cancellation revokes attempt capabilities before destroying sandboxes.
There is no resident scheduler or cron job.

Set `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY` and `QSTASH_NEXT_SIGNING_KEY` on
the backend. `QSTASH_URL` defaults to the hosted broker. Set `ACTIONS_SERVER_URL`
to the exact externally reachable backend URL used to publish callbacks and
verify their signed destination. Provider and broker credentials stay outside
sandbox manifests.

Integration/E2E fixtures start the official QStash image pinned by digest in
`backend/tests/conftest.py` with local test credentials and signature verification
enabled. Container callbacks use `host.docker.internal`; Linux Docker must
support `host-gateway`. Database locks exercise real delivery retries, and
pausing the broker exercises outbox recovery.

### Actions logs and completion

Agents push sequenced log chunks (64 KiB or every 500 ms) using fenced,
attempt-scoped Bearer capabilities. Unacknowledged chunks remain in a bounded
16 MiB local spool. Blob/S3 stores immutable, checksummed chunks; PostgreSQL
indexes and commits them before ACK. Redis Streams holds an expiring recent
tail and is optional for correctness. Run and PR-check rows contain metadata,
not complete log strings.

The Actions UI loads log history separately, follows authenticated SSE with
`Last-Event-ID`, and reconnects after bounded sessions. FastAPI handles SSE
framing and heartbeat comments; access and cursor validation happen before
streaming starts. Lost Redis data replays from Blob/S3. The viewer keeps a
bounded recent window and offers a full log download. Secret masking happens before segment boundaries.

Artifacts and structured completion results are pushed directly by the agent.
Completion waits for the final log ACK and releases dependent jobs through the
outbox. Sandbox clients only check liveness; they never fetch log, result or
artifact files. Rebuild prepared images/snapshots for version-four manifests.

## License

[MIT](LICENSE)
