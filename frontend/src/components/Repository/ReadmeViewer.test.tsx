import { render, screen } from "@testing-library/react"
import { describe, expect, test } from "vitest"

import ReadmeViewer from "./ReadmeViewer"

describe("ReadmeViewer", () => {
  test("renders the filename and rendered markdown", () => {
    render(<ReadmeViewer html="<h1>Title</h1>" content="# Title" filename="README.md" />)

    expect(screen.getByTestId("readme-viewer")).toBeInTheDocument()
    expect(screen.getByText("README.md")).toBeInTheDocument()
    expect(screen.getByTestId("readme-content")).toHaveTextContent("Title")
  })

  test("falls back to the raw content when there is no html", () => {
    render(<ReadmeViewer html="" content="plain text" />)

    expect(screen.getByText("plain text")).toBeInTheDocument()
  })

  test("defaults the filename to README.md", () => {
    render(<ReadmeViewer html="<p>hi</p>" content="hi" />)

    expect(screen.getByText("README.md")).toBeInTheDocument()
  })
})
