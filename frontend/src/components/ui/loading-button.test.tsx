import { describe, expect, test } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { LoadingButton } from "./loading-button"

describe("LoadingButton", () => {
  test("renders button with text", () => {
    render(<LoadingButton>Submit</LoadingButton>)

    expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument()
  })

  test("renders as a button element by default", () => {
    render(<LoadingButton>Test</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button.tagName).toBe("BUTTON")
  })

  test("shows loading spinner when loading is true", () => {
    render(<LoadingButton loading>Loading</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button.querySelector("svg.animate-spin")).toBeInTheDocument()
  })

  test("does not show loading spinner when loading is false", () => {
    render(<LoadingButton loading={false}>Not Loading</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button.querySelector("svg.animate-spin")).not.toBeInTheDocument()
  })

  test("is disabled when loading is true", () => {
    render(<LoadingButton loading>Loading</LoadingButton>)

    expect(screen.getByRole("button")).toBeDisabled()
  })

  test("is disabled when disabled prop is true", () => {
    render(<LoadingButton disabled>Disabled</LoadingButton>)

    expect(screen.getByRole("button")).toBeDisabled()
  })

  test("is disabled when both loading and disabled are true", () => {
    render(
      <LoadingButton loading disabled>
        Both
      </LoadingButton>
    )

    expect(screen.getByRole("button")).toBeDisabled()
  })

  test("is not disabled when neither loading nor disabled are true", () => {
    render(<LoadingButton>Enabled</LoadingButton>)

    expect(screen.getByRole("button")).not.toBeDisabled()
  })

  test("applies default variant classes", () => {
    render(<LoadingButton>Default</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("bg-primary")
  })

  test("applies destructive variant classes", () => {
    render(<LoadingButton variant="destructive">Delete</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("bg-destructive")
  })

  test("applies outline variant classes", () => {
    render(<LoadingButton variant="outline">Outline</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("border")
    expect(button).toHaveClass("bg-background")
  })

  test("applies secondary variant classes", () => {
    render(<LoadingButton variant="secondary">Secondary</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("bg-secondary")
  })

  test("applies small size classes", () => {
    render(<LoadingButton size="sm">Small</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("h-8")
  })

  test("applies large size classes", () => {
    render(<LoadingButton size="lg">Large</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("h-10")
  })

  test("applies icon size classes", () => {
    render(<LoadingButton size="icon">Icon</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("size-9")
  })

  test("handles click events when not loading", async () => {
    const user = userEvent.setup()
    let clicked = false
    const handleClick = () => {
      clicked = true
    }

    render(<LoadingButton onClick={handleClick}>Click</LoadingButton>)

    await user.click(screen.getByRole("button"))
    expect(clicked).toBe(true)
  })

  test("does not trigger click when loading", async () => {
    const user = userEvent.setup()
    let clicked = false
    const handleClick = () => {
      clicked = true
    }

    render(
      <LoadingButton loading onClick={handleClick}>
        Click
      </LoadingButton>
    )

    await user.click(screen.getByRole("button"))
    expect(clicked).toBe(false)
  })

  test("accepts custom className", () => {
    render(<LoadingButton className="custom-class">Custom</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveClass("custom-class")
  })

  test("can have type submit", () => {
    render(<LoadingButton type="submit">Submit</LoadingButton>)

    const button = screen.getByRole("button")
    expect(button).toHaveAttribute("type", "submit")
  })

  test("renders children correctly", () => {
    render(
      <LoadingButton>
        <span data-testid="child">Child Element</span>
      </LoadingButton>
    )

    expect(screen.getByTestId("child")).toBeInTheDocument()
  })

  test("renders children with loading spinner", () => {
    render(
      <LoadingButton loading>
        <span data-testid="child">Child Element</span>
      </LoadingButton>
    )

    expect(screen.getByTestId("child")).toBeInTheDocument()
    expect(
      screen.getByRole("button").querySelector("svg.animate-spin")
    ).toBeInTheDocument()
  })

  test("loading spinner has correct size", () => {
    render(<LoadingButton loading>Loading</LoadingButton>)

    const spinner = screen.getByRole("button").querySelector("svg.animate-spin")
    expect(spinner).toHaveClass("h-5")
    expect(spinner).toHaveClass("w-5")
  })
})
