import { createFileRoute } from "@tanstack/react-router"

import UserProfile from "@/components/Profile/UserProfile"

export const Route = createFileRoute("/_layout/profile/$username")({
  component: ProfilePage,
  head: ({ params }) => ({
    meta: [{ title: `${params.username} - GitEdge` }],
  }),
})

function ProfilePage() {
  const { username } = Route.useParams()
  return <UserProfile username={username} />
}
