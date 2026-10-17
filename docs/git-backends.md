# Git engines and object storage

`app/clients/git/interfaces.py` defines the application-facing `GitClient` and
`GitMergeClient` protocols. Services and HTTP routes use these protocols and
application schemas, bytes, and plain HTTP request/response records. Native Git
repositories, objects, walkers, and WSGI machinery stay in
`app/clients/git/dulwich/`.

To add Enroute or Gitoxide after suitable Python bindings become available:

1. Implement both protocols in a sibling adapter package. Translate its native
   objects and errors to the existing schemas and HTTP behavior inside the adapter.
2. Reuse `RepositoryStorage` for standard Git pack/index pairs and Redis refs, or
   provide an engine-specific persistence adapter over `BlobStorageClient` and the
   existing ref store. S3 and Vercel Blob selection remains independent of the engine.
3. Change `get_git_client` and `get_git_merge_client` in `app/api/dependencies.py`.
   Backend instances must remain request-scoped; mutable refs must be read fresh
   across requests. The metadata lookup callback only distinguishes an empty
   repository from a nonexistent repository when no Git data is stored.
4. Run the browsing, smart HTTP, merge, review, fork, rename, and deletion tests
   against the new implementation. Preserve object durability before ref
   publication, atomic merge tip checks, retained PR revisions, and merge recovery.

The refactor retains Dulwich as the only implemented engine. Neither proposed
replacement is a runtime dependency.

## Advanced Blob operations

Previously, every repository load listed the pack prefix. Derived-response caches
helped repeat requests, but misses for different files, protocol requests, and merge
checks still listed blobs. Forks and renames also listed objects before copying.

`RepositoryStorage` now stores a complete-pack catalog in Redis at
`<owner>/<repo>.git/pack-catalog:v1`. A missing catalog is discovered from blob
storage, retaining only matching `.pack`/`.idx` pairs, and installed atomically.
This works for existing repositories without rewriting objects. Catalog operations
use the same Redis availability and durability requirements as refs.

| Operation | Blob advanced operations after this change |
| --- | --- |
| Load with an existing catalog | Zero listings or uploads |
| First load, or recovery after catalog loss | One listing per page, then zero listings on later loads |
| Ref-only update | Zero listings or uploads |
| New pack | Two uploads, one pack and one index |
| Retry of a cataloged pack | Zero uploads |
| Fork or rename | Two uploads per missing pack pair; source/destination discovery only if their catalogs are missing |
| Delete | Listings remain, to find and remove uncataloged partial uploads too |

Uploads finish before catalog publication; catalog publication finishes before refs
become visible. Catalog updates use compare-and-set with retries so concurrent
writers adding distinct packs cannot lose each other's entries. Readers read refs
before the catalog to avoid observing newly published refs with an older catalog.
An incomplete cataloged pair fails the load rather than returning partial history.

The catalog has no TTL and is not stored in Vercel Runtime Cache. It must not be
served stale. All writers must update it: deploy the new writer code together, or
pause writes during a mixed-version rollout. After an out-of-band pack import or
an old writer has run, delete that repository's catalog key so the next load
rediscovers the pack pairs. Existing repository deletion removes the catalog too.
Repacking/removing packs still requires coordination with readers and writers;
the catalog does not introduce repository-wide locking.

## Caching and remaining costs

Vercel pack/index uploads use a one-year Blob cache lifetime, and downloads retain
the SDK's cached-read path. These keys are immutable: do not overwrite them with
unrelated data. Blob URL cache misses and metadata/download requests remain simple
operations under the supplied billing definition. Long Blob caching reduces those
misses; the Redis catalog eliminates the repeated advanced listing operations.
Vercel listings now request 1,000 items per page and follow every cursor, including
for legacy discovery and deletion.

Existing derived-response caches remain: branch-based responses use `CACHE_TTL`,
immutable revision responses use `CACHE_IMMUTABLE_TTL`, and writes invalidate the
repository group. Vercel Runtime Cache keys now include the repository group as
well as the response key, matching Redis's isolation. Tags alone only controlled
invalidation and could allow identical response keys in different repositories to
collide. The new `v2:` prefix also avoids reusing previously unscoped entries.

Forks retain independent physical objects, so their uploads remain advanced
operations. Sharing objects across repositories would require reference counting
and coordinated garbage collection before deletion could remain safe. Server-side
copy would still count as an advanced operation. Packing new objects into fewer
packs could reduce uploads further, but requires separately tuning push/merge
packing and compaction; this change preserves the existing pack format and layout.

The operation counts above follow code paths and unit-test assertions. They are
not measurements of production billing or a projected percentage saving.
