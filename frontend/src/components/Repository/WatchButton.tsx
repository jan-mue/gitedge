import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronDown, Eye, EyeOff } from "lucide-react"
import {
  watchersGetWatchStateOptions,
  watchersGetWatchStateQueryKey,
  watchersListWatchersQueryKey,
  watchersUnwatchRepositoryMutation,
  watchersWatchRepositoryMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  Popover,
  PopoverContent,
  PopoverTrigger,
  RepositoryMenuFooter,
  RepositoryMenuHeader,
  Link as RouterLink,
} from "@/components/design-system"
import { RepositoryNotificationOptions } from "@/components/Notifications/RepositoryNotificationPreferences"

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
        disabled={mutation.isPending || !state}
        aria-pressed={isWatching}
        variant="repository"
        size="compact"
        shape="start"
      >
        <Icon className="h-3.5 w-3.5" />
        <span>{isWatching ? "Unwatch" : "Watch"}</span>
      </Button>
      <RouterLink
        to="/$owner/$repo/watchers"
        params={{ owner, repo }}
        aria-label="View watchers"
        data-testid="watch-count"
        appearance="splitCount"
      >
        {count}
      </RouterLink>
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="repository" size="icon-sm" shape="end" aria-label="Notification settings">
            <ChevronDown className="size-3.5" />
          </Button>
        </PopoverTrigger>
        <PopoverContent appearance="watchSettings">
          <RepositoryMenuHeader>Notify me about</RepositoryMenuHeader>
          <RepositoryNotificationOptions repository={`${owner}/${repo}`} compact />
          <RepositoryMenuFooter>
            <RouterLink to="/notifications" appearance="caption">
              Open notifications
            </RouterLink>
          </RepositoryMenuFooter>
        </PopoverContent>
      </Popover>
    </div>
  )
}

export default WatchButton
