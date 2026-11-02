import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import {
  handleAuthorizationListCollaborators,
  handleAuthorizationListCollaboratorTeams,
  handleAuthorizationRemoveCollaborator,
  handleAuthorizationSearchCollaboratorCandidates,
  handleAuthorizationSetCollaborator,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { renderWithRouter, screen, waitFor, within } from "@/test/test-utils"
import RepositoryCollaborators from "./RepositoryCollaborators"

const userId = "00000000-0000-0000-0000-000000000001"
const teamId = "00000000-0000-0000-0000-000000000002"
const collaboratorId = "00000000-0000-0000-0000-000000000003"
const renderCollaborators = (canManageOwners = false) =>
  renderWithRouter({
    component: () => <RepositoryCollaborators owner="org" repo="repo" canManageOwners={canManageOwners} />,
  })

describe("RepositoryCollaborators", () => {
  beforeEach(() => {
    server.use(
      handleAuthorizationListCollaborators({ body: [] }),
      handleAuthorizationListCollaboratorTeams({ body: [{ id: teamId, organization_id: userId, name: "developers" }] }),
      handleAuthorizationSearchCollaboratorCandidates({
        body: [{ id: userId, name: "alice", display_name: "Alice Example", principal_type: "user" }],
      }),
    )
  })
  test("searches people and grants the selected role through the add dialog", async () => {
    const grant = vi.fn()
    server.use(
      handleAuthorizationSetCollaborator(async ({ request }) => {
        const body = await request.json()
        grant(body)
        return HttpResponse.json({ ...body, id: collaboratorId, subject_name: "alice" })
      }),
    )
    const { user } = renderCollaborators()
    await user.click(await screen.findByRole("button", { name: "Add people" }))
    const dialog = within(screen.getByRole("dialog"))
    expect(dialog.getByRole("button", { name: "Add to repository" })).toBeDisabled()
    await user.type(dialog.getByLabelText("Search by username, full name, or email"), "alice")
    await user.click(await dialog.findByRole("button", { name: /Alice Example/ }))
    await user.click(dialog.getByRole("combobox", { name: "Role" }))
    await user.click(screen.getByRole("option", { name: "Write" }))
    await user.click(dialog.getByRole("button", { name: "Add to repository" }))
    await waitFor(() => expect(grant).toHaveBeenCalledExactlyOnceWith({ user_id: userId, role: "write" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })
  test("adds an organization team from the same dialog", async () => {
    const grant = vi.fn()
    server.use(
      handleAuthorizationSetCollaborator(async ({ request }) => {
        const body = await request.json()
        grant(body)
        return HttpResponse.json({ ...body, id: collaboratorId, subject_name: "developers" })
      }),
    )
    const { user } = renderCollaborators(true)
    await user.click(await screen.findByRole("button", { name: "Add people" }))
    await user.click(screen.getByRole("button", { name: /developers Add team/ }))
    await user.click(screen.getByRole("combobox", { name: "Role" }))
    await user.click(screen.getByRole("option", { name: "Admin" }))
    await user.click(screen.getByRole("button", { name: "Add to repository" }))
    await waitFor(() => expect(grant).toHaveBeenCalledExactlyOnceWith({ team_id: teamId, role: "admin" }))
  })
  test("protects owners and filters and removes selected collaborators with confirmation", async () => {
    const remove = vi.fn()
    server.use(
      handleAuthorizationListCollaborators({
        body: [
          { id: collaboratorId, user_id: userId, subject_name: "alice", role: "owner" },
          { id: teamId, team_id: teamId, subject_name: "developers", role: "write" },
        ],
      }),
      handleAuthorizationRemoveCollaborator(({ params }) => {
        remove(params.collaborator_id)
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = renderCollaborators()
    expect(await screen.findByLabelText("Role for alice")).toBeDisabled()
    expect(screen.getByRole("button", { name: "Remove alice" })).toBeDisabled()
    expect(screen.getByRole("checkbox", { name: "Select alice" })).toBeDisabled()
    await user.type(screen.getByRole("textbox", { name: "Find a collaborator" }), "developers")
    expect(screen.queryByLabelText("Role for alice")).not.toBeInTheDocument()
    await user.click(screen.getByRole("checkbox", { name: "Select all" }))
    await user.click(screen.getByRole("button", { name: "Remove selected" }))
    expect(remove).not.toHaveBeenCalled()
    await user.click(screen.getByRole("button", { name: "Remove access" }))
    await waitFor(() => expect(remove).toHaveBeenCalledExactlyOnceWith(teamId))
  })
})
