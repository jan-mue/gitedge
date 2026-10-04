import { render, screen } from "@testing-library/react"
import React from "react"
import { describe, expect, test, vi } from "vitest"

// Mock TanStack Router's Link component
vi.mock("@tanstack/react-router", () => ({
  Link: vi.fn(({ children, to }: { children: React.ReactNode; to: string }) =>
    React.createElement("a", { href: to }, children),
  ),
}))

import NotFound from "./NotFound"

describe("NotFound", () => {
  test("renders 404 text", () => {
    render(<NotFound />)

    expect(screen.getByText("404")).toBeInTheDocument()
  })

  test("renders Oops! message", () => {
    render(<NotFound />)

    expect(screen.getByText("Oops!")).toBeInTheDocument()
  })

  test("renders page not found message", () => {
    render(<NotFound />)

    expect(screen.getByText("The page you are looking for was not found.")).toBeInTheDocument()
  })

  test("renders Go Back button", () => {
    render(<NotFound />)

    expect(screen.getByRole("button", { name: "Go Back" })).toBeInTheDocument()
  })

  test("Go Back button links to home page", () => {
    render(<NotFound />)

    const link = screen.getByRole("link")
    expect(link).toHaveAttribute("href", "/")
  })

  test("has correct test id", () => {
    render(<NotFound />)

    expect(screen.getByTestId("not-found")).toBeInTheDocument()
  })

  test("has min-h-screen class for full height", () => {
    render(<NotFound />)

    const container = screen.getByTestId("not-found")
    expect(container).toHaveClass("min-h-screen")
  })

  test("content is centered", () => {
    render(<NotFound />)

    const container = screen.getByTestId("not-found")
    expect(container).toHaveClass("flex")
    expect(container).toHaveClass("items-center")
    expect(container).toHaveClass("justify-center")
  })

  test("404 text has large font size", () => {
    render(<NotFound />)

    const text404 = screen.getByText("404")
    expect(text404).toHaveClass("text-6xl")
    expect(text404).toHaveClass("font-bold")
  })

  test("description has muted color", () => {
    render(<NotFound />)

    const description = screen.getByText("The page you are looking for was not found.")
    expect(description).toHaveClass("text-muted-foreground")
  })
})
