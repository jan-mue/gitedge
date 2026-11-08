export type { EnvironmentPublic, RunPublic, SessionPublic } from "@/client"

export const agentsBase = `${import.meta.env.VITE_API_URL ?? ""}/api/v1/agents`
export const agentHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
  "Content-Type": "application/json",
})
