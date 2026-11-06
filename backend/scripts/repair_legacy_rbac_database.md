# Recover a deployment blocked by a removed PR migration

The production backend build at main commit `2694347` and the PR preview build
at `93b22e3` both fail with:

```text
Can't locate revision identified by '05b106a4cc76'
```

That revision belongs to the old PR-only migration chain. Its two migrations
only created membership, team, collaborator, and token tables after main's
`c45f8528cc79`; they did not modify main's existing tables. This failure requires
database repair, not a dependency change or skipping migrations during builds.
Neon's Vercel integration has preview branching enabled, so repair the affected
production database and separately reset or repair the PR's preview branch.

Run [repair_legacy_rbac_database.sql](repair_legacy_rbac_database.sql) in the
affected database's Neon SQL editor, or with `psql` using its configured
connection. Verify the database branch before executing it. The script requires
exactly the obsolete revision and the expected legacy tables, and refuses an
unexpected schema. All changes run in one transaction.

The script archives the five obsolete feature tables in
`gitedge_rbac_archive_20261106` and restores the revision marker to main's
`c45f8528cc79`. It retains all their data, indexes, and foreign keys and leaves
users, organizations, repositories, discussions, and other application tables
in place. It does not grant access through archived roles or reuse old tokens.
Retain a provider snapshot if an independent backup is needed; do not drop the
archive as part of recovery.

After repair, redeploy main and confirm the backend becomes ready. Main has no
further migration after `c45f8528cc79`. The current PR can then apply its fresh
`346231be68fc` migration without colliding with the old feature tables. Resetting
a preview branch from an unrepaired production parent would inherit the same
obsolete revision, so repair production first.

This is a one-time operational repair. It is deliberately separate from the
application's Alembic chain and is never run automatically during deployment.
