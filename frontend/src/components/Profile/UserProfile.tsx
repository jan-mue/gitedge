import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { GitBranch } from "lucide-react"
import { useState } from "react"

import type { Repository } from "@/client"
import {
  profilesListUserRepositoriesOptions,
  profilesListUserStarredRepositoriesOptions,
  profilesReadUserByUsernameOptions,
} from "@/client/@tanstack/react-query.gen"
import StarButton from "@/components/Repository/StarButton"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"

interface UserProfileProps {
  username: string
}

const RepoCard = ({ repo }: { repo: Repository }) => (
  <div className="border border-border rounded-lg bg-card px-4 py-3" data-testid={`profile-repo-${repo.name}`}>
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <RouterLink
          to="/$owner/$repo"
          params={{ owner: repo.owner, repo: repo.name }}
          className="text-sm font-medium text-primary hover:underline"
        >
          {repo.owner}/{repo.name}
        </RouterLink>
        {repo.description && <p className="text-xs text-muted-foreground mt-1">{repo.description}</p>}
      </div>
      <StarButton owner={repo.owner} repo={repo.name} />
    </div>
  </div>
)

const UserProfile = ({ username }: UserProfileProps) => {
  const [tab, setTab] = useState<"repositories" | "starred">("repositories")

  const { data: user } = useQuery({
    ...profilesReadUserByUsernameOptions({ path: { username } }),
  })

  const isUser = user?.principal_type === "user"

  const { data: repos } = useQuery({
    ...profilesListUserRepositoriesOptions({ path: { username } }),
  })

  const { data: starred } = useQuery({
    ...profilesListUserStarredRepositoriesOptions({ path: { username } }),
    enabled: isUser,
  })

  const list = tab === "repositories" ? (repos?.data ?? []) : (starred?.data ?? [])

  return (
    <div className="container mx-auto max-w-7xl space-y-6 px-4 py-6" data-testid="user-profile">
      <div className="flex items-center gap-4">
        <Avatar className="size-16">
          <AvatarFallback className="text-xl">
            {(user?.display_name || username).slice(0, 1).toUpperCase()}
          </AvatarFallback>
        </Avatar>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{user?.display_name || username}</h1>
          <p className="text-muted-foreground">@{user?.name ?? username}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 border-b border-border">
        <Button
          variant="ghost"
          className={`rounded-none border-b-2 ${
            tab === "repositories" ? "border-primary text-foreground" : "border-transparent text-muted-foreground"
          }`}
          onClick={() => setTab("repositories")}
          data-testid="profile-tab-repositories"
        >
          <GitBranch className="w-4 h-4" />
          Repositories ({repos?.count ?? 0})
        </Button>
        {isUser && (
          <Button
            variant="ghost"
            className={`rounded-none border-b-2 ${
              tab === "starred" ? "border-primary text-foreground" : "border-transparent text-muted-foreground"
            }`}
            onClick={() => setTab("starred")}
            data-testid="profile-tab-starred"
          >
            Starred ({starred?.count ?? 0})
          </Button>
        )}
      </div>

      {list.length > 0 ? (
        <div className="space-y-3">
          {list.map((repo) => (
            <RepoCard key={`${repo.owner}/${repo.name}`} repo={repo} />
          ))}
        </div>
      ) : (
        <div className="py-12 text-center text-sm text-muted-foreground">
          {tab === "repositories" ? "No repositories yet." : "No starred repositories yet."}
        </div>
      )}
    </div>
  )
}

export default UserProfile
