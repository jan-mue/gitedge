import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router"
import { type RenderOptions, render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactElement, ReactNode } from "react"
import { ThemeProvider } from "@/components/theme-provider"

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

interface WrapperProps {
  children: ReactNode
}

// Create a wrapper with all necessary providers
function createWrapper() {
  const queryClient = createTestQueryClient()

  return function Wrapper({ children }: WrapperProps) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="light" storageKey="test-theme">
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    )
  }
}

// Custom render function that includes providers
function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return {
    user: userEvent.setup(),
    ...render(ui, { wrapper: createWrapper(), ...options }),
  }
}

// Create a test router for testing route components
interface TestRouterOptions {
  initialPath?: string
  component: () => ReactElement
}

function createTestRouter({ initialPath = "/", component }: TestRouterOptions) {
  const rootRoute = createRootRoute()
  const testRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: initialPath,
    component,
  })

  const routeTree = rootRoute.addChildren([testRoute])
  const memoryHistory = createMemoryHistory({ initialEntries: [initialPath] })

  return createRouter({
    routeTree,
    history: memoryHistory,
  })
}

function renderWithRouter(options: TestRouterOptions) {
  const router = createTestRouter(options)
  const queryClient = createTestQueryClient()

  return {
    user: userEvent.setup(),
    ...render(
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="light" storageKey="test-theme">
          <RouterProvider router={router} />
        </ThemeProvider>
      </QueryClientProvider>,
    ),
    router,
  }
}

// Re-export everything from testing-library
export * from "@testing-library/react"
export { createTestQueryClient, customRender as render, renderWithRouter }
