import { render, screen } from "@testing-library/react"
import React from "react"
import { describe, expect, test, vi } from "vitest"

// Mock TanStack Router's Link component
vi.mock("@tanstack/react-router", () => ({
  Link: vi.fn(({ children, to }: { children: React.ReactNode; to: string }) =>
    React.createElement("a", { href: to }, children),
  ),
}))

import ErrorComponent from "./ErrorComponent"

describe("ErrorComponent", () => {
  test("renders Error text", () => {
    render(<ErrorComponent />)

    expect(screen.getByText("Error")).toBeInTheDocument()
  })

  test("renders Oops! message", () => {
    render(<ErrorComponent />)

    expect(screen.getByText("Oops!")).toBeInTheDocument()
  })

  test("renders error description message", () => {
    render(<ErrorComponent />)

    expect(
      screen.getByText("Something went wrong. Please try again."),
    ).toBeInTheDocument()
  })

  test("renders Go Home button", () => {
    render(<ErrorComponent />)

    expect(screen.getByRole("button", { name: "Go Home" })).toBeInTheDocument()
  })

  test("Go Home button links to home page", () => {
    render(<ErrorComponent />)

    const link = screen.getByRole("link")
    expect(link).toHaveAttribute("href", "/")
  })

  test("has correct test id", () => {
    render(<ErrorComponent />)

    expect(screen.getByTestId("error-component")).toBeInTheDocument()
  })

  test("has min-h-screen class for full height", () => {
    render(<ErrorComponent />)

    const container = screen.getByTestId("error-component")
    expect(container).toHaveClass("min-h-screen")
  })

  test("content is centered", () => {
    render(<ErrorComponent />)

    const container = screen.getByTestId("error-component")
    expect(container).toHaveClass("flex")
    expect(container).toHaveClass("items-center")
    expect(container).toHaveClass("justify-center")
  })

  test("Error text has large font size", () => {
    render(<ErrorComponent />)

    const errorText = screen.getByText("Error")
    expect(errorText).toHaveClass("text-6xl")
    expect(errorText).toHaveClass("font-bold")
  })

  test("description has muted color", () => {
    render(<ErrorComponent />)

    const description = screen.getByText(
      "Something went wrong. Please try again.",
    )
    expect(description).toHaveClass("text-muted-foreground")
  })
})
