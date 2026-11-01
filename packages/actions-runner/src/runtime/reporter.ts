import type { JobSpec } from "../domain/job.ts"

export class JobReporter {
  constructor(private readonly input: JobSpec) {}

  get enabled(): boolean {
    return !!this.input.report_url
  }

  async post(operation: "logs" | "artifacts" | "complete", body: string | Blob): Promise<Response | undefined> {
    if (!this.enabled) return undefined
    if (!this.input.report_token) throw new Error("Job report capability is missing")
    const deadline = AbortSignal.timeout(12000)
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        const response = await fetch(`${this.input.report_url}/${operation}`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${this.input.report_token}`,
            "Content-Type": typeof body === "string" ? "application/json" : "application/gzip",
          },
          body,
          signal: AbortSignal.any([deadline, AbortSignal.timeout(3000)]),
        })
        if (response.ok) return response
        const status = response.status
        await response.body?.cancel()
        if (status < 500 && status !== 429) throw new Error(`Job report rejected: HTTP ${status}`)
      } catch (error) {
        if (deadline.aborted || attempt === 3) throw error
        if (error instanceof Error && error.message.startsWith("Job report rejected:")) throw error
      }
      await Bun.sleep(100 * 2 ** attempt)
    }
    throw new Error("Job report was not acknowledged")
  }
}
