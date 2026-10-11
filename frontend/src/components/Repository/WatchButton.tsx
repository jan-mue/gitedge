import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Eye, EyeOff } from "lucide-react"
import {
  watchersGetWatchStateOptions,
  watchersGetWatchStateQueryKey,
  watchersListWatchersQueryKey,
  watchersUnwatchRepositoryMutation,
  watchersWatchRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, Link as RouterLink } from "@/design-system"

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
      <Button
        type="button"
        onClick={() => mutation.mutate({ path: { owner, repo } })}
        disabled={mutation.isPending}
        aria-pressed={isWatching}
        variant="outline"
        size="sm"
        shape="start"
      >
        <Icon className="h-3.5 w-3.5" />
        <span>{isWatching ? "Unwatch" : "Watch"}</span>
      </Button>
      <RouterLink to="/$owner/$repo/watchers" params={{ owner, repo }} data-testid="watch-count" appearance="count">
        {count}
      </RouterLink>
    </div>
  )
}

export default WatchButton
