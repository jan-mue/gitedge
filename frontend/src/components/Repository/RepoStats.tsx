import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { Check, Copy, GitBranch, GitCommitHorizontal, Lock, Tag } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { RepositoriesService } from "@/client"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

interface RepoStatsProps {
  owner: string
  repo: string
  gitRef: string
  searchRef?: string
}

const RepoStats = ({ owner, repo, gitRef, searchRef }: RepoStatsProps) => {
  const [, copy] = useCopyToClipboard()
  const navigate = useNavigate()
  const cloneUrl = `${window.location.origin}/${owner}/${repo}.git`
  const repoPath = `${owner}/${repo}.git`

  const [branchDropdownOpen, setBranchDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: repoInfo } = useQuery({
    queryKey: ["repoInfo", repoPath, searchRef],
    queryFn: async () =>
      (
        await RepositoriesService.getRepositoryInfo({
          path: { path: repoPath },
          query: { ref: searchRef },
        })
      ).data,
  })

  const { data: branches } = useQuery({
    queryKey: ["branches", repoPath],
    queryFn: async () => (await RepositoriesService.listBranches({ path: { path: repoPath } })).data,
    enabled: branchDropdownOpen,
  })

  const handleClickOutside = useCallback((event: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
      setBranchDropdownOpen(false)
    }
  }, [])

  useEffect(() => {
    if (branchDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside)
    }
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [branchDropdownOpen, handleClickOutside])

  const handleBranchSelect = (branchName: string) => {
    setBranchDropdownOpen(false)
    navigate({
      to: "/$owner/$repo",
      params: { owner, repo },
      search: { ref: branchName },
    })
  }

  return (
    <div className="space-y-3" data-testid="repo-stats">
      {repoInfo?.description && <div className="text-foreground">{repoInfo.description}</div>}

      {repoInfo && (
        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
          {repoInfo.last_commit && (
            <RouterLink
              to="/$owner/$repo/commits"
              params={{ owner, repo }}
              className="flex items-center gap-1.5 transition-colors hover:text-foreground"
            >
              <GitCommitHorizontal className="h-4 w-4" />
              <span className="font-medium text-foreground">{repoInfo.last_commit.sha.slice(0, 10)}</span> commit
            </RouterLink>
          )}
          <span className="flex items-center gap-1.5">
            <GitBranch className="h-4 w-4" />
            <span className="font-medium text-foreground">{repoInfo.branch_count}</span>
            <span>{repoInfo.branch_count === 1 ? "branch" : "branches"}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <Tag className="h-4 w-4" />
            <span className="font-medium text-foreground">{repoInfo.tag_count}</span>
            <span>{repoInfo.tag_count === 1 ? "tag" : "tags"}</span>
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setBranchDropdownOpen((prev) => !prev)}
            className="flex items-center gap-1.5 rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
            data-testid="branch-selector"
          >
            <GitBranch className="h-3.5 w-3.5" />
            <span>{gitRef}</span>
            <span className="text-muted-foreground">&#9662;</span>
          </button>

          {branchDropdownOpen && (
            <div
              className="absolute left-0 top-full z-50 mt-1 w-56 overflow-hidden rounded-lg border border-border bg-card shadow-lg"
              data-testid="branch-dropdown"
            >
              <div className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
                Switch branch
              </div>
              <div className="max-h-64 overflow-y-auto py-1">
                {branches?.map((branch) => (
                  <button
                    key={branch.name}
                    type="button"
                    onClick={() => handleBranchSelect(branch.name)}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-foreground transition-colors hover:bg-accent"
                    data-testid={`branch-option-${branch.name}`}
                  >
                    {branch.name === gitRef ? (
                      <Check className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
                    ) : (
                      <span className="h-3.5 w-3.5 flex-shrink-0" />
                    )}
                    <span className="truncate">{branch.name}</span>
                    {branch.is_default && <span className="ml-auto text-xs text-muted-foreground">default</span>}
                  </button>
                ))}
                {!branches && <div className="px-3 py-2 text-sm text-muted-foreground">Loading...</div>}
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          className="flex items-center gap-1.5 rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
        >
          Find a file
        </button>

        <div className="ml-auto flex items-center gap-2">
          <span className="flex items-center gap-1.5 rounded bg-success px-2 py-1 text-xs font-bold text-success-foreground">
            <Lock className="h-3 w-3" />
            HTTPS
          </span>
          <div className="flex items-center">
            <input
              type="text"
              readOnly
              value={cloneUrl}
              data-testid="clone-url"
              className="w-72 rounded-l border border-border bg-secondary px-2.5 py-1.5 font-mono text-xs text-muted-foreground"
            />
            <button
              type="button"
              onClick={() => copy(cloneUrl)}
              data-testid="copy-clone-url"
              className="rounded-r border border-l-0 border-border bg-secondary px-2 py-1.5 transition-colors hover:bg-accent"
            >
              <Copy className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RepoStats
