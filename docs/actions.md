# GitEdge Actions

GitEdge discovers GitHub/Gitea-style YAML in `.gitedge/workflow/*.yml` and
`*.yaml`. Every expanded matrix job gets a separate disposable sandbox. There is
no registered runner, polling worker, shared job container, or mounted Docker
socket. The Bun workspace project `@gitedge/actions-runner` in
`packages/actions-runner` is a one-shot TypeScript executor running on Bun,
linted by Biome and tested with Vitest. Its dedicated GitHub Actions workflow
runs Vitest and strict `tsc` checks. Shared development dependencies live in the
workspace root. It uses the official `@actions/expressions`
library for workflow expressions, with JavaScript/composite actions, step
conditions, outputs, environment files, and action pre/post hooks. It contains
no Go executor or Bash launcher. JavaScript actions run in the prepared Node
runtime; workflow `run:` steps use their declared shell. Both provider adapters inherit `AbstractSandboxClient` in
`backend/app/clients/sandboxes.py`.
The Docker provider uses aiodocker's native asynchronous API; the synchronous
Docker SDK is only a development dependency for integration-test tooling.

The Actions migration is generated directly on main's `c1e7092e3487` revision,
with new head `084d6e4246d8`. Preview databases stamped with the superseded
feature/merge revisions need recreation before applying this linear history.

## Startup and image preparation

Image builds, action downloads (including nested composite actions), and common
toolchain installation happen **before** jobs are dispatched. Missing action
versions fail explicitly and require a new prepared image. Provisioning sends
only a job descriptor. Vercel descriptors use compressed environment data within
the 4 KiB platform limit, with a descriptor-file fallback for larger workflows. The actual `actions/checkout` action fetches source from
GitEdge at the recorded commit; source archives are not uploaded during startup.

Build the base image and the optional Python CodeQL image:

```sh
docker build -f packages/actions-runner/Dockerfile -t gitedge-actions:local .
docker build -f packages/actions-runner/Dockerfile.codeql \
  -t gitedge-actions:integration .
```

For a managed environment with a proxy CA, add
`--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt`. The build mounts the
CA for networked commands; a managed build can install it into image trust. Runtime CA trust
can be supplied using `ACTIONS_DOCKER_CA_BUNDLE`; `ACTIONS_DOCKER_ENV` accepts
explicit proxy configuration. Local integration fixtures configure access from
containers to their ephemeral backend using `host.docker.internal`.

The base image prepares the action references in `packages/actions-runner/actions.txt`,
Python 3.14.0, Node 24, uv 0.13.0, and Bun 1.4.3. Change the preparation recipe
for other tool versions. Pin deployed Docker images by digest so action code and
tools remain consistent across every job in a run. The inventory unit test ensures
that every action in this repository's GitHub workflows also has a prepared reference and a real
integration example.

**The requested sub-100 ms cold provisioning target is not met.**
`ActionJob.startup_ms` records dispatch through the first step, including fresh
provisioning and state restoration, using controller/sandbox UTC timestamps.
It assumes synchronized clocks. `ActionJob.provisioning_ms` measures the provider call, including creation and
starting the command, separately from source checkout. Time to the first step
also includes state restoration after provisioning. The managed test host uses
Docker's `vfs` driver, which copies complete filesystems and takes seconds to start the prepared image. A separate experiment
with 20 tiny fresh containers also missed 100 ms in every sample: minimum
101.82 ms, median 112.78 ms, maximum 297.61 ms, including creation and start.
On a GitHub-hosted Docker machine, one fresh prepared-image provisioning call
measured 90.52 ms. That measurement excludes job bootstrap and restoration before
the first step, so it does not establish the full startup target.
Live Vercel validation on 2026-10-18 ran the five jobs at commit `4044396` in
fresh two-vCPU Frankfurt sandboxes, using a prepared 1.17 GB snapshot colocated
with the backend. All three workflows passed, covering matrix isolation,
dependency outputs, checkout, prepared toolchains, pre-commit, Codecov dry-run,
cache, artifact upload, and CodeQL. The PR checks and job-log links were verified
in a browser against the preview deployment.

| Job | Provider provisioning (ms) | Dispatch to first step (ms) |
| --- | ---: | ---: |
| Toolchains | 3451.60 | 3606.73 |
| CodeQL | 2841.45 | 2997.16 |
| Bun runner (alpha) | 2983.09 | 3147.91 |
| Bun runner (beta) | 1026.47 | 1178.14 |
| Dependency outputs | 1319.21 | 1464.54 |

First-step startup: **minimum 1178.14 ms, median 2997.16 ms, maximum 3606.73 ms**
(n=5). None met 100 ms. These measurements include provisioning and state
restoration; repository source transfers in the subsequent checkout step.
No warm-pool lease is reported as fresh provisioning. The sub-100 ms requirement
remains unmet, so this implementation remains a draft.

Preview PR: [GitEdge Actions verification](https://gitedge-frontend-git-feat-gitedge-actions-jan-mue-projects.vercel.app/actions-preview-1792310786111/gitedge-actions/pulls/1).
The frontend preview retains Vercel deployment protection. The prepared snapshot
expires after seven days; refresh it and update `ACTIONS_VERCEL_SNAPSHOT` before
expiry. Keep its region aligned with `ACTIONS_VERCEL_REGION`.

### Startup optimizations and follow-up measurements

The executor is now built by Bun into a minified bundle with precompiled Bun
bytecode. Build and runtime must use the same Bun version (currently 1.4.3), and
both `gitedge-launch` and `gitedge-launch.jsc` must be installed together.
State restoration runs on the first authenticated cache/artifact request, rather
than blocking every job before checkout. Jobs using only checkout and shell
steps make no state request. Concurrent storage requests share one restore.
Ready jobs provision concurrently within `ACTIONS_MAX_PARALLEL`. Vercel result
collection reads the completion marker first, then fetches finished files in
parallel without redundant process-status requests.

A controlled benchmark on a two-vCPU Frankfurt Vercel sandbox used Bun 1.4.3
and 20 fresh runner processes per variant. With an empty state endpoint delayed
by 100 ms, median time to the **first step's process executing** fell from
**161 ms to 39 ms**. Removing eager restoration accounted for about 105 ms;
bytecode reduced the remaining median from 56 ms to 39 ms. These are fresh
processes on an already-running VM, so they do **not** include VM provisioning.
[Raw bootstrap measurements](benchmarks/actions-bootstrap-2026-10-18.json)
include all 120 samples, with and without the delayed endpoint.

Fresh-VM checks measured **132–137 ms** from provider request acceptance to
session start, and **63–80 ms** from command start to the first step's process
for three optimized jobs. Three baseline jobs measured 73–93 ms for the latter;
the small, overlapping samples do not establish a cold-start bytecode speedup.
A one-vCPU VM took 128 ms to start and the stock universal image took 124 ms;
two vCPUs remain the default. These observed VM start times alone exceed the
100 ms target, before control-plane calls and executor startup.
[Raw cold measurements](benchmarks/actions-vercel-cold-2026-10-18.json) retain
the timestamps and the multi-second MCP connector gaps. Those gaps make these
dispatch-to-step measurements unsuitable for comparison with the colocated
backend measurements above. Remeasuring that complete path requires the preview
database recreation described earlier.

Reproduce the process benchmark inside a disposable prepared sandbox:

```sh
bun run --filter @gitedge/actions-runner build
bun run --filter @gitedge/actions-runner benchmark optimized=/path/to/dist/gitedge-launch
```

The Docker integration workflow uploads `actions-startup-measurements` with
provisioning and dispatch-to-first-step timings for its three fresh matrix and
dependency jobs. No performance assertion treats a warm sandbox as newly provisioned.

## Configuration

| Setting | Purpose |
| --- | --- |
| `ACTIONS_PROVIDER` | `docker` locally or `vercel` in production |
| `ACTIONS_IMAGE` | Prepared local Docker image |
| `ACTIONS_VERCEL_SNAPSHOT` | Required prepared Vercel snapshot ID; no image fallback at dispatch |
| `ACTIONS_VERCEL_REGION` | Snapshot region; defaults to the SDK region, which must match the snapshot |
| `ACTIONS_SERVER_URL` | Backend origin reachable from sandbox jobs |
| `ACTIONS_MAX_TIMEOUT` | Maximum job lifetime, in seconds (default 1200) |
| `ACTIONS_MAX_PARALLEL` | Maximum simultaneous jobs in a workflow (default 2) |
| `ACTIONS_SECRETS` | JSON mapping repository UUIDs to explicitly scoped secret maps |

Vercel SDK authentication stays in the controller. It is not passed into job
sandboxes. Create an image/snapshot out of band, including the executor and
prepared tools, then configure its immutable identifier. Each job sandbox uses
`persistent=False` and is destroyed after completion or cancellation. The
Vercel adapter uses the installed asynchronous Python Sandbox SDK; its lifecycle
contract is also unit tested without making billable calls.

## Events and control flow

Authenticated pushes by a repository owner or administrator deliver push events
after Git refs are persisted. For Git clients, pass the normal GitEdge bearer
token through `http.extraHeader`. Anonymous Git traffic does not authorize
workflow execution. Owner-authored pull requests deliver an `opened` event;
subsequent authenticated pushes to their head branches deliver `synchronize`.
PR checks query the current head commit and cannot reuse an older commit's success.
Their job links open the shared design-system log viewer. Both components have
Storybook stories for loading, pending, passing, failing, and empty states.
There are no cron jobs, scheduled reconciliation endpoints, or periodic workers.
`on.schedule` syntax is accepted but automatic scheduled delivery is unavailable.
Manual dispatch requires `on: workflow_dispatch` and repository-owner or
administrator authorization. Private run history requires the same access.

Runs persist their exact definition, commit, event, provider, matrix variants,
masked logs, outputs, and lifecycle state in PostgreSQL. Short API invocations
advance state under a row lock with `SKIP LOCKED`. Short-lived signed completion
callbacks advance dependent jobs without waiting for UI polling. Reading run
history refreshes live logs and can retry collection or cleanup. Stable sandbox
names make repeated event handling idempotent. A job-local timeout leaves the
launcher alive to archive state and send completion, including on failure. A
30-second provider cleanup grace bounds finalization. Provider timeouts bound execution;
cleanup failures retain handles for retry. There is no background recovery sweep.
Cache/artifact state is stored in the
configured blob backend, with individual job archives retained under each run.
Repository cache snapshots contain cache data only; artifacts stay in run state.
Mutable Vercel Blob writes allow replacement, and restores bypass stale CDN
responses; immutable repository reads retain their normal caching behavior.

The Actions tab provides the reference UI's workflow sidebar, actor/status
filters, run list, jobs sidebar, expandable plain-text logs, dispatch, and
cancellation, using GitEdge's existing design-system controls and theme tokens.
Run URLs preserve the selected run in a query parameter.

## Compatibility and limits

Supported workflow features include push branch/tag/path filters, dispatch,
job dependencies and outputs, literal matrices with include/exclude, workflow,
job, and step environments, shell steps, local actions, prepared remote
JavaScript/composite actions, GitHub expressions, step `if`, `always()`,
`failure()`, step `continue-on-error`, and action cleanup hooks.

Dynamic matrices, reusable workflows, job/service containers, Docker actions,
Windows/macOS runners, and nested Docker execution are rejected explicitly.
Linux labels select the prepared Linux environment; they do not install a
particular Ubuntu release. Host resource limits and image selection are
operator policy and cannot be overridden by workflow YAML. Each transferred
sandbox file is limited to 32 MiB. Cache entries are persisted independently,
so parallel jobs and jobs without cache writes preserve unrelated keys. Restore
is bounded to 128 entries and 32 MiB; concurrent writes to the same key/version
remain last-writer-wins.
Artifact uploads use the executor's job-local results service. For official
artifact steps, the adapter adjusts the toolkit's hostname probe to allow this
protocol on GitEdge; checkout and the workflow's GitHub context keep GitEdge's
origin. Artifact archives are retained in blob storage; the UI currently shows
upload logs rather than an artifact download browser.

GitHub-hosted APIs are separate integrations: GitEdge does not pretend to host
GitHub's Code Scanning or Codecov service. Integration examples execute the real
Codecov action in dry-run mode and the real CodeQL init/analyze actions with
prepared tools, cached offline feature defaults, and uploads disabled; they do not send code or coverage to an
external account. Other uses must supply an appropriate external integration.

## Verification

```sh
bun install --frozen-lockfile
bun run --filter @gitedge/actions-runner typecheck
bun run --filter @gitedge/actions-runner test
uv run --directory backend pytest tests/unit
ACTIONS_IMAGE=gitedge-actions:integration \
  uv run --directory backend pytest tests/integration/actions
bun run --filter frontend test src/components/Actions/RepositoryActions.test.tsx
```

The integration workflows cover real Git checkout, isolated matrix jobs,
dependency outputs, failure propagation, `always()` cleanup, every action
reference currently used by the repository, cross-run caching, and artifact
upload with ZIP content readback. The push test also observes database state
without polling the Actions API, verifying completion-driven dependency execution.
The browser suite runs in a separate pytest process as required by the
repository's testing guidelines.

## Upstream references

- Runner architecture: <https://gitea.com/gitea/runner>
- Expression library: <https://github.com/actions/languageservices/tree/main/expressions>
- UI adapted from `src/pages/ActionsPage.tsx` at
  <https://github.com/jan-mue/gitea-clone/commit/11d7444379a8f0006b881081cedf0a34b9f77614>
