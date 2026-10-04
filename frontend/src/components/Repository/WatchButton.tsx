import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Eye } from "lucide-react"

import { WatchersService } from "@/client"

interface WatchButtonProps {
  owner: string
  repo: string
}

const WatchButton = ({ owner, repo }: WatchButtonProps) => {
  const repoPath = `${owner}/${repo}.git`
  const queryClient = useQueryClient()

  const { data: state } = useQuery({
    queryKey: ["watch", repoPath],
    queryFn: async () => (await WatchersService.getWatchState({ path: { path: repoPath } })).data,
  })

  const mutation = useMutation({
    mutationFn: async () =>
      state?.is_watching
        ? (await WatchersService.unwatchRepository({ path: { path: repoPath } })).data
        : (await WatchersService.watchRepository({ path: { path: repoPath } })).data,
    onSuccess: (next) => queryClient.setQueryData(["watch", repoPath], next),
  })

  const isWatching = state?.is_watching ?? false
  const count = state?.watchers_count ?? 0

  return (
    <div className="flex items-stretch" data-testid="watch-button">
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-l border border-border text-sm transition-colors ${
          isWatching
            ? "bg-primary text-primary-foreground border-primary"
            : "bg-secondary text-foreground hover:bg-accent"
        }`}
      >
        <Eye className="w-3.5 h-3.5" />
        <span>{isWatching ? "Watching" : "Watch"}</span>
      </button>
      <RouterLink
        to="/$owner/$repo/watchers"
        params={{ owner, repo }}
        className="flex items-center px-2.5 py-1.5 rounded-r border border-l-0 border-border bg-secondary text-sm text-foreground hover:bg-accent transition-colors"
        data-testid="watch-count"
      >
        {count}
      </RouterLink>
    </div>
  )
}

export default WatchButton
