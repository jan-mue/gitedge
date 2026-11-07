import { join } from "node:path"
import type { Environment } from "../domain/workflow.ts"
import type { JobEnvironment } from "./environment.ts"
import { readText, writeFile } from "./files.ts"
import type { JobLogger } from "./logger.ts"

export const COMMAND_FILE_BYTES = 1024 * 1024
const OUTPUT_LINE_CHARACTERS = 64 * 1024

export function parseFileCommands(text: string): Environment {
  if (Buffer.byteLength(text) > COMMAND_FILE_BYTES) throw new Error("Workflow file commands exceed 1 MiB")
  const values: Environment = {}
  const lines = text.replace(/\r\n/g, "\n").split("\n")
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]
    if (!line) continue
    const marker = line.indexOf("<<")
    const equal = line.indexOf("=")
    if (marker >= 0 && (equal < 0 || marker < equal)) {
      const delimiter = line.slice(marker + 2)
      const content: string[] = []
      while (++index < lines.length && lines[index] !== delimiter) content.push(lines[index])
      if (index === lines.length) throw new Error("Unterminated workflow file command")
      values[line.slice(0, marker)] = content.join("\n")
    } else if (equal >= 0) values[line.slice(0, equal)] = line.slice(equal + 1)
    else throw new Error("Invalid workflow file command")
  }
  return values
}

export class CommandFiles {
  readonly paths: Environment

  constructor(directory: string) {
    this.paths = Object.fromEntries(
      ["ENV", "OUTPUT", "PATH", "STATE", "STEP_SUMMARY"].map((key) => [
        `GITHUB_${key}`,
        join(directory, key.toLowerCase()),
      ]),
    )
  }

  async prepare(): Promise<void> {
    await Promise.all(Object.values(this.paths).map((path) => writeFile(path, "")))
  }

  async collect(environment: JobEnvironment, outputs: Environment, state: Environment): Promise<void> {
    const contents = await Promise.all(Object.values(this.paths).map((path) => readText(path, COMMAND_FILE_BYTES)))
    const [env, output, path, saved] = contents
    Object.assign(outputs, parseFileCommands(output))
    Object.assign(state, parseFileCommands(saved))
    environment.export(parseFileCommands(env))
    environment.prependPaths(path.split(/\r?\n/).filter(Boolean))
  }
}

const decode = (value: string) =>
  value.replace(/%0D/gi, "\r").replace(/%0A/gi, "\n").replace(/%3A/gi, ":").replace(/%2C/gi, ",").replace(/%25/gi, "%")

export class OutputCommands {
  private stopped: string | undefined
  private commandBytes = 0

  constructor(
    private readonly environment: JobEnvironment,
    private readonly logger: JobLogger,
    private readonly step: string,
    private readonly outputs: Environment,
    private readonly state: Environment,
  ) {}

  async line(line: string): Promise<void> {
    if (this.stopped) {
      if (line === `::${this.stopped}::`) this.stopped = undefined
      else await this.logger.emit(line, this.step)
      return
    }
    const match = line.match(/^::([\w-]+)(?:\s+([^:]*))?::(.*)$/)
    if (!match) {
      await this.logger.emit(line, this.step)
      return
    }
    const name = match[1]
    this.commandBytes += Buffer.byteLength(line)
    if (this.commandBytes > COMMAND_FILE_BYTES) throw new Error("Workflow output commands exceed 1 MiB")
    const value = decode(match[3])
    const properties: Environment = {}
    for (const item of (match[2] || "").split(",")) {
      const equal = item.indexOf("=")
      if (equal >= 0) properties[item.slice(0, equal)] = decode(item.slice(equal + 1))
    }
    switch (name) {
      case "stop-commands":
        this.stopped = value
        break
      case "add-mask":
        this.logger.mask(value)
        break
      case "set-output":
        this.outputs[properties.name] = value
        break
      case "save-state":
        this.state[properties.name] = value
        break
      case "set-env":
        this.environment.export({ [properties.name]: value })
        break
      case "add-path":
        this.environment.prependPaths([value])
        break
      default:
        await this.logger.emit(value, this.step)
    }
  }

  async consume(stream: ReadableStream<Uint8Array>, signal?: AbortSignal): Promise<void> {
    const decoder = new TextDecoder()
    let pending = ""
    let discarded = false
    const reader = stream.getReader()
    const abort = () => void reader.cancel()
    signal?.addEventListener("abort", abort, { once: true })
    if (signal?.aborted) abort()
    try {
      while (true) {
        const { value: part, done } = await reader.read()
        if (done) break
        const pieces = decoder.decode(part, { stream: true }).split("\n")
        for (const [index, piece] of pieces.entries()) {
          if (!discarded) {
            if (pending.length + piece.length > OUTPUT_LINE_CHARACTERS) {
              pending = ""
              discarded = true
              await this.logger.emit("[Output truncated: line exceeds 64 KiB]", this.step)
            } else pending += piece
          }
          if (index < pieces.length - 1) {
            if (!discarded) await this.line(pending.replace(/\r$/, ""))
            pending = ""
            discarded = false
          }
        }
      }
    } finally {
      signal?.removeEventListener("abort", abort)
      reader.releaseLock()
    }
    pending += decoder.decode()
    if (pending && !discarded) await this.line(pending)
  }
}
