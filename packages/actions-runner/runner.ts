// One invocation executes exactly one matrix job, then exits with its sandbox.
import { spawn } from "node:child_process"
import { randomUUID } from "node:crypto"
import { access, mkdir, readFile, writeFile } from "node:fs/promises"
import { join, resolve } from "node:path"
import type { Readable } from "node:stream"
import { parse } from "yaml"
import { condition, interpolate } from "./expressions.ts"
import { startStorage } from "./storage.ts"
import type {
  ActionMetadata,
  ExpressionContext,
  ExpressionMap,
  JobInput,
  JobResult,
  JobStatus,
  LogEntry,
  RunnerContext,
  StepResult,
  Workflow,
  WorkflowStep,
} from "./types.ts"

export function commands(text: string): Record<string, string> {
  const result: Record<string, string> = {}
  const lines = text.replace(/\r\n/g, "\n").split("\n")
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (!line) continue
    const multiline = line.indexOf("<<")
    const equal = line.indexOf("=")
    if (multiline >= 0 && (equal < 0 || multiline < equal)) {
      const name = line.slice(0, multiline)
      const delimiter = line.slice(multiline + 2)
      const value = []
      while (++i < lines.length && lines[i] !== delimiter) value.push(lines[i])
      if (i === lines.length) throw new Error("Unterminated workflow file command")
      result[name] = value.join("\n")
    } else if (equal >= 0) result[line.slice(0, equal)] = line.slice(equal + 1)
    else throw new Error("Invalid workflow file command")
  }
  return result
}
const string = (value: unknown): string =>
  value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value)
const decodeCommand = (value: string) =>
  value.replace(/%0D/gi, "\r").replace(/%0A/gi, "\n").replace(/%3A/gi, ":").replace(/%2C/gi, ",").replace(/%25/gi, "%")

export async function execute(
  input: JobInput,
  {
    root = "/gitedge",
    actionRoot = "/opt/gitedge/actions",
    signal = new AbortController().signal,
    restoreState,
    log = (entry) => process.stdout.write(`${JSON.stringify(entry)}\n`),
  }: {
    root?: string
    actionRoot?: string
    signal?: AbortSignal
    log?: (entry: LogEntry) => void
    restoreState?: () => Promise<void>
  } = {},
): Promise<JobResult> {
  const workflow = parse(input.workflow) as Workflow
  const job = workflow.jobs[input.job]
  if (!job) throw new Error(`Unknown job: ${input.job}`)
  const workspace = join(root, "source")
  const temporary = join(root, "temp")
  await mkdir(workspace, { recursive: true })
  await mkdir(temporary, { recursive: true })
  const eventPath = join(root, "event.json")
  await writeFile(eventPath, JSON.stringify(input.event || {}))
  const storage = await startStorage(join(root, "state"), input.env.GITHUB_RUN_ID, input.job, restoreState)
  const protectedEnvironment = {
    ...input.env,
    ...storage.environment,
    GITHUB_WORKSPACE: workspace,
    GITHUB_EVENT_PATH: eventPath,
    GITHUB_EVENT_NAME: input.event_name || "",
    GITHUB_ACTOR: input.actor || "",
    GITHUB_JOB: input.job,
    GITHUB_ACTIONS: "true",
    CI: "true",
    GITHUB_RUN_ATTEMPT: "1",
    RUNNER_NAME: "gitedge",
    RUNNER_ENVIRONMENT: "self-hosted",
    RUNNER_OS: "Linux",
    RUNNER_ARCH: process.arch === "arm64" ? "ARM64" : "X64",
    RUNNER_TEMP: temporary,
    RUNNER_TOOL_CACHE: process.env.RUNNER_TOOL_CACHE || "/opt/hostedtoolcache",
    AGENT_TOOLSDIRECTORY: process.env.AGENT_TOOLSDIRECTORY || "/opt/hostedtoolcache",
    GITHUB_TOKEN: input.secrets?.GITHUB_TOKEN || "",
  }
  const github = {
    ...input.event,
    repository: input.env.GITHUB_REPOSITORY,
    repository_owner: input.env.GITHUB_REPOSITORY_OWNER,
    server_url: input.env.GITHUB_SERVER_URL,
    api_url: input.env.GITHUB_API_URL,
    graphql_url: `${input.env.GITHUB_SERVER_URL}/api/graphql`,
    ref: input.env.GITHUB_REF,
    sha: input.env.GITHUB_SHA,
    ref_name: input.env.GITHUB_REF?.replace(/^refs\/(heads|tags)\//, ""),
    ref_type: input.env.GITHUB_REF?.startsWith("refs/tags/") ? "tag" : "branch",
    workspace,
    event_path: eventPath,
    event_name: input.event_name,
    event: input.event || {},
    actor: input.actor,
    run_id: input.env.GITHUB_RUN_ID,
    run_number: input.env.GITHUB_RUN_NUMBER,
    run_attempt: "1",
    job: input.job,
    token: input.secrets?.GITHUB_TOKEN || "",
    workflow: workflow.name || "",
    action_path: "",
    action_repository: "",
    action_ref: "",
  }
  const context: RunnerContext = {
    github,
    runner: {
      os: "Linux",
      arch: protectedEnvironment.RUNNER_ARCH,
      temp: temporary,
      tool_cache: protectedEnvironment.RUNNER_TOOL_CACHE,
      environment: "self-hosted",
    },
    matrix: input.matrix || {},
    needs: input.needs || {},
    inputs: input.event?.inputs || {},
    secrets: input.secrets || {},
    vars: input.vars || {},
    steps: {},
    env: {},
    job: { status: "success" },
    strategy: {},
  }
  const masks = new Set(Object.values(input.secrets || {}).filter(Boolean))
  const redact = (value: unknown) => {
    let message = String(value)
    for (const mask of [...masks].sort((a, b) => b.length - a.length)) message = message.split(mask).join("***")
    return message
  }
  const emit = (message: string, id?: string | null, result?: JobStatus) =>
    log({ msg: redact(message), stepID: id ? [id] : [], ...(result ? { stepResult: result } : {}) })
  const exportedEnvironment: Record<string, string> = {}
  const environment = { ...process.env }
  // Never expose the launch descriptor or controller callback capabilities to actions.
  delete environment.GITEDGE_JOB
  delete environment.GITEDGE_JOB_ENCODING
  delete environment.GITEDGE_RESTORE_URL
  delete environment.GITEDGE_JOB_ROOT
  const evaluateMap = (values: ExpressionMap | undefined, ctx: ExpressionContext, status: JobStatus) =>
    Object.fromEntries(
      Object.entries(values || {}).map(([key, value]) => [key, string(interpolate(value, ctx, status))]),
    )
  let status: JobStatus = Object.values(input.needs || {}).some((need) => need.result !== "success")
    ? "failure"
    : "success"
  const posts: {
    file: string
    environment: NodeJS.ProcessEnv
    context: ExpressionContext
    condition: unknown
    id: string
    state: Record<string, string>
  }[] = []
  let firstStepAt: number | undefined
  let stopping: JobStatus | null = null
  const abort = () => {
    stopping = "cancelled"
  }
  signal.addEventListener("abort", abort, { once: true })
  if (signal.aborted) abort()
  const setEnvironment = (values: Record<string, string>) => {
    for (const [key, value] of Object.entries(values)) {
      if (/^(GITHUB_|RUNNER_|ACTIONS_)/i.test(key) || key === "NODE_OPTIONS") continue
      environment[key] = value
      exportedEnvironment[key] = value
    }
  }
  async function processRun(
    command: string,
    args: string[],
    env: NodeJS.ProcessEnv,
    cwd: string,
    id: string,
    outputs: Record<string, string>,
    state: Record<string, string>,
    processSignal = signal,
  ) {
    const directory = join(temporary, randomUUID())
    await mkdir(directory)
    const paths = {
      GITHUB_ENV: join(directory, "env"),
      GITHUB_OUTPUT: join(directory, "output"),
      GITHUB_PATH: join(directory, "path"),
      GITHUB_STATE: join(directory, "state"),
      GITHUB_STEP_SUMMARY: join(directory, "summary"),
    }
    await Promise.all(Object.values(paths).map((path) => writeFile(path, "")))
    const child = spawn(command, args, {
      env: { ...env, ...paths },
      cwd,
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
    })
    let timer: ReturnType<typeof setTimeout> | undefined
    const onStop = () => {
      if (!child.pid) return
      const pid = child.pid
      try {
        process.kill(-pid, "SIGTERM")
      } catch (cause) {
        const error = cause as NodeJS.ErrnoException
        if (error.code !== "ESRCH") throw error
      }
      timer = setTimeout(() => {
        try {
          process.kill(-pid, "SIGKILL")
        } catch (cause) {
          const error = cause as NodeJS.ErrnoException
          if (error.code !== "ESRCH") throw error
        }
      }, 5000)
      timer.unref()
    }
    processSignal.addEventListener("abort", onStop, { once: true })
    if (processSignal.aborted) onStop()
    const consume = async (stream: Readable) => {
      let pending = ""
      let stopToken: string | null = null
      for await (const chunk of stream) {
        pending += chunk.toString()
        const lines = pending.split(/\r?\n/)
        pending = lines.pop() || ""
        for (const line of lines) {
          if (stopToken) {
            if (line === `::${stopToken}::`) stopToken = null
            else emit(line, id)
            continue
          }
          const match = line.match(/^::([\w-]+)(?:\s+([^:]*))?::(.*)$/)
          if (!match) {
            emit(line, id)
            continue
          }
          const [, name, properties = "", raw] = match
          const value = decodeCommand(raw)
          const params = Object.fromEntries(
            properties.split(",").map((item) => {
              const index = item.indexOf("=")
              return [item.slice(0, index), decodeCommand(item.slice(index + 1))]
            }),
          )
          if (name === "stop-commands") stopToken = value
          else if (name === "add-mask") {
            if (value) masks.add(value)
          } else if (name === "set-output") outputs[params.name] = value
          else if (name === "save-state") state[params.name] = value
          else if (name === "set-env") setEnvironment({ [params.name]: value })
          else if (name === "add-path") {
            environment.PATH = `${value}:${environment.PATH}`
            exportedEnvironment.PATH = environment.PATH
          } else emit(value, id)
        }
      }
      if (pending) emit(pending, id)
    }
    let failure: Error | undefined
    const exit = new Promise<number>((resolve, reject) => {
      child.on("error", reject)
      child.on("close", (code) => resolve(code ?? 1))
    })
    try {
      const [code] = await Promise.all([exit, consume(child.stdout), consume(child.stderr)])
      if (code !== 0) failure = new Error(`Process exited with code ${code}`)
    } finally {
      processSignal.removeEventListener("abort", onStop)
      clearTimeout(timer)
    }
    Object.assign(outputs, commands(await readFile(paths.GITHUB_OUTPUT, "utf8")))
    Object.assign(state, commands(await readFile(paths.GITHUB_STATE, "utf8")))
    setEnvironment(commands(await readFile(paths.GITHUB_ENV, "utf8")))
    const pathsAdded = (await readFile(paths.GITHUB_PATH, "utf8")).split(/\r?\n/).filter(Boolean)
    if (pathsAdded.length) {
      environment.PATH = `${pathsAdded.reverse().join(":")}:${environment.PATH}`
      exportedEnvironment.PATH = environment.PATH
    }
    if (failure) throw failure
  }
  async function actionDirectory(uses: string) {
    if (uses.startsWith("./")) {
      const path = resolve(workspace, uses)
      if (!path.startsWith(`${resolve(workspace)}/`)) throw new Error("Local action escapes workspace")
      return { directory: path, repositoryRoot: workspace }
    }
    const match = uses.match(/^([\w.-]+\/[\w.-]+)(\/[\w./-]+)?@([^\s]+)$/)
    if (!match || match[2]?.split("/").includes("..")) throw new Error(`Unsupported action: ${uses}`)
    const manifest = JSON.parse(await readFile(join(actionRoot, "manifest.json"), "utf8")) as Record<string, string>
    const tree = manifest[`${match[1]}@${match[3]}`]
    if (!tree) throw new Error(`Action ${uses} is not prepared in this image; rebuild the image before dispatch`)
    const repositoryRoot = join(actionRoot, tree)
    return { directory: join(repositoryRoot, match[2] || ""), repositoryRoot }
  }
  async function runAction(
    step: WorkflowStep,
    ctx: RunnerContext,
    env: NodeJS.ProcessEnv,
    id: string,
    outputs: Record<string, string>,
  ) {
    const uses = string(interpolate(step.uses, ctx, status))
    const { directory, repositoryRoot } = await actionDirectory(uses)
    let metadata: ActionMetadata | undefined
    for (const filename of ["action.yml", "action.yaml"]) {
      try {
        metadata = parse(await readFile(join(directory, filename), "utf8"))
        break
      } catch (cause) {
        const error = cause as NodeJS.ErrnoException
        if (error.code !== "ENOENT") throw error
      }
    }
    if (!metadata) throw new Error(`Missing action metadata: ${uses}`)
    const actionContext: RunnerContext = {
      ...ctx,
      github: {
        ...ctx.github,
        action_path: directory,
        action_repository: uses.startsWith("./") ? "" : uses.split("@")[0].split("/").slice(0, 2).join("/"),
        action_ref: uses.split("@")[1] || "",
      },
    }
    const inputs = Object.fromEntries(
      Object.entries(metadata.inputs || {}).map(([name, definition]) => [
        name,
        string(interpolate(definition.default ?? "", actionContext, status)),
      ]),
    )
    Object.assign(inputs, evaluateMap(step.with, ctx, status))
    actionContext.inputs = inputs
    const actionEnvironment: NodeJS.ProcessEnv = {
      ...env,
      GITHUB_ACTION_PATH: directory,
      GITHUB_ACTION_REPOSITORY: string(actionContext.github.action_repository),
      GITHUB_ACTION_REF: string(actionContext.github.action_ref),
    }
    for (const [name, value] of Object.entries(inputs))
      actionEnvironment[`INPUT_${name.replace(/ /g, "_").toUpperCase()}`] = value
    const runs = metadata.runs || {}
    if (runs.using === "composite") {
      const nested: RunnerContext = { ...actionContext, steps: {} }
      let nestedStatus: JobStatus = "success"
      for (const [index, child] of (runs.steps || []).entries()) {
        const result = await runStep(child, nested, id, `${index}`, nestedStatus, actionEnvironment)
        if (result.conclusion === "failure") nestedStatus = "failure"
      }
      for (const [name, definition] of Object.entries(metadata.outputs || {}))
        outputs[name] = string(interpolate(definition.value, nested, nestedStatus))
      if (nestedStatus === "failure") throw new Error(`Composite action failed: ${uses}`)
      return
    }
    if (!runs.using || !/^node(?:12|16|20|24)$/.test(runs.using) || !runs.main)
      throw new Error(`Unsupported action runtime: ${runs.using}`)
    const state: Record<string, string> = {}
    const file = (path: string) => {
      const absolute = resolve(directory, path)
      if (!absolute.startsWith(`${resolve(repositoryRoot)}/`))
        throw new Error("Action entrypoint escapes its repository")
      return absolute
    }
    if (runs.post)
      posts.push({
        file: file(runs.post),
        environment: actionEnvironment,
        context: actionContext,
        condition: runs["post-if"] ?? "always()",
        id,
        state,
      })
    if (runs.pre && condition(runs["pre-if"] ?? "always()", actionContext, status))
      await processRun(
        process.env.GITEDGE_NODE_BINARY || "node",
        [file(runs.pre)],
        actionEnvironment,
        workspace,
        id,
        outputs,
        state,
      )
    const mainEnvironment = {
      ...actionEnvironment,
      ...Object.fromEntries(Object.entries(state).map(([key, value]) => [`STATE_${key}`, value])),
    }
    await processRun(
      process.env.GITEDGE_NODE_BINARY || "node",
      [file(runs.main)],
      mainEnvironment,
      workspace,
      id,
      outputs,
      state,
    )
  }
  async function runStep(
    step: WorkflowStep,
    ctx: RunnerContext,
    rootId: string | null,
    generatedId: string,
    currentStatus: JobStatus,
    baseEnvironment: NodeJS.ProcessEnv = environment,
  ): Promise<StepResult> {
    const id = step.id || generatedId
    const displayId = rootId || id
    ctx.env = {
      ...baseEnvironment,
      ...evaluateMap(workflow.env, ctx, currentStatus),
      ...evaluateMap(job.env, ctx, currentStatus),
      ...exportedEnvironment,
      ...protectedEnvironment,
    }
    const result: StepResult = { outcome: "skipped", conclusion: "skipped", outputs: {} }
    ctx.steps[id] = result
    if (!condition(step.if, ctx, currentStatus) || stopping) {
      emit(`Skipped ${step.name || step.uses || id}`, displayId, "skipped")
      return result
    }
    firstStepAt ??= Date.now()
    emit(`Run ${step.name || step.uses || id}`, displayId)
    try {
      const env = {
        ...baseEnvironment,
        ...evaluateMap(workflow.env, ctx, currentStatus),
        ...evaluateMap(job.env, ctx, currentStatus),
        ...exportedEnvironment,
      }
      ctx.env = { ...env, ...protectedEnvironment }
      Object.assign(env, evaluateMap(step.env, ctx, currentStatus), protectedEnvironment)
      ctx.env = env
      if (step.uses) await runAction(step, ctx, env, displayId, result.outputs)
      else if (step.run != null) {
        const defaults = { ...(workflow.defaults?.run || {}), ...(job.defaults?.run || {}) }
        const shell = string(interpolate(step.shell || defaults.shell || "bash", ctx, currentStatus))
        const extension = shell === "bash" || shell === "sh" ? "sh" : shell === "python" ? "py" : "mjs"
        const script = join(temporary, `${randomUUID()}.${extension}`)
        await writeFile(script, string(interpolate(step.run, ctx, currentStatus)))
        let command: string
        let args: string[]
        if (shell === "bash") {
          command = "bash"
          args = ["--noprofile", "--norc", "-e", "-o", "pipefail", script]
        } else if (shell === "sh") {
          command = "sh"
          args = ["-e", script]
        } else if (shell === "python") {
          command = "python"
          args = [script]
        } else if (shell.includes("{0}")) {
          const parts = shell.split(/\s+/)
          command = parts.shift() || ""
          args = parts.map((part) => part.replace("{0}", script))
        } else throw new Error(`Unsupported shell: ${shell}`)
        const cwd = resolve(
          workspace,
          string(interpolate(step["working-directory"] || defaults["working-directory"] || ".", ctx, currentStatus)),
        )
        if (!cwd.startsWith(`${resolve(workspace)}/`) && cwd !== resolve(workspace))
          throw new Error("Working directory escapes workspace")
        await access(cwd)
        const limit = Number(interpolate(step["timeout-minutes"], ctx, currentStatus))
        const stepSignal = limit > 0 ? AbortSignal.any([signal, AbortSignal.timeout(limit * 60000)]) : signal
        await processRun(command, args, env, cwd, displayId, result.outputs, {}, stepSignal)
      } else throw new Error("Step needs run or uses")
      result.outcome = "success"
      result.conclusion = "success"
    } catch (cause) {
      const error = cause as NodeJS.ErrnoException
      result.outcome = stopping ? "cancelled" : "failure"
      result.conclusion =
        interpolate(step["continue-on-error"] ?? false, ctx, currentStatus) === true ? "success" : result.outcome
      emit(error.message, displayId)
    }
    emit(`${step.name || step.uses || id}: ${result.conclusion}`, displayId, result.conclusion)
    return result
  }
  let result: JobResult = { status: "failure", outputs: {}, steps: context.steps }
  try {
    context.env = { ...environment, ...protectedEnvironment }
    if (!condition(job.if, context, status)) return { ...result, status: "skipped" }
    status = "success"
    for (const [index, step] of job.steps.entries()) {
      context.job.status = status
      const result = await runStep(step, context, null, String(index), status)
      if (result.conclusion === "failure") status = "failure"
      if (result.conclusion === "cancelled") status = "cancelled"
    }
    for (const post of posts.reverse()) {
      if (!condition(post.condition, post.context, status)) continue
      emit("Post action cleanup", post.id)
      try {
        await processRun(
          process.env.GITEDGE_NODE_BINARY || "node",
          [post.file],
          {
            ...post.environment,
            PATH: environment.PATH,
            ...Object.fromEntries(Object.entries(post.state).map(([key, value]) => [`STATE_${key}`, value])),
          },
          workspace,
          post.id,
          {},
          post.state,
        )
      } catch (cause) {
        const error = cause as NodeJS.ErrnoException
        status = "failure"
        emit(error.message, post.id, "failure")
      }
    }
    result = {
      startup_ms: firstStepAt && input.dispatched_at_ms ? firstStepAt - input.dispatched_at_ms : null,
      status: stopping || status,
      outputs: evaluateMap(job.outputs, context, status),
      steps: context.steps,
    }
    return result
  } finally {
    signal.removeEventListener("abort", abort)
    await storage.close()
  }
}
