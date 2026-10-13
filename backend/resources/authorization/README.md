# Authorization

GitEdge uses PyCasbin directly (`casbin` on PyPI). Roles and their permission
inheritance live in `model.conf` and `policy.csv`; FastAPI endpoints declare
permissions with `@require_permission("repository:write")` or the relevant
permission. Handlers explicitly declare `owner`, `repo`, their authentication
argument, and their authorization service; the decorator checks those arguments
before calling the handler. It injects no repository object or extra parameters.
Underscored authentication/service arguments used only by the decorator are
explicitly mapped at the decorator call. No decorator library or OpenFGA server is required.

The database stores facts, not the static permission definitions:

- `organization_member`: organization membership and admin status.
- `team`: a named team belonging to one organization.
- `team_member`: team membership; users must also belong to its organization.
- `repository_collaborator`: a user or team granted a repository role.

The service creates an isolated Casbin enforcer from the files and current facts.
Repository and organization UUIDs are separate authorization domains. Grants
survive renames, and grants on one repository cannot authorize another. No
cross-request authorization cache is used; revocations apply on the next request.

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

Account Settings → Access tokens supports issuance, safe metadata listings,
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

Git clients can use their account username with the PAT as the HTTP Basic
password. Automation can instead use `Authorization: Bearer <PAT>` or
`X-API-Key: <PAT>`; the latter uses FastAPI's named `APIKeyHeader` security scheme.
Conflicting supplied credentials are rejected. The parser rejects malformed or
unknown PAT versions before querying token storage. Invalid supplied credentials
never fall back to anonymous reads. Existing account-password and session-token
Git authentication remain supported.

`git:read` permits clone/fetch, and `git:write` permits read plus push, including
receive-pack discovery. Scopes do not replace repository roles: both the token
scope and the owner's current repository permission must allow the operation.
Expired/revoked tokens and inactive accounts cannot authenticate. Revocation is
checked again after secret verification.

Each valid public token identifier is limited to 60 authentication attempts per
minute by an atomic PostgreSQL update shared across workers. Incorrect-secret
attempts count toward this limit; responses return 429 and `Retry-After: 60`.
Token metadata listings contain no hash or full secret. Metadata-only audit events
for issuance, successful authentication, rotation, and revocation are scheduled
with FastAPI background tasks, and successful use updates `last_used_at`.

Token management API (relative to `/api/v1`):

- `GET|POST /users/me/personal-access-tokens/`
- `POST /users/me/personal-access-tokens/{token_id}/revoke`
- `POST /users/me/personal-access-tokens/{token_id}/rotate`

Issuance/rotation input uses `name`, `scopes`, and optional `expires_at` (a future
ISO timestamp or null). Revocation input uses optional `reason`. Rotation
revokes the old token only when its replacement is persisted successfully.
