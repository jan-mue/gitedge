# GitEdge Agents (experimental)

Agents execute in the Python backend, with Restate journaling model and tool
calls. Only tool commands execute in sandboxes. `/api/v1/agents` requires the
existing Bearer authentication and checks ownership and repository access.
Conversations are serialized by a Restate virtual object keyed by session ID.
Model/tool execution runs in a private `GitEdgeAgentTurns` service. Its completed
message result is a durable child-call result, so parent replay never restarts
the agent against a VM that later cleanup has deleted. Conversation data is
saved before stopping compute; failure status/events are saved before best-effort
cleanup.

## Configuration

The agent workspace is always enabled. Running agents requires the following
infrastructure and configuration:

- A persistent `SECRET_KEY` for encrypted provider connections.
- `RESTATE_INGRESS_URL`, `RESTATE_AUTH_TOKEN`, and
  `RESTATE_IDENTITY_PUBLIC_KEY` for Restate Cloud. Identity verification is
  mandatory outside development.
- `AGENTS_SANDBOX=vercel` for native Vercel snapshots and deployment OIDC.
- `AGENTS_SANDBOX=smol` (the default) for local smolvm microVMs through the upstream
  `SmolSandboxBackend`. The `smol` harness extra is installed on supported
  platforms. Configure `AGENTS_SMOL_IMAGE`, `AGENTS_SMOL_CPUS` (default 2), and
  `AGENTS_SMOL_MEMORY_MB` (default 2048). Networking is disabled unless
  `AGENTS_SMOL_ALLOW_INTERNET_ACCESS=true`; enabling it also exposes the host's
  reachable local network, not just the public internet.
  The default image is `python:3.14.10-slim-bookworm`. For repository agents,
  use an immutable OCI image containing Python, Bash, Git, coreutils, findutils,
  and util-linux (`flock`/`setsid`), for example a published build of
  `dev/agents/Dockerfile`. Images are pulled by smolvm, not the Docker daemon.
  Smol requires Apple silicon/macOS or Linux x86_64/aarch64 with access to
  `/dev/kvm`; local VM reattachment requires the same host/OS user.
  Native checkpoint capture also needs host `e2fsprogs` (`mkfs.ext4` on `PATH`),
  or the storage template described by smolvm's runtime error. Store checkpoints
  in `AGENTS_SMOL_CHECKPOINT_DIR` (default `~/.gitedge/checkpoints`). Keep this
  directory private: checkpoints contain the VM's filesystem, RAM, and processes.
- `AGENTS_MODELS` is a JSON array of allowed provider-qualified model names.
  PydanticAI reads native provider credentials in the backend. Its
  `openai-chatgpt` provider uses subscription OAuth credentials; a ChatGPT
  subscription is not an OpenAI API key.
- `AGENTS_OPENAI_ENDPOINTS` is a server-managed JSON mapping of provider names
  to compatible API base URLs. For OpenCode Zen or Go, configure the appropriate
  endpoint, put its credential in `GITEDGE_<PROVIDER>_API_KEY`, and allow a model
  with that provider prefix. Credentials never enter tool machines or events.

The SDK app is mounted natively with `app.mount("/restate", restate_app())`.
Pure-ASGI middleware resolves the existing FastAPI dependency graph for Restate
requests without consuming the request body or wrapping the protocol response.
The SDK owns streaming, identity verification, and shutdown signaling; the parent
FastAPI app owns lifespan. Register an
immutable Vercel deployment URL with Restate, using HTTP/1.1 and any required
Vercel deployment protection bypass header. Keep earlier deployments available
until their invocations finish. This Python/FastAPI/Vercel combination still
requires deployment-level recovery and timeout validation.

`run_app_locally.py` keeps hot reload enabled and bounds graceful shutdown to
five seconds. Active SSE clients reconnect after a reload; unfinished Restate
work resumes from its journal instead of holding the old development worker open.

`get_coding_agent_deps` constructs `CodingAgentDeps` through FastAPI, with nested
stream-store and provider-client dependencies. It is passed explicitly to
PydanticAI with `deps_type`/`deps`. The Vercel capability and workspace adapter
live in `app/sandboxes/vercel.py`; Smol uses upstream `SmolSandbox` and
`SmolSandboxBackend` directly. There is no shared sandbox lifecycle hierarchy
or custom Smol implementation. SDK clients remain open through the response and
close at the dependency's request-scope teardown.

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

Vercel uses native filesystem snapshots and `SnapshotSource` to create new
sandboxes from them. Snapshot capture stops the Vercel session. Snapshots expire
30 days after their last use by default, according to the provider's retention
policy.

Smol uses its SDK's native `AsyncMachine.checkpoint` and `restore_checkpoint`,
accessed through the upstream backend's `get_sandbox`. Checkpoint files are
independent of their source VM and survive its deletion; multiple restored VMs
diverge independently. They preserve RAM/processes as well as disk, and restore
the captured resource/device shape rather than applying the new-VM CPU/memory
settings. OS, architecture, CPU-feature, and runtime-format compatibility are
checked by smolvm. There are no custom filesystem archives or baseline scripts.
Checkpoint paths are application-owned, never accepted from untrusted input.

Kubernetes agent-sandbox support is removed until upstream native snapshots
support the required development/runtime environments.

All providers expose PydanticAI's `WorkspaceBackend` and `SupportsCommands`.
Commands use `run`; file operations use `Workspace`'s `read_bytes`/`write_bytes`
and related methods. Agents receive the provider's native workspace directly;
there is no command-execution wrapper or application-owned receipt protocol.
`Coder`'s upstream shell owns detached jobs, output limits, and reattachment.
The application supplies a stable run ID so retried tool calls reuse the same
upstream job IDs. Setup scripts run through the native workspace and should be
idempotent if an interrupted, unjournaled setup step is retried.

## Streaming

AG-UI events are written to Redis Streams before delivery. Replay uses exclusive
Redis stream IDs supplied in `Last-Event-ID`; TCP Redis and Upstash REST both use
nonblocking polling. An atomic Lua operation deduplicates logical event IDs.
Native agent events, including upstream shell output, are saved separately to
reconstruct the adapter on Restate replay. Shell job handles and output files
remain in the sandbox, so a retried tool can reattach to its existing job.
Shell output events become command logs in the UI; setup stdout/stderr are
published after the native setup command returns. Browser transport reconnects with
its last received event cursor.

`RestateToolOrdering` is a PydanticAI capability that rebuilds the SDK's tool
turnstile from each completed model response, including journal replay. This
works around the streamed-tool initialization missing in restate-sdk
1.5.2–1.5.4 without patching the SDK or replacing its durable tool execution.

Permanent workspace failures (including damaged filesystem output and dead VMs)
are converted to `TerminalError` inside journaled tool execution, before the SDK
can retry them. Provider transport failures retain bounded step retries. Failed
turn cleanup is best-effort and cannot prevent the failure status/event from
being saved. Unexpected invocation failures stop automatically after three
attempts and pause for operator inspection rather than retrying indefinitely.

## Verification and remaining work

Run `uv run pytest tests/unit/test_agent_shell_events.py tests/unit/test_agent_cancellation.py`
from `backend` for command-log encoding and cooperative cancellation. Container tests
are in `tests/integration/agents`; they require a working Docker daemon and
sufficient disk for Restate, Ollama, Smol VMs/checkpoints, and `qwen3.5:0.8b`. Image versions are
pinned and tracked by Renovate.

On macOS, Homebrew's `e2fsprogs` is keg-only. From `backend`, run native
checkpoint tests with its tools on the process's `PATH`, without modifying the
global shell configuration:

```shell
PATH="$(brew --prefix e2fsprogs)/sbin:$PATH" uv run pytest tests/integration/agents
```

Agent integration tests use real Smol VMs, Redis Streams, MinIO repository
storage, and Ollama models. Native checkpoint/fork tests also exercise Smol, and
`tests/integration/agents/test_smol.py` checks the upstream workspace's literal
argv, environment, binary files, exit status, and fresh filesystem reads. Smol tests skip only if
the SDK, host virtualization, or native checkpoint prerequisites are unavailable.
Stream recovery interrupts a real model connection through a
forwarding proxy; these tests do not use mocks, fakes, or simulated models.

This is an experimental implementation, not a production release. Outstanding:

- The CPU Ollama tool-turn test can finish without executing the requested tool,
  leaving its filesystem assertion failing. The streamed-tool turnstile
  `KeyError` is covered by the compatibility capability described above. Text turns,
  stream recovery, native Smol checkpoint/fork isolation, and running-process
  preservation pass; Vercel transport tests remain unverified.
- The workspace ports the reference's sidebar/chat/composer structure; the full
  reference UI, environment editing, provider/account credential management,
  notification dismissal, and reconnecting active runs after a page reload are
  not complete.
- Native snapshot retention/garbage collection needs further work. Smol refs
  name local VMs and checkpoints are host files, so distributed workers need
  host affinity/shared checkpoint storage, and
  a worker crash can leave an orphan before its ref reaches the Restate journal.
- Runtime authorization should be rechecked when queued turns begin, and
  submissions need concurrency-conflict integration tests and quota enforcement.

Resolve these checks and gaps before production use.
