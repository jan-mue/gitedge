import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AtSign, CircleDot, GitPullRequest, Tag, Users } from "lucide-react"
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

export const RepositoryNotificationPreferences = ({
  repository,
  onClose,
}: {
  repository: string
  onClose: () => void
}) => {
  const [owner, repo] = repository.split("/")
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { data, isError, refetch } = useQuery(notificationsGetRepositoryPreferencesOptions({ path: { owner, repo } }))
  const mutation = useMutation({
    ...notificationsSetRepositoryPreferencesMutation(),
    onSuccess: (response) =>
      queryClient.setQueryData(notificationsGetRepositoryPreferencesQueryKey({ path: { owner, repo } }), response),
    onError: handleError.bind(showErrorToast),
  })
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Notification settings</DialogTitle>
          <DialogDescription>
            Choose what <span className="font-medium text-foreground">{repository}</span> notifies you about.
          </DialogDescription>
        </DialogHeader>
        {isError ? (
          <div role="alert">
            <p>Unable to load settings.</p>
            <Button variant="repository" size="compact" onClick={() => refetch()}>
              Try again
            </Button>
          </div>
        ) : !data ? (
          <p role="status">Loading settings…</p>
        ) : (
          <div className="divide-y divide-border border border-border rounded-md">
            {(Object.keys(categoryMeta) as (keyof typeof categoryMeta)[]).map((category) => {
              const meta = categoryMeta[category]
              return (
                <label
                  htmlFor={`notification-category-${category}`}
                  key={category}
                  className="flex items-center justify-between gap-3 px-3 py-2.5 cursor-pointer"
                >
                  <span className="flex items-center gap-2 text-sm text-foreground">
                    <meta.icon className={`w-4 h-4 ${meta.color}`} />
                    {meta.label}
                  </span>
                  <ChoiceInput
                    id={`notification-category-${category}`}
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
                </label>
              )
            })}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Changes apply to future notifications. Your existing notifications stay in your inbox.
        </p>
      </DialogContent>
    </Dialog>
  )
}
