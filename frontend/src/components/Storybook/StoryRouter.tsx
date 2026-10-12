import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router"
import { type ReactNode, useState } from "react"
/** A fresh query cache per story keeps API state isolated. */
export const StoryRouter = ({ children }: { children: ReactNode }) => {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }),
  )
  const [router] = useState(() => {
    // Keep the pattern visible while real navigation updates route match state.
    const root = createRootRoute({ component: () => children })
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
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
