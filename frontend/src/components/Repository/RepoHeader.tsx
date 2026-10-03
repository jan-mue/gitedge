import { Link as RouterLink, useMatches } from "@tanstack/react-router"
import {
  CircleDot,
  Code,
  GitFork,
  GitPullRequest,
  Moon,
  Sun,
} from "lucide-react"

import { useTheme } from "@/components/theme-provider"

interface RepoHeaderProps {
  owner: string
  repo: string
}

const tabs = [
  {
    label: "Code",
    icon: Code,
    path: "/$owner/$repo" as const,
    testId: "tab-code",
  },
  {
    label: "Issues",
    icon: CircleDot,
    path: "/$owner/$repo/issues" as const,
    testId: "tab-issues",
  },
  {
    label: "Pull Requests",
    icon: GitPullRequest,
    path: "/$owner/$repo/pulls" as const,
    testId: "tab-pulls",
  },
] as const

const RepoHeader = ({ owner, repo }: RepoHeaderProps) => {
  const { setTheme, resolvedTheme } = useTheme()
  const matches = useMatches()
  const currentPath = matches[matches.length - 1]?.fullPath ?? ""

  const isActive = (tabPath: string) => {
    if (tabPath === "/$owner/$repo") {
      return (
        currentPath === "/$owner/$repo/" || currentPath === "/$owner/$repo/blob"
      )
    }
    return currentPath.startsWith(tabPath)
  }

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark")
  }

  return (
    <header
      className="border-b border-border bg-background"
      data-testid="repo-header"
    >
      {/* Top bar */}
      <div className="container max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RouterLink
              to="/$owner/$repo"
              params={{ owner, repo }}
              className="flex items-center gap-2"
            >
              <div className="w-7 h-7 rounded bg-primary flex items-center justify-center">
                <GitFork className="w-4 h-4 text-primary-foreground" />
              </div>
              <span className="text-foreground font-medium">
                {owner} / <span className="font-bold">{repo}</span>
              </span>
            </RouterLink>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggleTheme}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-secondary text-foreground text-sm hover:bg-accent transition-colors"
              title={
                resolvedTheme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
              data-testid="theme-toggle"
            >
              {resolvedTheme === "dark" ? (
                <Sun className="w-3.5 h-3.5" />
              ) : (
                <Moon className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="container max-w-7xl mx-auto px-4">
        <nav className="flex gap-1 overflow-x-auto -mb-px">
          {tabs.map((tab) => (
            <RouterLink
              key={tab.label}
              to={tab.path}
              params={{ owner, repo }}
              data-testid={tab.testId}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 transition-colors whitespace-nowrap ${
                isActive(tab.path)
                  ? "border-primary text-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </RouterLink>
          ))}
        </nav>
      </div>
    </header>
  )
}

export default RepoHeader
