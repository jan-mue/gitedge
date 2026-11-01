// Workflow sidebar, filters, run rows, and detail layout adapted from jan-mue/gitea-clone.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Clock } from "lucide-react"
import { useState } from "react"
import {
  actionsCancelRunMutation,
  actionsDispatchWorkflowMutation,
  actionsListRunsOptions,
  actionsListRunsQueryKey,
  actionsListWorkflowsOptions,
} from "@/client/@tanstack/react-query.gen"
import { Badge, Button, CheckStatusIcon, FilterDropdown, Input, Label } from "@/components/design-system"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { formatDuration, handleError } from "@/utils"
import { RunDetail } from "./RunDetail"

export const RepositoryActions = ({
  owner,
  repo,
  runId,
  jobId,
  onSelectRun,
}: {
  owner: string
  repo: string
  runId?: string
  jobId?: string
  onSelectRun: (id?: string) => void
}) => {
  const path = { owner, repo }
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [workflow, setWorkflow] = useState("")
  const [actor, setActor] = useState("")
  const [status, setStatus] = useState("")
  const [ref, setRef] = useState("HEAD")
  const [inputs, setInputs] = useState("{}")
  const runs = useQuery({
    ...actionsListRunsOptions({ path }),
    refetchInterval: (query) =>
      query.state.data?.some((run) => ["queued", "running"].includes(run.status)) ? 2000 : false,
  })
  const workflows = useQuery(actionsListWorkflowsOptions({ path }))
  const refresh = () => queryClient.invalidateQueries({ queryKey: actionsListRunsQueryKey({ path }) })
  const dispatch = useMutation({
    ...actionsDispatchWorkflowMutation(),
    onSuccess: (run) => {
      refresh()
      onSelectRun(run.id)
    },
    onError: handleError.bind(showErrorToast),
  })
  const cancel = useMutation({
    ...actionsCancelRunMutation(),
    onSuccess: refresh,
    onError: handleError.bind(showErrorToast),
  })
  const canManage = !!user && (user.name.toLowerCase() === owner.toLowerCase() || user.is_superuser === true)
  const selected = runs.data?.find((run) => run.id === runId)
  if (runs.isPending || workflows.isPending) return <RepositoryLoading label="Loading workflow runs" />
  if (runs.isError || workflows.isError)
    return (
      <RepositoryError
        message="Unable to load Actions."
        retry={() => {
          runs.refetch()
          workflows.refetch()
        }}
      />
    )
  if (runId && !selected)
    return (
      <div className="space-y-3">
        <Button variant="link" onClick={() => onSelectRun()}>
          ← Back to runs
        </Button>
        <RepositoryError message="Workflow run not found." />
      </div>
    )
  if (selected)
    return (
      <div className="space-y-4">
        <Button variant="link" size="text" onClick={() => onSelectRun()}>
          ← Back to runs
        </Button>
        <RunDetail
          owner={owner}
          repo={repo}
          initialJob={jobId}
          key={selected.id}
          run={selected}
          canManage={canManage}
          cancelling={cancel.isPending}
          onCancel={() => cancel.mutate({ path: { ...path, run_id: selected.id } })}
        />
      </div>
    )
  const filtered = runs.data.filter(
    (run) =>
      (!workflow || run.workflow === workflow) && (!actor || run.actor === actor) && (!status || run.status === status),
  )
  return (
    <div className="flex flex-col gap-6 md:flex-row">
      <nav aria-label="Workflows" className="w-full shrink-0 md:w-52">
        <div className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {[{ path: "", name: "All workflows" }, ...workflows.data].map((item) => (
            <Button
              key={item.path}
              variant="activity"
              size="activity"
              aria-pressed={workflow === item.path}
              onClick={() => setWorkflow(item.path)}
            >
              {item.path ? item.path.split("/").pop() : item.name}
            </Button>
          ))}
        </div>
      </nav>
      <div className="min-w-0 flex-1 space-y-4">
        {canManage && workflows.data.find((item) => item.path === workflow)?.dispatch && (
          <form
            className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4"
            onSubmit={(event) => {
              event.preventDefault()
              try {
                const parsed: unknown = JSON.parse(inputs)
                if (
                  !parsed ||
                  typeof parsed !== "object" ||
                  Array.isArray(parsed) ||
                  Object.values(parsed).some((value) => typeof value !== "string")
                )
                  throw new Error("Use a JSON object with string input values.")
                dispatch.mutate({ path, body: { workflow, ref, inputs: parsed as Record<string, string> } })
              } catch (error) {
                showErrorToast(error instanceof Error ? error.message : "Invalid workflow inputs")
              }
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="workflow-ref">Branch, tag, or commit</Label>
              <Input id="workflow-ref" value={ref} onChange={(event) => setRef(event.target.value)} required />
            </div>
            <div className="space-y-1">
              <Label htmlFor="workflow-inputs">Inputs (JSON)</Label>
              <Input id="workflow-inputs" value={inputs} onChange={(event) => setInputs(event.target.value)} />
            </div>
            <Button type="submit" loading={dispatch.isPending}>
              Run workflow
            </Button>
          </form>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          <FilterDropdown
            label="Actor"
            value={actor}
            onChange={setActor}
            options={[
              { value: "", label: "All actors" },
              ...[...new Set(runs.data.map((run) => run.actor))].map((value) => ({ value, label: value })),
            ]}
          />
          <FilterDropdown
            label="Status"
            value={status}
            onChange={setStatus}
            options={[
              { value: "", label: "All statuses" },
              ...["queued", "running", "success", "failure", "skipped", "cancelled"].map((value) => ({
                value,
                label: value[0].toUpperCase() + value.slice(1),
              })),
            ]}
          />
          <Button variant="repository" size="compact" onClick={() => runs.refetch()} loading={runs.isFetching}>
            Refresh
          </Button>
        </div>
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {filtered.map((run) => (
            <Button key={run.id} variant="actionRun" size="file-row" onClick={() => onSelectRun(run.id)}>
              <CheckStatusIcon status={run.status} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{run.name}</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {run.workflow.split("/").pop()} · Commit {run.sha.slice(0, 10)} · {run.actor}
                </div>
              </div>
              <Badge variant="outline">{run.ref.replace(/^refs\/(heads|tags)\//, "")}</Badge>
              <div className="shrink-0 text-right text-xs text-muted-foreground">
                <div>{new Date(run.created_at).toLocaleString()}</div>
                <div className="mt-1 flex items-center justify-end gap-1">
                  <Clock className="size-3" />
                  {formatDuration(run.created_at, run.completed_at)}
                </div>
              </div>
            </Button>
          ))}
          {filtered.length === 0 && (
            <div className="py-12 text-center text-sm text-muted-foreground">
              {workflows.data.length
                ? "No workflow runs found."
                : "Add a workflow in .gitedge/workflow to get started."}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
