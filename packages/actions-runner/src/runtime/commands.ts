import { join } from "node:path"
import type { Environment } from "../domain/workflow.ts"
import type { JobEnvironment } from "./environment.ts"
import { readText, writeFile } from "./files.ts"
import type { JobLogger } from "./logger.ts"

export function parseFileCommands(text: string): Environment {
  const values: Environment = {},
    lines = text.replace(/\r\n/g, "\n").split("\n")
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]
    if (!line) continue
    const marker = line.indexOf("<<"),
      equal = line.indexOf("=")
    if (marker >= 0 && (equal < 0 || marker < equal)) {
      const delimiter = line.slice(marker + 2),
        content: string[] = []
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
    Object.assign(outputs, parseFileCommands(await readText(this.paths.GITHUB_OUTPUT)))
    Object.assign(state, parseFileCommands(await readText(this.paths.GITHUB_STATE)))
    environment.export(parseFileCommands(await readText(this.paths.GITHUB_ENV)))
    environment.prependPaths((await readText(this.paths.GITHUB_PATH)).split(/\r?\n/).filter(Boolean))
  }
}
const decode = (value: string) =>
  value.replace(/%0D/gi, "\r").replace(/%0A/gi, "\n").replace(/%3A/gi, ":").replace(/%2C/gi, ",").replace(/%25/gi, "%")
export class OutputCommands {
  private stopped: string | undefined
  constructor(
    private readonly environment: JobEnvironment,
    private readonly logger: JobLogger,
    private readonly step: string,
    private readonly outputs: Environment,
    private readonly state: Environment,
  ) {}
  line(line: string): void {
    if (this.stopped) {
      if (line === `::${this.stopped}::`) this.stopped = undefined
      else this.logger.emit(line, this.step)
      return
    }
    const match = line.match(/^::([\w-]+)(?:\s+([^:]*))?::(.*)$/)
    if (!match) {
      this.logger.emit(line, this.step)
      return
    }
    const name = match[1],
      value = decode(match[3]),
      properties: Environment = {}
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
        this.logger.emit(value, this.step)
    }
  }
  async consume(stream: ReadableStream<Uint8Array>): Promise<void> {
    const decoder = new TextDecoder()
    let pending = ""
    for await (const part of stream) {
      pending += decoder.decode(part, { stream: true })
      const lines = pending.split(/\r?\n/)
      pending = lines.pop() || ""
      for (const line of lines) this.line(line)
    }
    pending += decoder.decode()
    if (pending) this.line(pending)
  }
}
