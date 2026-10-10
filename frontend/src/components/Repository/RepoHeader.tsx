import { Link as RouterLink, useMatches } from "@tanstack/react-router"
import {
  Activity,
  CircleDot,
  Code,
  GitBranch,
  GitFork,
  GitPullRequest,
  MoreHorizontal,
  Settings,
  Tag,
} from "lucide-react"
import ForkButton from "@/components/Repository/ForkButton"
import StarButton from "@/components/Repository/StarButton"
import WatchButton from "@/components/Repository/WatchButton"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

interface RepoHeaderProps {
  owner: string
  repo: string
}

const tabs = [
  { label: "Code", icon: Code, path: "/$owner/$repo" as const, testId: "tab-code" },
  { label: "Issues", icon: CircleDot, path: "/$owner/$repo/issues" as const, testId: "tab-issues" },
  { label: "Pull requests", icon: GitPullRequest, path: "/$owner/$repo/pulls" as const, testId: "tab-pulls" },
  { label: "Releases", icon: Tag, path: "/$owner/$repo/releases" as const, testId: "tab-releases" },
  { label: "Branches", icon: GitBranch, path: "/$owner/$repo/branches" as const, testId: "tab-branches" },
  { label: "Settings", icon: Settings, path: "/$owner/$repo/settings" as const, testId: "tab-settings" },
  { label: "Activity", icon: Activity, path: "/$owner/$repo/activity" as const, testId: "tab-activity" },
] as const

const VISIBLE_TABS_MOBILE = 4

const RepoHeader = ({ owner, repo }: RepoHeaderProps) => {
  const [, copy] = useCopyToClipboard()
  const matches = useMatches()
  const currentPath = matches[matches.length - 1]?.fullPath ?? ""

  const isActive = (tabPath: string) => {
    if (tabPath === "/$owner/$repo") {
      return (
        currentPath === "/$owner/$repo/" ||
        currentPath.startsWith("/$owner/$repo/src/") ||
        currentPath.startsWith("/$owner/$repo/blame/")
      )
    }
    return currentPath.startsWith(tabPath)
  }

  const visibleTabs = tabs.slice(0, VISIBLE_TABS_MOBILE)
  const overflowTabs = tabs.slice(VISIBLE_TABS_MOBILE)

  return (
    <header className="border-b border-border" data-testid="repo-header">
      <div className="container mx-auto max-w-7xl px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <RouterLink to="/$owner/$repo" params={{ owner, repo }} className="shrink-0">
              <div className="flex h-8 w-8 items-center justify-center rounded bg-primary">
                <GitFork className="h-4 w-4 text-primary-foreground" />
              </div>
            </RouterLink>
            <span className="block truncate text-base font-medium text-foreground">
              <RouterLink
                to="/profile/$username"
                params={{ username: owner }}
                className="hover:text-primary hover:underline"
              >
                {owner}
              </RouterLink>
              {" / "}
              <RouterLink
                to="/$owner/$repo"
                params={{ owner, repo }}
                className="font-bold hover:text-primary hover:underline"
              >
                {repo}
              </RouterLink>
            </span>
          </div>

          <div className="flex w-full shrink-0 flex-wrap items-center gap-1 sm:w-auto sm:gap-2 [&>div>button]:px-2 sm:[&>div>button]:px-3">
            <WatchButton owner={owner} repo={repo} />
            <StarButton owner={owner} repo={repo} />
            <ForkButton owner={owner} repo={repo} />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label="Repository menu"
                  className="inline-flex h-8 w-8 items-center justify-center rounded border border-border bg-secondary text-foreground transition-colors hover:bg-accent"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => copy(`${window.location.origin}/${owner}/${repo}`)}>
                  Copy URL
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      <div className="container mx-auto flex max-w-7xl px-4">
        <nav className="flex min-w-0 flex-1 -mb-px gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <RouterLink
              key={tab.label}
              to={tab.path}
              params={{ owner, repo }}
              data-testid={tab.testId}
              className={`hidden items-center gap-1.5 whitespace-nowrap border-b-2 px-4 py-3 text-sm transition-colors md:flex ${
                isActive(tab.path)
                  ? "border-primary font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
              }`}
            >
              <tab.icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </RouterLink>
          ))}

          {visibleTabs.map((tab) => (
            <RouterLink
              key={`m-${tab.label}`}
              to={tab.path}
              params={{ owner, repo }}
              className={`flex items-center gap-1 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors md:hidden ${
                isActive(tab.path)
                  ? "border-primary font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <tab.icon className="h-3.5 w-3.5" />
              <span>{tab.label}</span>
            </RouterLink>
          ))}
        </nav>
        {overflowTabs.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="More repository tabs"
                className="flex items-center gap-1 border-b-2 border-transparent px-3 py-2.5 text-sm text-muted-foreground hover:text-foreground md:hidden"
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {overflowTabs.map((tab) => (
                <DropdownMenuItem key={tab.label} asChild>
                  <RouterLink to={tab.path} params={{ owner, repo }} className="flex items-center gap-2">
                    <tab.icon className="h-4 w-4" />
                    {tab.label}
                  </RouterLink>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  )
}

export default RepoHeader
