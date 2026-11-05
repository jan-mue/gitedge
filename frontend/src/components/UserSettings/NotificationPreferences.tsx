import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Inbox, Mail } from "lucide-react"
import {
  notificationsGetPreferencesOptions,
  notificationsGetPreferencesQueryKey,
  notificationsSetPreferencesMutation,
} from "@/client/@tanstack/react-query.gen"
import { Button, ChoiceInput } from "@/components/design-system"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const NotificationPreferences = () => {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { data, isPending, isError, refetch } = useQuery(notificationsGetPreferencesOptions())
  const mutation = useMutation({
    ...notificationsSetPreferencesMutation(),
    onSuccess: (response) => queryClient.setQueryData(notificationsGetPreferencesQueryKey(), response),
    onError: handleError.bind(showErrorToast),
  })
  return (
    <section className="border border-border rounded">
      <div className="px-4 py-3 bg-secondary border-b border-border rounded-t">
        <h2 className="font-semibold text-foreground">Notification delivery</h2>
      </div>
      <div className="p-4 space-y-4">
        <p className="text-sm text-muted-foreground">
          Choose how you receive updates from repositories and discussions you follow.
        </p>
        {isPending && (
          <p role="status" className="text-sm text-muted-foreground">
            Loading preferences…
          </p>
        )}
        {isError && (
          <p role="alert" className="text-sm text-destructive">
            Unable to load notification preferences.
          </p>
        )}
        {isError && <RetryPreferences onClick={() => refetch()} />}
        {data && (
          <fieldset disabled={mutation.isPending} className="space-y-3">
            <legend className="sr-only">Delivery channel</legend>
            <label htmlFor="notification-center-only" className="flex items-start gap-3 text-sm cursor-pointer">
              <ChoiceInput
                id="notification-center-only"
                type="radio"
                name="notification-channel"
                checked={!data.email}
                onChange={() => mutation.mutate({ body: { email: false } })}
              />
              <span>
                <span className="flex items-center gap-2 font-medium">
                  <Inbox className="w-4 h-4" />
                  Notification center only
                </span>
                <span className="block mt-1 text-muted-foreground">Read all your notifications in GitEdge.</span>
              </span>
            </label>
            <label htmlFor="notification-email" className="flex items-start gap-3 text-sm cursor-pointer">
              <ChoiceInput
                id="notification-email"
                type="radio"
                name="notification-channel"
                checked={data.email}
                disabled={!data.email_available && !data.email}
                onChange={() => mutation.mutate({ body: { email: true } })}
              />
              <span>
                <span className="flex items-center gap-2 font-medium">
                  <Mail className="w-4 h-4" />
                  Email and notification center
                </span>
                <span className="block mt-1 text-muted-foreground">
                  Also send activity notifications to your account email address.
                </span>
              </span>
            </label>
            {!data.email_available && (
              <p className="text-xs text-muted-foreground">
                Email delivery is unavailable until an administrator configures email for this installation.
              </p>
            )}
          </fieldset>
        )}
        <p role="status" className="text-xs text-muted-foreground">
          {mutation.isPending ? "Saving…" : mutation.isSuccess ? "Preferences saved." : ""}
        </p>
      </div>
    </section>
  )
}

const RetryPreferences = ({ onClick }: { onClick: () => void }) => (
  <Button variant="repository" size="compact" onClick={onClick}>
    Try again
  </Button>
)
