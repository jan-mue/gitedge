import { useQuery } from "@tanstack/react-query"
import { Bell } from "lucide-react"
import { Link } from "@/components/design-system"

export const AgentNotifications = () => {
  const { data = [] } = useQuery({
    queryKey: ["agent-notifications"],
    queryFn: async (): Promise<{ id: string; status: string }[]> => {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/v1/agents/notifications`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}` },
      })
      if (response.status === 503) return []
      if (!response.ok) throw new Error("Unable to fetch agent notifications")
      return response.json()
    },
    refetchInterval: 15_000,
  })
  if (data.length === 0) return null
  return (
    <Link to="/agents" appearance="item" aria-label={`${data.length} completed or failed agent runs`}>
      <Bell className="size-4" />
      {data.length}
    </Link>
  )
}
