import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import { ThemeProvider, useTheme } from "./theme-provider"

// Test component that uses the theme context
function TestComponent() {
  const { theme, resolvedTheme, setTheme } = useTheme()

  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button type="button" onClick={() => setTheme("light")}>
        Light
      </button>
      <button type="button" onClick={() => setTheme("dark")}>
        Dark
      </button>
      <button type="button" onClick={() => setTheme("system")}>
        System
      </button>
    </div>
  )
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    // Reset document classes
    document.documentElement.classList.remove("light", "dark")
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  test("renders children", () => {
    render(
      <ThemeProvider>
        <div data-testid="child">Child content</div>
      </ThemeProvider>,
    )

    expect(screen.getByTestId("child")).toBeInTheDocument()
  })

  test("provides default theme as system", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    expect(screen.getByTestId("theme")).toHaveTextContent("system")
  })

  test("uses custom default theme", () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <TestComponent />
      </ThemeProvider>,
    )

    expect(screen.getByTestId("theme")).toHaveTextContent("dark")
  })

  test("setTheme updates the theme", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole("button", { name: "Dark" }))

    expect(screen.getByTestId("theme")).toHaveTextContent("dark")
  })

  test("adds light class to document when theme is light", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole("button", { name: "Light" }))

    expect(document.documentElement).toHaveClass("light")
  })

  test("adds dark class to document when theme is dark", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole("button", { name: "Dark" }))

    expect(document.documentElement).toHaveClass("dark")
  })

  test("removes previous theme class when changing theme", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider defaultTheme="light">
        <TestComponent />
      </ThemeProvider>,
    )

    expect(document.documentElement).toHaveClass("light")

    await user.click(screen.getByRole("button", { name: "Dark" }))

    expect(document.documentElement).not.toHaveClass("light")
    expect(document.documentElement).toHaveClass("dark")
  })

  test("resolvedTheme is light when theme is light", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole("button", { name: "Light" }))

    expect(screen.getByTestId("resolved-theme")).toHaveTextContent("light")
  })

  test("resolvedTheme is dark when theme is dark", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole("button", { name: "Dark" }))

    expect(screen.getByTestId("resolved-theme")).toHaveTextContent("dark")
  })

  test("can switch between themes multiple times", async () => {
    const user = userEvent.setup()

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>,
    )

    await user.click(screen.getByRole("button", { name: "Light" }))
    expect(screen.getByTestId("theme")).toHaveTextContent("light")

    await user.click(screen.getByRole("button", { name: "Dark" }))
    expect(screen.getByTestId("theme")).toHaveTextContent("dark")

    await user.click(screen.getByRole("button", { name: "System" }))
    expect(screen.getByTestId("theme")).toHaveTextContent("system")
  })

  test("theme starts with dark when defaultTheme is dark", () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <TestComponent />
      </ThemeProvider>,
    )

    expect(screen.getByTestId("theme")).toHaveTextContent("dark")
    expect(document.documentElement).toHaveClass("dark")
  })

  test("theme starts with light when defaultTheme is light", () => {
    render(
      <ThemeProvider defaultTheme="light">
        <TestComponent />
      </ThemeProvider>,
    )

    expect(screen.getByTestId("theme")).toHaveTextContent("light")
    expect(document.documentElement).toHaveClass("light")
  })
})
