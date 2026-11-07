import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Bell, Check, CircleAlert } from "lucide-react"
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
  Link,
} from "@/components/design-system"
import { agentApi, type RunPublic } from "./api"

export const AgentNotifications = () => {
  const query = useQueryClient()
  const { data = [] } = useQuery({
    queryKey: ["agent-notifications"],
    queryFn: async () => {
      const result = await fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/v1/agents/notifications`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
      })
      if (result.status === 503) return [] as RunPublic[]
      if (!result.ok) throw new Error("Unable to fetch agent notifications")
      return result.json() as Promise<RunPublic[]>
    },
    refetchInterval: 15000,
  })
  const read = useMutation({
    mutationFn: (id: string) => agentApi(`/runs/${id}/read`, {}),
    onSuccess: () => query.invalidateQueries({ queryKey: ["agent-notifications"] }),
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
              onClick={() => read.mutate(run.id)}
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
            {read.error.message}
          </p>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
