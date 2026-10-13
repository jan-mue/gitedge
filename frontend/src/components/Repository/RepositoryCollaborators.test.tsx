import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import {
  handleAuthorizationListCollaborators,
  handleAuthorizationListCollaboratorTeams,
  handleAuthorizationSetCollaborator,
  handleProfilesReadUserByUsername,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { render, screen, waitFor } from "@/test/test-utils"
import RepositoryCollaborators from "./RepositoryCollaborators"

vi.mock("@/hooks/useCustomToast", () => ({ default: () => ({ showSuccessToast: vi.fn(), showErrorToast: vi.fn() }) }))

const userId = "00000000-0000-0000-0000-000000000001"
const teamId = "00000000-0000-0000-0000-000000000002"
const collaboratorId = "00000000-0000-0000-0000-000000000003"

describe("RepositoryCollaborators", () => {
  beforeEach(() => {
    server.use(
      handleAuthorizationListCollaborators({ body: [] }),
      handleAuthorizationListCollaboratorTeams({ body: [{ id: teamId, organization_id: userId, name: "developers" }] }),
      handleProfilesReadUserByUsername({ body: { id: userId, name: "alice", principal_type: "user" } }),
    )
  })

  test("grants a user role by username", async () => {
    const grant = vi.fn()
    server.use(
      handleAuthorizationSetCollaborator(async ({ request }) => {
        const body = await request.json()
        grant(body)
        return HttpResponse.json({ ...body, id: collaboratorId, subject_name: "alice" })
      }),
    )
    const { user } = render(<RepositoryCollaborators owner="org" repo="repo" canManageOwners={false} />)
    await screen.findByText("No additional collaborators.")
    await user.type(screen.getByLabelText("Username"), "alice")
    await user.selectOptions(screen.getByLabelText("Role"), "write")
    await user.click(screen.getByRole("button", { name: "Add collaborator" }))
    await waitFor(() => expect(grant).toHaveBeenCalledExactlyOnceWith({ user_id: userId, role: "write" }))
  })

  test("grants a team role using its name", async () => {
    const grant = vi.fn()
    server.use(
      handleAuthorizationSetCollaborator(async ({ request }) => {
        const body = await request.json()
        grant(body)
        return HttpResponse.json({ ...body, id: collaboratorId, subject_name: "developers" })
      }),
    )
    const { user } = render(<RepositoryCollaborators owner="org" repo="repo" canManageOwners />)
    await screen.findByRole("option", { name: "Organization team" })
    await user.selectOptions(screen.getByLabelText("Collaborator type"), "team")
    await user.selectOptions(screen.getByLabelText("Team"), teamId)
    await user.selectOptions(screen.getByLabelText("Role"), "admin")
    await user.click(screen.getByRole("button", { name: "Add collaborator" }))
    await waitFor(() => expect(grant).toHaveBeenCalledExactlyOnceWith({ team_id: teamId, role: "admin" }))
  })

  test("prevents admins from changing owner grants", async () => {
    server.use(
      handleAuthorizationListCollaborators({
        body: [{ id: collaboratorId, user_id: userId, team_id: null, subject_name: "alice", role: "owner" }],
      }),
    )
    render(<RepositoryCollaborators owner="org" repo="repo" canManageOwners={false} />)
    expect(await screen.findByLabelText("Role for alice")).toBeDisabled()
    expect(screen.getByRole("button", { name: "Remove" })).toBeDisabled()
    expect(screen.getByLabelText("Role")).not.toContainElement(screen.getByRole("option", { name: "Owner" }))
  })
})
