import { afterEach, describe, expect, test, vi } from "vitest"
import adapter from "../../api/compile.ts"
import { type CompileRequest, compiledWorkflowSchema } from "../domain/compiled-workflow.ts"
import { CompileError, compileWorkflow } from "./compile.ts"
import { handleCompile } from "./handler.ts"

const event = { name: "push" as const, ref: "refs/heads/main" }
const compile = (source: string, context: CompileRequest["event"] = event) =>
  compileWorkflow({ version: 1, filename: "test.yaml", source, event: context })
function workflow(job: string, trigger = "push"): string {
  return `on: ${trigger}\njobs:\n  test:\n    runs-on: ubuntu-latest\n${job}`
}

describe("official parser compiler", () => {
  test.each(["basic", "parallel", "dependencies"])("matches the %s golden contract", async (name) => {
    const root = new URL(`./fixtures/${name}`, import.meta.url)
    const source = await Bun.file(`${root.pathname}.yaml`).text()
    const output = await compileWorkflow({ version: 1, filename: `.gitedge/workflow/${name}.yaml`, source, event })
    expect(output).toEqual(await Bun.file(`${root.pathname}.json`).json())
    expect(compiledWorkflowSchema.parse(JSON.parse(JSON.stringify(output)))).toEqual(output)
  })
  test("retains execution fields omitted by the convenience converter", async () => {
    const source = await Bun.file(new URL("./fixtures/basic.yaml", import.meta.url)).text()
    const output = await compile(source)
    const [command, checkout] = output.jobs[0].config.steps
    expect(command).toMatchObject({
      id: "command",
      shell: "bash",
      "working-directory": ".",
      "timeout-minutes": 1,
      env: { FLAG: "${{ github.event_name }}" },
    })
    expect(checkout).toMatchObject({ with: { ref: "${{ github.sha }}", "fetch-depth": "0" } })
    expect(output.defaults).toEqual({ run: { shell: "bash" } })
    expect(output.jobs[0].config.defaults).toEqual({ run: { "working-directory": "." } })
  })
  test.each([
    workflow("    steps:\n      - run: true\n").replace("runs-on: ubuntu-latest", "runs-on: [linux, ARM64]"),
    "on: [push\njobs: {}",
    "on: push\non: pull_request\njobs: {}",
    workflow("    steps:\n      - run: echo '${{ not_a_context.value }}'\n"),
    workflow("    needs: absent\n    steps:\n      - run: true\n"),
    workflow("    needs: test\n    steps:\n      - run: true\n"),
    workflow("    steps:\n      - id: duplicate\n        run: true\n      - id: duplicate\n        run: false\n"),
    workflow("    steps:\n      - uses: docker://alpine:latest\n"),
    workflow("    steps:\n      - uses: actions/checkout@v4\n        with: ${{ fromJSON('{}') }}\n"),
    workflow("    services:\n      db:\n        image: postgres\n    steps:\n      - run: true\n"),
    workflow("    concurrency: shared\n    steps:\n      - run: true\n"),
    workflow(
      "    strategy:\n      matrix: ${{ fromJSON(needs.parent.outputs.matrix) }}\n    steps:\n      - run: true\n",
    ),
    "on: push\njobs:\n  call:\n    uses: owner/repo/.github/workflows/build.yml@main\n",
  ])("rejects invalid or unsupported source visibly", async (source) => {
    await expect(compile(source)).rejects.toBeInstanceOf(CompileError)
  })
  test("expands static include/exclude matrices and exposes strategy context", async () => {
    const output = await compile(
      workflow(
        "    strategy:\n      fail-fast: false\n      matrix:\n        node: [20, 24]\n        exclude: [{node: 20}]\n        include: [{node: 20, extra: true}]\n    timeout-minutes: ${{ matrix.node }}\n    steps:\n      - run: echo '${{ strategy.job-index }}'\n",
      ),
    )
    expect(output.jobs.map((job) => job.matrix)).toEqual([{ node: 24 }, { node: 20, extra: true }])
    expect(output.jobs.map((job) => job.timeoutSeconds)).toEqual([1440, 1200])
    expect(output.jobs[1].strategy).toEqual({ "job-index": 1, "job-total": 2 })
  })
  test.each(["0", "-1", ".inf", "not-a-number"])("rejects invalid timeout %s", async (duration) => {
    await expect(
      compile(workflow(`    timeout-minutes: ${duration}\n    steps:\n      - run: true\n`)),
    ).rejects.toBeInstanceOf(CompileError)
    await expect(
      compile(workflow(`    steps:\n      - timeout-minutes: ${duration}\n        run: true\n`)),
    ).rejects.toBeInstanceOf(CompileError)
  })
  test("bounds matrix expansion before allocation and preserves include merges", async () => {
    const source = workflow(
      "    strategy:\n      fail-fast: false\n      matrix:\n        os: [linux, windows]\n        node: [20, 24]\n        exclude: [{os: windows, node: 20}]\n        include: [{os: linux, extra: true}, {os: mac, node: 24}]\n    steps:\n      - run: true\n",
    )
    const result = await compile(source)
    expect(result.jobs.map((job) => job.matrix)).toEqual([
      { os: "linux", node: 20, extra: true },
      { os: "linux", node: 24, extra: true },
      { os: "windows", node: 24 },
      { os: "mac", node: 24 },
    ])
    expect(new Set(result.jobs.map((job) => job.id)).size).toBe(4)
    await expect(
      compile(
        workflow(
          `    strategy:\n      fail-fast: false\n      matrix:\n        x: [${Array.from({ length: 257 }, (_, index) => index).join(",")}]\n    steps:\n      - run: true\n`,
        ),
      ),
    ).rejects.toBeInstanceOf(CompileError)
    await expect(
      compile(workflow("    strategy:\n      matrix: {x: []}\n    steps:\n      - run: true\n")),
    ).rejects.toBeInstanceOf(CompileError)
  })
  test("matches GitHub branch and path filters without a Python matcher", async () => {
    const source = workflow(
      "    steps:\n      - run: true\n",
      "\n  push:\n    branches: [main, 'release/**', '!release/test']\n    paths: ['src/**/*.py']",
    )
    expect((await compile(source, { ...event, changedPaths: ["src/test.py"] })).matched).toBe(true)
    expect(
      (await compile(source, { ...event, ref: "refs/heads/release/test", changedPaths: ["src/test.py"] })).matched,
    ).toBe(false)
    expect((await compile(source, { ...event, changedPaths: ["docs/test.md"] })).matched).toBe(false)
  })
  test("ignore-only ref filters exclude the other ref type and empty path changes", async () => {
    const source = workflow("    steps:\n      - run: true\n", "\n  push:\n    branches-ignore: [private]")
    expect((await compile(source, { ...event, ref: "refs/tags/v1" })).matched).toBe(false)
    expect((await compile(source, { ...event, ref: "refs/heads/main" })).matched).toBe(true)
    const paths = workflow("    steps:\n      - run: true\n", "\n  push:\n    paths-ignore: ['docs/**']")
    expect((await compile(paths, { ...event, changedPaths: [] })).matched).toBe(false)
  })
  test("resolves expressions in runner label arrays and rejects empty expanded matrices", async () => {
    const source = workflow("    strategy:\n      matrix: {os: [linux]}\n    steps:\n      - run: true\n").replace(
      "runs-on: ubuntu-latest",
      "runs-on: [self-hosted, '${{ matrix.os }}']",
    )
    expect((await compile(source)).jobs[0].matrix).toEqual({ os: "linux" })
    await expect(
      compile(
        workflow("    strategy:\n      matrix: {os: [linux], exclude: [{os: linux}]}\n    steps:\n      - run: true\n"),
      ),
    ).rejects.toBeInstanceOf(CompileError)
  })
  test("PR filters use the base branch and GitHub default activity types", async () => {
    const source = workflow("    steps:\n      - run: true\n", "\n  pull_request:\n    branches: [main]")
    const request = { name: "pull_request" as const, ref: "refs/heads/feature", baseRef: "main" }
    expect((await compile(source, { ...request, action: "synchronize" })).matched).toBe(true)
    expect((await compile(source, { ...request, action: "closed" })).matched).toBe(false)
  })
  test("keeps typed dispatch defaults and quoted expression delimiters", async () => {
    const source = workflow(
      "    steps:\n      - run: echo \"${{ format('a}}b-{0}', inputs.enabled) }}\"\n",
      "\n  workflow_dispatch:\n    inputs:\n      enabled:\n        type: boolean\n        default: true",
    )
    const result = await compile(source, { name: "workflow_dispatch", ref: "refs/heads/main" })
    expect(result.inputs).toEqual({ enabled: true })
    expect(result.jobs[0].config.steps[0]).toMatchObject({ run: expect.stringContaining("a}}b") })
  })
})

afterEach(() => vi.unstubAllEnvs())
const request = (body: unknown, token = "compiler-test") =>
  new Request("http://compiler/api/compile", {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
test("production adapter and local server share authenticated bounded HTTP behavior", async () => {
  vi.stubEnv("COMPILER_TOKEN", "compiler-test")
  expect(adapter.fetch).toBe(handleCompile)
  expect((await handleCompile(new Request("http://compiler/healthz"))).status).toBe(200)
  const input = { version: 1, filename: "test.yaml", source: workflow("    steps:\n      - run: true\n"), event }
  expect((await handleCompile(request(input, "wrong"))).status).toBe(401)
  const response = await handleCompile(request(input))
  expect(response.status).toBe(200)
  expect(compiledWorkflowSchema.parse(await response.json()).version).toBe(1)
  expect((await handleCompile(request({ ...input, version: 2 }))).status).toBe(422)
  expect((await handleCompile(request({ ...input, filename: "../../other.yaml" }))).status).toBe(422)
  const invalid = await handleCompile(request({ ...input, source: "on: [push\n" }))
  expect(invalid.status).toBe(422)
  expect(await invalid.json()).toMatchObject({
    error: "invalid_workflow",
    issues: [{ filename: "test.yaml", line: expect.any(Number) }],
  })
  expect((await handleCompile(request("x".repeat(2 * 1024 * 1024)))).status).toBe(413)
})

test("unexpected HTTP handler faults stay internal errors", async () => {
  vi.stubEnv("COMPILER_TOKEN", "compiler-test")
  const request = new Request("http://compiler/api/compile", {
    method: "POST",
    headers: { authorization: "Bearer compiler-test" },
    body: "{}",
  })
  Object.defineProperty(request, "body", {
    get: () => {
      throw new Error("Simulated internal transport failure")
    },
  })
  const response = await handleCompile(request)
  expect(response.status).toBe(500)
  expect(await response.json()).toEqual({ error: "internal_error" })
})

test("the GitEdge runner workflow shares the GitHub definition through a symlink", async () => {
  const source = await Bun.file(
    new URL("../../../../.gitedge/workflow/actions-runner-tests.yaml", import.meta.url),
  ).text()
  const compiled = await compile(source, { name: "pull_request", ref: "refs/heads/feature", action: "opened" })
  expect(compiled.matched).toBe(true)
  expect(compiled.jobs[0].config.steps.some((step) => step.kind === "run" && step.run.includes("typecheck"))).toBe(true)
})

test.each(["write-all", "{contents: write}", "{issues: read}"])(
  "rejects unsupported token permissions %s",
  async (access) => {
    await expect(
      compile(workflow(`    permissions: ${access}\n    steps:\n      - run: true\n`)),
    ).rejects.toBeInstanceOf(CompileError)
  },
)
