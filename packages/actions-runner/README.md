# Actions compiler and agent

This Bun 1.4.3 workspace contains the on-demand compiler Function and the
job-scoped sandbox agent. `@actions/workflow-parser` and `@actions/expressions`
are pinned together at 0.3.61. FastAPI sends workflow source over HTTP and stores
the returned IR; the agent executes that manifest without parsing workflow YAML.

## Compiler endpoint

Deploy this workspace as a Vercel project with root directory
`packages/actions-runner` and access to source files outside that directory so
the root Bun workspace and lockfile are available. The included `vercel.json`
selects the provider-managed Bun 1.4.x runtime and caps Function duration at ten
seconds. Local tests and sandbox bytecode builds pin Bun 1.4.3; Vercel may
advance the compiler runtime patch version within 1.4.x. `api/compile.ts` and the local server use the same Web API handler.

Set a dedicated `COMPILER_TOKEN` on the compiler project. Set
`ACTIONS_COMPILER_URL` to its HTTPS `/api/compile` endpoint and
`ACTIONS_COMPILER_TOKEN` to the same secret on FastAPI. Keep these credentials
out of job manifests. If platform deployment protection is enabled, arrange
service access separately; the dedicated bearer token remains mandatory.

For development, configure `COMPILER_TOKEN` and run from the monorepo root:

```sh
bun run --filter @gitedge/actions-runner compiler:dev
```

The local server binds only `127.0.0.1`, defaults to port 8765, and supports
`COMPILER_PORT`. Point FastAPI at `http://127.0.0.1:8765/api/compile`.
Pytest starts and stops this server through its session-owned xprocess fixture
after infrastructure startup. Production FastAPI never spawns Bun.

## Versioned contracts

`src/domain/compiled-workflow.ts` defines compiler requests and IR; `job.ts`
defines agent intake. FastAPI validates the matching Pydantic contracts in
`backend/app/schemas/workflows.py`. Compiler requests and IR require version 1;
agent intake requires version 2 with a job UUID, attempt UUID, generation, and
fence. Rebuild prepared Docker images and Vercel snapshots when upgrading the
agent contract. Golden
JSON fixtures under `src/compiler/fixtures` are checked by Bun and Python tests.

The compiler checks parser errors before and after template conversion. It
extracts execution fields from validated tokens, retaining normalized official
expressions, `with`, shell, working directory, defaults, timeouts, environment,
outputs, and stable step IDs. The converter's convenience step model is not the
execution manifest. Compiled variant IDs are separate from sandbox resource IDs.
Raw source remains available for audit; persisted compiled IR drives execution.
Historical runs without compiled IR require a new dispatch to execute jobs.

Requests are limited to 2 MiB, source to 1 MiB of UTF-8, and IR to 4 MiB. Schema
or workflow errors return structured 422 diagnostics with source locations when
available. Authentication failures return 401; unexpected failures return 500.

Prepared runner labels target x64 Linux; ARM64 and other operating systems fail
explicitly. Supported triggers are push, pull request, and manual dispatch. Static matrices
support include/exclude, a maximum of 256 expanded jobs, and require
`fail-fast: false` when there are multiple variants. Branch/path filters support
`*`, `**`, `?`, and ordered negation. Advanced filter patterns, dynamic matrices,
reusable workflows, containers/services, concurrency, permissions, deployment
environments, and whole-object `with` expressions fail explicitly. Individual
action input expressions remain supported. Job metadata expressions must be resolvable using
the supplied event, static matrix, strategy, and dispatch inputs. Other execution
expressions are evaluated by the sandbox agent. Actions resolve from the prepared
image or checked-out repository; JavaScript actions use real Node from that image.

## Durable dispatch

FastAPI commits run transitions, fenced attempts, and outbox commands together
in PostgreSQL. QStash delivers signed dispatch, inspection, and cleanup requests
to `/api/v1/actions/internal/`. Provider I/O happens after transaction commit;
results are accepted only for the current claim and attempt. History and PR
check reads have no scheduling side effects. Cancellation revokes attempt
capabilities before resource cleanup.

Configure `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, and
`QSTASH_NEXT_SIGNING_KEY` on FastAPI. `QSTASH_URL` defaults to the hosted broker.
`ACTIONS_SERVER_URL` must be the exact externally reachable backend URL used
for publishing callbacks and verifying their signed destination. Keep provider
and broker credentials out of job manifests. Startup arms a delayed QStash
recovery callback; each callback arms its successor before recovering outbox
commands and expired leases. There is no resident scheduler or cron job.

Integration and browser tests require `ACTIONS_TEST_QSTASH_IMAGE` to be an
official `public.ecr.aws/upstash/qstash@sha256:...` image reference. Configure the
same repository Actions variable for GitHub CI. A missing or unpinned reference
fails the suite. Pytest starts the real `qstash dev` container with its documented
local-only credentials alongside PostgreSQL, Redis, and MinIO. The broker calls
back through `host.docker.internal`; Linux Docker must support `host-gateway`.
Test-owned HTTP fault proxies preserve signed URLs and original request bytes
while exercising native broker retries and recovery after failed publishing.

The durable log-segment archive, Redis tail, resumable SSE, and streaming large
artifact/cache transfers belong to subsequent phases. This phase retains the
existing bounded job log snapshots and Blob/S3 artifact and cache payloads.
