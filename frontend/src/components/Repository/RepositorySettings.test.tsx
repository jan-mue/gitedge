import { HttpResponse } from "msw"
import { beforeEach, describe, expect, test, vi } from "vitest"
import {
  handleAuthorizationGetPermissions,
  handleAuthorizationListCollaborators,
  handleAuthorizationListCollaboratorTeams,
  handleRepositoriesGetRepository,
  handleRepositoriesListBranches,
  handleRepositoriesUpdateRepository,
} from "@/client/msw.gen"
import { server } from "@/test/server"
import { renderWithRouter, screen, waitFor } from "@/test/test-utils"
import RepositorySettings from "./RepositorySettings"

vi.mock("@/hooks/useAuth", () => ({ default: () => ({ user: { name: "alice", is_superuser: false } }) }))
vi.mock("@/hooks/useCustomToast", () => ({ default: () => ({ showSuccessToast: vi.fn(), showErrorToast: vi.fn() }) }))
const repository = {
  owner: "org",
  name: "repo",
  description: "A repository",
  default_branch: "main",
  is_private: false,
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
}
const renderSettings = () =>
  renderWithRouter({
    initialPath: "/org/repo/settings",
    component: () => <RepositorySettings owner="org" repo="repo" />,
  })

describe("RepositorySettings permissions", () => {
  beforeEach(() => {
    server.use(
      handleRepositoriesGetRepository({ body: repository }),
      handleRepositoriesListBranches({ body: [{ name: "main", is_default: true }] }),
      handleAuthorizationListCollaborators({ body: [] }),
      handleAuthorizationListCollaboratorTeams({ body: [] }),
      handleAuthorizationGetPermissions({ body: { read: true, write: true, admin: true, owner: false } }),
    )
  })
  test("allows a collaborator admin to change visibility while hiding owner actions", async () => {
    const update = vi.fn()
    server.use(
      handleRepositoriesUpdateRepository(async ({ request }) => {
        const body = await request.json()
        update(body)
        return HttpResponse.json({ ...repository, ...body })
      }),
    )
    const { user } = renderSettings()
    await user.click(await screen.findByRole("checkbox", { name: "Private repository" }))
    expect(screen.queryByRole("button", { name: "Delete this repository" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Save settings" }))
    await waitFor(() =>
      expect(update).toHaveBeenCalledExactlyOnceWith({
        name: "repo",
        description: "A repository",
        default_branch: "main",
        is_private: true,
      }),
    )
  })
  test("exposes deletion and owner grants to repository owners", async () => {
    server.use(handleAuthorizationGetPermissions({ body: { read: true, write: true, admin: true, owner: true } }))
    const { user } = renderSettings()
    expect(await screen.findByRole("button", { name: "Delete this repository" })).toBeInTheDocument()
    await user.click(screen.getByRole("combobox", { name: "Role" }))
    expect(screen.getByRole("option", { name: "Owner" })).toBeInTheDocument()
  })
  test("denies settings to readers", async () => {
    server.use(handleAuthorizationGetPermissions({ body: { read: true, write: false, admin: false, owner: false } }))
    renderSettings()
    expect(
      await screen.findByText("Repository admin permission is required to change these settings."),
    ).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Save settings" })).not.toBeInTheDocument()
  })
})
