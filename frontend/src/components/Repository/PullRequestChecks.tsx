import { useQuery } from "@tanstack/react-query"
import { GitBranch } from "lucide-react"
import { actionsGetPullRequestChecksOptions } from "@/client/@tanstack/react-query.gen"
import { PullRequestChecks as Checks, ConversationItem, Link } from "@/components/design-system"
import { formatDuration } from "@/utils"

export const PullRequestChecks = ({
  owner,
  repo,
  number,
  open,
}: {
  owner: string
  repo: string
  number: number
  open: boolean
}) => {
  const query = useQuery({
    ...actionsGetPullRequestChecksOptions({ path: { owner, repo, number } }),
    refetchInterval: (query) =>
      open || query.state.data?.runs.some((run) => ["queued", "running"].includes(run.status)) ? 2000 : false,
  })
  const checks =
    query.data?.runs.flatMap((run) =>
      run.jobs.length
        ? run.jobs.map((job) => ({
            id: `${run.id}:${job.id}`,
            name: `${run.name} / ${job.name}`,
            status: job.status ?? ("queued" as const),
            duration: formatDuration(job.started_at, job.completed_at),
            details: (
              <Link
                to="/$owner/$repo/actions"
                params={{ owner, repo }}
                search={{ run: run.id, job: job.id }}
                appearance="caption"
              >
                Details
              </Link>
            ),
          }))
        : [
            {
              id: run.id,
              name: run.name,
              status: run.status,
              details: (
                <Link to="/$owner/$repo/actions" params={{ owner, repo }} search={{ run: run.id }} appearance="caption">
                  Details
                </Link>
              ),
            },
          ],
    ) ?? []
  return (
    <ConversationItem icon={<GitBranch className="size-4 shrink-0" />}>
      <Checks
        checks={checks}
        loading={query.isPending}
        error={query.isError ? "Unable to load workflow results." : undefined}
        retry={() => query.refetch()}
        revision={query.data?.head_sha}
      />
    </ConversationItem>
  )
}
