import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { Check, GitBranch } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { repositoriesListBranchesOptions, repositoriesListCommitsOptions } from "@/client/@tanstack/react-query.gen"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"

interface CommitsListProps {
  owner: string
  repo: string
  branch?: string
  filePath?: string
}

const formatDate = (timestamp: number) => new Date(timestamp * 1000).toLocaleString()

const CommitsList = ({ owner, repo, branch, filePath }: CommitsListProps) => {
  const ref = branch ?? "main"
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const {
    data: commitsData,
    isPending,
    isError,
    refetch,
  } = useQuery({
    ...repositoriesListCommitsOptions({ path: { owner, repo }, query: { ref, limit: 50, file_path: filePath } }),
  })

  const { data: branches } = useQuery({
    ...repositoriesListBranchesOptions({ path: { owner, repo } }),
    enabled: open,
  })

  const handleClickOutside = useCallback((event: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
      setOpen(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      document.addEventListener("mousedown", handleClickOutside)
    }
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [open, handleClickOutside])

  const commits = commitsData?.data ?? []

  const selectBranch = (branchName: string) => {
    setOpen(false)
    navigate({ to: "/$owner/$repo/commits/branch/$branch", params: { owner, repo, branch: branchName } })
  }

  if (isPending) return <RepositoryLoading label="Loading commits" />
  if (isError) return <RepositoryError message="Unable to load commits." retry={() => refetch()} />

  return (
    <div className="space-y-3">
      {filePath && (
        <h2 className="text-sm font-medium">
          History of <span className="font-mono">{filePath}</span>
        </h2>
      )}
      <div className="flex items-center gap-2">
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setOpen((prev) => !prev)}
            className="flex items-center gap-1.5 rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
            data-testid="commits-branch-selector"
          >
            <GitBranch className="h-3.5 w-3.5" />
            <span>{ref}</span>
            <span className="text-muted-foreground">&#9662;</span>
          </button>
          {open && (
            <div
              className="absolute left-0 top-full z-50 mt-1 w-56 overflow-hidden rounded-lg border border-border bg-card shadow-lg"
              data-testid="commits-branch-dropdown"
            >
              <div className="max-h-64 overflow-y-auto py-1">
                {branches?.map((branch) => (
                  <button
                    key={branch.name}
                    type="button"
                    onClick={() => selectBranch(branch.name)}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-foreground transition-colors hover:bg-accent"
                  >
                    {branch.name === ref ? (
                      <Check className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
                    ) : (
                      <span className="h-3.5 w-3.5 flex-shrink-0" />
                    )}
                    <span className="truncate">{branch.name}</span>
                  </button>
                ))}
                {!branches && <div className="px-3 py-2 text-sm text-muted-foreground">Loading...</div>}
              </div>
            </div>
          )}
        </div>
        <span className="text-sm text-muted-foreground">
          {commits.length} {commits.length === 1 ? "commit" : "commits"}
        </span>
      </div>

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
              <RouterLink
                to="/$owner/$repo/commit/$hash"
                params={{ owner, repo, hash: commit.sha }}
                className="text-sm font-medium text-foreground hover:text-primary"
              >
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
              className="flex-shrink-0 font-mono text-xs text-primary hover:underline"
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

export default CommitsList
