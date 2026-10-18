import { test } from "bun:test"
import assert from "node:assert/strict"
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { condition, evaluate, interpolate } from "./expressions.mjs"
import { commands, execute } from "./runner.mjs"

test("official expressions preserve types, context wildcards, and status conditions", () => {
  const context = {
    matrix: { version: 24 },
    needs: { one: { result: "failure" }, two: { result: "success" } },
    github: { workspace: "/tmp" },
  }
  assert.equal(interpolate("${{ matrix.version }}", context), 24)
  assert.equal(interpolate("node-${{ format('{0}', matrix.version) }}", context), "node-24")
  assert.equal(evaluate("contains(needs.*.result, 'failure')", context).value, true)
  assert.equal(condition("always()", context, "failure"), true)
  assert.equal(condition("matrix.version == 24", context, "failure"), false)
  assert.equal(condition("failure() && matrix.version == 24", context, "failure"), true)
})
test("file commands support multiline and preserve embedded equals", () => {
  assert.deepEqual(commands("a=one=two\nb<<END\nline1\nline2\nEND\n"), { a: "one=two", b: "line1\nline2" })
  assert.throws(() => commands("a<<END\nunfinished"), /Unterminated/)
})
test("shell, composite and JavaScript actions share outputs, environment, pre/post state and masks", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-executor-"))
  try {
    const directory = join(root, "source", ".gitedge", "local")
    await mkdir(directory, { recursive: true })
    await writeFile(
      join(directory, "action.yml"),
      `name: Local\nruns:\n  using: node24\n  main: main.cjs\n  post: post.cjs\n`,
    )
    await writeFile(
      join(directory, "main.cjs"),
      `const fs=require('fs');fs.appendFileSync(process.env.GITHUB_OUTPUT,'value=javascript\\n');fs.appendFileSync(process.env.GITHUB_STATE,'cleanup=present\\n');console.log('secret-value')`,
    )
    await writeFile(
      join(directory, "post.cjs"),
      `if(process.env.STATE_cleanup!=='present')process.exit(4);console.log('cleanup verified')`,
    )
    const composite = join(root, "source", ".gitedge", "composite")
    await mkdir(composite, { recursive: true })
    await writeFile(
      join(composite, "action.yml"),
      `name: Composite
inputs:
  message:
    default: present
outputs:
  value:
    value: \${{ steps.nested.outputs.value }}
runs:
  using: composite
  steps:
    - id: nested
      uses: ./.gitedge/local
    - shell: bash
      env:
        MESSAGE: \${{ inputs.message }}
      run: test "$MESSAGE" = present
`,
    )
    const entries = []
    const result = await execute(
      {
        workflow: `on: workflow_dispatch
jobs:
  test:
    outputs:
      result: \${{ steps.action.outputs.value }}
    steps:
      - id: export
        run: |
          echo "VALUE=works" >> "$GITHUB_ENV"
          echo "message=hello" >> "$GITHUB_OUTPUT"
      - id: action
        uses: ./.gitedge/composite
      - run: test "$VALUE" = works
      - id: failure
        continue-on-error: true
        run: exit 7
      - if: steps.failure.outcome == 'failure'
        run: echo recovered
`,
        job: "test",
        event_name: "workflow_dispatch",
        env: { GITHUB_RUN_ID: "1" },
        secrets: { TOKEN: "secret-value" },
      },
      { root, log: (entry) => entries.push(entry) },
    )
    assert.equal(result.status, "success")
    assert.equal(result.outputs.result, "javascript")
    assert.equal(result.steps.failure.outcome, "failure")
    assert.equal(result.steps.failure.conclusion, "success")
    assert.ok(entries.some((entry) => entry.msg === "cleanup verified"))
    assert.ok(entries.some((entry) => entry.msg === "***"))
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})
test("failed dependencies skip jobs unless an explicit status function allows them", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-executor-"))
  try {
    const result = await execute(
      {
        workflow: "jobs:\n  test:\n    steps:\n      - run: exit 99\n",
        job: "test",
        env: { GITHUB_RUN_ID: "1" },
        needs: { build: { result: "failure" } },
      },
      { root, log: () => {} },
    )
    assert.equal(result.status, "skipped")
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})

test("repository subdirectory actions share JavaScript entrypoints and cleanup hooks", async () => {
  const root = await mkdtemp(join(tmpdir(), "gitedge-subdirectory-action-"))
  try {
    const actionRoot = join(root, "prepared")
    const repository = join(actionRoot, "owner-repo", "sha")
    await mkdir(join(repository, "init"), { recursive: true })
    await mkdir(join(repository, "lib"), { recursive: true })
    await writeFile(join(actionRoot, "manifest.json"), JSON.stringify({ "owner/repo@sha": "owner-repo/sha" }))
    await writeFile(
      join(repository, "init", "action.yml"),
      "name: Nested\nruns:\n  using: node24\n  main: ../lib/main.cjs\n  post: ../lib/post.cjs\n",
    )
    await writeFile(
      join(repository, "lib", "main.cjs"),
      "require('fs').appendFileSync(process.env.GITHUB_OUTPUT,'value=shared\\n')",
    )
    await writeFile(join(repository, "lib", "post.cjs"), "console.log('shared cleanup')")
    const entries = []
    const result = await execute(
      {
        workflow: "jobs:\n  test:\n    steps:\n      - id: nested\n        uses: owner/repo/init@sha\n",
        job: "test",
        env: { GITHUB_RUN_ID: "1" },
      },
      { root, actionRoot, log: (entry) => entries.push(entry) },
    )
    assert.equal(result.status, "success")
    assert.equal(result.steps.nested.outputs.value, "shared")
    assert.ok(entries.some((entry) => entry.msg === "shared cleanup"))
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})
