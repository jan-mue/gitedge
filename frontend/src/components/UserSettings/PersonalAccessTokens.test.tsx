import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import type { PersonalAccessTokenPublic } from "@/client"
import {
  handlePersonalAccessTokensCreateToken,
  handlePersonalAccessTokensListTokens,
  handlePersonalAccessTokensRepositoryOptions,
  handlePersonalAccessTokensRevokeToken,
  handlePersonalAccessTokensRotateToken,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import PersonalAccessTokens from "./PersonalAccessTokens"

vi.mock("@/hooks/useCustomToast", () => ({ default: () => ({ showSuccessToast: vi.fn(), showErrorToast: vi.fn() }) }))
const fullToken = `gitedge_pat_live_v1_${"a".repeat(24)}.${"b".repeat(43)}`
const metadata: PersonalAccessTokenPublic = {
  id: "00000000-0000-0000-0000-000000000001",
  owner_id: "00000000-0000-0000-0000-000000000002",
  name: "Laptop",
  prefix: "gitedge_pat_live_v1_",
  key_id: "a".repeat(24),
  secret_last4: "bbbb",
  scopes: ["git:read"],
  repository_ids: ["00000000-0000-0000-0000-000000000003"],
  created_at: "2026-10-13T10:00:00Z",
  expires_at: null,
  last_used_at: null,
  revoked_at: null,
  revoked_reason: null,
}

describe("PersonalAccessTokens", () => {
  beforeEach(() =>
    server.use(
      handlePersonalAccessTokensListTokens({ body: [] }),
      handlePersonalAccessTokensRepositoryOptions({
        body: [{ id: "00000000-0000-0000-0000-000000000003", owner: "jan", name: "gitedge" }],
      }),
    ),
  )

  test("shows the issued secret once and submits selected scope and expiry", async () => {
    const create = vi.fn()
    server.use(
      handlePersonalAccessTokensCreateToken(async ({ request }) => {
        create(await request.json())
        return HttpResponse.json({ ...metadata, token: fullToken }, { status: 201 })
      }),
    )
    const { user } = render(<PersonalAccessTokens />)
    await screen.findByText("No personal access tokens.")
    await user.type(screen.getByLabelText("Token name"), "Laptop")
    await user.click(await screen.findByRole("checkbox", { name: "jan/gitedge" }))
    await user.click(screen.getByRole("checkbox", { name: "Push commits (includes clone and fetch)" }))
    await user.click(screen.getByRole("checkbox", { name: "Create and update issues" }))
    await user.click(screen.getByRole("button", { name: "Create token" }))
    expect(await screen.findByLabelText("New personal access token")).toHaveValue(fullToken)
    expect(create).toHaveBeenCalledExactlyOnceWith({
      name: "Laptop",
      scopes: ["repository:read", "git:write", "issues:write"],
      repository_ids: metadata.repository_ids,
      expires_at: expect.any(String),
    })
    await user.click(screen.getByRole("button", { name: "I've saved my token" }))
    expect(screen.queryByLabelText("New personal access token")).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain(fullToken)
  })

  test("requires repository and operation selections and preserves selection while searching", async () => {
    const create = vi.fn()
    server.use(
      handlePersonalAccessTokensCreateToken(async () => {
        create()
        return HttpResponse.json({ ...metadata, token: fullToken }, { status: 201 })
      }),
    )
    const { user } = render(<PersonalAccessTokens />)
    await user.type(screen.getByLabelText("Token name"), "Restricted")
    await screen.findByRole("checkbox", { name: "jan/gitedge" })
    await user.click(screen.getByRole("button", { name: "Create token" }))
    expect(await screen.findByText("Select at least one repository")).toBeInTheDocument()
    await user.click(screen.getByRole("checkbox", { name: "jan/gitedge" }))
    await user.click(screen.getByRole("checkbox", { name: "Read repository contents and discussions" }))
    await user.click(screen.getByRole("button", { name: "Create token" }))
    expect(await screen.findByText("Select at least one operation")).toBeInTheDocument()
    await user.type(screen.getByLabelText("Search repositories"), "missing")
    expect(screen.queryByRole("checkbox", { name: "jan/gitedge" })).not.toBeInTheDocument()
    await user.clear(screen.getByLabelText("Search repositories"))
    expect(screen.getByRole("checkbox", { name: "jan/gitedge" })).toBeChecked()
    expect(create).not.toHaveBeenCalled()
  })

  test("revokes a token and lists only its masked metadata", async () => {
    const revoke = vi.fn()
    server.use(
      handlePersonalAccessTokensListTokens({ body: [metadata] }),
      handlePersonalAccessTokensRevokeToken(async ({ request, params }) => {
        revoke({ params, body: await request.json() })
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = render(<PersonalAccessTokens />)
    expect(await screen.findByText("Laptop")).toBeInTheDocument()
    expect(screen.getByText(/Ending in bbbb/)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain(fullToken)
    await user.click(screen.getByRole("button", { name: "Revoke" }))
    await waitFor(() =>
      expect(revoke).toHaveBeenCalledExactlyOnceWith({
        params: expect.objectContaining({ token_id: metadata.id }),
        body: { reason: "Revoked in account settings" },
      }),
    )
  })

  test("rotates through the same show-once flow", async () => {
    const rotate = vi.fn()
    server.use(
      handlePersonalAccessTokensListTokens({ body: [metadata] }),
      handlePersonalAccessTokensRotateToken(async ({ request, params }) => {
        rotate({ params, body: await request.json() })
        return HttpResponse.json({ ...metadata, token: fullToken }, { status: 201 })
      }),
    )
    const { user } = render(<PersonalAccessTokens />)
    await user.click(await screen.findByRole("button", { name: "Rotate" }))
    expect(screen.getByText("The old token will be revoked when its replacement is created.")).toBeInTheDocument()
    await user.click(screen.getByRole("combobox", { name: "Expiration" }))
    await user.click(screen.getByRole("option", { name: "No expiration" }))
    await user.click(screen.getByRole("button", { name: "Create replacement" }))
    expect(await screen.findByLabelText("New personal access token")).toHaveValue(fullToken)
    expect(rotate).toHaveBeenCalledExactlyOnceWith({
      params: expect.objectContaining({ token_id: metadata.id }),
      body: { name: "Laptop", scopes: ["git:read"], repository_ids: metadata.repository_ids, expires_at: null },
    })
  })
})
