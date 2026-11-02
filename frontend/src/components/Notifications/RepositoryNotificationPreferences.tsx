import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AtSign, CircleDot, GitPullRequest, Tag, Users } from "lucide-react"
import { useId } from "react"
import {
  notificationsGetRepositoryPreferencesOptions,
  notificationsGetRepositoryPreferencesQueryKey,
  notificationsSetRepositoryPreferencesMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  ChoiceInput,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  NotificationPreferenceList,
  NotificationPreferenceOption,
} from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const categoryMeta = {
  pull: { label: "Pull requests", icon: GitPullRequest, color: "text-success" },
  issue: { label: "Issues", icon: CircleDot, color: "text-success" },
  release: { label: "Releases", icon: Tag, color: "text-warning" },
  mention: { label: "Direct mentions", icon: AtSign, color: "text-primary" },
  repository: { label: "Repository activity", icon: Users, color: "text-info" },
}

export const RepositoryNotificationOptions = ({
  repository,
  compact = false,
}: {
  repository: string
  compact?: boolean
}) => {
  const [owner, repo] = repository.split("/")
  const id = useId()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { data, isError, refetch } = useQuery(notificationsGetRepositoryPreferencesOptions({ path: { owner, repo } }))
  const mutation = useMutation({
    ...notificationsSetRepositoryPreferencesMutation(),
    onSuccess: (response) =>
      queryClient.setQueryData(notificationsGetRepositoryPreferencesQueryKey({ path: { owner, repo } }), response),
    onError: handleError.bind(showErrorToast),
  })
  if (isError)
    return (
      <div role="alert" className="p-3 text-sm">
        <p>Unable to load settings.</p>
        <Button variant="text" size="text" onClick={() => refetch()}>
          Try again
        </Button>
      </div>
    )
  if (!data)
    return (
      <p role="status" className="p-3 text-sm">
        Loading settings…
      </p>
    )
  return (
    <NotificationPreferenceList compact={compact}>
      {(Object.keys(categoryMeta) as (keyof typeof categoryMeta)[]).map((category) => {
        const meta = categoryMeta[category]
        return (
          <NotificationPreferenceOption
            compact={compact}
            key={category}
            htmlFor={`${id}-${category}`}
            icon={<meta.icon className={`size-4 ${meta.color}`} />}
            label={meta.label}
          >
            <ChoiceInput
              id={`${id}-${category}`}
              appearance="notificationSwitch"
              type="checkbox"
              role="switch"
              aria-label={meta.label}
              checked={data.categories?.includes(category) ?? false}
              disabled={mutation.isPending}
              onChange={(event) =>
                mutation.mutate({
                  path: { owner, repo },
                  body: {
                    categories: event.target.checked
                      ? [...(data.categories ?? []), category]
                      : data.categories?.filter((value) => value !== category),
                  },
                })
              }
            />
          </NotificationPreferenceOption>
        )
      })}
    </NotificationPreferenceList>
  )
}

export const RepositoryNotificationPreferences = ({
  repository,
  onClose,
}: {
  repository: string
  onClose: () => void
}) => (
  <Dialog open onOpenChange={(open) => !open && onClose()}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Notification settings</DialogTitle>
        <DialogDescription>
          Choose what <span className="font-medium text-foreground">{repository}</span> notifies you about.
        </DialogDescription>
      </DialogHeader>
      <RepositoryNotificationOptions repository={repository} />
    </DialogContent>
  </Dialog>
)
