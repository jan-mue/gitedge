import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"
import { AgentWorkspace } from "@/components/Agents/AgentWorkspace"

export const Route = createFileRoute("/_layout/agents")({
  component: AgentWorkspace,
  validateSearch: z.object({ session: z.string().uuid().optional() }),
  head: () => ({ meta: [{ title: "Agents - GitEdge" }] }),
})
