# GitEdge Agents (experimental)

Agents execute in the Python backend, with Restate journaling model and tool
calls. Only tool commands execute in sandboxes. `/api/v1/agents` requires the
existing Bearer authentication and checks ownership and repository access.
Conversations are serialized by a Restate virtual object keyed by session ID.

## Configuration

Agents are disabled by default. Configure infrastructure before setting
`AGENTS_ENABLED=true`:

- `RESTATE_INGRESS_URL`, `RESTATE_AUTH_TOKEN`, and
  `RESTATE_IDENTITY_PUBLIC_KEY` for Restate Cloud. Identity verification is
  mandatory outside development.
- `AGENTS_SANDBOX=vercel` for native Vercel snapshots and deployment OIDC.
- `AGENTS_SANDBOX=kubernetes` for the upstream agent-sandbox Python SDK.
  Install the controller, extensions, router, and a warm pool first. Configure
  kubeconfig, kubectl, `AGENTS_KUBERNETES_NAMESPACE`, and
  `AGENTS_KUBERNETES_WARMPOOL`. Use a runtime image with Python, Bash, Git,
  coreutils, and flock, with permission to write `/workspace` and `/opt/gitedge`.
- `AGENTS_MODELS` is a JSON array of allowed provider-qualified model names.
  PydanticAI reads native provider credentials in the backend. Its
  `openai-chatgpt` provider uses subscription OAuth credentials; a ChatGPT
  subscription is not an OpenAI API key.
- `AGENTS_OPENAI_ENDPOINTS` is a server-managed JSON mapping of provider names
  to compatible API base URLs. For OpenCode Zen or Go, configure the appropriate
  endpoint, put its credential in `GITEDGE_<PROVIDER>_API_KEY`, and allow a model
  with that provider prefix. Credentials never enter tool machines or events.

Mounting `/restate` uses the SDK's ASGI request-response protocol. Register an
immutable Vercel deployment URL with Restate, using HTTP/1.1 and any required
Vercel deployment protection bypass header. Keep earlier deployments available
until their invocations finish. This Python/FastAPI/Vercel combination still
requires deployment-level recovery and timeout validation.

## Setup and snapshots

Create a private environment containing one or more authorized repositories,
then create a setup session. Repository contents and history are transferred as
Git bundles, without forge access tokens. Each repository is checked out below
`/workspace/<repository UUID>`. The setup script and instructions are written to
`.gitedge/agents/setup.sh` and `.gitedge/agents/instructions.md`.

A coding session requires a successful setup snapshot and forks that image.
Each turn resumes its session image, runs the backend harness, captures file and
line attribution, snapshots the machine, stops compute, and saves conversation
messages. Messages are stored individually; Agent Trace headers and ranges have
separate relational tables.

Vercel snapshots use the provider's native filesystem image. The portable
Kubernetes implementation archives `/workspace` and `/opt/gitedge` in application
blob storage because upstream PodSnapshot support targets GKE. Install portable
dependencies under those prefixes; system packages must be supplied by the warm
pool image. Running processes are not portable snapshot state.

## Streaming

AG-UI events are written to Redis Streams before delivery. Replay uses exclusive
Redis stream IDs supplied in `Last-Event-ID`; TCP Redis and Upstash REST both use
nonblocking polling. An atomic Lua operation deduplicates logical event IDs.
Native model events are saved separately to reconstruct the adapter on Restate
replay. Command receipts and output files remain in the sandbox, so a retried
tool can poll a previously started command. Browser transport reconnects with
its last received event cursor.

## Verification and remaining work

Run `uv run pytest tests/unit/test_agent_workspace.py` from `backend` for command
reattachment, shell validation, exit status, and output capture. Container tests
are in `tests/integration/agents`; they require a working Docker daemon and
sufficient disk for Restate, Ollama, K3S, and `qwen3.5:0.8b`. Image versions are
pinned and tracked by Renovate.

This is an experimental implementation, not a production release. Outstanding:

- The K3S fixture starts a cluster but does not yet install and validate the
  complete agent-sandbox controller/router/runtime stack or exercise snapshot
  fork isolation against it.
- Container replay, model interruption, recovery, and Vercel transport tests
  remain unverified. A partially streamed model request retried before its
  journal entry commits needs additional divergence/replacement testing.
- The workspace ports the reference's sidebar/chat/composer structure; the full
  reference UI, environment editing, provider/account credential management,
  notification dismissal, and reconnecting active runs after a page reload are
  not complete.
- Kubernetes portable snapshots cover the prefixes above rather than the full
  root filesystem. Large snapshot transfer and retention/garbage collection need
  further work.
- Runtime authorization should be rechecked when queued turns begin, and
  submissions need concurrency-conflict integration tests and quota enforcement.

Keep `AGENTS_ENABLED=false` until these checks and gaps are addressed.
