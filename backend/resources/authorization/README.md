# Authorization

GitEdge uses PyCasbin directly (`casbin` on PyPI). Roles and their permission
inheritance live in `model.conf` and `policy.csv`. FastAPI endpoints compose
permission checks with an explicit authentication dependency:

```python
current_user: Annotated[
    User,
    Depends(require_permission("issues:write", user_dep=RepositoryUser)),
]
```

The dependency returns the authenticated user. `user_dep` accepts an Annotated
alias (`CurrentUser`, `OptionalUser`, `RepositoryUser`,
`OptionalRepositoryUser`, or `GitUser`) or its dependency callable.
FastAPI preserves dependency caching, overrides, and security metadata. `owner`
and `repo` are explicit named path parameters in the permission dependency;
handlers keep their normal path arguments. There is no signature rewriting,
argument-name mapping, or decorator library. Endpoints that do not consume the
user declare the permission in the router's `dependencies` list.

Routes declare one operation. The central `app/permissions.py` policy maps that
operation to both the account's Casbin permission and its PAT scope. For example,
`issues:write` requires repository read access plus the token's issue-write scope;
`repository:write` requires repository admin access plus the repository-write
scope. `git:read` and `git:write` map to their own token scopes. Session-only
operations such as collaborator management have no token scope, and unknown
operations are denied. There is no separate per-route `token_scope` declaration.

The database stores facts, not the static permission definitions:

- `organization_member`: organization membership and admin status.
- `team`: a named team belonging to one organization.
- `team_member`: team membership; users must also belong to its organization.
- `repository_collaborator`: a user or team granted a repository role.

The service caches the deployment-static Casbin model and policy once per warm
process, and compiles their role-to-permission relation into immutable sets.
Casbin only evaluates role names and actions: user IDs, team memberships, and
repository grants never enter the shared enforcer. `FastEnforcer` is a synchronous
policy-filter optimization; the installed PyCasbin version has no async cached
enforcer. `AsyncEnforcer` makes adapter/policy management async, while `enforce()`
is synchronous. Static in-memory evaluation does not need an async adapter.

Current actor roles come from asynchronous PostgreSQL queries scoped to repository
UUIDs. A single batch query combines direct grants, organization administration,
and team grants with both current organization membership and matching ownership.
Repository listings, starred profiles, forks, and feeds batch these lookups;
anonymous listings need no authorization query. The permissions endpoint resolves
roles once and derives all four flags from the static permission relation.

No user grants or access decisions are cached across requests or authorization
operations. Revocations are visible on the next check, including in another warm
instance; no distributed invalidation, background watcher, or persistent worker
is required. Cold starts rebuild the small static policy; warm invocations reuse
it. Role resolution for one repository or organization cannot authorize another,
and UUID-scoped grants survive renames. Automatic policy persistence is disabled.

| Role | Permissions |
| --- | --- |
| Read | Browse, clone, and read discussions, releases, and activity |
| Write | Read plus push, manage releases/drafts, and maintain discussions |
| Admin | Write plus edit repository settings and manage collaborators |
| Owner | Admin plus delete the repository and manage owner grants |

A repository's personal account owner has owner permission. Organization admins
inherit owner permission on their organization's repositories. Ordinary members
have no implicit access to private repositories: grant a user role or a team
role. Explicit user collaborators may be outside the organization; team grants
must belong to the repository's owning organization. The organization creator
becomes its first admin atomically. Only org admins can create repositories in
that namespace or manage membership and teams. Membership endpoints preserve
at least one admin. Existing site superusers retain administrative access.

Public repositories give everyone read permission, including anonymous visitors.
Private repositories require both authentication and a role. Anonymous requests
without permission return 401; authenticated users lacking permission get 403.
Invalid supplied credentials are rejected even on public repositories. Repository
listings, starred profiles, forks, and feeds filter inaccessible repositories.
Draft releases require write permission. Authenticated readers can open issues,
pull requests, and comments; authors can edit their discussions, and writers can
maintain them. Marking a pull request merged requires write permission.

Repository settings include a collaborators section for user and team grants.
Only owners can grant, demote, or revoke owner roles; admins cannot promote
themselves to owner. The structural repository owner always retains access.
Visibility is editable by repository admins; a private-source fork must stay private.

The API accepts Bearer access tokens. Git HTTP accepts Bearer access tokens or
HTTP Basic using the account username and password. Public clone/fetch is
anonymous; receive-pack discovery and push require write permission. Git
repositories must exist before cloning or pushing; unauthorized requests cannot
implicitly create repositories or load Git storage.

Management endpoints:

- `GET /repositories/{owner}/{repo}/permissions`
- `GET|PUT /repositories/{owner}/{repo}/collaborators`
- `DELETE /repositories/{owner}/{repo}/collaborators/{collaborator_id}`
- `GET /repositories/{owner}/{repo}/collaborator-teams`
- `GET /organizations/{organization}/members`
- `PUT|DELETE /organizations/{organization}/members/{user_id}`
- `GET|POST /organizations/{organization}/teams`
- `DELETE /organizations/{organization}/teams/{team_id}`
- `GET /organizations/{organization}/teams/{team_id}/members`
- `PUT|DELETE /organizations/{organization}/teams/{team_id}/members/{user_id}`

All paths are relative to `/api/v1`. Collaborator input requires exactly one of
`user_id` or `team_id`, plus `role` (`read`, `write`, `admin`, or `owner`). Membership
input uses `is_admin`. Team input uses `name`. The generated frontend SDK includes
these endpoints.

Apply the generated migration with `cd backend && uv run alembic upgrade head`.
Existing organizations have no reliable creator information in the old schema;
a site superuser must assign their initial admins with the membership endpoint.

## Personal access tokens

Account Settings → Access tokens supports an explicit repository selection and operation permissions,
issuance, safe metadata listings,
revocation, and atomic rotation. Copy each token when it is issued; it is shown
once. The account settings API requires an ordinary signed-in session, so PATs
cannot mint other tokens or access account management endpoints.

Tokens use `gitedge_pat_live_v1_<key_id>.<secret>`. The public lookup ID uses 12
random bytes and the credential secret uses `secrets.token_urlsafe(32)`. PostgreSQL
stores only an Argon2id hash of the secret (19,456 KiB memory, two iterations,
one lane), plus the public prefix/ID, last four characters, owner, name, scopes,
creation/expiry/last-use/revocation timestamps, and optional revocation reason.
Plaintext secrets appear only in issuance/rotation responses, which carry
`Cache-Control: private, no-store`. Hashing and verification run in a thread pool.

Repository API clients use `Authorization: Bearer <PAT>` or `X-API-Key: <PAT>`.
Only repository endpoints that explicitly declare a token operation accept PATs.
Account settings, organization administration, token management, and repository
creation require an account session. Tokens cannot mint other tokens.

Git clients can use their account username with the PAT as the HTTP Basic
password. Automation can instead use `Authorization: Bearer <PAT>` or
`X-API-Key: <PAT>`; the latter uses FastAPI's named `APIKeyHeader` security scheme.
Conflicting supplied credentials are rejected. The parser rejects malformed or
unknown PAT versions before querying token storage. Invalid supplied credentials
never fall back to anonymous reads. Existing account-password and session-token
Git authentication remain supported.

Each token has a nonempty, explicit `repository_ids` selection (up to 1,000 UUIDs).
There is no implicit “all repositories” or wildcard selection. The same operation
permissions apply to every selected repository. UUIDs preserve access across a
rename; newly created repositories are not included. Unselected repositories,
including public ones, are denied when a token is supplied. Deleted repositories
cannot become new grants through name reuse.

| Operation permission | Allowed operations |
| --- | --- |
| `repository:read` | Read repository contents, issues, pull requests, comments, releases, and activity |
| `git:read` | Clone and fetch |
| `git:write` | Push, clone, and fetch |
| `issues:write` | Create and update issues |
| `pull_requests:write` | Create and update pull requests |
| `pull_requests:merge` | Merge pull requests |
| `comments:write` | Create, edit, delete, and react to comments |
| `reviews:write` | Submit reviews/replies and manage private review drafts and viewed files |
| `releases:write` | Create and update releases |
| `repository:write` | Rename repositories and update settings |
| `repository:delete` | Delete repositories |

Permissions are independent except that Git write includes Git read. Review
endpoints also require `repository:read`. The older PATCH-to-merged endpoint
requires both pull-request write and merge permissions. Token permissions never
replace RBAC: the owner's current repository role must also allow each operation.
Removing a repository role immediately removes the token's corresponding access.
Expired/revoked tokens and inactive accounts cannot authenticate. Revocation is
checked again after secret verification.

New token records require a repository selection from creation. Rotation
atomically replaces both selections and revokes the old credential. Selection
validation and repository-role resolution use batch queries rather than one
query per selected repository.

Each valid public token identifier is limited to 60 authentication attempts per
minute by an atomic PostgreSQL update shared across workers. Incorrect-secret
attempts count toward this limit; responses return 429 and `Retry-After: 60`.
Token metadata listings contain no hash or full secret. Metadata-only audit events
for issuance, successful authentication, rotation, and revocation are scheduled
with FastAPI background tasks, and successful use updates `last_used_at`.

Token management API (relative to `/api/v1`):

- `GET /users/me/personal-access-tokens/repositories` (selectable repository identities)
- `GET|POST /users/me/personal-access-tokens/`
- `POST /users/me/personal-access-tokens/{token_id}/revoke`
- `POST /users/me/personal-access-tokens/{token_id}/rotate`

Issuance/rotation input uses `name`, `repository_ids`, `scopes`, and optional `expires_at` (a future
ISO timestamp or null). Revocation input uses optional `reason`. Rotation
revokes the old token only when its replacement is persisted successfully.
