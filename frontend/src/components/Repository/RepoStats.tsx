import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Check, Copy, GitBranch, GitCommitHorizontal, HardDrive, Lock, Tag } from "lucide-react"
import { useState } from "react"
import {
  releasesListTagsOptions,
  repositoriesGetRepositoryInfoOptions,
  repositoriesGetStatisticsOptions,
  repositoriesListBranchesOptions,
} from "@/client/@tanstack/react-query.gen"
import { Button, Input, LanguageBar, Link as RouterLink, Skeleton } from "@/components/design-system"
import type { SourceMode } from "@/components/Repositories/SourceLink"
import BranchSelector from "@/components/Repository/BranchSelector"
import FileFinder from "@/components/Repository/FileFinder"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import { formatSize } from "@/utils"

interface RepoStatsProps {
  owner: string
  repo: string
  gitRef: string
  /** Ref used for API calls (branch name or commit SHA). Defaults to gitRef. */
  revision?: string
  showStatistics?: boolean
  mode?: SourceMode
}

const RepoStats = ({ owner, repo, gitRef, revision, showStatistics = true, mode = "branch" }: RepoStatsProps) => {
  const ref = revision ?? gitRef
  const [copiedText, copy] = useCopyToClipboard()
  const navigate = useNavigate()
  const cloneUrl = `${window.location.origin}/${owner}/${repo}.git`
  const isCopied = copiedText === cloneUrl

  const [branchDropdownOpen, setBranchDropdownOpen] = useState(false)

  const { data: repoInfo } = useQuery({
    ...repositoriesGetRepositoryInfoOptions({ path: { owner, repo }, query: { ref } }),
  })

  const { data: statistics, isPending: statisticsPending } = useQuery({
    ...repositoriesGetStatisticsOptions({ path: { owner, repo }, query: { ref } }),
    staleTime: 30_000,
    enabled: showStatistics,
  })

  const {
    data: branches,
    isPending: branchesPending,
    isError: branchesError,
    refetch: refetchBranches,
  } = useQuery({
    ...repositoriesListBranchesOptions({ path: { owner, repo } }),
  })

  const {
    data: tags,
    isPending: tagsPending,
    isError: tagsError,
    refetch: refetchTags,
  } = useQuery({
    ...releasesListTagsOptions({ path: { owner, repo } }),
    enabled: branchDropdownOpen,
  })

  const handleBranchSelect = (branchName: string, kind: "branch" | "tag") => {
    setBranchDropdownOpen(false)
    if (kind === "tag") navigate({ to: "/$owner/$repo/src/tag/$tag", params: { owner, repo, tag: branchName } })
    else
      navigate({
        to: "/$owner/$repo/src/branch/$branch",
        params: { owner, repo, branch: branchName },
      })
  }

  return (
    <div className="space-y-3" data-testid="repo-stats">
      {repoInfo?.description && <div className="text-foreground">{repoInfo.description}</div>}

      {showStatistics && repoInfo && (
        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
          {mode === "tag" ? (
            <RouterLink to="/$owner/$repo/commits/tag/$tag" params={{ owner, repo, tag: gitRef }} appearance="stat">
              <GitCommitHorizontal className="size-4" />
              {statisticsPending ? (
                <Skeleton appearance="short" />
              ) : (
                <span className="font-medium text-foreground">{statistics?.commit_count ?? "—"}</span>
              )}{" "}
              commits
            </RouterLink>
          ) : (
            <RouterLink
              to="/$owner/$repo/commits/branch/$branch"
              params={{ owner, repo, branch: ref }}
              appearance="stat"
            >
              <GitCommitHorizontal className="size-4" />
              {statisticsPending ? (
                <Skeleton appearance="short" />
              ) : (
                <span className="font-medium text-foreground">{statistics?.commit_count ?? "—"}</span>
              )}{" "}
              commits
            </RouterLink>
          )}

          <RouterLink to="/$owner/$repo/branches" params={{ owner, repo }} appearance="stat">
            <GitBranch className="h-4 w-4" />
            <span className="font-medium text-foreground">{repoInfo.branch_count}</span>
            <span>{repoInfo.branch_count === 1 ? "branch" : "branches"}</span>
          </RouterLink>
          <RouterLink to="/$owner/$repo/releases" params={{ owner, repo }} appearance="stat">
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

      {showStatistics &&
        (statisticsPending ? (
          <Skeleton appearance="bar" />
        ) : (
          statistics && <LanguageBar languages={statistics.languages ?? []} />
        ))}
      <div className="flex flex-wrap items-center gap-2">
        <BranchSelector
          branches={branches ?? []}
          tags={tags?.data ?? []}
          kind={mode === "tag" ? "tag" : "branch"}
          value={gitRef}
          onValueChange={handleBranchSelect}
          open={branchDropdownOpen}
          onOpenChange={setBranchDropdownOpen}
          loading={branchesPending}
          error={branchesError}
          onRetry={() => refetchBranches()}
          tagsLoading={tagsPending}
          tagsError={tagsError}
          onRetryTags={() => refetchTags()}
          data-testid="branch-selector"
        />

        <FileFinder owner={owner} repo={repo} revision={ref} mode={mode} />

        <div className="flex w-full min-w-0 items-center gap-2 sm:ml-auto sm:w-auto">
          <span className="flex h-8 items-center gap-1.5 rounded bg-success-emphasis px-2.5 text-xs font-bold text-success-foreground">
            <Lock className="h-3 w-3" />
            HTTPS
          </span>
          <div className="flex h-8 min-w-0 flex-1 items-stretch">
            <Input
              type="text"
              readOnly
              value={cloneUrl}
              data-testid="clone-url"
              aria-label="HTTPS clone URL"
              onFocus={(e) => e.currentTarget.select()}
              appearance="clone"
            />
            <div className="relative flex">
              <Button
                type="button"
                onClick={() => copy(cloneUrl)}
                aria-label="Copy clone URL"
                data-testid="copy-clone-url"
                variant="repository"
                size="icon-sm"
                shape="end"
              >
                {isCopied ? (
                  <Check className="h-3.5 w-3.5 text-success" />
                ) : (
                  <Copy className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </Button>
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
