# Diff viewer and pull request review verification

Verified locally on 2026-10-15 with Chromium, FastAPI, PostgreSQL, Redis, and
MinIO. The integration tests use real Git pushes, normal login, real HTTP requests,
and the migrated database; they do not replace storage or authentication with fakes.

## Performance design

The previous eager renderer mounted 532,553 elements for 500 files with 40 removed
and 40 added lines each. One development-build sample took 12.6 seconds to mount
and 20.4 seconds to switch to split layout. This was unsuitable for large PRs.

The replacement uses these techniques, informed by Pierre's source at
[3c763dc](https://github.com/pierrecomputer/pierre/tree/3c763dc3b84943e30f13a665ef178499c2822b22/packages/diffs):

- [CodeView](https://github.com/pierrecomputer/pierre/blob/3c763dc3b84943e30f13a665ef178499c2822b22/packages/diffs/src/components/CodeView.ts)
  bounds rendering to the visible file window. GitEdge uses TanStack Virtual for
  files, large file rows, and long file navigation lists, with overscan and stable
  path keys. A 10,000-row diff does not mount 10,000 rows.
- [Virtualizer](https://github.com/pierrecomputer/pierre/blob/3c763dc3b84943e30f13a665ef178499c2822b22/packages/diffs/src/components/Virtualizer.ts)
  measures changing content and scroll positions. GitEdge measures variable row
  heights so wrapping and comments work; active editors remain mounted while
  scrolling. Loading placeholders reserve their eventual height to avoid fetching
  an entire PR when initially empty files enter the viewport.
- [UniversalRenderingManager](https://github.com/pierrecomputer/pierre/blob/3c763dc3b84943e30f13a665ef178499c2822b22/packages/diffs/src/managers/UniversalRenderingManager.ts)
  batches rendering by animation frame. GitEdge batches resize measurements by
  animation frame and uses passive scroll observation through TanStack Virtual.
- Pierre caches derived results and annotations. GitEdge caches highlighted files
  by immutable comparison revisions, reuses client query results across remounts,
  and indexes annotations by file and line rather than scanning every comment for
  every line.
- Pierre moves highlighting work away from rendering. GitEdge keeps highlighting
  and token diffing on the backend, moves computation off the async event loop,
  returns a compact file index first, and highlights only requested files. Review
  validation loads only files containing comments; marking a file viewed does not
  highlight the whole PR.

No Pierre source was copied. Shiki and client-side diff calculation are not part
of GitEdge's production viewer.

## Rendering comparison

Production builds; 1440 × 1000 viewport; three samples per case; medians in ms.
Both inputs contain the same 40 removed and 40 added TypeScript lines per file.
Input generation/parsing and HTTP transfer are outside this rendering benchmark.
Mount timing ends after two animation frames. Layout-switch timing uses the same
click and two-frame boundary. Element counts include shadow roots.
Pierre uses npm `@pierre/diffs@1.5.2`, its virtualized React `CodeView`, word diffs,
and a viewport-height container. GitEdge also renders its file navigation and
layout toolbar. Default fonts and renderer themes differ.

| Files | Renderer | Mount | Switch to split | Mounted elements after switch |
| --- | --- | ---: | ---: | ---: |
| 100 | GitEdge | 471 | 72 | 2,886 |
| 100 | Pierre CodeView | 227 | 54 | 1,894 |
| 500 | GitEdge | 292 | 50 | 2,330 |
| 500 | Pierre CodeView | 118 | 68 | 1,894 |

Pierre mounts faster in this microbenchmark. Both implementations now keep DOM
size bounded and switch layouts in a comparable time range, rather than growing
work with the total line count. These are local samples, not a universal claim
of equal performance or a network latency guarantee.

## Full-stack checks

The 500-file PR integration test observed a 96,161-byte file-index response,
initially requested only two highlighted files, and displayed the first
highlighted file in 436–1,338 ms across the local verification runs. The index was
already warmed by loading the PR conversation; this is not a cold-cache API
benchmark. The test enforces bounded DOM, bounded rendered rows, and fewer than
ten initial per-file requests instead of fragile wall-clock limits.

The tests cover:

- UI PR creation after real Git pushes; commit and standalone comparison pages.
- Backend syntax tokens and inline changes, unified/split layouts, wrapping,
  filtering, and navigation to file 500.
- Private line drafts on both sides, persistence after reload, viewed-file
  progress, all three review outcomes, and author self-approval rejection.
- A new push rejecting an old review, preserving the old draft, clearing viewed
  progress, and starting a review at the new revision.
- A 10,000-row file, bounded row rendering, and retaining an unfinished comment
  while scrolling away and back.
- Mobile comparison layout without page-level horizontal overflow.

The new-push test caught stale browser/CDN caching of PR comparison metadata.
PR file indexes and mutable standalone comparisons now use `Cache-Control: no-store`; immutable per-file responses
remain cacheable. Unit tests also cover deleted files, binary files, CRLF source,
root commits, missing/unchanged paths, submodule changes, syntax context outside
hunks, and unequal replacement blocks.

## Reproduction

From `backend/`, with Docker available:

```sh
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium uv run pytest \
  tests/integration/test_diff_reviews.py tests/integration/test_commit_history.py -q -s
uv run pytest tests/unit
```

Omit `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` when using Playwright's installed
Chromium. For the standalone production rendering fixture, from `frontend/`:

```sh
bun run benchmark:build
bun run benchmark:serve
# In another terminal:
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium bun run benchmark:measure
```

The benchmark is a separate build, not a production application route. Its fixture
can also be opened with `?files=500&lines=1000` to check a much larger in-memory
input; the normal application avoids transferring this entire highlighted input.
The measurement script accepts an alternate URL for another renderer exposing the
same `window.benchmark` timing contract and Unified/Split buttons.

To reproduce the Pierre comparison without adding Pierre to application dependencies:

```sh
# From frontend/; creates and installs a pinned, isolated temporary workspace:
node benchmarks/prepare-pierre.mjs
# Follow the printed build/serve command in that temporary directory, then:
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
  bun run benchmark:measure http://127.0.0.1:5176/
```

The online GitHub Actions advisory lookup is blocked by the environment's network
policy. The remaining repository checks, including zizmor's offline audits, can
run normally with `ZIZMOR_OFFLINE=true pre-commit run -a`.
