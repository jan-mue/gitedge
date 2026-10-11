import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"
import { repositoriesCreateIssueMutation, repositoriesListIssuesQueryKey } from "@/client/@tanstack/react-query.gen"
import { Button, Input, Label, Link as RouterLink, Textarea } from "@/design-system"

interface NewIssueFormProps {
  owner: string
  repo: string
}

const NewIssueForm = ({ owner, repo }: NewIssueFormProps) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")

  const createIssueMutation = useMutation({
    ...repositoriesCreateIssueMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: repositoriesListIssuesQueryKey({ path: { owner, repo } }) })
      navigate({
        to: "/$owner/$repo/issues",
        params: { owner, repo },
      })
    },
  })

  const handleSubmit = () => {
    if (!title.trim()) return
    createIssueMutation.mutate({ path: { owner, repo }, body: { title, body: body || null } })
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <RouterLink to="/$owner/$repo/issues" params={{ owner, repo }} appearance="muted">
          <ArrowLeft className="w-4 h-4" />
          Back to issues
        </RouterLink>
      </div>

      <h1 className="text-xl font-bold text-foreground">New Issue</h1>

      <div className="space-y-4">
        <div>
          <Label htmlFor="issue-title" appearance="field">
            Title
          </Label>
          <Input
            id="issue-title"
            type="text"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="issue-title-input"
          />
        </div>

        <div>
          <Label htmlFor="issue-body" appearance="field">
            Description
          </Label>
          <Textarea
            id="issue-body"
            rows={12}
            placeholder="Leave a comment"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            data-testid="issue-body-input"
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <RouterLink to="/$owner/$repo/issues" params={{ owner, repo }} appearance="action">
            Cancel
          </RouterLink>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!title.trim() || createIssueMutation.isPending}
            data-testid="submit-issue-btn"
            variant="success"
            size="sm"
          >
            {createIssueMutation.isPending ? "Submitting..." : "Submit new issue"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default NewIssueForm
