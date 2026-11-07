import { createFileRoute } from "@tanstack/react-router"
import { AgentWorkspace } from "@/components/Agents/AgentWorkspace"

export const Route = createFileRoute("/_layout/agents")({
  component: AgentWorkspace,
  head: () => ({ meta: [{ title: "Agents - GitEdge" }] }),
})
