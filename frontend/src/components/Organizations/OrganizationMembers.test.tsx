import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import {
  handleAuthorizationGetOrganizationPermissions,
  handleAuthorizationListMembers,
  handleAuthorizationSearchMemberCandidates,
  handleAuthorizationSetMember,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { renderWithRouter, screen, waitFor, within } from "@/test/test-utils"
import { OrganizationMembers } from "./OrganizationMembers"

const adminId = "00000000-0000-0000-0000-000000000001"
const userId = "00000000-0000-0000-0000-000000000002"
const renderMembers = () => renderWithRouter({ component: () => <OrganizationMembers organization="company" /> })
describe("OrganizationMembers", () => {
  beforeEach(() =>
    server.use(
      handleAuthorizationGetOrganizationPermissions({ body: { admin: true } }),
      handleAuthorizationListMembers({ body: [{ user_id: adminId, name: "admin", is_admin: true }] }),
      handleAuthorizationSearchMemberCandidates({
        body: [{ id: userId, name: "alice", display_name: "Alice Example", principal_type: "user" }],
      }),
    ),
  )
  test("adds a member with the selected organization role and protects the last admin", async () => {
    const grant = vi.fn()
    server.use(
      handleAuthorizationSetMember(async ({ request }) => {
        const body = await request.json()
        grant(body)
        return HttpResponse.json({ user_id: userId, name: "alice", ...body })
      }),
    )
    const { user } = renderMembers()
    expect(await screen.findByLabelText("Role for admin")).toBeDisabled()
    expect(screen.getByRole("button", { name: "Remove admin" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Add people" }))
    const dialog = within(screen.getByRole("dialog"))
    await user.type(dialog.getByLabelText("Search by username, full name, or email"), "alice")
    await user.click(await dialog.findByRole("button", { name: /Alice Example/ }))
    await user.click(dialog.getByRole("combobox", { name: "Role" }))
    await user.click(screen.getByRole("option", { name: "Admin" }))
    await user.click(dialog.getByRole("button", { name: "Add to organization" }))
    await waitFor(() => expect(grant).toHaveBeenCalledExactlyOnceWith({ is_admin: true }))
  })
  test("members can view and search the table but cannot change roles or add people", async () => {
    server.use(handleAuthorizationGetOrganizationPermissions({ body: { admin: false } }))
    renderMembers()
    expect(await screen.findByLabelText("Role for admin")).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Add people" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Remove admin" })).not.toBeInTheDocument()
  })
  test("filters and paginates the same table", async () => {
    server.use(
      handleAuthorizationListMembers({
        body: Array.from({ length: 12 }, (_, index) => ({
          user_id: String(index),
          name: `member-${index}`,
          is_admin: index === 0,
        })),
      }),
    )
    const { user } = renderMembers()
    await screen.findByLabelText("Role for member-0")
    expect(screen.queryByLabelText("Role for member-10")).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Next" }))
    expect(screen.getByLabelText("Role for member-10")).toBeInTheDocument()
    await user.type(screen.getByRole("textbox", { name: "Find a member" }), "member-0")
    expect(screen.getByLabelText("Role for member-0")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled()
  })
})
