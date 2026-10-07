import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"

import { RepositoriesService } from "@/client"

interface NewIssueFormProps {
  owner: string
  repo: string
}

const NewIssueForm = ({ owner, repo }: NewIssueFormProps) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const repoPath = `${owner}/${repo}.git`

  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")

  const createIssueMutation = useMutation({
    mutationFn: () =>
      RepositoriesService.createIssue({
        path: { owner, repo },
        body: { title, body: body || null },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues", repoPath] })
      navigate({
        to: "/$owner/$repo/issues",
        params: { owner, repo },
      })
    },
  })

  const handleSubmit = () => {
    if (!title.trim()) return
    createIssueMutation.mutate()
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <RouterLink
          to="/$owner/$repo/issues"
          params={{ owner, repo }}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to issues
        </RouterLink>
      </div>

      <h1 className="text-xl font-bold text-foreground">New Issue</h1>

      <div className="space-y-4">
        <div>
          <label htmlFor="issue-title" className="block text-sm font-medium text-foreground mb-1.5">
            Title
          </label>
          <input
            id="issue-title"
            type="text"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="issue-title-input"
            className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div>
          <label htmlFor="issue-body" className="block text-sm font-medium text-foreground mb-1.5">
            Description
          </label>
          <textarea
            id="issue-body"
            rows={12}
            placeholder="Leave a comment"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            data-testid="issue-body-input"
            className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-y"
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <RouterLink
            to="/$owner/$repo/issues"
            params={{ owner, repo }}
            className="px-4 py-2 text-sm rounded border border-border bg-secondary text-foreground hover:bg-accent transition-colors"
          >
            Cancel
          </RouterLink>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!title.trim() || createIssueMutation.isPending}
            data-testid="submit-issue-btn"
            className="px-4 py-2 text-sm rounded bg-success text-success-foreground font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {createIssueMutation.isPending ? "Submitting..." : "Submit new issue"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default NewIssueForm
