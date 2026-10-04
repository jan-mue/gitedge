import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useState } from "react"

import { RepositoriesService } from "@/client"

interface NewPullRequestFormProps {
  owner: string
  repo: string
}

const NewPullRequestForm = ({ owner, repo }: NewPullRequestFormProps) => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const repoPath = `${owner}/${repo}.git`

  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [headBranch, setHeadBranch] = useState("")
  const [baseBranch, setBaseBranch] = useState("main")

  const { data: branches } = useQuery({
    queryKey: ["branches", repoPath],
    queryFn: async () => (await RepositoriesService.listBranches({ path: { path: repoPath } })).data,
  })

  const createPRMutation = useMutation({
    mutationFn: () =>
      RepositoriesService.createPullRequest({
        path: { path: repoPath },
        body: {
          title,
          body: body || null,
          head_branch: headBranch,
          base_branch: baseBranch,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pulls", repoPath] })
      navigate({
        to: "/$owner/$repo/pulls",
        params: { owner, repo },
      })
    },
  })

  const handleSubmit = () => {
    if (!title.trim() || !headBranch.trim()) return
    createPRMutation.mutate()
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <RouterLink
          to="/$owner/$repo/pulls"
          params={{ owner, repo }}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to pull requests
        </RouterLink>
      </div>

      <h1 className="text-xl font-bold text-foreground">New Pull Request</h1>

      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label htmlFor="head-branch" className="block text-sm font-medium text-foreground mb-1.5">
              Source branch
            </label>
            <select
              id="head-branch"
              value={headBranch}
              onChange={(e) => setHeadBranch(e.target.value)}
              data-testid="pr-source-branch"
              className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select a branch</option>
              {branches?.map((branch) => (
                <option key={branch.name} value={branch.name}>
                  {branch.name}
                </option>
              ))}
            </select>
          </div>
          <span className="mt-6 text-muted-foreground">&rarr;</span>
          <div className="flex-1">
            <label htmlFor="base-branch" className="block text-sm font-medium text-foreground mb-1.5">
              Target branch
            </label>
            <select
              id="base-branch"
              value={baseBranch}
              onChange={(e) => setBaseBranch(e.target.value)}
              data-testid="pr-target-branch"
              className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {branches?.map((branch) => (
                <option key={branch.name} value={branch.name}>
                  {branch.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="pr-title" className="block text-sm font-medium text-foreground mb-1.5">
            Title
          </label>
          <input
            id="pr-title"
            type="text"
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            data-testid="pr-title-input"
            className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div>
          <label htmlFor="pr-body" className="block text-sm font-medium text-foreground mb-1.5">
            Description
          </label>
          <textarea
            id="pr-body"
            rows={12}
            placeholder="Leave a comment"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            data-testid="pr-body-input"
            className="w-full px-3 py-2 text-sm bg-secondary border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-y"
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <RouterLink
            to="/$owner/$repo/pulls"
            params={{ owner, repo }}
            className="px-4 py-2 text-sm rounded border border-border bg-secondary text-foreground hover:bg-accent transition-colors"
          >
            Cancel
          </RouterLink>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!title.trim() || !headBranch.trim() || createPRMutation.isPending}
            data-testid="submit-pr-btn"
            className="px-4 py-2 text-sm rounded bg-success text-success-foreground font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {createPRMutation.isPending ? "Creating..." : "Create pull request"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default NewPullRequestForm
