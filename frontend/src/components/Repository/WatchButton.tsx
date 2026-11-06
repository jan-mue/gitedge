import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
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
import { useRepositoryViewer } from "@/hooks/useRepositoryViewer"

interface WatchButtonProps {
  owner: string
  repo: string
}

const WatchButton = ({ owner, repo }: WatchButtonProps) => {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { authenticated, repository } = useRepositoryViewer(owner, repo)

  const { data: state } = useQuery({
    ...watchersGetWatchStateOptions({ path: { owner, repo } }),
    enabled: authenticated,
  })

  const mutation = useMutation({
    ...(state?.is_watching ? watchersUnwatchRepositoryMutation() : watchersWatchRepositoryMutation()),
    onSuccess: (next) => {
      queryClient.setQueryData(watchersGetWatchStateQueryKey({ path: { owner, repo } }), next)
      queryClient.invalidateQueries({ queryKey: watchersListWatchersQueryKey({ path: { owner, repo } }) })
    },
  })

  const isWatching = authenticated && (state?.is_watching ?? false)
  const count = (authenticated ? state?.watchers_count : repository?.watchers_count) ?? 0
  const Icon = isWatching ? EyeOff : Eye

  return (
    <div className="flex items-stretch" data-testid="watch-button">
      <Button
        type="button"
        onClick={() => (authenticated ? mutation.mutate({ path: { owner, repo } }) : navigate({ to: "/login" }))}
        disabled={mutation.isPending || (authenticated && !state)}
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
          <Button
            variant="repository"
            size="icon-sm"
            shape="end"
            aria-label="Notification settings"
            disabled={!authenticated}
          >
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
