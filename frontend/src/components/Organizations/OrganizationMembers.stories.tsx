import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import type { MemberPublic } from "@/client"
import {
  handleAuthorizationGetOrganizationPermissions,
  handleAuthorizationListMembers,
  handleAuthorizationRemoveMember,
  handleAuthorizationSearchMemberCandidates,
  handleAuthorizationSetMember,
} from "@/client/msw.gen"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import { OrganizationMembers } from "./OrganizationMembers"

const initial: MemberPublic[] = [
  { user_id: "00000000-0000-0000-0000-000000000001", name: "jan-mue", display_name: "Jan Müller", is_admin: true },
  { user_id: "00000000-0000-0000-0000-000000000002", name: "garrett", display_name: "Garrett Yan", is_admin: false },
]
let members = [...initial]
const handlers = [
  handleAuthorizationGetOrganizationPermissions({ body: { admin: true } }),
  handleAuthorizationListMembers(() => HttpResponse.json(members)),
  handleAuthorizationSearchMemberCandidates(({ request }) => {
    const q = new URL(request.url).searchParams.get("q")?.toLowerCase() ?? ""
    return HttpResponse.json(
      [
        {
          id: "00000000-0000-0000-0000-000000000003",
          name: "alice",
          display_name: "Alice Example",
          principal_type: "user" as const,
        },
      ].filter((user) => `${user.name} ${user.display_name}`.toLowerCase().includes(q)),
    )
  }),
  handleAuthorizationSetMember(async ({ params, request }) => {
    const body = await request.json()
    const existing = members.find((member) => member.user_id === params.user_id)
    const member = {
      user_id: String(params.user_id),
      name: existing?.name ?? "alice",
      display_name: existing?.display_name ?? "Alice Example",
      is_admin: body.is_admin ?? false,
    }
    members = [...members.filter((item) => item.user_id !== member.user_id), member]
    return HttpResponse.json(member)
  }),
  handleAuthorizationRemoveMember(({ params }) => {
    members = members.filter((member) => member.user_id !== params.user_id)
    return new HttpResponse(null, { status: 204 })
  }),
]
const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Organization/Members",
  component: OrganizationMembers,
  args: { organization: "GitEdge" },
  beforeEach: () => {
    members = [...initial]
  },
  parameters: { msw: { handlers } },
} satisfies Meta<typeof OrganizationMembers>
export default meta
type Story = StoryObj<typeof meta>
export const Admin: Story = {}
export const Member: Story = {
  parameters: {
    msw: {
      handlers: [handleAuthorizationGetOrganizationPermissions({ body: { admin: false } }), ...handlers.slice(1)],
    },
  },
}
export const Loading: Story = {
  parameters: {
    msw: {
      handlers: [
        handleAuthorizationListMembers(async () => {
          await delay("infinite")
          return HttpResponse.json([])
        }),
        ...handlers.filter((handler) => handler !== handlers[1]),
      ],
    },
  },
}
export const Unavailable: Story = {
  parameters: {
    msw: {
      handlers: [
        handleAuthorizationListMembers(() => HttpResponse.json({ detail: "Unavailable" }, { status: 503 })),
        ...handlers.filter((handler) => handler !== handlers[1]),
      ],
    },
  },
}
export const ManyMembers: Story = {
  beforeEach: () => {
    members = [
      ...initial,
      ...Array.from({ length: 22 }, (_, index) => ({
        user_id: `00000000-0000-0000-0001-${String(index).padStart(12, "0")}`,
        name: `member-${index + 1}`,
        display_name: `Member ${index + 1}`,
        is_admin: false,
      })),
    ]
  },
}
