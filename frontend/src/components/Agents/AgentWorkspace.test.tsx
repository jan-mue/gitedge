import { HttpResponse } from "msw"
import { describe, expect, test, vi } from "vitest"
import type { CredentialPublic } from "@/client"
import {
  handleAgentsCredentials,
  handleAgentsEnvironments,
  handleAgentsModels,
  handleAgentsProviders,
  handleAgentsRemoveCredentials,
  handleAgentsSaveCredentials,
  handleAgentsSessions,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import { AgentWorkspace } from "./AgentWorkspace"

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn(), useSearch: () => ({}) }))

const models = [
  "ollama:local",
  "opencode-zen:hy4-flash-free",
  "opencode-zen:gpt-6.2-sol",
  "opencode-go:hungerg-free",
  "opencode-go:minimax-m3",
  "opencode-go:gemini-4-argon",
]

const workspaceHandlers = () => {
  server.use(
    handleAgentsEnvironments({ body: [] }),
    handleAgentsSessions({ body: [] }),
    handleAgentsModels({ body: models }),
  )
}

describe("OpenCode workspace model discovery", () => {
  test("renders API model suggestions and lets the user select free Zen and Go models", async () => {
    workspaceHandlers()
    const { user, container } = render(<AgentWorkspace />)
    const input = screen.getByRole("combobox", { name: "Model", exact: true })
    await waitFor(() => expect(input).toHaveValue("ollama:local"))
    expect(
      [...container.querySelectorAll("#agent-model-options option")].map((option) => option.getAttribute("value")),
    ).toEqual(models)
    for (const model of ["opencode-zen:hy4-flash-free", "opencode-go:hungerg-free"]) {
      await user.clear(input)
      await user.type(input, model)
      expect(input).toHaveValue(model)
      if (model.startsWith("opencode-zen:")) {
        expect(
          screen.getByText("Free Zen models are restricted to the OpenCode client. They cannot be used from GitEdge."),
        ).toBeInTheDocument()
      } else {
        expect(
          screen.queryByText(
            "Free Zen models are restricted to the OpenCode client. They cannot be used from GitEdge.",
          ),
        ).not.toBeInTheDocument()
      }
    }
  })

  test("saves and removes an OpenCode connection without displaying the secret", async () => {
    workspaceHandlers()
    let connections: CredentialPublic[] = []
    const submitted: unknown[] = []
    server.use(
      handleAgentsProviders({
        body: [
          { provider: "openai", label: "OpenAI", auth: "key" },
          { provider: "opencode-zen", label: "OpenCode Zen", auth: "key" },
          { provider: "opencode-go", label: "OpenCode Go", auth: "key" },
        ],
      }),
      handleAgentsCredentials(() => HttpResponse.json(connections)),
      handleAgentsSaveCredentials(async ({ request, params }) => {
        submitted.push({ provider: params.provider, body: await request.json() })
        connections = [{ provider: "opencode-zen", label: "Free OpenCode" }]
        return HttpResponse.json(connections[0])
      }),
      handleAgentsRemoveCredentials(() => {
        connections = []
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = render(<AgentWorkspace />)
    await user.click(screen.getByRole("button", { name: "AI credentials", exact: true }))
    await user.click(screen.getByRole("combobox", { name: "Provider", exact: true }))
    await user.click(await screen.findByRole("option", { name: "OpenCode Zen", exact: true }))
    await user.type(screen.getByLabelText("Connection label"), "Free OpenCode")
    const secret = screen.getByLabelText("API key", { exact: true })
    expect(secret).toHaveAttribute("type", "password")
    await user.type(secret, "unit-test-key")
    await user.click(screen.getByRole("button", { name: "Save connection", exact: true }))
    await screen.findByRole("button", { name: "Remove Free OpenCode", exact: true })
    expect(submitted).toEqual([{ provider: "opencode-zen", body: { label: "Free OpenCode", secret: "unit-test-key" } }])
    expect(secret).toHaveValue("")
    expect(screen.queryByText("unit-test-key")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Remove Free OpenCode", exact: true }))
    await waitFor(() => expect(screen.queryByRole("button", { name: "Remove Free OpenCode" })).not.toBeInTheDocument())
  })
})
