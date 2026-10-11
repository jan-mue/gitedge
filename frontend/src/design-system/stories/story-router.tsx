import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router"
import { type ReactNode, useState } from "react"
/** A fresh query cache per story keeps API state isolated. */
export const StoryRouter = ({ children }: { children: ReactNode }) => {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }),
  )
  const [router] = useState(() => {
    const root = createRootRoute()
    const route = createRoute({ getParentRoute: () => root, path: "/$owner/$repo", component: () => children })
    return createRouter({
      routeTree: root.addChildren([route]),
      history: createMemoryHistory({ initialEntries: ["/jan-mue/gitedge"] }),
    })
  })
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
