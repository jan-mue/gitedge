# Actions sandbox agent

One Bun agent executes one version-one job manifest inside an ephemeral Docker
container or Vercel Sandbox. Workflow YAML is compiled by
[`@gitedge/actions-compiler`](../actions-compiler/README.md); the agent validates its
shared IR and evaluates runtime expressions without reparsing workflow source.
JavaScript actions run under Node from the prepared image. Shell and composite
actions share command files, outputs, environment, masks and cancellation.

Build the pinned Bun 1.4.4 bytecode launcher with `bun run --filter
@gitedge/actions-runner build`. Images/snapshots prepare the action inventory and
toolchains before jobs start. Checkout transfers source at the immutable commit.
Prepared labels target x64 Linux; unsupported architectures fail explicitly.

`bun run test:actions` runs compiler and agent Vitest projects together under Bun;
`bun run typecheck:actions` checks both projects. `bun run test` also runs the
frontend project under Node. The runner check in `.gitedge/workflow` symlinks to
its GitHub definition.

## Cache storage

Repository-scoped cache metadata is stored in PostgreSQL, with immutable,
checksummed archive generations in the existing Blob/S3 provider. The agent
provides the v1/v2 Actions cache protocols locally and uses a scoped controller
capability to transfer payloads. Cache archives remain bounded to 32 MiB.
