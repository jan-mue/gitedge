import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useParams } from "@tanstack/react-router"
import { ArrowLeft, CircleCheck, CircleDot } from "lucide-react"

import { RepositoriesService } from "@/client"
import CommentsSection from "@/components/Repository/CommentsSection"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const IssueDetail = () => {
  const { owner, repo, number } = useParams({ from: "/_layout/$owner/$repo/issues/$number" })
  const repoPath = `${owner}/${repo}.git`
  const issueNumber = Number(number)
  const queryClient = useQueryClient()

  const { data: issue } = useQuery({
    queryKey: ["issue", repoPath, issueNumber],
    queryFn: async () => (await RepositoriesService.getIssue({ path: { path: repoPath, number: issueNumber } })).data,
  })

  const mutation = useMutation({
    mutationFn: (state: string) =>
      RepositoriesService.updateIssue({
        path: { path: repoPath, number: issueNumber },
        body: { state },
      }),
    onSuccess: (response) => {
      queryClient.setQueryData(["issue", repoPath, issueNumber], response.data)
      queryClient.invalidateQueries({ queryKey: ["issues", repoPath] })
    },
  })

  if (!issue) {
    return <div className="text-sm text-muted-foreground">Loading issue...</div>
  }

  const isOpen = issue.state === "open"

  return (
    <div className="max-w-4xl mx-auto space-y-6" data-testid="issue-detail">
      <RouterLink
        to="/$owner/$repo/issues"
        params={{ owner, repo }}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to issues
      </RouterLink>

      <div className="space-y-3">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-xl font-bold text-foreground">
            {issue.title} <span className="text-muted-foreground font-normal">#{issue.number}</span>
          </h1>
          <Badge variant={isOpen ? "default" : "secondary"} data-testid="issue-state">
            {isOpen ? (
              <>
                <CircleDot className="w-3 h-3" /> Open
              </>
            ) : (
              <>
                <CircleCheck className="w-3 h-3" /> Closed
              </>
            )}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{issue.author_email ?? "unknown"}</span>
          {issue.created_at && ` opened ${new Date(issue.created_at).toLocaleString()}`}
        </p>
      </div>

      {issue.body && (
        <div className="border border-border rounded-lg bg-card px-4 py-3">
          <p className="text-sm text-foreground whitespace-pre-wrap break-words">{issue.body}</p>
        </div>
      )}

      <CommentsSection owner={owner} repo={repo} number={issueNumber} />

      <div className="flex items-center gap-2">
        <Button
          variant={isOpen ? "outline" : "default"}
          size="sm"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(isOpen ? "closed" : "open")}
          data-testid="toggle-issue-state"
        >
          {isOpen ? "Close issue" : "Reopen issue"}
        </Button>
      </div>
    </div>
  )
}

export default IssueDetail
