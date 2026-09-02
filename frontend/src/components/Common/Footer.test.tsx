import { render, screen } from "@testing-library/react"
import { describe, expect, test } from "vitest"

import { Footer } from "./Footer"

describe("Footer", () => {
  test("renders GitEdge text", () => {
    render(<Footer />)

    expect(screen.getByText(/GitEdge/)).toBeInTheDocument()
  })

  test("displays current year", () => {
    render(<Footer />)

    const currentYear = new Date().getFullYear()
    expect(
      screen.getByText(new RegExp(String(currentYear))),
    ).toBeInTheDocument()
  })

  test("renders GitHub link", () => {
    render(<Footer />)

    const githubLink = screen.getByRole("link", { name: /github/i })
    expect(githubLink).toBeInTheDocument()
    expect(githubLink).toHaveAttribute(
      "href",
      "https://github.com/jan-mue/gitedge",
    )
  })

  test("GitHub link opens in new tab", () => {
    render(<Footer />)

    const githubLink = screen.getByRole("link", { name: /github/i })
    expect(githubLink).toHaveAttribute("target", "_blank")
  })

  test("GitHub link has security attributes", () => {
    render(<Footer />)

    const githubLink = screen.getByRole("link", { name: /github/i })
    expect(githubLink).toHaveAttribute("rel", "noopener noreferrer")
  })

  test("renders footer element", () => {
    render(<Footer />)

    const footer = document.querySelector("footer")
    expect(footer).toBeInTheDocument()
  })

  test("footer has border-t class", () => {
    render(<Footer />)

    const footer = document.querySelector("footer")
    expect(footer).toHaveClass("border-t")
  })

  test("has proper padding", () => {
    render(<Footer />)

    const footer = document.querySelector("footer")
    expect(footer).toHaveClass("py-4")
    expect(footer).toHaveClass("px-6")
  })

  test("copyright text has muted color", () => {
    render(<Footer />)

    const currentYear = new Date().getFullYear()
    const copyrightText = screen.getByText(`GitEdge - ${currentYear}`)
    expect(copyrightText).toHaveClass("text-muted-foreground")
  })

  test("copyright text has small font size", () => {
    render(<Footer />)

    const currentYear = new Date().getFullYear()
    const copyrightText = screen.getByText(`GitEdge - ${currentYear}`)
    expect(copyrightText).toHaveClass("text-sm")
  })

  test("link has hover styling", () => {
    render(<Footer />)

    const githubLink = screen.getByRole("link", { name: /github/i })
    expect(githubLink).toHaveClass("hover:text-foreground")
  })

  test("link has transition styling", () => {
    render(<Footer />)

    const githubLink = screen.getByRole("link", { name: /github/i })
    expect(githubLink).toHaveClass("transition-colors")
  })

  test("GitHub icon has correct size", () => {
    render(<Footer />)

    const icon = document.querySelector("svg")
    expect(icon).toHaveClass("h-5")
    expect(icon).toHaveClass("w-5")
  })
})
