// Adapted from jan-mue/gitea-clone's ActionsPage: job sidebar and expandable step logs.
import { useState } from "react"
import type { ActionRun } from "@/client"
import { Badge, Button, CheckStatusIcon } from "@/components/design-system"
import { formatDuration } from "@/utils"
import { JobLogs } from "./JobLogs"

export const RunDetail = ({
  run,
  owner,
  repo,
  initialJob,
  canManage,
  cancelling,
  onCancel,
}: {
  owner: string
  repo: string
  initialJob?: string
  run: ActionRun
  canManage: boolean
  cancelling: boolean
  onCancel: () => void
}) => {
  const [selectedJob, setSelectedJob] = useState<string | null>(initialJob ?? null)
  const job = run.jobs.find((job) => job.id === selectedJob) ?? run.jobs[0]
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <CheckStatusIcon status={run.status} />
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
                <CheckStatusIcon status={item.status ?? "queued"} />
                <span className="min-w-0 flex-1 truncate">{item.name}</span>
                <span className="text-xs text-muted-foreground">
                  {formatDuration(item.started_at, item.completed_at)}
                </span>
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
              <span className="text-xs text-muted-foreground">{formatDuration(job.started_at, job.completed_at)}</span>
            </div>
            {job.error && (
              <p role="alert" className="p-4 text-sm text-destructive">
                {job.error}
              </p>
            )}
            <JobLogs key={job.id} owner={owner} repo={repo} runId={run.id} job={job} />
          </div>
        )}
      </div>
    </div>
  )
}
