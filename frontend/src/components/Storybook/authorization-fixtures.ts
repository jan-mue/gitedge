import { HttpResponse } from "msw"
import type { CollaboratorPublic } from "@/client"
import {
  handleAuthorizationListCollaborators,
  handleAuthorizationListCollaboratorTeams,
  handleAuthorizationRemoveCollaborator,
  handleAuthorizationSearchCollaboratorCandidates,
  handleAuthorizationSetCollaborator,
} from "@/client/msw.gen"

const userId = "00000000-0000-0000-0000-000000000001"
const teamId = "00000000-0000-0000-0000-000000000002"
export const storyCollaborators: CollaboratorPublic[] = [
  { id: "00000000-0000-0000-0000-000000000003", user_id: userId, team_id: null, subject_name: "alice", role: "owner" },
  {
    id: "00000000-0000-0000-0000-000000000004",
    user_id: null,
    team_id: teamId,
    subject_name: "developers",
    role: "write",
  },
]

export const createCollaboratorFixtures = (initial: CollaboratorPublic[] = storyCollaborators) => {
  let collaborators = [...initial]
  return {
    reset: () => {
      collaborators = [...initial]
    },
    handlers: [
      handleAuthorizationListCollaborators(() => HttpResponse.json(collaborators)),
      handleAuthorizationListCollaboratorTeams({ body: [{ id: teamId, organization_id: userId, name: "developers" }] }),
      handleAuthorizationSearchCollaboratorCandidates(({ request }) => {
        const query = new URL(request.url).searchParams.get("q")?.toLowerCase() ?? ""
        return HttpResponse.json(
          [
            {
              id: "00000000-0000-0000-0000-000000000005",
              name: "garrett",
              display_name: "Garrett Yan",
              principal_type: "user" as const,
            },
            {
              id: "00000000-0000-0000-0000-000000000006",
              name: "jan-mueller",
              display_name: "Jan Müller",
              principal_type: "user" as const,
            },
          ].filter((user) => `${user.name} ${user.display_name}`.toLowerCase().includes(query)),
        )
      }),
      handleAuthorizationSetCollaborator(async ({ request }) => {
        const body = await request.json()
        const existing = collaborators.find((item) =>
          body.team_id ? item.team_id === body.team_id : item.user_id === body.user_id,
        )
        const collaborator: CollaboratorPublic = {
          ...body,
          id: existing?.id ?? crypto.randomUUID(),
          subject_name: body.team_id ? "developers" : "garrett",
        }
        collaborators = [...collaborators.filter((item) => item.id !== collaborator.id), collaborator]
        return HttpResponse.json(collaborator)
      }),
      handleAuthorizationRemoveCollaborator(({ params }) => {
        collaborators = collaborators.filter((item) => item.id !== params.collaborator_id)
        return new HttpResponse(null, { status: 204 })
      }),
    ],
  }
}
