import { Link as RouterLink } from "@tanstack/react-router"
import { Activity, GitFork, MessageSquare, Star, Tag } from "lucide-react"

import type { ActivityPublic } from "@/client"

const kindIcon = (kind: string) => {
  if (kind.startsWith("pull_request")) return <Activity className="w-4 h-4 text-purple-500" />
  if (kind === "star") return <Star className="w-4 h-4 text-warning" />
  if (kind === "watch") return <Activity className="w-4 h-4 text-primary" />
  if (kind === "fork") return <GitFork className="w-4 h-4 text-info" />
  if (kind === "comment") return <MessageSquare className="w-4 h-4 text-muted-foreground" />
  if (kind === "release") return <Tag className="w-4 h-4 text-success" />
  return <Activity className="w-4 h-4 text-success" />
}

const kindLabel = (kind: string) => kind.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())

interface ActivityListProps {
  activities: ActivityPublic[]
  emptyText?: string
}

const ActivityList = ({ activities, emptyText = "No activity yet." }: ActivityListProps) => {
  if (activities.length === 0) {
    return <div className="py-12 text-center text-sm text-muted-foreground">{emptyText}</div>
  }

  return (
    <div className="space-y-2" data-testid="activity-list">
      {activities.map((activity) => {
        const owner = activity.repo_owner
        const repoName = activity.repo_name

        return (
          <div key={activity.id} className="flex items-start gap-3 border border-border rounded-lg bg-card px-4 py-3">
            {kindIcon(activity.kind)}
            <div className="min-w-0 flex-1">
              <p className="text-sm text-foreground">
                <span className="font-medium">{activity.actor_username ?? "Someone"}</span>{" "}
                <span className="text-muted-foreground">{kindLabel(activity.kind).toLowerCase()}</span>
                {activity.title && (
                  <>
                    {" "}
                    <span className="font-medium">{activity.title}</span>
                  </>
                )}
                {owner && repoName && (
                  <>
                    {" in "}
                    <RouterLink
                      to="/$owner/$repo"
                      params={{ owner, repo: repoName }}
                      className="text-primary hover:underline"
                    >
                      {owner}/{repoName}
                    </RouterLink>
                  </>
                )}
              </p>
              {activity.created_at && (
                <p className="text-xs text-muted-foreground mt-0.5">{new Date(activity.created_at).toLocaleString()}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default ActivityList
