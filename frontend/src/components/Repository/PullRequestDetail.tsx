import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useParams } from "@tanstack/react-router"
import { ArrowLeft, CircleCheck, GitMerge, GitPullRequest } from "lucide-react"

import { type IssueState, RepositoriesService } from "@/client"
import CommentsSection from "@/components/Repository/CommentsSection"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const stateBadge = (state: string) => {
  if (state === "merged") {
    return (
      <Badge className="bg-purple-500 text-white" data-testid="pr-state">
        <GitMerge className="w-3 h-3" /> Merged
      </Badge>
    )
  }
  if (state === "closed") {
    return (
      <Badge variant="secondary" data-testid="pr-state">
        <CircleCheck className="w-3 h-3" /> Closed
      </Badge>
    )
  }
  return (
    <Badge className="bg-success text-success-foreground" data-testid="pr-state">
      <GitPullRequest className="w-3 h-3" /> Open
    </Badge>
  )
}

const changeBadge: Record<string, string> = {
  add: "bg-success/15 text-success",
  delete: "bg-destructive/15 text-destructive",
  rename: "bg-info/15 text-info",
  modify: "bg-muted text-muted-foreground",
}

const changeLabel: Record<string, string> = {
  add: "Added",
  delete: "Deleted",
  rename: "Renamed",
  modify: "Modified",
}

const PullRequestDetail = () => {
  const { owner, repo, number } = useParams({ from: "/_layout/$owner/$repo/pulls/$number" })
  const repoPath = `${owner}/${repo}.git`
  const prNumber = Number(number)
  const queryClient = useQueryClient()

  const { data: pull } = useQuery({
    queryKey: ["pull", repoPath, prNumber],
    queryFn: async () =>
      (await RepositoriesService.getPullRequest({ path: { path: repoPath, number: prNumber } })).data,
  })

  const { data: changes } = useQuery({
    queryKey: ["pull-files", repoPath, prNumber],
    queryFn: async () =>
      (await RepositoriesService.getPullRequestFiles({ path: { path: repoPath, number: prNumber } })).data,
  })

  const mutation = useMutation({
    mutationFn: (state: IssueState) =>
      RepositoriesService.updatePullRequest({
        path: { path: repoPath, number: prNumber },
        body: { state },
      }),
    onSuccess: (response) => {
      queryClient.setQueryData(["pull", repoPath, prNumber], response.data)
      queryClient.invalidateQueries({ queryKey: ["pulls", repoPath] })
    },
  })

  if (!pull) {
    return <div className="text-sm text-muted-foreground">Loading pull request...</div>
  }

  const isOpen = pull.state === "open"

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="pull-detail">
      <RouterLink
        to="/$owner/$repo/pulls"
        params={{ owner, repo }}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to pull requests
      </RouterLink>

      <div className="space-y-3">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-xl font-bold text-foreground">
            {pull.title} <span className="text-muted-foreground font-normal">#{pull.number}</span>
          </h1>
          {stateBadge(pull.state)}
        </div>
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{pull.author_email ?? "unknown"}</span>
          {pull.created_at && ` opened ${new Date(pull.created_at).toLocaleString()}`}
          {" · "}
          <span className="font-mono text-foreground">{pull.head_branch}</span> &rarr;{" "}
          <span className="font-mono text-foreground">{pull.base_branch}</span>
        </p>
      </div>

      {pull.body && (
        <div className="border border-border rounded-lg bg-card px-4 py-3">
          <p className="text-sm text-foreground whitespace-pre-wrap break-words">{pull.body}</p>
        </div>
      )}

      {changes && changes.files.length > 0 && (
        <div className="space-y-2" data-testid="pr-files">
          <h2 className="text-sm font-semibold text-foreground">
            {changes.files.length} {changes.files.length === 1 ? "file" : "files"} changed
          </h2>
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            {changes.files.map((file, index) => (
              <div
                key={file.path}
                className={`flex items-center gap-3 px-4 py-2 text-sm ${
                  index < changes.files.length - 1 ? "border-b border-border" : ""
                }`}
                data-testid={`pr-file-${file.path}`}
              >
                <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${changeBadge[file.change_type] ?? ""}`}>
                  {changeLabel[file.change_type] ?? file.change_type}
                </span>
                <span className="min-w-0 flex-1 truncate font-mono text-foreground">{file.path}</span>
                <span className="font-mono text-xs text-success">+{file.additions}</span>
                <span className="font-mono text-xs text-destructive">-{file.deletions}</span>
                {changes.head_commit && (
                  <RouterLink
                    to="/$owner/$repo/src/commit/$sha/$"
                    params={{ owner, repo, sha: changes.head_commit, _splat: file.path }}
                    className="text-xs text-primary hover:underline"
                    data-testid={`view-file-${file.path}`}
                  >
                    View file
                  </RouterLink>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <CommentsSection owner={owner} repo={repo} number={prNumber} />

      <div className="flex items-center gap-2">
        {isOpen ? (
          <>
            <Button
              size="sm"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate("merged")}
              data-testid="merge-pr"
            >
              <GitMerge className="w-3.5 h-3.5" />
              Merge
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate("closed")}
              data-testid="close-pr"
            >
              Close
            </Button>
          </>
        ) : (
          <Button
            variant="outline"
            size="sm"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate("open")}
            data-testid="reopen-pr"
          >
            Reopen
          </Button>
        )}
      </div>
    </div>
  )
}

export default PullRequestDetail
