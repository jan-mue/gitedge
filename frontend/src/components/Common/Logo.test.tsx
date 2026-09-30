import { render, screen } from "@testing-library/react"
import React from "react"
import { describe, expect, test, vi } from "vitest"

// Mock TanStack Router's Link component
vi.mock("@tanstack/react-router", () => ({
  Link: vi.fn(({ children, to }: { children: React.ReactNode; to: string }) =>
    React.createElement("a", { href: to }, children),
  ),
}))

import { Logo } from "./Logo"

describe("Logo", () => {
  test("renders full variant by default", () => {
    render(<Logo />)

    expect(screen.getByText("GitEdge")).toBeInTheDocument()
  })

  test("renders full variant with icon and text", () => {
    render(<Logo variant="full" />)

    expect(screen.getByText("GitEdge")).toBeInTheDocument()
  })

  test("renders icon variant without text", () => {
    render(<Logo variant="icon" />)

    expect(screen.queryByText("GitEdge")).not.toBeInTheDocument()
  })

  test("renders responsive variant with both visible and hidden elements", () => {
    render(<Logo variant="responsive" />)

    expect(screen.getByText("GitEdge")).toBeInTheDocument()
  })

  test("renders as a link by default", () => {
    render(<Logo />)

    const link = screen.getByRole("link")
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/")
  })

  test("renders without link when asLink is false", () => {
    render(<Logo asLink={false} />)

    expect(screen.queryByRole("link")).not.toBeInTheDocument()
    expect(screen.getByText("GitEdge")).toBeInTheDocument()
  })

  test("applies custom className to full variant", () => {
    render(<Logo variant="full" className="custom-class" asLink={false} />)

    const container = screen.getByText("GitEdge").parentElement
    expect(container).toHaveClass("custom-class")
  })

  test("applies custom className to icon variant", () => {
    render(<Logo variant="icon" className="custom-icon-class" asLink={false} />)

    const svg = document.querySelector("svg")
    expect(svg).toHaveClass("custom-icon-class")
  })

  test("full variant has correct flex layout", () => {
    render(<Logo variant="full" asLink={false} />)

    const container = screen.getByText("GitEdge").parentElement
    expect(container).toHaveClass("flex")
    expect(container).toHaveClass("items-center")
    expect(container).toHaveClass("gap-2")
  })

  test("text has correct styling", () => {
    render(<Logo variant="full" asLink={false} />)

    const text = screen.getByText("GitEdge")
    expect(text).toHaveClass("font-bold")
    expect(text).toHaveClass("text-lg")
  })

  test("icon has primary color", () => {
    render(<Logo variant="icon" asLink={false} />)

    const svg = document.querySelector("svg")
    expect(svg).toHaveClass("text-primary")
  })

  test("full variant icon has correct size", () => {
    render(<Logo variant="full" asLink={false} />)

    const svg = document.querySelector("svg")
    expect(svg).toHaveClass("size-6")
  })

  test("icon variant has correct size", () => {
    render(<Logo variant="icon" asLink={false} />)

    const svg = document.querySelector("svg")
    expect(svg).toHaveClass("size-5")
  })

  test("link points to home page", () => {
    render(<Logo asLink={true} />)

    const link = screen.getByRole("link")
    expect(link).toHaveAttribute("href", "/")
  })
})
