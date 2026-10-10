import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useParams } from "@tanstack/react-router"
import { ArrowLeft, CircleCheck, CircleDot } from "lucide-react"
import { useState } from "react"

import { type IssueState, RepositoriesService } from "@/client"
import MarkdownContent from "@/components/Common/MarkdownContent"
import CommentsSection from "@/components/Repository/CommentsSection"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const IssueDetail = () => {
  const { owner, repo, number } = useParams({ from: "/_layout/$owner/$repo/issues/$number" })
  const repoPath = `${owner}/${repo}.git`
  const issueNumber = Number(number)
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const { showErrorToast } = useCustomToast()
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState("")
  const [editBody, setEditBody] = useState("")

  const { data: issue } = useQuery({
    queryKey: ["issue", repoPath, issueNumber],
    queryFn: async () => (await RepositoriesService.getIssue({ path: { owner, repo, number: issueNumber } })).data,
  })

  const mutation = useMutation({
    mutationFn: (state: IssueState) =>
      RepositoriesService.updateIssue({
        path: { owner, repo, number: issueNumber },
        body: { state },
      }),
    onSuccess: (response) => {
      queryClient.setQueryData(["issue", repoPath, issueNumber], response.data)
      queryClient.invalidateQueries({ queryKey: ["issues", repoPath] })
    },
  })

  const editMutation = useMutation({
    mutationFn: () =>
      RepositoriesService.updateIssue({
        path: { owner, repo, number: issueNumber },
        body: { title: editTitle, body: editBody },
      }),
    onSuccess: (response) => {
      queryClient.setQueryData(["issue", repoPath, issueNumber], response.data)
      queryClient.invalidateQueries({ queryKey: ["issues", repoPath] })
      setEditing(false)
    },
    onError: handleError.bind(showErrorToast),
  })

  if (!issue) {
    return <div className="text-sm text-muted-foreground">Loading issue...</div>
  }

  const isOpen = issue.state === "open"
  const canEdit = issue.author_username === user?.name

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

      {editing ? (
        <div className="space-y-3">
          <input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            data-testid="edit-issue-title"
            className="w-full rounded border border-border bg-card px-3 py-2 text-lg font-bold text-foreground focus:outline-none"
          />
          <textarea
            value={editBody}
            onChange={(e) => setEditBody(e.target.value)}
            rows={5}
            data-testid="edit-issue-body"
            className="w-full rounded border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none resize-y"
          />
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="outline" onClick={() => setEditing(false)} data-testid="edit-issue-cancel">
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!editTitle.trim() || editMutation.isPending}
              onClick={() => editMutation.mutate()}
              data-testid="edit-issue-submit"
            >
              Save
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <h1 className="text-xl font-bold text-foreground">
                {issue.title} <span className="text-muted-foreground font-normal">#{issue.number}</span>
              </h1>
              <div className="flex items-center gap-2">
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setEditTitle(issue.title)
                      setEditBody(issue.body ?? "")
                      setEditing(true)
                    }}
                    data-testid="edit-issue"
                  >
                    Edit
                  </Button>
                )}
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
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{issue.author_username ?? "unknown"}</span>
              {issue.created_at && ` opened ${new Date(issue.created_at).toLocaleString()}`}
            </p>
          </div>

          {issue.body && (
            <div className="border border-border rounded-lg bg-card px-4 py-3">
              <MarkdownContent html={issue.body_html} />
            </div>
          )}
        </>
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
