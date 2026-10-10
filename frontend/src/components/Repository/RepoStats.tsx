import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink, useNavigate } from "@tanstack/react-router"
import { Check, Copy, GitBranch, GitCommitHorizontal, HardDrive, Lock, Tag } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import {
  repositoriesGetRepositoryInfoOptions,
  repositoriesGetStatisticsOptions,
  repositoriesListBranchesOptions,
} from "@/client/@tanstack/react-query.gen"
import FileFinder from "@/components/Repository/FileFinder"
import LanguageBar from "@/components/Repository/LanguageBar"
import RepositoryLoading, { RepositoryError } from "@/components/Repository/RepositoryLoading"
import { Skeleton } from "@/components/ui/skeleton"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { formatSize } from "@/utils"

interface RepoStatsProps {
  owner: string
  repo: string
  gitRef: string
  /** Ref used for API calls (branch name or commit SHA). Defaults to gitRef. */
  revision?: string
}

const RepoStats = ({ owner, repo, gitRef, revision }: RepoStatsProps) => {
  const ref = revision ?? gitRef
  const [copiedText, copy] = useCopyToClipboard()
  const navigate = useNavigate()
  const cloneUrl = `${window.location.origin}/${owner}/${repo}.git`
  const isCopied = copiedText === cloneUrl

  const [branchDropdownOpen, setBranchDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: repoInfo } = useQuery({
    ...repositoriesGetRepositoryInfoOptions({ path: { owner, repo }, query: { ref } }),
  })

  const { data: statistics, isPending: statisticsPending } = useQuery({
    ...repositoriesGetStatisticsOptions({ path: { owner, repo }, query: { ref } }),
    staleTime: 30_000,
  })

  const {
    data: branches,
    isError: branchesError,
    refetch: refetchBranches,
  } = useQuery({
    ...repositoriesListBranchesOptions({ path: { owner, repo } }),
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
      to: "/$owner/$repo/src/branch/$branch",
      params: { owner, repo, branch: branchName },
    })
  }

  return (
    <div className="space-y-3" data-testid="repo-stats">
      {repoInfo?.description && <div className="text-foreground">{repoInfo.description}</div>}

      {repoInfo && (
        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
          <RouterLink
            to="/$owner/$repo/commits/branch/$branch"
            params={{ owner, repo, branch: ref }}
            className="flex items-center gap-1.5 hover:text-primary"
          >
            <GitCommitHorizontal className="size-4" />
            {statisticsPending ? (
              <Skeleton className="h-4 w-12" />
            ) : (
              <span className="font-medium text-foreground">{statistics?.commit_count ?? "—"}</span>
            )}{" "}
            commits
          </RouterLink>
          <RouterLink
            to="/$owner/$repo/branches"
            params={{ owner, repo }}
            className="flex items-center gap-1.5 hover:text-primary"
          >
            <GitBranch className="h-4 w-4" />
            <span className="font-medium text-foreground">{repoInfo.branch_count}</span>
            <span>{repoInfo.branch_count === 1 ? "branch" : "branches"}</span>
          </RouterLink>
          <RouterLink
            to="/$owner/$repo/releases"
            params={{ owner, repo }}
            className="flex items-center gap-1.5 hover:text-primary"
          >
            <Tag className="h-4 w-4" />
            <span className="font-medium text-foreground">{repoInfo.tag_count}</span>
            <span>{repoInfo.tag_count === 1 ? "tag" : "tags"}</span>
          </RouterLink>
          {statistics && (
            <span className="ml-auto flex items-center gap-1.5" title="File size at this revision">
              <HardDrive className="size-4" />
              {formatSize(statistics.size ?? 0)}
            </span>
          )}
        </div>
      )}

      {statisticsPending ? (
        <Skeleton className="h-2 w-full" />
      ) : (
        statistics && <LanguageBar languages={statistics.languages ?? []} />
      )}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setBranchDropdownOpen((prev) => !prev)}
            className="flex items-center gap-1.5 rounded border border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent"
            aria-expanded={branchDropdownOpen}
            aria-label="Switch branch"
            onKeyDown={(event) => {
              if (event.key === "Escape") setBranchDropdownOpen(false)
            }}
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
                {branchesError ? (
                  <RepositoryError message="Unable to load branches." retry={() => refetchBranches()} />
                ) : !branches ? (
                  <RepositoryLoading label="Loading branches" rows={3} />
                ) : (
                  branches.length === 0 && <p className="px-3 py-2 text-sm text-muted-foreground">No branches yet.</p>
                )}
              </div>
            </div>
          )}
        </div>

        <FileFinder owner={owner} repo={repo} revision={ref} mode={/^[0-9a-f]{40}$/.test(ref) ? "commit" : "branch"} />

        <div className="flex w-full min-w-0 items-center gap-2 sm:ml-auto sm:w-auto">
          <span className="flex h-8 items-center gap-1.5 rounded bg-success px-2.5 text-xs font-bold text-success-foreground">
            <Lock className="h-3 w-3" />
            HTTPS
          </span>
          <div className="flex h-8 min-w-0 flex-1 items-stretch">
            <input
              type="text"
              readOnly
              value={cloneUrl}
              data-testid="clone-url"
              onFocus={(e) => e.currentTarget.select()}
              className="h-8 min-w-0 w-full sm:w-72 rounded-l border border-border bg-secondary px-2.5 font-mono text-xs text-muted-foreground focus:outline-none"
            />
            <div className="relative flex">
              <button
                type="button"
                onClick={() => copy(cloneUrl)}
                aria-label="Copy clone URL"
                data-testid="copy-clone-url"
                className="flex h-8 w-9 items-center justify-center rounded-r border border-l-0 border-border bg-secondary transition-colors hover:bg-accent"
              >
                {isCopied ? (
                  <Check className="h-3.5 w-3.5 text-success" />
                ) : (
                  <Copy className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </button>
              {isCopied && (
                <span
                  role="status"
                  className="absolute bottom-full right-0 mb-2 whitespace-nowrap rounded border border-border bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95"
                >
                  Copied to clipboard
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RepoStats
