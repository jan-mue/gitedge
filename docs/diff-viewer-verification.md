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

### Backend loading improvements

The follow-up profiling compared the previous implementation at `8977b70` with
the optimized backend, in the same Python environment. These are CPU-only local
medians, excluding storage and HTTP latency:

| Fixture | Before | After |
| --- | ---: | ---: |
| 500 files with unique contents, compact index (7 runs) | 64.55 ms | 19.99 ms |
| 500 files repeating the same contents, compact index (7 runs) | 61.07 ms | 3.50 ms |
| 20,000-line file, one hunk near line 121, diff and highlighting (5 runs) | 2,418.07 ms | 24.62 ms |

Compact indexes now count changed ranges directly instead of constructing and
parsing every unified patch. Statistics for identical blob pairs are reused within
the request. Highlighting preserves multiline lexer context but retains tokens
only for displayed lines and stops after the last displayed line. Changes near
the end of a file still require lexing earlier content. Lazy file responses omit
the redundant raw patch. Cold repository loading downloads pack/index pairs
concurrently, with at most eight object-storage reads at once.

The final full-stack 500-file run observed a 24 ms file-index request and a first
highlighted file in 470 ms, with two initial per-file requests. This remains a
local development-server measurement with warmed repository data.

The follow-up verification passed 272 backend tests, 273 frontend tests, 13
full-stack browser tests, and 12 Storybook interaction checks across light/dark
desktop/mobile layouts. The browser checks cover the commits tab (excluding base
history), review dropdown placement and Escape/focus behavior, saved drafts,
automatic collapse of viewed files after reload, Markdown preview, comment
editing/deletion, and merging. Application and Storybook production builds pass.

Reproduce with `cd backend && PYTHONPATH=. uv run python benchmarks/diff_loading.py`.
For the baseline, check out `8977b70` into a separate worktree and set `PYTHONPATH`
to that worktree's `backend` directory while running the same benchmark script.

### Full application and renderer checks

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

## 2026-10-16 reference and CI corrections

Compared the running reference application with GitEdge at 820 and 1280 pixels,
including separate tab-strip screenshots. The reference uses 42-pixel tabs with
a 2-pixel blue active underline (`rgb(60, 140, 221)`). GitEdge previously inherited
a gray active border and pointer-focus outline from the shared pill-style preset,
and drew the bottom divider twice. PR tabs now use unstyled Radix primitives with
the reference's spacing and underline; keyboard focus remains visible. The Files
Changed tab also displays the reference's addition/deletion summary.

Sidebar geometry is checked at 768, 820, 1024, and 1180 pixels in both themes,
including portrait iPads. Metadata remains in the right column without page-level
horizontal overflow. Review events use Gitea's actual icon mapping:
[check for approvals, diff for requested changes](https://github.com/go-gitea/gitea/blob/main/models/issues/review.go),
with colored timeline markers and a purple merge marker. Merged PRs have no
reopen/close action, and the API rejects both transitions with HTTP 409; closed
PRs remain reopenable.

The [failed GitHub job](https://github.com/jan-mue/gitedge/actions/runs/38809693614)
had one failure and 126 passes. Its older PR file test expected files on the
conversation tab. It now opens Files Changed, and the diff header's missing
View file link is restored. Links address the displayed head revision, or the
base revision for deleted files, with encoded paths.

After merging main, local validation passed: all 127 integration tests against
real dependencies, 274 backend unit tests, and 282 frontend tests. The production
frontend and Storybook builds passed. The built-Storybook PR checks passed 18
cases; two tablet-only cases are intentionally skipped in the mobile projects.
Frontend unit tests used one worker and a 15-second timeout to avoid contention
with the full integration run; no assertions were disabled.

## Conversation ordering and review context

PR state events now come from the recorded activity rows, scoped to the exact
repository and PR. Merge, close, and reopen events are sorted with reviews and
comments by their original dates. Editing a description or repeating an unchanged
state does not move or duplicate the merge event. The final timeline segment
turns toward the comment composer's border instead of continuing alongside it.

Review comments display a short unified snippet from their immutable base/head
revisions, including line numbers, syntax tokens, changed-token emphasis, and a
marker on the commented line. Older comparisons have an Outdated label. Snippets
share the main viewer's code-row renderer and cached file requests; only previews
within 400 pixels of the viewport start loading. The browser selects at most six
existing diff rows without calculating diffs or syntax tokens. Failed or missing
context leaves the comment visible, with a retry for failed requests.

Regression coverage includes comments before and after merging, later description
edits, original/deleted versus changed lines, original revision context after a
new push, request deduplication, and unavailable-context handling. Browser checks
cover both themes and desktop/mobile layouts, including the connector's endpoint.

Validation for this follow-up passed: 274 backend unit tests, 285 frontend tests,
five full-stack PR/review regression cases, and 26 built-Storybook browser checks
(two intentional tablet-only skips on mobile projects). Both production builds
passed. The full-stack cases include the 500-file and 10,000-row diff checks.

## Anchored replies and initial conversation loading

Review snippets now end exactly at the commented line, without following code
rows or bottom padding before the comment header. Review badges use a separate
32-pixel circular wrapper around a 16-pixel SVG, with no padding on the SVG;
normal conversation markers use the same readable dimensions.

Published line comments and overall review comments support persistent replies,
including after new pushes and merging. Replies use a separate table keyed by
the immutable review and comment index, so simultaneous replies do not overwrite
one another or modify the original review. Reply text is rendered as Markdown in
the backend. The API requires authentication and verifies the requested PR and
comment index. Apply the additional autogenerated migration with
`cd backend && uv run alembic upgrade head`.

The conversation no longer starts commit-history or changed-file requests before
those tabs are opened. New reviews save a bounded highlighted snapshot during
submission, reusing the file already loaded for anchor validation. Older reviews
load a compact context endpoint only near the viewport. Outdated status uses two
branch-tip reads rather than calculating a comparison. Metadata queries no longer
eagerly load every discussion comment; discussion reads load comments explicitly,
and the state-event and author lookups use joined queries.

Run `PYTHONPATH=. uv run python benchmarks/review_loading.py` from `backend/` to
compare full-file loading with compact context on the same 10,000-row diff. The
full-file response is 3,459,704 bytes; the measured old/new line-1 snippets are
384 and 1,389 bytes, respectively. CPU timings are printed by the script and
depend on lexer context and available CPU. Newly submitted reviews require no
additional Git or context requests to display these snippets.

Browser regression checks assert that the anchor is the final rendered code row,
SVGs fit inside their circular badges, replies stay in their thread, and the
conversation does not fetch inactive Git tabs. Full-stack checks cover persisted
replies, post-merge replies, original snapshots after pushes, a 10,000-row reviewed
file, and normal PR/issue commenting, editing, deletion, and feed previews.

Local validation passed: 284 backend unit tests, 288 frontend tests, and 12
full-stack regression cases. All 30 distinct Storybook PR checks passed across
both themes and desktop/mobile, with two intentional tablet-only mobile skips.
One static asset fetch failed in the first tablet run; that tablet check passed
on recheck in both themes. Production app and Storybook builds passed. The real
10,000-row conversation fixture returned 899 bytes of review data and issued no
Git/context requests; conversation readiness was 1,415 ms in the local dev server.
