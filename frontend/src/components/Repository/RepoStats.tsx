import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  Check,
  Copy,
  GitBranch,
  GitCommitHorizontal,
  Lock,
  Tag,
} from "lucide-react"
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
    queryFn: async () =>
      (await RepositoriesService.listBranches({ path: { path: repoPath } }))
        .data,
    enabled: branchDropdownOpen,
  })

  const handleClickOutside = useCallback((event: MouseEvent) => {
    if (
      dropdownRef.current &&
      !dropdownRef.current.contains(event.target as Node)
    ) {
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
      {/* Stats */}
      {repoInfo && (
        <div className="flex items-center gap-6 text-sm text-muted-foreground">
          {repoInfo.last_commit && (
            <span className="flex items-center gap-1.5">
              <GitCommitHorizontal className="w-4 h-4" />
              <span className="text-foreground font-medium">
                {repoInfo.last_commit.sha.slice(0, 10)}
              </span>
            </span>
          )}
          <span className="flex items-center gap-1.5">
            <GitBranch className="w-4 h-4" />
            <span className="text-foreground font-medium">
              {repoInfo.branch_count}
            </span>{" "}
            {repoInfo.branch_count === 1 ? "branch" : "branches"}
          </span>
          <span className="flex items-center gap-1.5">
            <Tag className="w-4 h-4" />
            <span className="text-foreground font-medium">
              {repoInfo.tag_count}
            </span>{" "}
            {repoInfo.tag_count === 1 ? "tag" : "tags"}
          </span>
        </div>
      )}

      {/* Branch selector and clone URL */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setBranchDropdownOpen((prev) => !prev)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-secondary text-sm text-foreground hover:bg-accent transition-colors"
            data-testid="branch-selector"
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span>{gitRef}</span>
            <span className="text-muted-foreground">&#9662;</span>
          </button>

          {branchDropdownOpen && (
            <div
              className="absolute top-full left-0 mt-1 w-56 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden"
              data-testid="branch-dropdown"
            >
              <div className="px-3 py-2 border-b border-border text-xs font-medium text-muted-foreground">
                Switch branch
              </div>
              <div className="max-h-64 overflow-y-auto py-1">
                {branches?.map((branch) => (
                  <button
                    key={branch.name}
                    type="button"
                    onClick={() => handleBranchSelect(branch.name)}
                    className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-foreground hover:bg-accent transition-colors text-left"
                    data-testid={`branch-option-${branch.name}`}
                  >
                    {branch.name === gitRef ? (
                      <Check className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                    ) : (
                      <span className="w-3.5 h-3.5 flex-shrink-0" />
                    )}
                    <span className="truncate">{branch.name}</span>
                    {branch.is_default && (
                      <span className="ml-auto text-xs text-muted-foreground">
                        default
                      </span>
                    )}
                  </button>
                ))}
                {!branches && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    Loading...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <span className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-bold bg-success text-success-foreground">
            <Lock className="w-3 h-3" />
            HTTPS
          </span>
          <div className="flex items-center">
            <input
              type="text"
              readOnly
              value={cloneUrl}
              data-testid="clone-url"
              className="px-2.5 py-1.5 text-xs font-mono bg-secondary border border-border rounded-l text-muted-foreground w-72"
            />
            <button
              type="button"
              onClick={() => copy(cloneUrl)}
              data-testid="copy-clone-url"
              className="px-2 py-1.5 border border-l-0 border-border rounded-r bg-secondary hover:bg-accent transition-colors"
            >
              <Copy className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RepoStats
