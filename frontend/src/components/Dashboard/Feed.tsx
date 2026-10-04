import { useQuery } from "@tanstack/react-query"

import { ActivityService } from "@/client"
import ActivityList from "@/components/Repository/ActivityList"
import useAuth from "@/hooks/useAuth"

const Feed = () => {
  const { user } = useAuth()

  const { data } = useQuery({
    queryKey: ["feed"],
    queryFn: async () => (await ActivityService.getFeed()).data,
  })

  return (
    <div className="space-y-6" data-testid="dashboard-feed">
      <div>
        <h1 className="text-2xl truncate max-w-sm">Hi, {user?.full_name || user?.username || user?.email} 👋</h1>
        <p className="text-muted-foreground">Here is what is happening in your repositories.</p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Activity feed</h2>
        <ActivityList activities={data?.data ?? []} emptyText="No activity yet. Create a repository to get started." />
      </section>
    </div>
  )
}

export default Feed
