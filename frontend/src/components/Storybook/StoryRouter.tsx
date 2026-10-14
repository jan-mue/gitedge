import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router"
import { createContext, type ReactNode, useContext, useState } from "react"

const StoryContent = createContext<ReactNode>(null)
const CurrentStory = () => <>{useContext(StoryContent)}</>
export const StoryRouter = ({ children }: { children: ReactNode }) => {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }),
  )
  const [router] = useState(() => {
    const root = createRootRoute({ component: CurrentStory })
    const repository = createRoute({ getParentRoute: () => root, path: "/$owner/$repo" })
    const pages = [
      "/",
      "issues",
      "pulls",
      "releases",
      "branches",
      "settings",
      "activity",
      "stars",
      "watchers",
      "forks",
      "src/branch/$branch",
      "src/branch/$branch/$",
      "src/commit/$sha",
      "src/commit/$sha/$",
      "src/tag/$tag",
      "src/tag/$tag/$",
      "commits/branch/$branch",
      "commits/tag/$tag",
      "commit/$hash",
      "blame/$",
    ] as const
    const childrenRoutes = pages.map((path) => createRoute({ getParentRoute: () => repository, path }))
    const profile = createRoute({ getParentRoute: () => root, path: "/profile/$username" })
    return createRouter({
      routeTree: root.addChildren([repository.addChildren(childrenRoutes), profile]),
      history: createMemoryHistory({ initialEntries: ["/jan-mue/gitedge"] }),
    })
  })
  return (
    <StoryContent value={children}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StoryContent>
  )
}
