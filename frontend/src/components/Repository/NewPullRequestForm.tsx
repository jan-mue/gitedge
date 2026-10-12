import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"
import {
  repositoriesCreatePullRequestMutation,
  repositoriesListBranchesOptions,
  repositoriesListPullRequestsQueryKey,
} from "@/client/@tanstack/react-query.gen"
import { Button, Input, Label, Link as RouterLink, Textarea } from "@/components/design-system"

import BranchSelector from "./BranchSelector"

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

  const {
    data: branches,
    isPending: branchesPending,
    isError: branchesError,
    refetch: refetchBranches,
  } = useQuery({
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
          <div className="min-w-0 flex-1">
            <Label htmlFor="head-branch" appearance="field">
              Source branch
            </Label>
            <BranchSelector
              id="head-branch"
              label="Source branch"
              value={headBranch}
              onValueChange={setHeadBranch}
              branches={branches ?? []}
              loading={branchesPending}
              error={branchesError}
              onRetry={() => refetchBranches()}
              appearance="field"
              data-testid="pr-source-branch"
            />
          </div>
          <span className="mt-6 text-muted-foreground">&rarr;</span>
          <div className="min-w-0 flex-1">
            <Label htmlFor="base-branch" appearance="field">
              Target branch
            </Label>
            <BranchSelector
              id="base-branch"
              label="Target branch"
              value={baseBranch}
              onValueChange={setBaseBranch}
              branches={branches ?? []}
              loading={branchesPending}
              error={branchesError}
              onRetry={() => refetchBranches()}
              appearance="field"
              data-testid="pr-target-branch"
            />
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
          <RouterLink to="/$owner/$repo/pulls" params={{ owner, repo }} appearance="formAction">
            Cancel
          </RouterLink>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!title.trim() || !headBranch.trim() || createPRMutation.isPending}
            data-testid="submit-pr-btn"
            variant="success"
            size="form"
          >
            {createPRMutation.isPending ? "Creating..." : "Create pull request"}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default NewPullRequestForm
