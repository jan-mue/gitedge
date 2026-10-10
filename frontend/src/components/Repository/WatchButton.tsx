import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Eye, EyeOff } from "lucide-react"

import {
  watchersGetWatchStateOptions,
  watchersGetWatchStateQueryKey,
  watchersListWatchersQueryKey,
  watchersUnwatchRepositoryMutation,
  watchersWatchRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"

interface WatchButtonProps {
  owner: string
  repo: string
}

const WatchButton = ({ owner, repo }: WatchButtonProps) => {
  const queryClient = useQueryClient()

  const { data: state } = useQuery({
    ...watchersGetWatchStateOptions({ path: { owner, repo } }),
  })

  const mutation = useMutation({
    ...(state?.is_watching ? watchersUnwatchRepositoryMutation() : watchersWatchRepositoryMutation()),
    onSuccess: (next) => {
      queryClient.setQueryData(watchersGetWatchStateQueryKey({ path: { owner, repo } }), next)
      queryClient.invalidateQueries({ queryKey: watchersListWatchersQueryKey({ path: { owner, repo } }) })
    },
  })

  const isWatching = state?.is_watching ?? false
  const count = state?.watchers_count ?? 0
  const Icon = isWatching ? EyeOff : Eye

  return (
    <div className="flex items-stretch" data-testid="watch-button">
      <button
        type="button"
        onClick={() => mutation.mutate({ path: { owner, repo } })}
        disabled={mutation.isPending}
        className="flex items-center gap-1.5 rounded-l border border-r-0 border-border bg-secondary px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-accent disabled:opacity-50"
      >
        <Icon className="h-3.5 w-3.5" />
        <span>{isWatching ? "Unwatch" : "Watch"}</span>
      </button>
      <RouterLink
        to="/$owner/$repo/watchers"
        params={{ owner, repo }}
        data-testid="watch-count"
        className="flex items-center justify-center rounded-r border border-border bg-secondary px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent"
      >
        {count}
      </RouterLink>
    </div>
  )
}

export default WatchButton
