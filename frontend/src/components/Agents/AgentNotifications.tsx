import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Bell, Check, CircleAlert } from "lucide-react"
import {
  agentsNotificationsOptions,
  agentsNotificationsQueryKey,
  agentsReadNotificationMutation,
} from "@/client/@tanstack/react-query.gen"
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
  Link,
} from "@/components/design-system"
import { extractErrorMessage } from "@/utils"
export const AgentNotifications = () => {
  const query = useQueryClient()
  const { data = [] } = useQuery({ ...agentsNotificationsOptions(), refetchInterval: 15000 })
  const read = useMutation({
    ...agentsReadNotificationMutation(),
    onSuccess: () => query.invalidateQueries({ queryKey: agentsNotificationsQueryKey() }),
  })
  if (!data.length) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="notification" size="icon-sm" aria-label={`${data.length} completed or failed agent runs`}>
          <Bell className="size-4" />
          <span className="absolute -right-1 -top-1 rounded-full bg-primary px-1 text-[10px] text-primary-foreground">
            {data.length}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Agent runs</DropdownMenuLabel>
        {data.map((run) => (
          <DropdownMenuItem key={run.id} asChild>
            <Link
              to="/agents"
              search={{ session: run.session_id }}
              appearance="item"
              onClick={() => read.mutate({ path: { run_id: run.id } })}
            >
              {run.status === "completed" ? (
                <Check className="size-4 text-success" />
              ) : (
                <CircleAlert className="size-4 text-destructive" />
              )}
              <span className="max-w-64 truncate">
                {run.status === "completed" ? "Completed" : "Failed"}: {run.prompt}
              </span>
            </Link>
          </DropdownMenuItem>
        ))}
        {read.error && (
          <p role="alert" className="p-2 text-xs text-destructive">
            {extractErrorMessage(read.error)}
          </p>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
