import type { JobStatus, LogEntry, LogSink } from "../domain/job.ts"

export class FileLog implements LogSink {
  private readonly writer: Bun.FileSink
  private pending = Promise.resolve()

  constructor(path: string) {
    this.writer = Bun.file(path).writer()
  }

  write(entry: LogEntry): void {
    this.pending = this.pending.then(async () => {
      this.writer.write(`${JSON.stringify(entry)}\n`)
      await this.writer.flush()
    })
  }

  async close(): Promise<void> {
    await this.flush()
    await this.writer.end()
  }

  async flush(): Promise<void> {
    await this.pending
    await this.writer.flush()
  }
}

export class JobLogger {
  private readonly masks: Set<string>

  constructor(
    private readonly sink: LogSink,
    secrets: readonly string[],
  ) {
    this.masks = new Set(secrets.filter(Boolean))
  }

  mask(value: string): void {
    if (value) this.masks.add(value)
  }

  redact(value: string): string {
    let result = value
    for (const secret of [...this.masks].sort((a, b) => b.length - a.length)) result = result.split(secret).join("***")
    return result
  }

  emit(message: string, step?: string, status?: JobStatus): void {
    this.sink.write({
      msg: this.redact(message),
      stepID: step ? [step] : [],
      ...(status ? { stepResult: status } : {}),
    })
  }
}
