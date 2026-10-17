// Adapted from jan-mue/gitea-clone's ActionsPage: job sidebar and expandable step logs.
import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"
import type { ActionRun } from "@/client"
import { Badge, Button } from "@/components/design-system"
import { duration, StatusIcon } from "./StatusIcon"

export const RunDetail = ({
  run,
  canManage,
  cancelling,
  onCancel,
}: {
  run: ActionRun
  canManage: boolean
  cancelling: boolean
  onCancel: () => void
}) => {
  const [selectedJob, setSelectedJob] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const job = run.jobs.find((job) => job.id === selectedJob) ?? run.jobs[0]
  const toggle = (id: string) =>
    setExpanded((old) => {
      const next = new Set(old)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <StatusIcon status={run.status} />
          <div>
            <h2 className="text-lg font-semibold">{run.name}</h2>
            <p className="text-sm text-muted-foreground">
              Commit {run.sha.slice(0, 10)} · {run.actor}{" "}
              <Badge variant="secondary">{run.ref.replace(/^refs\/(heads|tags)\//, "")}</Badge>
            </p>
            <p className="text-sm text-muted-foreground">Workflow {run.workflow.split("/").pop()}</p>
          </div>
        </div>
        {canManage && ["queued", "running"].includes(run.status) && (
          <Button variant="repository" size="compact" loading={cancelling} onClick={onCancel}>
            Cancel run
          </Button>
        )}
      </div>
      {run.error && (
        <p role="alert" className="rounded border border-destructive p-3 text-sm text-destructive">
          {run.error}
        </p>
      )}
      <div className="flex flex-col gap-4 md:flex-row">
        <nav aria-label="Jobs" className="w-full shrink-0 space-y-1 md:w-72">
          {run.jobs.map((item) => (
            <div key={item.id} className="flex">
              <Button
                variant="activity"
                size="activity"
                fullWidth
                aria-pressed={job?.id === item.id}
                onClick={() => setSelectedJob(item.id)}
              >
                <StatusIcon status={item.status ?? "queued"} />
                <span className="min-w-0 flex-1 truncate">{item.name}</span>
                <span className="text-xs text-muted-foreground">{duration(item.started_at, item.completed_at)}</span>
              </Button>
            </div>
          ))}
        </nav>
        {job && (
          <div className="min-w-0 flex-1 overflow-hidden rounded-lg border border-border">
            <div className="flex items-center justify-between border-b bg-secondary px-4 py-3">
              <div>
                <h3 className="text-sm font-semibold">{job.name}</h3>
                <p className="text-xs capitalize text-muted-foreground">{job.status}</p>
              </div>
              <span className="text-xs text-muted-foreground">
                {duration(job.started_at, job.completed_at)}
                {job.provisioning_ms != null && ` · Provisioned in ${Math.round(job.provisioning_ms)} ms`}
              </span>
            </div>
            {job.error && (
              <p role="alert" className="p-4 text-sm text-destructive">
                {job.error}
              </p>
            )}
            <div className="divide-y divide-border bg-secondary/40">
              {job.steps?.map((step) => {
                const id = `${job.id}:${step.id}`
                return (
                  <div key={step.id}>
                    <Button
                      variant="actionStep"
                      size="file-row"
                      aria-expanded={expanded.has(id)}
                      aria-controls={`log-${id}`}
                      onClick={() => toggle(id)}
                    >
                      {expanded.has(id) ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                      <StatusIcon status={step.status ?? "queued"} />
                      <span className="flex-1 text-left">{step.name}</span>
                    </Button>
                    {expanded.has(id) && (
                      <pre
                        id={`log-${id}`}
                        className="overflow-x-auto whitespace-pre-wrap break-all px-4 py-3 font-mono text-xs text-foreground"
                      >
                        {step.log || "No log output."}
                      </pre>
                    )}
                  </div>
                )
              })}
              <details className="px-4 py-3 text-sm">
                <summary className="cursor-pointer">Complete job log</summary>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs">
                  {job.log || "Waiting for log output…"}
                </pre>
              </details>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
