import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"
import {
  repositoriesCreatePullRequestMutation,
  repositoriesListBranchesOptions,
  repositoriesListPullRequestsQueryKey,
} from "@/client/@tanstack/react-query.gen"
import { Button, Input, Label, NativeSelect, Link as RouterLink, Textarea } from "@/design-system"

interface NewPullRequestFormProps {
  owner: string
  repo: string
}

const NewPullRequestForm = ({ owner, repo }: NewPullRequestFormProps) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [headBranch, setHeadBranch] = useState("")
  const [baseBranch, setBaseBranch] = useState("main")

  const { data: branches } = useQuery({
    ...repositoriesListBranchesOptions({ path: { owner, repo } }),
  })

  const createPRMutation = useMutation({
    ...repositoriesCreatePullRequestMutation(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: repositoriesListPullRequestsQueryKey({ path: { owner, repo } }) })
      navigate({
        to: "/$owner/$repo/pulls",
        params: { owner, repo },
      })
    },
  })

  const handleSubmit = () => {
    if (!title.trim() || !headBranch.trim()) return
    createPRMutation.mutate({
      path: { owner, repo },
      body: { title, body: body || null, head_branch: headBranch, base_branch: baseBranch },
    })
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <RouterLink to="/$owner/$repo/pulls" params={{ owner, repo }} appearance="muted">
          <ArrowLeft className="w-4 h-4" />
          Back to pull requests
        </RouterLink>
      </div>

      <h1 className="text-xl font-bold text-foreground">New Pull Request</h1>

      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <Label htmlFor="head-branch" appearance="field">
              Source branch
            </Label>
            <NativeSelect
              id="head-branch"
              value={headBranch}
              onChange={(e) => setHeadBranch(e.target.value)}
              data-testid="pr-source-branch"
            >
              <option value="">Select a branch</option>
              {branches?.map((branch) => (
                <option key={branch.name} value={branch.name}>
                  {branch.name}
                </option>
              ))}
            </NativeSelect>
          </div>
          <span className="mt-6 text-muted-foreground">&rarr;</span>
          <div className="flex-1">
            <Label htmlFor="base-branch" appearance="field">
              Target branch
            </Label>
            <NativeSelect
              id="base-branch"
              value={baseBranch}
              onChange={(e) => setBaseBranch(e.target.value)}
              data-testid="pr-target-branch"
            >
              {branches?.map((branch) => (
                <option key={branch.name} value={branch.name}>
                  {branch.name}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>

        <div>
          <Label htmlFor="pr-title" appearance="field">
            Title
          </Label>
          <Input
            id="pr-title"
            type="text"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="pr-title-input"
          />
        </div>

        <div>
          <Label htmlFor="pr-body" appearance="field">
            Description
          </Label>
          <Textarea
            id="pr-body"
            rows={12}
            placeholder="Leave a comment"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            data-testid="pr-body-input"
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <RouterLink to="/$owner/$repo/pulls" params={{ owner, repo }} appearance="action">
            Cancel
          </RouterLink>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!title.trim() || !headBranch.trim() || createPRMutation.isPending}
            data-testid="submit-pr-btn"
            variant="success"
            size="sm"
          >
            {createPRMutation.isPending ? "Creating..." : "Create pull request"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default NewPullRequestForm
