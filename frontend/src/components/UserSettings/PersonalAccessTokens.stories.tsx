import type { Meta, StoryObj } from "@storybook/react-vite"
import { delay, HttpResponse } from "msw"
import type { PersonalAccessTokenCreate, PersonalAccessTokenPublic } from "@/client"
import {
  handlePersonalAccessTokensCreateToken,
  handlePersonalAccessTokensListTokens,
  handlePersonalAccessTokensRevokeToken,
  handlePersonalAccessTokensRotateToken,
} from "@/client/msw.gen"
import { repositoryStoryMeta } from "@/components/Storybook/repository-fixtures"
import PersonalAccessTokens from "./PersonalAccessTokens"

const initialToken: PersonalAccessTokenPublic = {
  id: "00000000-0000-0000-0000-000000000001",
  owner_id: "00000000-0000-0000-0000-000000000002",
  name: "Work laptop",
  prefix: "gitedge_pat_live_v1_",
  key_id: "a".repeat(24),
  secret_last4: "demo",
  scopes: ["git:read", "git:write"],
  created_at: "2026-10-01T12:00:00Z",
  expires_at: null,
  last_used_at: "2026-10-12T12:00:00Z",
  revoked_at: null,
  revoked_reason: null,
}
let tokens = [initialToken]
const issue = (body: PersonalAccessTokenCreate) => {
  const token: PersonalAccessTokenPublic = {
    ...initialToken,
    ...body,
    id: crypto.randomUUID(),
    expires_at: body.expires_at ?? null,
    created_at: new Date().toISOString(),
    last_used_at: null,
  }
  tokens = [token, ...tokens]
  return HttpResponse.json(
    { ...token, token: `gitedge_pat_live_v1_${token.key_id}.${"b".repeat(39)}demo` },
    { status: 201 },
  )
}
const handlers = [
  handlePersonalAccessTokensListTokens(() => HttpResponse.json(tokens)),
  handlePersonalAccessTokensCreateToken(async ({ request }) => issue(await request.json())),
  handlePersonalAccessTokensRotateToken(async ({ request, params }) => {
    tokens = tokens.map((token) =>
      token.id === params.token_id
        ? { ...token, revoked_at: new Date().toISOString(), revoked_reason: "Rotated" }
        : token,
    )
    return issue(await request.json())
  }),
  handlePersonalAccessTokensRevokeToken(async ({ request, params }) => {
    const body = await request.json()
    tokens = tokens.map((token) =>
      token.id === params.token_id
        ? { ...token, revoked_at: new Date().toISOString(), revoked_reason: body.reason ?? null }
        : token,
    )
    return new HttpResponse(null, { status: 204 })
  }),
]
const meta = {
  ...repositoryStoryMeta,
  title: "Patterns/Account/Personal access tokens",
  component: PersonalAccessTokens,
  beforeEach: () => {
    tokens = [initialToken]
  },
  parameters: { msw: { handlers } },
} satisfies Meta<typeof PersonalAccessTokens>
export default meta
type Story = StoryObj<typeof meta>
export const Tokens: Story = {}
export const Empty: Story = {
  beforeEach: () => {
    tokens = []
  },
}
export const Loading: Story = {
  parameters: {
    msw: {
      handlers: [
        handlePersonalAccessTokensListTokens(async () => {
          await delay("infinite")
          return HttpResponse.json([])
        }),
        ...handlers,
      ],
    },
  },
}
export const Unavailable: Story = {
  parameters: {
    msw: {
      handlers: [
        handlePersonalAccessTokensListTokens(() => HttpResponse.json({ detail: "Unavailable" }, { status: 503 })),
        ...handlers,
      ],
    },
  },
}
