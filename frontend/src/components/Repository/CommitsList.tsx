import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import {
  releasesListTagsOptions,
  repositoriesListBranchesOptions,
  repositoriesListCommitsOptions,
} from "@/client/@tanstack/react-query.gen"
import { Link as RouterLink } from "@/components/design-system"
import { BranchSelector } from "@/components/Repository/BranchSelector"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

interface CommitsListProps {
  owner: string
  repo: string
  branch?: string
  filePath?: string
  tag?: string
}

const formatDate = (timestamp: number) => new Date(timestamp * 1000).toLocaleString()

export const CommitsList = ({ owner, repo, branch, tag, filePath }: CommitsListProps) => {
  const ref = tag ? `refs/tags/${tag}` : (branch ?? "main")
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const {
    data: commitsData,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesListCommitsOptions({ path: { owner, repo }, query: { ref, limit: 50, file_path: filePath } }),
  })

  const {
    data: branches,
    isPending: branchesPending,
    isError: branchesError,
    refetch: refetchBranches,
  } = useQuery({
    ...repositoriesListBranchesOptions({ path: { owner, repo } }),
  })

  const commits = commitsData?.data ?? []

  const {
    data: tags,
    isPending: tagsPending,
    isError: tagsError,
    refetch: refetchTags,
  } = useQuery({
    ...releasesListTagsOptions({ path: { owner, repo } }),
    enabled: open,
  })

  const selectBranch = (branchName: string, kind: "branch" | "tag") => {
    setOpen(false)
    if (kind === "tag")
      navigate({
        to: "/$owner/$repo/commits/tag/$tag",
        params: { owner, repo, tag: branchName },
        search: { path: filePath },
      })
    else
      navigate({
        to: "/$owner/$repo/commits/branch/$branch",
        params: { owner, repo, branch: branchName },
        search: { path: filePath },
      })
  }

  if (isPending) return <RepositoryLoading label="Loading commits" />
  if (isError) return <RepositoryError message="Unable to load commits." retry={() => refetch()} />
  const renderBranchSelector = () => (
    <div className="flex items-center gap-2">
      <BranchSelector
        branches={branches ?? []}
        tags={tags?.data ?? []}
        value={tag ?? ref}
        kind={tag ? "tag" : "branch"}
        onValueChange={selectBranch}
        disclosure={{ open: open, onOpenChange: setOpen }}
        status={{
          branch: { loading: branchesPending, error: branchesError, onRetry: () => refetchBranches() },
          tag: { loading: tagsPending, error: tagsError, onRetry: () => refetchTags() },
        }}
        data-testid="commits-branch-selector"
        dropdownTestId="commits-branch-dropdown"
      />
      <span className="text-sm text-muted-foreground">
        {commits.length} {commits.length === 1 ? "commit" : "commits"}
      </span>
    </div>
  )

  return (
    <div className="space-y-3">
      {filePath && (
        <h2 className="text-sm font-medium">
          History of <span className="font-mono">{filePath}</span>
        </h2>
      )}
      {renderBranchSelector()}

      <div className="overflow-hidden rounded-lg border border-border bg-card" data-testid="commits-list">
        {commits.map((commit, index) => (
          <div
            key={commit.sha}
            className={`flex items-start gap-3 px-4 py-3 ${index < commits.length - 1 ? "border-b border-border" : ""}`}
            data-testid={`commit-${commit.sha.slice(0, 10)}`}
          >
            <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-accent text-xs font-medium text-accent-foreground">
              {commit.author.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <RouterLink to="/$owner/$repo/commit/$hash" params={{ owner, repo, hash: commit.sha }} appearance="title">
                {commit.message.split("\n")[0]}
              </RouterLink>
              <p className="mt-0.5 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{commit.author}</span> committed{" "}
                {formatDate(commit.timestamp)}
              </p>
            </div>
            <RouterLink
              to="/$owner/$repo/commit/$hash"
              params={{ owner, repo, hash: commit.sha }}
              appearance="commitHash"
            >
              {commit.sha.slice(0, 10)}
            </RouterLink>
          </div>
        ))}
        {commits.length === 0 && (
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">No commits yet.</div>
        )}
      </div>
    </div>
  )
}
