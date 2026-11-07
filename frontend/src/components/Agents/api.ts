export type { CredentialPublic, EnvironmentPublic, ProviderPublic, RunPublic, SessionPublic } from "@/client"

export const agentsBase = `${import.meta.env.VITE_API_URL ?? ""}/api/v1/agents`
export const agentHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
  "Content-Type": "application/json",
})

export async function agentApi<T>(
  path: string,
  body?: unknown,
  method = body === undefined ? "GET" : "POST",
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${agentsBase}${path}`, {
    method,
    headers: agentHeaders(),
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    const result = await response.json().catch(() => null)
    throw new Error(typeof result?.detail === "string" ? result.detail : `Agent request failed (${response.status})`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}
