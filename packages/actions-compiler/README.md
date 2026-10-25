# Actions compiler

This Bun workspace validates GitHub/Gitea workflow syntax with the official
`@actions/workflow-parser` and evaluates static expressions with
`@actions/expressions`, pinned together at 0.3.61. It extracts version-one IR from
validated source tokens, preserving execution fields omitted by the convenience
converter. `@gitedge/actions-compiler/workflow` exports the shared Zod/TypeScript
contract; the sandbox agent imports that schema without bundling the parser.

## Deployment and authentication

Deploy this package as the `gitedge-actions-compiler` Vercel project, with root
`packages/actions-compiler` and source files outside the root enabled for the Bun
workspace lockfile. Local builds pin Bun 1.4.4; the Function uses Vercel's managed
1.4.x runtime. The function duration is capped at ten seconds.

Enable Vercel Authentication for all compiler deployments. In Trusted Sources,
authorize the `gitedge-backend` project for preview → preview and production →
production. Enable OIDC on the backend project and set `COMPILER_CALLER_PROJECT_ID`
on the compiler to the backend's project ID. The Python client obtains the current
identity from Vercel's SDK and forwards `x-vercel-trusted-oidc-idp-token`.

The compiler also verifies signatures, expiry, the calling project and matching
deployment environment with `@vercel/oidc`. Missing identity is rejected; missing
caller configuration fails closed. `COMPILER_TOKEN` and `ACTIONS_COMPILER_TOKEN`
are no longer used. On FastAPI, set `ACTIONS_COMPILER_URL` to `/api/compile` on this
project's deployment.

See [Trusted Sources](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/trusted-sources).

## Local development and tests

Run `bun run --filter @gitedge/actions-compiler dev` from the repository root.
`COMPILER_PORT` defaults to 8765. The test/development server binds only to
`127.0.0.1` and uses the same bounded HTTP handler with local access. FastAPI allows
unauthenticated HTTP only to loopback in its development environment; remote
compiler requests require HTTPS and OIDC. Production never starts a compiler
subprocess.

Use `bun run test:actions` and `bun run typecheck:actions` for compiler and agent
checks. The root Vitest projects configuration also includes the frontend; its
tests and coverage run under Node, while Actions tests run under Bun.

Requests are limited to 2 MiB, source to 1 MiB and IR to 4 MiB. Invalid workflows
return structured 422 diagnostics; unexpected faults remain 500 responses.
Supported triggers are push, pull request and manual dispatch. Static matrices
support include/exclude and require `fail-fast: false` for multiple variants.
Filters use minimatch with ordered exclusion and re-inclusion. Dynamic matrices,
reusable workflows, containers/services, concurrency and deployment environments
fail explicitly. Explicit permissions are limited to `contents: read`.
